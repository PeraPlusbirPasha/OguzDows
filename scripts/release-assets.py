#!/usr/bin/env python3
"""Başarılı PC / isteğe bağlı Pi artefaktlarını mevcut release TASLAĞINA aktar.

İmaj derlemez/değiştirmez; işi iptal etmez, etiket oluşturmaz, yayını herkese
AÇMAZ. Son yayımlama, doğrulama sonrası ayrıca gh release edit ile yapılır.
Pi eklenirse dört imajın iç kimliği salt okunur olarak ayrıca incelenir.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import lzma
import os
import re
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHES = ('amd64', 'i386')
PI_ARCHES = ('armhf', 'arm64')
DESKTOP = {'xfce4-session', 'xfwm4', 'xfce4-panel', 'xfdesktop'}
# v1.0.0 korunur; v1.1 ara güncelleme, sonraki ana yayınlar v2.0 / v3.0.
TAG = re.compile(r'v[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:-[a-z0-9]+(?:[.-][a-z0-9]+)*)?')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError('Normal, dolu yayın dosyası gerekli: ' + str(path))
    return path


def read_json(path):
    if regular(path).stat().st_size > 2 * 1024**2:
        raise ValueError('JSON raporu boyut sınırını aştı: ' + str(path))
    return json.loads(path.read_text())


def single(directory, name):
    paths = list(directory.rglob(name))
    if len(paths) != 1 or not paths[0].resolve().is_relative_to(directory.resolve()):
        raise ValueError('Tek ve kök içinde kanıt dosyası gerekli: ' + name)
    return regular(paths[0])


def checked_image(directory, name):
    image, checksum = regular(directory / name), regular(directory / (name + '.sha256'))
    if image.stat().st_size >= 2 * 1024**3 or checksum.stat().st_size > 256:
        raise ValueError('İmaj, GitHub dosya sınırını veya checksum beklenen boyutunu aştı.')
    match = re.fullmatch(r'([0-9a-f]{64})  ' + re.escape(name) + r'\n?', checksum.read_text())
    digest = sha256(image)
    if match is None or match[1] != digest:
        raise ValueError('İmaj SHA-256 doğrulaması başarısız: ' + name)
    return image, checksum, digest


def validate_run(run, run_id, repository, branch, *, pi=False, mobile=False):
    paths = {'.github/workflows/main.yml'}
    if mobile:
        paths = {'.github/workflows/mobile-emulator.yml'}
    elif pi:
        paths.add('.github/workflows/raspberrypi.yml')
    if (run.get('id') != run_id or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('full_name') != repository
            or run.get('head_branch') != branch or run.get('path') not in paths
            or not re.fullmatch(r'[0-9a-f]{40}', run.get('head_sha', ''))):
        raise ValueError('Kaynak, aynı depo/dalın başarıyla tamamlanmış PC/Pi çalışması olmalı.')
    return run['head_sha']


def validate_artifacts(data, names, run_id, revision):
    result = {}
    for name in names:
        matches = [item for item in data.get('artifacts', []) if item.get('name') == name]
        if len(matches) != 1:
            raise ValueError('Tek kaynak artefaktı gerekli: ' + name)
        item = matches[0]
        if (item.get('expired') is not False or item.get('workflow_run', {}).get('id') != run_id
                or item.get('workflow_run', {}).get('head_sha') != revision
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', item.get('digest', ''))):
            raise ValueError('Artefaktın süre/kaynak/hash kimliği geçersiz: ' + name)
        result[name] = {key: item[key] for key in ('id', 'name', 'size_in_bytes', 'digest')}
    return result


def validate_draft(release, release_id, tag, revision, notes):
    if (release.get('id') != release_id or release.get('draft') is not True
            or release.get('tag_name') != tag or release.get('target_commitish') != revision
            or release.get('body', '').strip() != notes.strip()):
        raise ValueError('Release kimliği, taslak durumu, kaynak commit veya sürüm notları eşleşmiyor.')


def validate_changes(paths):
    # Ürün dosyası/lock/recipe için geniş raspberrypi/** istisnası YOKTUR.
    mobile_docs = {f'mobile/{name}.md' for name in ('README', 'INSTALL', 'VERIFICATION', 'CONNECTED', 'DESIGN', 'ROADMAP')}
    mobile_docs.add('mobile/android/README.md')
    for path in paths:
        mobile_evidence = re.fullmatch(r'mobile/android/evidence/(?:sdk|emulator|acceptance|package)-[0-9a-f]{7,40}\.json', path)
        if not (path.startswith(('.github/', 'docs/', 'tests/')) or path in mobile_docs or mobile_evidence
                or path in ('README.md', 'raspberrypi/README.md', 'build.yml', 'scripts/release-assets.py')):
            raise ValueError('ISO sonrasında ürün/derleme içeriği değişmiş; yeni ISO gerekir: ' + path)


def host_evidence(tag, revision):
    """Keep published 1.1 proof immutable; later releases need their own proof."""
    if not TAG.fullmatch(tag):
        raise ValueError('Geçerli sürüm etiketi gerekli.')
    name = 'v1.1-elementary-host.json' if tag == 'v1.1' else tag + '-host.json'
    path = ROOT / 'docs/releases' / name
    report = read_json(path)
    if report.get('source_revision') != revision or report.get('conclusion') != 'success':
        raise ValueError('Host görsel/Haber kanıtı kaynakla eşleşmiyor.')
    return path


def inventory(directory):
    result = {}
    for path in sorted(directory.iterdir()):
        regular(path)
        result[path.name] = {'size': path.stat().st_size, 'sha256': sha256(path)}
    return result


def validate_memory(measurement, arch, revision, ram_mib=None):
    build, samples = measurement.get('build', {}), measurement.get('samples', [])
    if (build.get('source_revision') != revision or build.get('arch') != arch
            or measurement.get('valid_idle_measurement') is not True
            or measurement.get('target_met') is not True or measurement.get('invalid_reasons')
            or measurement.get('settled_seconds', 0) < 120 or measurement.get('sample_interval_seconds', 0) < 5
            or len(samples) < 6 or measurement.get('sample_count') != len(samples)
            or not all(item.get('graphical_xfce') is True and DESKTOP <= set(item.get('desktop_processes', []))
                       and not item.get('known_foreground_or_package_work') for item in samples)
            or max(item['used_bytes'] for item in samples) != measurement.get('max_used_bytes')
            or measurement.get('max_used_bytes', 600_000_001) > 600_000_000):
        raise ValueError('Gerçek, kaynakla eşleşen ve hedefi geçen tam Xfce RAM kanıtı gerekli: ' + arch)
    if ram_mib is not None:
        budget = measurement.get('low_ram_budget', {})
        if (measurement.get('vm_ram_mib') != ram_mib or budget.get('passed') is not True
                or budget.get('fail_reasons') != []
                or not all(type(item.get('total_bytes')) is int and type(item.get('available_bytes')) is int
                           and ram_mib * 1024**2 * .75 <= item['total_bytes'] <= ram_mib * 1024**2
                           and 0 <= item['available_bytes'] <= item['total_bytes'] for item in samples)):
            raise ValueError('Düşük RAM / OOM / kullanılabilir pay kanıtı geçersiz: ' + arch)
        threshold = max(32 * 1024**2, (max(item['total_bytes'] for item in samples) + 9) // 10)
        observed = min(item['available_bytes'] for item in samples)
        if (budget.get('minimum_available_bytes') != threshold or observed < threshold
                or budget.get('observed_min_available_bytes') != observed):
            raise ValueError('Düşük RAM kullanılabilir payı yeniden hesaplamayla eşleşmiyor: ' + arch)


def validate_identity(build, text, arch, revision, version, *, pi=False):
    release = {key: value.strip('"') for key, value in
               (line.split('=', 1) for line in text.splitlines() if '=' in line)}
    # Pi'de lsb-release YOKTUR: teknik bookworm/12 kimliği korunur;
    # ürün sürümü ayrı OGUZDOWS_VERSION_ID anahtarındadır.
    product_matches = (release.get('NAME') == 'OğuzDows' and release.get('OGUZDOWS_VERSION_ID') == version) if pi else (
        release.get('DISTRIB_ID') == 'OguzDows' and release.get('DISTRIB_RELEASE') == version)
    if (build.get('source_revision') != revision or build.get('arch') != arch
            or 'source_dirty' not in build or build['source_dirty'] not in (False, None)
            or type(build['source_dirty']) not in (bool, type(None)) or not product_matches):
        raise ValueError('İmaj içindeki kaynak/mimari/ürün sürümü eşleşmiyor: ' + arch)


def inspect_pc(image, arch, revision, version, work):
    squash = work / (arch + '.squashfs')
    try:
        command('xorriso', '-osirrox', 'on', '-indev', str(image), '-extract', '/live/filesystem.squashfs', str(squash))
        build = json.loads(command('unsquashfs', '-cat', str(squash), 'usr/share/oguzdows/build-info.json'))
        lsb = command('unsquashfs', '-cat', str(squash), 'etc/lsb-release')
        validate_identity(build, lsb, arch, revision, version)
        return {'scope': 'read-only-ISO-squashfs-identity-not-physical-boot', 'build': build, 'version': version}
    finally:
        squash.unlink(missing_ok=True)


def validate_partitions(table, image_bytes):
    parts = table.get('partitions', [])
    if (table.get('label') != 'dos' or table.get('sectorsize') != 512 or len(parts) != 2
            or parts[0].get('type', '').lower() not in ('b', 'c', '0b', '0c') or parts[1].get('type') != '83'
            or not all(type(part.get('start')) is int and type(part.get('size')) is int
                       and part['start'] > 0 and part['size'] > 0 and part['start'] % 16384 == 0
                       and (part['start'] + part['size']) * 512 <= image_bytes for part in parts)
            or parts[0]['start'] + parts[0]['size'] > parts[1]['start']):
        raise ValueError('Pi MBR/FAT/ext4 / 8 MiB hizalama / bölüm sınırları geçersiz.')


def inspect_pi(image, arch, revision, version, work, runtime):
    # İmajdan kod çalıştırılmaz; yalnız host verifier ve salt okunur mount.
    scratch = Path(tempfile.mkdtemp(prefix=arch + '-', dir=work))
    raw, root = scratch / 'image.img', scratch / 'root'
    root.mkdir()
    loop, mounts, size = None, [], 0
    digest = hashlib.sha256()
    try:
        with lzma.open(image, 'rb') as source, raw.open('xb') as target:
            while chunk := source.read(4 * 1024**2):
                size += len(chunk)
                if size > 16 * 1024**3:
                    raise ValueError('Pi ham imajı 16 GiB inceleme sınırını aştı.')
                digest.update(chunk)
                target.write(chunk)
        table = json.loads(command('sfdisk', '--json', str(raw)))['partitiontable']
        validate_partitions(table, size)
        loop = command('sudo', 'losetup', '--find', '--show', '--partscan', '--read-only', str(raw)).strip()
        if not re.fullmatch(r'/dev/loop[0-9]+', loop):
            raise ValueError('Beklenmeyen salt okunur loop aygıtı.')
        command('sudo', 'udevadm', 'settle')
        command('sudo', 'mount', '-o', 'ro,noload,nodev,nosuid,noexec', loop + 'p2', str(root))
        mounts.append(root)
        boot = root / 'boot/firmware'
        command('sudo', 'mount', '-o', 'ro,nodev,nosuid,noexec', loop + 'p1', str(boot))
        mounts.append(boot)
        command('sudo', 'python3', str(ROOT / 'scripts/verify-pi.py'), '--root', str(root), '--arch', arch)
        build = read_json(root / 'usr/share/oguzdows/build-info.json')
        validate_identity(build, (root / 'usr/lib/os-release').read_text(), arch, revision, version, pi=True)
        if (read_json(root / 'usr/share/oguzdows/pi-build-report.json') != runtime
                or read_json(root / 'etc/oguzdows/pi-image.json') != build
                or read_json(root / 'usr/share/oguzdows/pi-gen.lock.json') != read_json(ROOT / 'raspberrypi/pi-gen.lock.json')):
            raise ValueError('Pi imaj içi rapor / kaynak kilidi artefaktlarla eşleşmiyor: ' + arch)
        return {'scope': 'read-only-MBR-FAT-ext4-identity-and-existing-verifier-not-physical-boot',
                'build': build, 'version': version, 'uncompressed_bytes': size, 'uncompressed_sha256': digest.hexdigest(),
                'existing_pi_verifier_passed': True, 'embedded_runtime_matches_raw_artifact': True}
    finally:
        # Unmount/detach başarısızsa aşağıdaki silme ÇALIŞMAZ; mount'ta rmtree yok.
        for location in reversed(mounts):
            command('sudo', 'umount', str(location))
        if loop:
            command('sudo', 'losetup', '--detach', loop)
        shutil.rmtree(scratch)


def inspect_images(inputs, revision, tag, runtime):
    identities = {}
    # Hatalı unmount'ta bir dış TemporaryDirectory de mount'u silmeye kalkmasın.
    work = Path(tempfile.mkdtemp(prefix='read-only-image-check-', dir=inputs.parent))
    for arch in ARCHES:
        print('ISO iç kimliği salt okunur inceleniyor: ' + arch, flush=True)
        identities[arch] = inspect_pc(inputs / arch / f'OguzDows-{arch}.iso', arch, revision, tag[1:], work)
    for arch in PI_ARCHES:
        print('Pi ham imajı salt okunur inceleniyor: ' + arch, flush=True)
        identities['rpi-' + arch] = inspect_pi(inputs / ('rpi-' + arch) / f'OguzDows-rpi-{arch}.img.xz',
                                              arch, revision, tag[1:], work, runtime[arch])
    work.rmdir()  # Ancak bütün salt-okunur bağlar başarıyla bırakıldıktan sonra.
    for arch, identity in identities.items():
        print('::notice title=Salt okunur imaj kimliği::' + json.dumps({'arch': arch, **identity}, ensure_ascii=True), flush=True)
    return identities


def deterministic_bundle(files, destination):
    # Sabit, düz dosya adları; yeniden denemede saat/tar uid'si hash'i değiştirmez.
    with destination.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name, path in sorted(files.items()):
                if Path(name).name != name or not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
                    raise ValueError('Kanıt arşiv adı düz / güvenli olmalı.')
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = regular(path).stat().st_size, 0o644, 0
                with path.open('rb') as source:
                    archive.addfile(info, source)


# Raw accepted reports, not borrowed historical documentation receipts.
MOBILE_EVIDENCE = {
    'build': ('build.json', 'mobile-build.json'),
    'device': ('evidence.json', 'mobile-emulator.json'),
    'acceptance': ('acceptance.json', 'mobile-acceptance.json'),
    'package': ('release-package.json', 'mobile-release-package.json'),
    'frame': ('connected-real-mediaprojection.jpg', 'mobile-connected-real-mediaprojection.jpg'),
    'product': ('product-identity.json', 'product-identity.json'),
}


def mobile_product(tag):
    product = read_json(ROOT / 'system/usr/share/oguzdows/product.json')
    if (tag != product.get('release_tag') or product.get('version') != tag[1:]
            or product.get('bridge_protocol') != 1 or product.get('codename') != 'Akıncı'
            or product.get('mobile_version_code') != 20 or product.get('mobile_version_name') != '2.0.0-akinci'):
        raise ValueError('Mobil yayın gerçek ortak Akıncı ürün kimliğiyle eşleşmeli.')
    for key in ('mobile_apk', 'mobile_tests_apk', 'web_bundle'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', product.get(key, '')):
            raise ValueError('Sabit/güvenli mobil dosya adı gerekli.')
    return product


def mobile_assets(product):
    return {product['mobile_apk'], product['mobile_apk'] + '.sha256', product['mobile_tests_apk'],
            'OguzDows-inert-install-fixture.apk', 'APK-SIGNATURE.txt', 'MOBILE-BUILD.txt',
            product['web_bundle'], product['web_bundle'] + '.sha256', 'BAGLANTI-REHBERI.md'}


def instrumentation_identity(xml):
    """Parse only direct attributes of the one binary-manifest instrumentation node."""
    lines, blocks = xml.splitlines(), []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'( *)E: instrumentation \(line=[0-9]+\)', line)
        if match is None:
            continue
        depth, attributes = len(match[1]), []
        for child in lines[index + 1:]:
            if child.strip() and len(child) - len(child.lstrip()) <= depth:
                break
            attribute = re.fullmatch(' ' * (depth + 2) +
                r'A: android:(name|targetPackage)\(0x[0-9a-f]{8}\)="([^"]+)"(?: \(Raw: "\2"\))?', child)
            if attribute:
                attributes.append(attribute.groups())
        blocks.append(attributes)
    expected = {'name': 'androidx.test.runner.AndroidJUnitRunner', 'targetPackage': 'org.oguzdows.mobile'}
    if len(blocks) != 1 or len(blocks[0]) != 2 or dict(blocks[0]) != expected:
        raise ValueError('Test APK’sında tek ve doğru runner / hedef paket instrumentation düğümü gerekli.')
    return {'runner': expected['name'], 'target_package': expected['targetPackage']}


def inspect_apk(path, package, *, version=None, code=None):
    """Independent host data readers, never execute/install code from the APK."""
    badging = command('aapt', 'dump', 'badging', str(path))
    matches = re.findall(r"^package: name='([^']+)' versionCode='([0-9]*)' versionName='([^']*)'(?: |$)", badging, re.MULTILINE)
    signature = command('apksigner', 'verify', '--verbose', '--print-certs', str(path))
    pins = re.findall(r'^Signer #1 certificate SHA-256 digest: ([a-f0-9]{64})$', signature, re.MULTILINE)
    if len(matches) != 1 or matches[0][0] != package or len(pins) != 1:
        raise ValueError('APK iç paket/sürüm/imza kimliği geçersiz: ' + path.name)
    _, raw_code, actual_version = matches[0]
    actual_code = int(raw_code) if raw_code else None
    # AGP's instrumentation APK legitimately omits versionCode/versionName.
    # Never borrow the application's version or permit missing versions in it.
    test_package = package == 'org.oguzdows.mobile.test'
    if (not test_package and (actual_code is None or not actual_version)
            or version is not None and actual_version != version or code is not None and actual_code != code):
        raise ValueError('APK iç paket/sürüm/imza kimliği geçersiz: ' + path.name)
    identity = {'package': package, 'version_code': actual_code, 'version_name': actual_version,
                'certificate_sha256': pins[0], 'signature_verified': True,
                'scope': 'read-only-aapt-and-apksigner-not-physical-install'}
    if test_package:
        identity['instrumentation'] = instrumentation_identity(command('aapt', 'dump', 'xmltree', str(path), 'AndroidManifest.xml'))
    return identity


def validate_web_bundle(path, revision, build_text):
    total, names = 0, set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            name = member.name
            if (name in names or len(names) >= 1500 or not member.isfile() or member.size > 16 * 1024**2
                    or name.startswith('/') or '..' in Path(name).parts
                    or not (name in ('BUILD.txt', 'ASSETS.md', 'BAGLANTI-REHBERI.md') or name.startswith('web/'))):
                raise ValueError('Web arşivinde beklenmeyen yol/tür/boyut var.')
            names.add(name)
            total += member.size
            if total > 64 * 1024**2:
                raise ValueError('Web arşivi toplam boyut sınırı.')
            if name in ('BUILD.txt', 'BAGLANTI-REHBERI.md'):
                with archive.extractfile(member) as stream:
                    text = stream.read(2 * 1024**2 + 1).decode()
                expected = build_text if name == 'BUILD.txt' else (ROOT / 'docs/AKINCI-BAGLANTI.md').read_text()
                if text != expected or name == 'BUILD.txt' and revision not in text:
                    raise ValueError('Web kaynağı/bağlantı rehberi eşleşmiyor.')
    if not {'web/index.html', 'BUILD.txt', 'ASSETS.md', 'BAGLANTI-REHBERI.md'} <= names:
        raise ValueError('Gerçek web derlemesi/kimliği/rehberi eksik.')


def verify_mobile_files(paths, revision, tag):
    """Identical fail-closed verification for source artifacts and re-downloaded assets."""
    product = mobile_product(tag)
    if read_json(paths['product']) != product:
        raise ValueError('Mobil paketin ortak ürün kimliği eski veya farklı.')
    rules = runpy.run_path(str(ROOT / 'mobile/scripts/acceptance.py'))
    build, device, accepted, package = (read_json(paths[key]) for key in ('build', 'device', 'acceptance', 'package'))
    frame = regular(paths['frame'])
    if frame.stat().st_size > 512 * 1024:
        raise ValueError('Gerçek yakalama kare sınırını aşıyor.')
    rules['validate_build'](build, revision)
    rules['validate_emulator'](device, revision, frame.read_bytes())
    if (device.get('passed') is not True or accepted.get('source_sha') != revision or accepted.get('passed') is not True
            or accepted.get('native_cases') != 24 or accepted.get('jvm_cases') != 20
            or accepted.get('interop_files') != 4 or accepted.get('real_capture_sha256') != sha256(frame)
            or accepted.get('physical_devices_tested') is not False or accepted.get('rom_or_gms_certification') is not False):
        raise ValueError('Tam/same-source mobil kabul makbuzu gerekli.')
    if (package.get('source_sha') != revision or package.get('version') != product['mobile_version_name']
            or package.get('version_code') != product['mobile_version_code'] or package.get('release_tag') != tag
            or package.get('bridge_protocol') != 1 or package.get('apksigner_verified') is not True
            or package.get('production_signing') is not False or package.get('physical_devices_tested') is not False):
        raise ValueError('Mobil paket makbuzu kaynak/sürüm/kapsam eşleşmesi başarısız.')
    originals = {item['file']: item for item in build['assembled']}
    names = [product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk']
    files = package.get('files', [])
    if len(files) != 3 or {item.get('file') for item in files} != set(names):
        raise ValueError('Üç özgün, tekil mobil APK gerekli.')
    by_name = {item['file']: item for item in files}
    signatures = regular(paths['signature'])
    build_file = regular(paths['build_text'])
    if signatures.stat().st_size > 65536 or build_file.stat().st_size > 4096:
        raise ValueError('Mobil imza/build metni boyut sınırı.')
    signature_text, build_text = signatures.read_text(), build_file.read_text()
    if ('SOURCE_SHA=' + revision + '\n' not in build_text or 'DEBUG' not in build_text):
        raise ValueError('Mobil BUILD kaynak/debug kimliği eksik.')
    identities = {}
    for index, (original, name) in enumerate(zip(rules['APK_PATHS'], names)):
        item, file = by_name[name], regular(paths[name])
        if file.stat().st_size > 256 * 1024**2:
            raise ValueError('APK boyut sınırı.')
        actual = {'bytes': file.stat().st_size, 'sha256': sha256(file)}
        if (actual != {key: originals[original].get(key) for key in actual}
                or actual != {key: item.get(key) for key in actual}):
            raise ValueError('APK kabulden sonra değişmiş veya eski dosya: ' + name)
        identity = inspect_apk(file, ('org.oguzdows.mobile', 'org.oguzdows.mobile.test', 'org.oguzdows.fixture')[index],
                               version=product['mobile_version_name'] if index == 0 else None,
                               code=product['mobile_version_code'] if index == 0 else None)
        pin = identity['certificate_sha256']
        if package.get('certificate_sha256', {}).get(name) != pin or name + '\n' not in signature_text or pin not in signature_text:
            raise ValueError('Bağımsız APK imzası kabul makbuzuyla eşleşmiyor.')
        identities[name] = identity
    if identities[names[0]]['certificate_sha256'] != identities[names[1]]['certificate_sha256']:
        raise ValueError('Ana APK ve instrumentation APK imzacısı farklı.')
    sums = ''.join(by_name[name]['sha256'] + '  ' + name + '\n' for name in names)
    if regular(paths['apk_sums']).read_text() != sums:
        raise ValueError('Özgün APK SHA256SUMS listesi eşleşmiyor.')
    web = package.get('web_bundle', {})
    path = regular(paths['web'])
    if (web.get('file') != product['web_bundle'] or web.get('bytes') != path.stat().st_size
            or web.get('sha256') != sha256(path) or path.stat().st_size > 64 * 1024**2):
        raise ValueError('Web demeti kabulden sonra değişmiş.')
    validate_web_bundle(path, revision, build_text)
    return {'source_revision': revision, 'version': product['mobile_version_name'], 'version_code': product['mobile_version_code'],
            'bridge_protocol': 1, 'acceptance': accepted, 'package': package, 'apk_identity': identities,
            'production_signing': False, 'rom': False, 'physical_devices_tested': False}


def mobile_capture(directory, device_report):
    """Use the harness's accepted sibling frame, never the first filename match.

    emulator-smoke.py pulls the complete diagnostic directory to screenshots/
    and separately pulls the canonical frame next to evidence.json. Depending
    on adb's destination-directory layout the diagnostic copy has one of two
    fixed paths. Every present copy must be regular, bounded and byte-identical;
    an unexpected location, missing canonical frame or divergent copy fails.
    """
    name = MOBILE_EVIDENCE['frame'][0]
    frame = regular(device_report.parent / name)
    if frame.stat().st_size > 512 * 1024:
        raise ValueError('Gerçek yakalama kare sınırını aşıyor.')
    allowed = {frame, device_report.parent / 'screenshots' / name,
               device_report.parent / 'screenshots/evidence' / name}
    digest = sha256(frame)
    candidates = list(directory.rglob(name))
    if frame not in candidates:
        raise ValueError('Kabul raporunun yanındaki özgün ekran karesi gerekli.')
    for path in candidates:
        if (path not in allowed or not path.resolve().is_relative_to(directory.resolve())
                or regular(path).stat().st_size != frame.stat().st_size or sha256(path) != digest):
            raise ValueError('Ekran kanıtının tanısal kopyası belirsiz veya özgün kareyle farklı.')
    return frame


def prepare_mobile(inputs, output, revision, tag, checksums, evidence):
    directory = inputs / 'mobile'
    product = mobile_product(tag)
    paths = {key: single(directory, original) for key, (original, _) in MOBILE_EVIDENCE.items() if key != 'frame'}
    paths['frame'] = mobile_capture(directory, paths['device'])
    for name in (product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk'):
        paths[name] = single(directory, name)
    paths.update(signature=single(directory, 'APK-SIGNATURE.txt'), build_text=single(directory, 'BUILD.txt'),
                 apk_sums=single(directory, 'SHA256SUMS'), web=single(directory, product['web_bundle']))
    report = verify_mobile_files(paths, revision, tag)
    names = [product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk', product['web_bundle']]
    for name in names:
        path = paths['web'] if name == product['web_bundle'] else paths[name]
        os.link(path, output / name)
        checksum = sha256(path) + '  ' + name + '\n'
        checksums.append(checksum)
        if name in (product['mobile_apk'], product['web_bundle']):
            (output / (name + '.sha256')).write_text(checksum)
    shutil.copyfile(paths['signature'], output / 'APK-SIGNATURE.txt')
    shutil.copyfile(paths['build_text'], output / 'MOBILE-BUILD.txt')
    shutil.copyfile(ROOT / 'docs/AKINCI-BAGLANTI.md', output / 'BAGLANTI-REHBERI.md')
    for key, (_, name) in MOBILE_EVIDENCE.items():
        evidence[name] = paths[key]
    return report


def audit_mobile(downloaded, evidence_dir, revision, tag, manifest, work):
    product = mobile_product(tag)
    paths = {key: regular(evidence_dir / name) for key, (_, name) in MOBILE_EVIDENCE.items()}
    for name in (product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk'):
        paths[name] = regular(downloaded / name)
    # Recreate only the fixed original three-APK sum view; the global sum file also covers images/web.
    apk_sums = work / 'mobile-apk-SHA256SUMS'
    names = [product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk']
    apk_sums.write_text(''.join(sha256(paths[name]) + '  ' + name + '\n' for name in names))
    paths.update(signature=downloaded / 'APK-SIGNATURE.txt', build_text=downloaded / 'MOBILE-BUILD.txt',
                 apk_sums=apk_sums, web=downloaded / product['web_bundle'])
    report = verify_mobile_files(paths, revision, tag)
    expected = {key: value for key, value in manifest['mobile'].items() if key not in ('source_run_id', 'source_run_url')}
    if report != expected or (downloaded / 'BAGLANTI-REHBERI.md').read_text() != (ROOT / 'docs/AKINCI-BAGLANTI.md').read_text():
        raise ValueError('Yeniden indirilen mobil paket/bağlantı kimliği manifestle eşleşmiyor.')
    return names + [product['web_bundle']]


def prepare_pi(inputs, output, revision, checksums, evidence):
    lock = read_json(ROOT / 'raspberrypi/pi-gen.lock.json')
    upstream = read_json(ROOT / 'raspberrypi/upstream-contract.json')
    runtime = {}
    for arch in PI_ARCHES:
        directory = inputs / ('rpi-' + arch)
        name = f'OguzDows-rpi-{arch}.img.xz'
        image, checksum, digest = checked_image(directory, name)
        actual_lock = single(directory, 'pi-gen.lock.json')
        if read_json(actual_lock) != lock:
            raise ValueError('Pi artefaktı kaynak kilidi eşleşmiyor: ' + arch)
        package_name = f'OguzDows-rpi-{arch}.packages.txt'
        packages = regular(directory / package_name)
        if packages.stat().st_size > 2 * 1024**2:
            raise ValueError('Pi paket envanteri aşırı büyük.')
        proof = inputs / 'evidence' / ('OguzDows-Pi-gunluk-' + arch)
        paths = {name: single(proof, name + '.json') for name in
                 ('pi-runtime-report', 'pi-upstream-audit', 'pi-apt-adaptation', 'collection')}
        report, audit, apt, collection = (read_json(paths[name]) for name in paths)
        if (report.get('source_revision') != revision or report.get('arch') != arch or report.get('errors') != []
                or report.get('pi_gen_commit') != lock[arch]['commit']
                or report.get('scope') != 'ARM-qemu-user-with-host-Xvfb'
                or any(report.get(key) is not False for key in ('physical_boot', 'hardware_gpu', 'performance_measurement',
                                                                'real_package_transactions', 'real_audio_playback'))):
            raise ValueError('Pi hedef rapor kaynak/mimari/sınırları geçersiz: ' + arch)
        if (audit.get('arch') != arch or audit.get('errors') != [] or audit.get('physical_boot') is not False
                or audit.get('pi_gen_commit') != lock[arch]['commit']
                or audit.get('archive_sha256') != lock[arch]['archive_sha256']
                or audit.get('files') != upstream['architectures'][arch]['files']):
            raise ValueError('Pi resmî kaynak denetimi geçersiz: ' + arch)
        if (apt.get('arch') != arch or apt.get('pi_gen_commit') != lock[arch]['commit']
                or apt.get('signature_checks_disabled') is not False
                or apt.get('before_sha256') != upstream['architectures'][arch]['files']['stage0/00-configure-apt/files/sources.list']
                or apt.get('apt_config_sha256') != sha256(ROOT / 'raspberrypi/apt/80oguzdows-resilience')
                or apt.get('mirror_list_sha256') != sha256(ROOT / 'raspberrypi/apt/raspbian.mirrors')):
            raise ValueError('Pi APT uyarlama kanıtı geçersiz: ' + arch)
        records = {row.get('file'): row for row in collection.get('logs', [])}
        if (collection.get('arch') != arch or collection.get('recursive_rootfs_scan') is not False
                or collection.get('source_permissions_changed') is not False
                or any(records.get(name + '.json', {}).get('status') != 'copied'
                       or records[name + '.json'].get('truncated') is not False
                       or records[name + '.json'].get('copied_bytes') != path.stat().st_size
                       for name, path in paths.items() if name != 'collection')):
            raise ValueError('Pi ham JSON kanıtı eksik / kesik / reddedilmiş: ' + arch)
        os.link(image, output / name)
        shutil.copyfile(checksum, output / checksum.name)
        shutil.copyfile(packages, output / package_name)
        checksums.append(digest + '  ' + name + '\n')
        for name, path in paths.items():
            evidence[name + '-' + arch + '.json'] = path
        runtime[arch] = report
        if arch == PI_ARCHES[0]:
            shutil.copyfile(actual_lock, output / 'pi-gen.lock.json')
    return runtime


def prepare(inputs, output, *, repository, run_id, release_id, revision, publisher_revision, tag,
            pi_run_id=None, mobile_run_id=None, source_artifacts=None):
    if tag == 'v2.0' and not (pi_run_id and mobile_run_id):
        raise ValueError('Akıncı yayını aynı kaynaklı PC + iki Pi + tam kabul edilmiş mobil paket gerektirir.')
    if mobile_run_id and not pi_run_id:
        raise ValueError('Birleşik mobil yayında iki Pi imajı da gerekli.')
    output.mkdir(parents=True, exist_ok=False)
    reports, checksums, evidence = {}, [], {}
    for arch in ARCHES:
        name = f'OguzDows-{arch}.iso'
        image, checksum, digest = checked_image(inputs / arch, name)
        proof = inputs / 'evidence' / ('OguzDows-ISO-hedef-test-' + arch)
        result_path, memory_path = single(proof, 'target-os-result.json'), single(proof, 'desktop-idle.json')
        result, measurement = read_json(result_path), read_json(memory_path)
        modes = ['bios', 'efi'] if arch == 'amd64' else ['bios']
        if (result.get('arch') != arch or result.get('source_revision') != revision or result.get('error')
                or result.get('modes') != modes or result.get('build', {}).get('source_dirty') is True):
            raise ValueError('ISO hedef açılış kanıtı kaynak/mimariyle eşleşmiyor: ' + arch)
        validate_memory(measurement, arch, revision)
        os.link(image, output / name)  # Aynı baytlar; yeniden paketleme yok.
        shutil.copyfile(checksum, output / checksum.name)
        shutil.copyfile(memory_path, output / f'desktop-idle-{arch}.json')
        checksums.append(digest + '  ' + name + '\n')
        reports[arch] = result
        if pi_run_id:
            evidence[f'target-os-result-{arch}.json'] = result_path
            evidence[f'desktop-idle-{arch}.json'] = memory_path
            for ram in (512, 1024):
                path = single(result_path.parent / f'ram-{ram}', 'low-ram-idle.json')
                validate_memory(read_json(path), arch, revision, ram)
                evidence[f'low-ram-idle-{arch}-{ram}.json'] = path
    manifest = {'format': 1, 'repository': repository, 'release_id': release_id, 'tag': tag,
                'source_run_id': run_id, 'source_run_url': f'https://github.com/{repository}/actions/runs/{run_id}',
                'source_revision': revision, 'publisher_revision': publisher_revision,
                'iso_rebuilt': False, 'target_os': reports}
    if pi_run_id:
        runtime = prepare_pi(inputs, output, revision, checksums, evidence)
        identities = inspect_images(inputs, revision, tag, runtime)
        if set(identities) != set(ARCHES) | {'rpi-' + arch for arch in PI_ARCHES}:
            raise ValueError('Dört imaj iç kimliği birlikte gerekli.')
        for arch in ARCHES:
            if identities[arch]['build'] != reports[arch].get('build'):
                raise ValueError('ISO iç kimliği hedef açılış raporuyla eşleşmiyor: ' + arch)
        generated = output.parent / 'evidence-generated'
        generated.mkdir(exist_ok=False)
        for arch, identity in identities.items():
            path = generated / ('image-identity-' + arch + '.json')
            path.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + '\n')
            evidence[path.name] = path
        evidence['host-gtk-panels-effects.json'] = host_evidence(tag, revision)
        mobile = None
        if mobile_run_id:
            mobile = prepare_mobile(inputs, output, revision, tag, checksums, evidence)
            mobile.update(source_run_id=mobile_run_id, source_run_url=f'https://github.com/{repository}/actions/runs/{mobile_run_id}')
        deterministic_bundle(evidence, output / 'test-evidence.tar.gz')
        shutil.copyfile(ROOT / 'docs/releases' / (tag + '.md'), output / 'INDIRME-REHBERI.md')
        manifest.update(format=2, pi_source_run_id=pi_run_id,
                        pi_source_run_url=f'https://github.com/{repository}/actions/runs/{pi_run_id}',
                        images_rebuilt=False, image_identity=identities,
                        pi_runtime={arch: {key: report.get(key) for key in
                                           ('scope', 'arch', 'source_revision', 'minimum_cpu', 'pi_gen_commit',
                                            'physical_boot', 'hardware_gpu', 'performance_measurement',
                                            'feature_presence', 'full_session', 'gui', 'errors')}
                                    for arch, report in runtime.items()},
                        evidence_files={name: {'sha256': sha256(path), 'size': path.stat().st_size}
                                        for name, path in sorted(evidence.items())},
                        source_artifacts=source_artifacts or {},
                        artifact_digest_scope='ZIP archive only; product digests are in files/SHA256SUMS')
        if mobile is not None:
            manifest.update(format=3, mobile=mobile, product=mobile_product(tag),
                            mobile_source_run_id=mobile_run_id,
                            mobile_source_run_url=f'https://github.com/{repository}/actions/runs/{mobile_run_id}')
    (output / 'SHA256SUMS').write_text(''.join(checksums))
    manifest['files'] = inventory(output)
    (output / 'release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return inventory(output)


def check_remote(release, expected, *, complete):
    assets = release.get('assets', [])
    actual = {item['name']: item for item in assets}
    if len(actual) != len(assets) or set(actual) - set(expected) or complete and set(actual) != set(expected):
        raise ValueError('Release dosya listesi beklenen listeyle eşleşmiyor; hiçbir dosya silinmedi/ezilmedi.')
    for name, item in actual.items():
        known = expected[name]
        if (item.get('state') != 'uploaded' or item.get('size') != known['size']
                or item.get('digest') != 'sha256:' + known['sha256']):
            raise ValueError('Sunucudaki dosyanın durumu/boyutu/SHA-256 değeri eşleşmiyor: ' + name)
    return set(expected) - set(actual)


def emit_files(expected):
    # GitHub aynı adımda yalnız ilk 10 notice'ı saklayabilir. Dosya başına
    # notice yerine en çok üç küçük grup; JSON ne kesilir ne kaybolur.
    records = [{'name': name, **data} for name, data in sorted(expected.items())]
    for offset in range(0, len(records), 8):
        text = json.dumps(records[offset:offset + 8], ensure_ascii=True)
        if len(text) > 3500:
            raise ValueError('Yayın envanteri kontrol notu sınırını aştı.')
        print(f'::notice title=Release doğrulanmış dosyalar {offset // 8 + 1}::' + text, flush=True)


def audit_release(release, work, *, repository, run_id, pi_run_id, release_id, revision, tag, notes, mobile_run_id=None):
    """Yüklenmiş tüm dosyaları tekrar indir/hash'le; release'e hiçbir şey YAZMA."""
    if not pi_run_id:
        raise ValueError('Dört imajlı release denetiminde Pi kaynak çalışması gerekli.')
    if tag == 'v2.0' and not mobile_run_id:
        raise ValueError('Akıncı denetiminde tam kabul edilmiş mobil kaynak çalışması gerekli.')
    work.mkdir(parents=True, exist_ok=False)
    metadata, downloaded = work / 'metadata', work / 'download'
    command('gh', 'release', 'download', tag, '--repo', repository,
            '--pattern', 'release-manifest.json', '--dir', str(metadata))
    path = regular(metadata / 'release-manifest.json')
    manifest = read_json(path)
    allowed = {'INDIRME-REHBERI.md', 'SHA256SUMS', 'test-evidence.tar.gz', 'pi-gen.lock.json',
               'desktop-idle-amd64.json', 'desktop-idle-i386.json'}
    images = [f'OguzDows-{arch}.iso' for arch in ARCHES] + [f'OguzDows-rpi-{arch}.img.xz' for arch in PI_ARCHES]
    allowed.update(images)
    allowed.update(name + '.sha256' for name in images)
    allowed.update(f'OguzDows-rpi-{arch}.packages.txt' for arch in PI_ARCHES)
    if mobile_run_id:
        product = mobile_product(tag)
        allowed.update(mobile_assets(product))
        mobile = manifest.get('mobile', {})
        if (manifest.get('mobile_source_run_id') != mobile_run_id or mobile.get('source_run_id') != mobile_run_id
                or manifest.get('product') != product or mobile.get('source_revision') != revision):
            raise ValueError('Yüklü manifestin mobil kaynak/ürün sözleşmesi geçersiz.')
    expected = manifest.get('files', {})
    if (set(expected) != allowed or manifest.get('format') != (3 if mobile_run_id else 2) or manifest.get('repository') != repository
            or manifest.get('release_id') != release_id or manifest.get('tag') != tag
            or manifest.get('source_revision') != revision or manifest.get('source_run_id') != run_id
            or manifest.get('pi_source_run_id') != pi_run_id or manifest.get('images_rebuilt') is not False
            or not re.fullmatch('[0-9a-f]{40}', manifest.get('publisher_revision', ''))):
        raise ValueError('Yüklü manifestin kaynak/17 dosya/yayımlayıcı sözleşmesi geçersiz.')
    command('git', 'merge-base', '--is-ancestor', manifest['publisher_revision'], 'HEAD')
    expected['release-manifest.json'] = {'size': path.stat().st_size, 'sha256': sha256(path)}
    validate_draft(release, release_id, tag, revision, notes)
    check_remote(release, expected, complete=True)
    # Manifestten yol/kalıp alınmaz; yalnız doğrulanmış sabit isimler indirilir.
    command('gh', 'release', 'download', tag, '--repo', repository, '--pattern', '*', '--dir', str(downloaded))
    if inventory(downloaded) != expected:
        raise ValueError('Release yeniden indirme SHA-256/boyut doğrulaması başarısız.')
    evidence = manifest.get('evidence_files', {})
    evidence_dir = work / 'evidence'
    evidence_dir.mkdir()
    with tarfile.open(downloaded / 'test-evidence.tar.gz', 'r:gz') as archive:
        members = archive.getmembers()
        if (len(members) != len(evidence) or {item.name for item in members} != set(evidence)
                or not all(item.isfile() and Path(item.name).name == item.name and item.name not in ('.', '..')
                           and item.size <= 2 * 1024**2 for item in members)):
            raise ValueError('İndirilen kanıt arşivi düz/normal/beklenen dosya listesi değil.')
        for item in members:
            with archive.extractfile(item) as stream:
                content = stream.read(2 * 1024**2 + 1)
            if {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()} != evidence[item.name]:
                raise ValueError('Kanıt arşivindeki özgün JSON/çerçeve hash/boyutu eşleşmiyor: ' + item.name)
            (evidence_dir / item.name).write_bytes(content)
    checksums = []
    for name in images:
        _, _, digest = checked_image(downloaded, name)
        checksums.append(digest + '  ' + name + '\n')
    if mobile_run_id:
        names = audit_mobile(downloaded, evidence_dir, revision, tag, manifest, work)
        for name in names:
            line = sha256(downloaded / name) + '  ' + name + '\n'
            checksums.append(line)
            if name in (product['mobile_apk'], product['web_bundle']) and (downloaded / (name + '.sha256')).read_text() != line:
                raise ValueError('Mobil/web ayrı SHA-256 dosyası eşleşmiyor.')
    if (downloaded / 'SHA256SUMS').read_text() != ''.join(checksums):
        raise ValueError('Tüm imaj/APK/web birleşik SHA256SUMS listesi eşleşmiyor.')
    if (downloaded / 'INDIRME-REHBERI.md').read_text() != notes:
        raise ValueError('İndirilen rehber taslağın sürüm notlarıyla eşleşmiyor.')
    current = api(f'repos/{repository}/releases/{release_id}')
    validate_draft(current, release_id, tag, revision, notes)
    check_remote(current, expected, complete=True)
    emit_files(expected)
    identities = manifest.get('image_identity', {})
    if set(identities) != set(ARCHES) | {'rpi-' + arch for arch in PI_ARCHES}:
        raise ValueError('Yüklü manifestte dört iç imaj kimliği gerekli.')
    for arch, identity in identities.items():
        print('::notice title=Salt okunur imaj kimliği::' + json.dumps({'arch': arch, **identity}, ensure_ascii=True), flush=True)
    print('::notice title=Release yeniden indirme doğrulaması::' + json.dumps(
        {'release_id': release_id, 'tag': tag, 'source_revision': revision,
         'publisher_revision': manifest['publisher_revision'], 'asset_count': len(expected),
         'evidence_json_count': sum(name.endswith('.json') for name in evidence),
         'evidence_file_count': len(evidence), 'mobile_source_run_id': mobile_run_id,
         'all_release_assets_redownloaded_and_hashed': True,
         'release_modified': False, 'draft': True}), flush=True)
    return expected


def command(*args):
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as error:
        print((error.stderr or '')[-2000:], file=sys.stderr, flush=True)
        raise


def api(path):
    return json.loads(command('gh', 'api', path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--pi-run', type=int, help='Aynı kaynak/dalın başarılı armhf+arm64 çalışması; yeniden derlemez')
    parser.add_argument('--mobile-run', type=int, help='Aynı kaynak/dalın tam kabul edilmiş mobil APK/emülatör çalışması')
    parser.add_argument('--release-id', type=int, required=True)
    parser.add_argument('--audit', action='store_true', help='Mevcut taslağı yeniden indir/doğrula; hiçbir dosya yükleme veya değiştirme')
    parser.add_argument('--tag', required=True)
    parser.add_argument('--work', type=Path, default=Path('.cache/release'))
    args = parser.parse_args()
    repository, branch = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_REF_NAME']
    if (args.run <= 0 or args.release_id <= 0 or args.pi_run is not None and args.pi_run <= 0
            or args.mobile_run is not None and args.mobile_run <= 0
            or not TAG.fullmatch(args.tag) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)):
        parser.error('Yayın etiketi / çalışma / release kimliği geçersiz.')
    notes = (ROOT / 'docs/releases' / (args.tag + '.md')).read_text()
    revision = validate_run(api(f'repos/{repository}/actions/runs/{args.run}'), args.run, repository, branch)
    if revision not in notes or f'actions/runs/{args.run}' not in notes:
        raise ValueError('Sürüm notlarında doğru kaynak commit ve başarılı çalışma bağlantısı gerekli.')
    if args.pi_run:
        pi_revision = validate_run(api(f'repos/{repository}/actions/runs/{args.pi_run}'), args.pi_run, repository, branch, pi=True)
        if pi_revision != revision or f'actions/runs/{args.pi_run}' not in notes:
            raise ValueError('PC/Pi imajları aynı kaynaktan gelmeli ve Pi çalışması notlarda bulunmalı.')
    if args.tag == 'v2.0' and not (args.pi_run and args.mobile_run):
        raise ValueError('Akıncı için PC/Pi/mobil kaynakları birlikte zorunlu.')
    if args.mobile_run:
        mobile_revision = validate_run(api(f'repos/{repository}/actions/runs/{args.mobile_run}'),
                                       args.mobile_run, repository, branch, mobile=True)
        if mobile_revision != revision or f'actions/runs/{args.mobile_run}' not in notes:
            raise ValueError('PC/Pi/mobil aynı kaynak olmalı; mobil kabul bağlantısı notlarda bulunmalı.')
    command('git', 'merge-base', '--is-ancestor', revision, 'HEAD')
    validate_changes(command('git', 'diff', '--name-only', revision, 'HEAD').splitlines())
    if command('git', 'status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Yayın aracı çalışma ağacı değiştirilmiş; kaynak denetimi atlanmadı.')
    endpoint = f'repos/{repository}/releases/{args.release_id}'
    release = api(endpoint)
    validate_draft(release, args.release_id, args.tag, revision, notes)
    if args.audit:
        audit_release(release, args.work, repository=repository, run_id=args.run, pi_run_id=args.pi_run,
                      release_id=args.release_id, revision=revision, tag=args.tag, notes=notes, mobile_run_id=args.mobile_run)
        return
    sources = [(args.run, ['OguzDows-' + arch for arch in ARCHES]
                + ['OguzDows-ISO-hedef-test-' + arch for arch in ARCHES])]
    if args.pi_run:
        sources.append((args.pi_run, ['OguzDows-rpi-' + arch for arch in PI_ARCHES]
                        + ['OguzDows-Pi-gunluk-' + arch for arch in PI_ARCHES]))
    if args.mobile_run:
        sources.append((args.mobile_run, ['oguzdows-mobile-emulator-' + str(args.mobile_run)]))
    source_artifacts = {}
    for run_id, names in sources:
        source_artifacts[str(run_id)] = validate_artifacts(
            api(f'repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100'), names, run_id, revision)
    args.work.mkdir(parents=True, exist_ok=False)
    inputs, output = args.work / 'input', args.work / 'upload'
    for run_id, names in sources:
        for name in names:
            if name.startswith('oguzdows-mobile-emulator-'):
                destination = inputs / 'mobile'
            elif name.startswith(('OguzDows-ISO-hedef-test-', 'OguzDows-Pi-gunluk-')):
                destination = inputs / 'evidence' / name
            else:
                destination = inputs / name.removeprefix('OguzDows-')
            print('Başarılı çalışmadan alınıyor: ' + name, flush=True)
            command('gh', 'run', 'download', str(run_id), '--repo', repository, '--name', name, '--dir', str(destination))
    expected = prepare(inputs, output, repository=repository, run_id=args.run, release_id=args.release_id,
                       revision=revision, publisher_revision=command('git', 'rev-parse', 'HEAD').strip(), tag=args.tag,
                       pi_run_id=args.pi_run, mobile_run_id=args.mobile_run, source_artifacts=source_artifacts)
    # Yalnızca aynı hash/boyuttaki tamamlanmış dosyalar korunur. Ezme/silme yok.
    release = api(endpoint)
    validate_draft(release, args.release_id, args.tag, revision, notes)
    missing = check_remote(release, expected, complete=False)
    for name in sorted(missing):
        print('Release taslağına yükleniyor: ' + name, flush=True)
        command('gh', 'release', 'upload', args.tag, str(output / name), '--repo', repository)
    release = api(endpoint)
    validate_draft(release, args.release_id, args.tag, revision, notes)
    check_remote(release, expected, complete=True)
    emit_files(expected)
    print('::notice title=Doğrulanmış release taslağı::' + json.dumps(
        {'release_id': args.release_id, 'tag': args.tag, 'draft': True, 'source_revision': revision,
         'pc_run_id': args.run, 'pi_run_id': args.pi_run, 'mobile_run_id': args.mobile_run, 'asset_count': len(expected)}), flush=True)


if __name__ == '__main__':
    main()
