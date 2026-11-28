#!/usr/bin/env python3
"""Package only same-source accepted APKs and static web assets; never publish a Release."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from acceptance import APK_PATHS, ROOT, validate_build, validate_emulator


def package():
    product = json.loads((ROOT / 'system/usr/share/oguzdows/product.json').read_text())
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    folder = ROOT / 'test-results/mobile'
    build = json.loads((folder / 'build.json').read_text())
    device = json.loads((folder / 'emulator/evidence.json').read_text())
    accepted = json.loads((folder / 'acceptance.json').read_text())
    frame = (folder / 'emulator/connected-real-mediaprojection.jpg').read_bytes()
    validate_build(build, head)
    validate_emulator(device, head, frame)
    if device.get('passed') is not True or accepted.get('passed') is not True or accepted.get('source_sha') != head:
        raise ValueError('Full same-source acceptance required')
    metadata = json.loads((ROOT / 'mobile/android/app/build/outputs/apk/debug/output-metadata.json').read_text())
    elements = metadata['elements']
    if (len(elements) != 1 or elements[0]['versionCode'] != product['mobile_version_code']
            or elements[0]['versionName'] != product['mobile_version_name']
            or metadata['applicationId'] != 'org.oguzdows.mobile'):
        raise ValueError('Real APK version/name does not match shared Akıncı identity')
    output = folder / 'package'
    output.mkdir(exist_ok=False)
    names = [product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk']
    signer = Path(os.environ['ANDROID_HOME']) / 'build-tools/35.0.0/apksigner'
    files, signatures, signers = [], [], {}
    by_path = {item['file']: item for item in build['assembled']}
    for original, name in zip(APK_PATHS, names):
        item = by_path[original]
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\.apk', name):
            raise ValueError('Invalid fixed APK filename')
        source = ROOT / 'mobile/android' / item['file']
        target = output / name
        shutil.copyfile(source, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if target.stat().st_size != item['bytes'] or digest != item['sha256']:
            raise ValueError('APK changed after acceptance')
        verified = subprocess.check_output([str(signer), 'verify', '--verbose', '--print-certs', str(target)], text=True)
        pins = re.findall(r'^Signer #1 certificate SHA-256 digest: ([a-f0-9]{64})$', verified, re.MULTILINE)
        if len(pins) != 1:
            raise ValueError('One verified signing certificate required')
        signers[name] = pins[0]
        signatures.append(name + '\n' + verified)
        files.append({'file': name, 'bytes': target.stat().st_size, 'sha256': digest})
    (output / 'APK-SIGNATURE.txt').write_text('\n'.join(signatures))
    (output / 'SHA256SUMS').write_text(''.join(item['sha256'] + '  ' + item['file'] + '\n' for item in files))
    (output / 'BUILD.txt').write_text('SOURCE_SHA=' + head + '\nPRODUCT=OğuzDows 2.0 Akıncı\nDEBUG APK / API35 emulator acceptance; not a ROM, production signature, physical SIM or GMS certification.\n')
    web = ROOT / 'mobile/preview/dist'
    if not (web / 'index.html').is_file():
        raise ValueError('Actual built web assets required')
    with tarfile.open(folder / product['web_bundle'], 'w:gz') as archive:
        for path in sorted(web.rglob('*')):
            if path.is_symlink() or path.is_file() and path.stat().st_size > 16 * 1024**2:
                raise ValueError('Unexpected web asset')
            if path.is_file():
                archive.add(path, arcname='web/' + str(path.relative_to(web)), recursive=False)
        archive.add(ROOT / 'docs/AKINCI-BAGLANTI.md', arcname='BAGLANTI-REHBERI.md', recursive=False)
        archive.add(ROOT / 'mobile/ASSETS.md', arcname='ASSETS.md', recursive=False)
        archive.add(output / 'BUILD.txt', arcname='BUILD.txt', recursive=False)
    (folder / 'product-identity.json').write_text(json.dumps(product, ensure_ascii=False, indent=2) + '\n')
    web_path = folder / product['web_bundle']
    receipt = {'source_sha': head, 'version': product['mobile_version_name'], 'version_code': product['mobile_version_code'],
               'release_tag': product['release_tag'], 'bridge_protocol': product['bridge_protocol'],
               'apksigner_verified': True, 'production_signing': False, 'files': files, 'certificate_sha256': signers,
               'web_bundle': {'file': product['web_bundle'], 'bytes': web_path.stat().st_size,
                              'sha256': hashlib.sha256(web_path.read_bytes()).hexdigest()}, 'physical_devices_tested': False}
    (folder / 'release-package.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Mobile release package::' + json.dumps(receipt, ensure_ascii=True, separators=(',', ':')))
    # Separate packaging step: acceptance + receipt + six preview notices fit the ten-notice cap.
    preview = folder / 'emulator/native-launcher-preview.b64'
    if preview.is_file():
        encoded = preview.read_text().strip()
        pixels = base64.b64decode(encoded, validate=True)
        if not pixels.startswith(b'\xff\xd8\xff') or len(encoded) > 24000:
            raise ValueError('Invalid bounded actual native thumbnail')
        pieces = [encoded[i:i + 3400] for i in range(0, len(encoded), 3400)]
        for index, piece in enumerate(pieces):
            print(f'::notice title=Native launcher preview {index+1:02}/{len(pieces):02}::' + piece)


if __name__ == '__main__':
    package()
