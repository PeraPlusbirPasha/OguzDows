#!/usr/bin/env python3
"""Üretilen ISO → özel sanal hedef → gerçek çekirdek/initramfs/systemd açılışı.

Yalnızca CI'de kendi oluşturduğu loop dosyasına yazar. Fiziksel disk adı kabul
etmez. Calamares'in GUI bölümleme/kullanıcı akışını otomatikleştirmez: aynı ISO
squashfs'i ve üretim temizleme/initramfs komutlarıyla düz ext4 hedef hazırlar.
Bu, firmware→GRUB testinden daha kapsamlıdır; fiziksel PC / LUKS testi değildir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import yaml

from support import ROOT, load
import target_system

firmware = load('iso_test_firmware', 'tests/smoke-installed-boot.py')
ci = load('iso_test_annotations', 'scripts/ci-run.py')
initrd_report = load('iso_initrd_report', 'scripts/initramfs-report.py')


def run(*args, timeout=600, **kwargs):
    print('+', *map(str, args), flush=True)
    return subprocess.run(list(map(str, args)), check=True, timeout=timeout, **kwargs)


def put(root, relative, text, mode=0o644):
    path = target_system.inside(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


def validate_source(build, revision, arch):
    # checkout, Git yerine commit'e sabitlenmiş kaynak arşivi kullanabilir.
    # null = temizlik bilinmiyor; false diye etiketleme ama true ile de karıştırma.
    if (not isinstance(build, dict) or build.get('source_revision') != revision
            or build.get('arch') != arch or 'source_dirty' not in build
            or (build['source_dirty'] is not False and build['source_dirty'] is not None)):
        raise RuntimeError('Yanlış / kirli / eski ISO kaynak kimliği: ' + json.dumps(build))
    if build['source_dirty'] is None:
        print('::notice title=Kaynak kimliği sınırı::Commit kimliği eşleşti; Git çalışma ağacı temizliği belirlenemedi (null). Temiz olduğu iddia edilmiyor.', flush=True)


def iso_mount_configuration(root, arch):
    actual = yaml.safe_load(target_system.nonempty(root, 'etc/calamares/modules/mount.conf').read_text())
    relative = 'installer/overrides/trixie/mount.conf' if arch == 'amd64' else 'installer/modules/mount.conf'
    expected = yaml.safe_load((ROOT / relative).read_text())
    if actual != expected:
        raise RuntimeError('ISO içindeki Calamares mount.conf kaynak / mimari yapılandırmasıyla eşleşmiyor.')
    return actual


def expose_loop_uuid(device, uuid, directory=Path('/dev/disk/by-uuid')):
    """Udev daemonu olmayan CI'de yalnızca doğrulanan özel loop'un UUID adı.

    GRUB 10_linux, UUID'yi bilse bile /dev/disk bağlantısı yoksa geçici aygıt
    adını root= yapar. Üretilen grub.cfg'yi elle düzeltmek yerine aynı udev
    adlandırma koşulunu sağla. Var olan hiçbir aygıt bağlantısını ezme.
    """
    if not re.fullmatch(r'/dev/loop[0-9]+p[0-9]+', device) or not re.fullmatch(r'[0-9a-f-]{36}', uuid):
        raise RuntimeError('Özel loop bölümü / UUID dışında bağlantı oluşturulamaz.')
    if not Path(device).is_block_device():
        raise RuntimeError('UUID bağlantısı için geçerli loop blok aygıtı yok.')
    directory.mkdir(parents=True, exist_ok=True)
    link = directory / uuid
    if link.exists() or link.is_symlink():
        if link.resolve() != Path(device).resolve():
            raise RuntimeError('Var olan UUID bağlantısı başka bir aygıta ait; değiştirilmedi.')
        return None
    link.symlink_to(device)
    return (link, device)


def remove_owned_uuid_links(links):
    for link, device in links:
        if link.is_symlink() and os.readlink(link) == device:
            link.unlink()  # Yalnızca bu testin oluşturduğu ve değişmemiş bağlantı.


def record_live_state(root, output, phase):
    """Gerçek ISO paketlerini / diversion ve bakım betiklerini kanıta ekle."""
    status = target_system.nonempty(root, 'var/lib/dpkg/status').read_text()
    selected = target_system.LIVE_PACKAGES | {'initramfs-tools', 'initramfs-tools-core'}
    packages = []
    for paragraph in status.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines()
                      if ': ' in line and not line.startswith((' ', '\t')))
        if fields.get('Package') in selected:
            packages.append({key: fields.get(key) for key in ('Package', 'Version', 'Status')})
    diversions = target_system.inside(root, 'var/lib/dpkg/diversions')
    report = {'packages': packages, 'diversions': diversions.read_text() if diversions.exists() else ''}
    (output / ('target-live-' + phase + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    for relative in ('usr/sbin/update-initramfs', 'var/lib/dpkg/info/live-tools.postinst',
                     'var/lib/dpkg/info/live-tools.postrm', 'var/lib/dpkg/info/live-tools.prerm'):
        path = target_system.inside(root, relative)
        if path.is_file():
            (output / (phase + '-' + path.name + '.txt')).write_text(path.read_text())
    print('::notice title=ISO canlı paket durumu ' + phase + '::' + json.dumps(report), flush=True)


def desktop_contract(root):
    """Paket, sahiplik, kapalı depo ve yeni görseller gerçek ISO'da olmalı."""
    secured = ('usr', 'usr/lib', 'usr/share', 'usr/local', 'usr/local/sbin', 'usr/lib/oguzdows',
               'usr/local/sbin/oguzdows-maintenance', 'usr/lib/oguzdows/maintenance.py',
               'usr/lib/oguzdows/hardware.py', 'usr/lib/oguzdows/pi_support.py',
               'usr/lib/oguzdows/app_catalog.py', 'usr/lib/oguzdows/store_service.py',
               'usr/lib/oguzdows/oguzdows-store-native', 'usr/lib/oguzdows/oguzdows-news-native',
               'usr/lib/oguzdows/news_service.py', 'usr/lib/oguzdows/news_core.py',
               'usr/share/oguzdows/picom.conf', 'usr/share/oguzdows/build-info.json',
               'usr/share/polkit-1/actions/org.oguzdows.maintenance.policy',
               'etc/apt/preferences.d/oguzdows-pardus', 'etc/apt/sources.list.d/oguzdows-pardus.sources',
               'usr/share/keyrings/oguzdows-pardus.asc')
    for relative in secured:
        path = target_system.inside(root, relative)
        details = path.stat()
        if details.st_uid != 0 or details.st_gid != 0 or details.st_mode & 0o022:
            raise RuntimeError('Yetkili bakım kodu / üst dizini root sahipli ve yazmaya kapalı değil: ' + relative)
    installed = set()
    status = target_system.nonempty(root, 'var/lib/dpkg/status').read_text()
    for paragraph in status.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines() if ': ' in line and not line.startswith((' ', '\t')))
        if fields.get('Status') == 'install ok installed':
            installed.add(fields.get('Package'))
    required = {'python3-apt', 'gnome-software', 'gnome-software-plugin-flatpak', 'iso-codes', 'flatpak', 'gpgv', 'xdg-desktop-portal-gtk', 'gir1.2-flatpak-1.0', 'libjson-glib-1.0-0', 'picom'}
    if required - installed:
        raise RuntimeError('ISO bakım / mağaza paketleri eksik: ' + ', '.join(sorted(required - installed)))
    # Software 48 bu isteğe bağlı gibi görünen veri olmadan SIGTRAP ile çıkar.
    target_system.nonempty(root, 'usr/share/xml/iso-codes/iso_639.xml')
    if 'Enabled: no' not in target_system.nonempty(root, 'etc/apt/sources.list.d/oguzdows-pardus.sources').read_text():
        raise RuntimeError('Pardus kanalı ISO içinde varsayılan kapalı değil.')
    if 'Hidden=true' not in target_system.nonempty(root, 'etc/xdg/autostart/org.gnome.Software.desktop').read_text():
        raise RuntimeError('Mağazanın otomatik açılışı engellenmemiş.')
    for record in json.loads((ROOT / 'artwork/landscapes.json').read_text()):
        picture = target_system.nonempty(root, 'usr/share/backgrounds/oguzdows/' + record['file'])
        if hashlib.sha256(picture.read_bytes()).hexdigest() != record['packaged_sha256']:
            raise RuntimeError('ISO yeni logolu manzarayı taşımıyor: ' + record['file'])
    target_system.nonempty(root, 'usr/share/icons/OguzDowsTespih/cursors/left_ptr')
    for identifier in json.loads((ROOT / 'system/usr/share/oguzdows/own-app-icons.json').read_text())['icons']:
        target_system.nonempty(root, f'usr/share/icons/hicolor/64x64/apps/oguzdows-{identifier}.png')
    target_system.nonempty(root, 'usr/share/oguzdows/news-sources.json')
    return {'packages': sorted(required), 'privileged_ownership_verified': True,
            'pardus_enabled': False, 'replacement_wallpapers': 20, 'native_cursor': True}


def configure_idle_test(root, uid):
    """SADECE geçici CI diskinde otomatik giriş; üretim katmanını değiştirmez."""
    if uid < 1000:
        raise RuntimeError('Geçici grafik test hesabı normal bir kullanıcı olmalı.')
    user = 'oguz-idle-proof'
    target_system.inside(root, 'var/log/oguzdows').mkdir(parents=True, exist_ok=True)
    put(root, f'home/{user}/.local/state/oguzdows/welcome-installed-1.1-seen', 'Disposable graphical measurement\n')
    put(root, 'etc/lightdm/lightdm.conf.d/99-oguzdows-disposable-idle.conf',
        f'[Seat:*]\nautologin-user={user}\nautologin-user-timeout=0\nuser-session=oguzdows\nautologin-session=oguzdows\n')
    put(root, 'usr/local/sbin/oguzdows-disposable-idle', '#!/bin/sh\nset -eu\n'
        + f'/usr/local/bin/oguzdows-memory-report --user {uid} --wait-for-desktop 180 --settle-seconds 120 '
          '--samples 6 --interval 5 --idle-confirmed --output /var/log/oguzdows/disposable-idle.json '
          '> /var/log/oguzdows/disposable-idle.stdout\n'
        + "/usr/bin/python3 -I - <<'PY' > /dev/ttyS0\nimport json\nfrom pathlib import Path\n"
          "data = json.loads(Path('/var/log/oguzdows/disposable-idle.json').read_text())\n"
          "print('OGUZDOWS-DESKTOP-IDLE-JSON:' + json.dumps(data, ensure_ascii=True, separators=(',', ':')), flush=True)\nPY\n", 0o755)
    unit = 'oguzdows-disposable-idle.service'
    put(root, 'etc/systemd/system/' + unit,
        '[Unit]\nDescription=Disposable full Xfce idle measurement\nAfter=display-manager.service\n'
        '[Service]\nType=oneshot\nTimeoutStartSec=420\nExecStart=/usr/local/sbin/oguzdows-disposable-idle\n'
        '[Install]\nWantedBy=graphical.target\n')
    wants = root / 'etc/systemd/system/graphical.target.wants'
    wants.mkdir(parents=True, exist_ok=True)
    (wants / unit).symlink_to('../' + unit)


def low_ram_budget(measurement, ram_mib):
    """600 MB hedefi 512 MiB'de tek başına anlamsızdır; gerçek pay da kalmalı."""
    if ram_mib not in (512, 1024):
        raise ValueError('Düşük RAM bütçesi yalnızca 512 / 1024 MiB için ölçülür.')
    reasons = []
    samples = measurement.get('samples', [])
    valid = (isinstance(samples, list) and 6 <= len(samples) <= 60
             and all(isinstance(item, dict) and type(item.get('total_bytes')) is int
                     and type(item.get('available_bytes')) is int
                     and ram_mib * 1024**2 * .75 <= item['total_bytes'] <= ram_mib * 1024**2
                     and 0 <= item['available_bytes'] <= item['total_bytes'] for item in samples))
    threshold = observed = None
    if not valid:
        reasons.append('En az altı örnekte gerçek VM MemTotal / MemAvailable baytları doğrulanamadı.')
    else:
        threshold = max(32 * 1024**2, (max(item['total_bytes'] for item in samples) + 9) // 10)
        observed = min(item['available_bytes'] for item in samples)
        if observed < threshold:
            reasons.append('Boşta kullanılabilir bellek payı yetersiz: en az max(32 MiB, MemTotal / 10) gerekli.')
    if not measurement.get('valid_idle_measurement'):
        reasons.append('Yerleşmiş boşta ölçüm geçerli değil.')
    if not measurement.get('target_met'):
        reasons.append('600 decimal MB boşta hedefi geçilmedi.')
    return {'passed': not reasons, 'minimum_available_bytes': threshold, 'observed_min_available_bytes': observed,
            'policy': 'Geçerli tam Xfce boşta ölçümü + en çok 600 MB kullanım + en az max(32 MiB, MemTotal / 10) kullanılabilir RAM; aktif uygulama gecikmesi garantisi değil.',
            'fail_reasons': reasons}


def boot_os(image, mode, output, work, root_uuid, graphical_idle=False, ram_mib=2048):
    if ram_mib not in (512, 1024, 2048):
        raise ValueError("VM RAM bütçesi 512, 1024 veya 2048 MiB olmalı.")
    serial = output / ('target-os-' + mode + '.serial.log')
    marker = 'OGUZDOWS-TARGET-OS-OK:' + root_uuid
    args = ['qemu-system-x86_64', '-machine', 'pc,accel=tcg', '-m', str(ram_mib), '-smp', '2',
            '-vga', 'std', '-display', 'none', '-monitor', 'none', '-serial', 'file:' + str(serial),
            '-drive', f'file={image},format=raw,if=none,id=testdisk,snapshot=on',
            '-device', 'virtio-blk-pci,drive=testdisk', '-nic', 'none', '-boot', 'c', '-no-reboot']
    if mode == 'efi':
        args += firmware.firmware_files(work)
    with (output / ('target-os-' + mode + '.qemu.log')).open('w') as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        try:
            timeout = 600 if graphical_idle else 240
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                text = serial.read_text(errors='replace') if serial.exists() else ''
                if re.search(r'Kernel panic - not syncing:', text):
                    # initramfs unpack OOM, systemd / masaüstü işaretinden önce
                    # olur; bilinen ölümcül hatada 600 saniye boşuna bekleme.
                    raise RuntimeError(f'{mode}: {ram_mib} MiB erken çekirdek paniği:\n' + text[-7000:])
                if marker in text and not graphical_idle:
                    print(mode + ': gerçek hedef çekirdek, initramfs ve systemd disk kökünde açıldı.', flush=True)
                    return None
                # UART dosyası hâlâ yazılıyor olabilir; yarım JSON'u hata sayma.
                idle_match = re.search(r'OGUZDOWS-DESKTOP-IDLE-JSON:([^\r\n]+)\r?\n', text) if graphical_idle else None
                if marker in text and idle_match:
                    measurement = json.loads(idle_match[1])
                    measurement['vm_ram_mib'] = ram_mib
                    if ram_mib <= 1024:
                        measurement['low_ram_budget'] = low_ram_budget(measurement, ram_mib)
                        if re.search(r'out of memory|oom-kill', text, re.IGNORECASE):
                            measurement['low_ram_budget']['passed'] = False
                            measurement['low_ram_budget']['fail_reasons'].append('Düşük RAM testinde OOM görüldü; başarı sayılmadı.')
                    if not all(item.get('graphical_xfce') for item in measurement.get('samples', [])) or not measurement.get('samples'):
                        raise RuntimeError('Hedef kullanıcı için tam Xfce grafik oturumu açılamadı: ' + json.dumps(measurement.get('invalid_reasons')))
                    (output / ('low-ram-idle.json' if ram_mib <= 1024 else 'desktop-idle.json')).write_text(json.dumps(measurement, ensure_ascii=False, indent=2) + '\n')
                    if ram_mib <= 1024 and not measurement['low_ram_budget']['passed']:
                        raise RuntimeError('Düşük RAM bütçesi geçilmedi: ' + json.dumps(measurement['low_ram_budget'], ensure_ascii=False))
                    status = 'notice' if measurement.get('target_met') else 'warning'
                    summary = {key: measurement.get(key) for key in ('valid_idle_measurement', 'median_used_mb', 'max_used_mb', 'target_met', 'invalid_reasons')}
                    summary['vm_ram_mib'] = ram_mib
                    if ram_mib <= 1024:
                        summary['low_ram_budget'] = measurement['low_ram_budget']
                    print('::' + status + ' title=Tam Xfce oturumu RAM (VM)::' + json.dumps(summary, ensure_ascii=False), flush=True)
                    return summary
                if process.poll() is not None:
                    raise RuntimeError(mode + ': hedef OS erken kapandı:\n' + text[-7000:])
                time.sleep(.5)
            raise RuntimeError(mode + f': hedef OS / grafik ölçüm işareti {timeout} saniyede oluşmadı:\n' + text[-7000:])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def check_low_ram(image, output, work, root_uuid, results):
    """512 hatası 1 GiB kanıtını saklamasın; herhangi bir hata yine işi düşürür."""
    errors = []
    for ram in (512, 1024):
        low_output = output / f'ram-{ram}'
        low_output.mkdir()
        try:
            measurement = boot_os(image, 'bios', low_output, work, root_uuid, graphical_idle=True, ram_mib=ram)
            if not measurement or not measurement.get('valid_idle_measurement'):
                raise RuntimeError(f'{ram} MiB tam Xfce ölçümü geçerli değil: ' + json.dumps(measurement))
            results.append(measurement)
        except Exception as error:
            failure = {'vm_ram_mib': ram, 'valid_idle_measurement': False, 'error': str(error)}
            (low_output / 'low-ram-boot-error.json').write_text(json.dumps(failure, ensure_ascii=True, indent=2) + '\n')
            results.append(failure)
            errors.append(failure)
    if errors:
        raise RuntimeError('Düşük RAM açılışı başarısız; her bütçenin kanıtı korundu:\n'
                           + '\n'.join(str(item['vm_ram_mib']) + ' MiB: ' + item['error'] for item in errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso', type=Path, required=True)
    parser.add_argument('--arch', choices=('amd64', 'i386'), required=True)
    parser.add_argument('--expected-revision', required=True)
    parser.add_argument('--output', type=Path, default=Path('test-results/iso-target'))
    parser.add_argument('--graphical-idle', action='store_true', help='Geçici test hesabıyla tam Xfce oturumu ve yerleşmiş RAM raporu')
    parser.add_argument('--low-ram-checks', action='store_true', help='Aynı geçici hedefte 512 / 1024 MiB tam Xfce boot ve RAM kontrolü ekle; fiziksel ARM testi değil')
    args = parser.parse_args()
    if args.low_ram_checks and not args.graphical_idle:
        parser.error('--low-ram-checks için --graphical-idle gerekli.')
    if os.geteuid() != 0 or os.environ.get('CI') != 'true':
        parser.error('Yalnızca ayrıcalıklı, tek kullanımlık CI konteynerinde çalıştırılır.')
    if not args.iso.is_file() or not stat.S_ISREG(args.iso.stat().st_mode):
        parser.error('Girdi normal bir ISO dosyası olmalı; blok aygıtı kabul edilmez.')
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', args.expected_revision):
        parser.error('Doğrulanmış kaynak commit kimliği gerekli.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='oguzdows-iso-target-')).resolve()
    image = work / 'private-target-only.img'
    iso_root = work / 'iso'
    target = work / 'target'
    iso_root.mkdir()
    target.mkdir()
    mounts = []
    uuid_links = []
    loop = None
    report = {'arch': args.arch, 'source_revision': args.expected_revision, 'modes': [],
              'gui_installation_tested': False, 'physical_boot_verified': False, 'encrypted_root_tested': False}
    def mount(*command, at):
        run('mount', *command, at)
        mounts.append(at)
    def chroot(*command):
        return run('chroot', target, '/usr/bin/env', 'DEBIAN_FRONTEND=noninteractive',
                   'LC_ALL=C', *command, timeout=900)
    try:
        mount('-o', 'loop,ro', args.iso.resolve(), at=iso_root)
        squashfs = iso_root / 'live/filesystem.squashfs'
        if not squashfs.is_file() or not squashfs.stat().st_size:
            raise RuntimeError('ISO içindeki kurulum kök sistemi yok / boş.')
        with image.open('wb') as stream:
            stream.truncate(24 * 1024**3)
        if args.arch == 'amd64':
            run('parted', '--script', image, 'mklabel', 'gpt',
                'mkpart', 'BIOS', '1MiB', '3MiB', 'set', '1', 'bios_grub', 'on',
                'mkpart', 'ESP', 'fat32', '3MiB', '515MiB', 'set', '2', 'esp', 'on',
                'mkpart', 'ROOT', 'ext4', '515MiB', '100%')
            root_number = 3
        else:
            run('parted', '--script', image, 'mklabel', 'msdos', 'mkpart', 'primary', 'ext4', '1MiB', '100%')
            root_number = 1
        allocated = subprocess.check_output(['losetup', '--find', '--show', '--partscan', str(image)], text=True).strip()
        if not re.fullmatch(r'/dev/loop[0-9]+', allocated):
            raise RuntimeError('Özel loop aygıtı dışında hedef reddedildi: ' + allocated)
        backing = Path('/sys/class/block') / Path(allocated).name / 'loop/backing_file'
        if Path(backing.read_text().strip()).resolve() != image:
            raise RuntimeError('Loop aygıtı bu testin özel dosyasına bağlı değil.')
        loop = allocated
        root_device = firmware.partition_device(loop, root_number)
        run('mkfs.ext4', '-q', '-F', root_device)
        mount(root_device, at=target)
        # /dev vb. bind edilmeden açılır: arşiv asla canlı /dev üzerine yazılmaz.
        run('unsquashfs', '-no-progress', '-f', '-processors', '2', '-d', target, squashfs, timeout=900)
        build = json.loads((target / 'usr/share/oguzdows/build-info.json').read_text())
        report['build'] = build
        validate_source(build, args.expected_revision, args.arch)
        report['mount_configuration'] = iso_mount_configuration(target, args.arch)
        report['desktop_contract'] = desktop_contract(target)
        esp_device = None
        if args.arch == 'amd64':
            esp_device = firmware.partition_device(loop, 2)
            run('mkfs.fat', '-F', '32', esp_device)
            (target / 'boot/efi').mkdir(parents=True, exist_ok=True)
            mount(esp_device, at=target / 'boot/efi')
        root_uuid = subprocess.check_output(['blkid', '-s', 'UUID', '-o', 'value', root_device], text=True).strip()
        if not re.fullmatch(r'[0-9a-f-]{36}', root_uuid):
            raise RuntimeError('Özel test kök UUID değeri geçersiz.')
        created_link = expose_loop_uuid(root_device, root_uuid)
        if created_link:
            uuid_links.append(created_link)
        report['root_uuid'] = root_uuid
        fstab = f'UUID={root_uuid} / ext4 defaults 0 1\n'
        if esp_device:
            esp_uuid = subprocess.check_output(['blkid', '-s', 'UUID', '-o', 'value', esp_device], text=True).strip()
            fstab += f'UUID={esp_uuid} /boot/efi vfat umask=0077 0 2\n'
        put(target, 'etc/fstab', fstab)
        for relative in ('dev', 'dev/pts', 'proc', 'sys'):
            (target / relative).mkdir(parents=True, exist_ok=True)
            mount('--bind', '/' + relative, at=target / relative)
        # Paket betikleri yalnızca test hedefindedir; servisleri CI'de başlatmasın.
        record_live_state(target, output, 'before')
        policy = target_system.inside(target, 'usr/sbin/policy-rc.d')
        saved_policy = (policy.read_bytes(), stat.S_IMODE(policy.stat().st_mode)) if policy.exists() else None
        put(target, 'usr/sbin/policy-rc.d', '#!/bin/sh\nexit 101\n', 0o755)
        try:
            chroot('/bin/sh', '/usr/lib/oguzdows/finish-install.sh')
            packages = yaml.safe_load((ROOT / 'installer/modules/packages.conf').read_text())
            for operation in packages['operations']:
                if set(operation) != {'remove'}:
                    raise RuntimeError('Test yalnızca zorunlu üretim temizlik işlemini kabul eder.')
                chroot('apt-get', '--purge', '-q', '-y', 'remove', *operation['remove'])
                chroot('apt-get', '--purge', '-q', '-y', 'autoremove')
        finally:
            if saved_policy:
                policy.write_bytes(saved_policy[0])
                policy.chmod(saved_policy[1])
            else:
                policy.unlink(missing_ok=True)
        record_live_state(target, output, 'after')
        target_system.require_clean_target(target)
        before = target_system.kernel_snapshot(target)
        if args.graphical_idle:
            # Üretim kullanıcı / otomatik giriş politikasına dokunmaz. Bu hesap
            # yalnızca testin özel, hiç yayımlanmayan disk dosyasında bulunur.
            chroot('useradd', '--create-home', '--shell', '/bin/bash', 'oguz-idle-proof')
            uid = int(subprocess.check_output(['chroot', str(target), 'id', '-u', 'oguz-idle-proof'], text=True).strip())
            configure_idle_test(target, uid)
            chroot('chown', '-R', 'oguz-idle-proof:oguz-idle-proof', '/home/oguz-idle-proof')
        put(target, 'etc/initramfs-tools/conf.d/calamares-safe-initramfs.conf', 'UMASK=0077\n')
        put(target, 'etc/initramfs-tools/conf.d/resume', 'RESUME=none\n')
        # Calamares InitramfsJob ile aynı gerçek komut, aynı güvenli UMASK.
        chroot('update-initramfs', '-k', 'all', '-c', '-t')
        report['initramfs'] = target_system.verify_initramfs(target, before)
        report['initramfs_inventory'] = []
        for version in report['initramfs']:
            inventory = initrd_report.record(target / ('boot/initrd.img-' + version), output, work)
            if args.arch == 'amd64' and (len(inventory['firmware']) != 1
                    or not inventory['firmware'][0].get('kernel_support_verified')
                    or inventory['firmware'][0].get('payloads_verified', 0) == 0):
                raise RuntimeError('amd64 initramfs GPU firmware sıkıştırma / içerik kanıtı eksik.')
            report['initramfs_inventory'].append(inventory)
            summary = json.dumps(inventory, ensure_ascii=True, separators=(',', ':'))
            if len(summary) > 3500:
                raise RuntimeError('initramfs envanteri kontrol notu sınırını aştı; kesik JSON yayımlanmadı.')
            print('::notice title=Gerçek initramfs envanteri::' + ci.escape_data(summary), flush=True)
        put(target, 'etc/default/grub.d/99-disposable-test.cfg',
            'GRUB_DISABLE_OS_PROBER=true\nGRUB_TIMEOUT=1\nGRUB_TERMINAL="serial console"\n'
            'GRUB_SERIAL_COMMAND="serial --unit=0 --speed=115200"\n'
            'GRUB_CMDLINE_LINUX_DEFAULT="console=ttyS0,115200 loglevel=5 systemd.show_status=1"\n')
        # Sadece hedefte gerçek systemd çalışınca işaret üretilir; GRUB echo'su değil.
        put(target, 'usr/local/sbin/oguzdows-disposable-proof', '#!/bin/sh\nset -eu\n'
            + f'test "$(findmnt -n -o UUID /)" = "{root_uuid}"\n'
            + '! grep -qw boot=live /proc/cmdline\n'
            + 'test ! -e /usr/local/sbin/oguzdows-installer\n'
            + f'printf "OGUZDOWS-TARGET-OS-OK:{root_uuid}\\n" > /dev/ttyS0\n', 0o755)
        unit = 'oguzdows-disposable-proof.service'
        put(target, 'etc/systemd/system/' + unit,
            '[Unit]\nDescription=Disposable ISO target boot proof\nAfter=local-fs.target\n'
            '[Service]\nType=oneshot\nExecStart=/usr/local/sbin/oguzdows-disposable-proof\n'
            '[Install]\nWantedBy=multi-user.target\n')
        wants = target / 'etc/systemd/system/multi-user.target.wants'
        wants.mkdir(parents=True, exist_ok=True)
        (wants / unit).symlink_to('../' + unit)
        chroot('grub-install', '--target=i386-pc', '--recheck', loop)
        if esp_device:
            chroot('grub-install', '--target=x86_64-efi', '--efi-directory=/boot/efi', '--bootloader-id=OguzDows', '--no-nvram')
            fallback = target / 'boot/efi/EFI/BOOT/BOOTX64.EFI'
            fallback.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target / 'boot/efi/EFI/OguzDows/grubx64.efi', fallback)
        chroot('grub-mkconfig', '-o', '/boot/grub/grub.cfg')
        shutil.copy2(target / 'boot/grub/grub.cfg', output / 'target-grub.cfg')
        report['kernel'] = target_system.verify_grub_menu(target, expected_root='UUID=' + root_uuid)
        # Mevcut üretim disk denetimini gerçek dosyalarla da çalıştır.
        sys.modules['libcalamares'] = SimpleNamespace(utils=SimpleNamespace(debug=print))
        boot = load('iso_target_disk_check', 'installer/modules/oguzdowsboot/main.py')
        parts = [{'device': root_device, 'mountPoint': '/', 'fs': 'ext4'}]
        boot.check(target, 'bios', parts, {'installPath': loop}, 'verify')
        if esp_device:
            parts.append({'device': esp_device, 'mountPoint': '/boot/efi', 'fs': 'fat32'})
            boot.check(target, 'efi', parts, None, 'verify')
        while mounts:
            run('umount', mounts[-1])
            mounts.pop()
        remove_owned_uuid_links(uuid_links)
        uuid_links.clear()
        run('losetup', '--detach', loop)
        loop = None
        for mode in (('bios', 'efi') if esp_device else ('bios',)):
            idle = boot_os(image, mode, output, work, root_uuid, graphical_idle=args.graphical_idle and mode == 'bios')
            if idle is not None:
                report['desktop_idle'] = idle
            report['modes'].append(mode)
        if args.low_ram_checks:
            report['low_ram'] = []
            check_low_ram(image, output, work, root_uuid, report['low_ram'])
        print('::notice title=ISO hedef sistem açılışı::' + json.dumps(report), flush=True)
    except Exception as error:
        report['error'] = str(error)
        # Artefakt deposuna erişilemese bile kesin hata API'den okunabilsin.
        ci.emit_error('ISO hedef sistem ' + args.arch, str(error))
        raise
    finally:
        (output / 'target-os-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        safe = True
        for location in reversed(mounts):
            if subprocess.run(['umount', str(location)], check=False).returncode:
                safe = False
        try:
            remove_owned_uuid_links(uuid_links)
        except OSError as error:
            safe = False
            print('Özel UUID bağlantısı temizlenemedi: ' + str(error), file=sys.stderr)
        if loop and safe:
            safe = subprocess.run(['losetup', '--detach', loop], check=False).returncode == 0
        if safe:
            shutil.rmtree(work)
        else:
            print('Bağlı test alanı korunuyor, silinmedi: ' + str(work), file=sys.stderr)


if __name__ == '__main__':
    main()
