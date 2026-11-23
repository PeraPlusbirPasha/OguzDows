#!/usr/bin/env python3
"""Cihaz özgü çalışan ARM64 Linux için incelenebilir deneysel masaüstü katmanı.

Rootfs / telefon flaşlayıcısı değildir. Cihazın U-Boot / UEFI / çekirdek / DTB /
modem ayarlarını değiştirmez. Root, ağ veya hedef aygıt gerektirmez.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system/usr/lib/oguzdows'))
import device_support

spec = importlib.util.spec_from_file_location('arm_pi_config', ROOT / 'scripts/configure-pi.py')
pi_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi_config)


def configure(identifier, output):
    if identifier not in device_support.OVERLAY_PROFILES:
        raise ValueError('Bu araç yalnızca listelenen ARM64 katmanları içindir. Pi için ayrı pi-gen tarifini kullanın.')
    profile = device_support.get(identifier)
    output.mkdir(parents=True, exist_ok=False)
    overlay = output / 'overlay'
    shutil.copytree(ROOT / 'system', overlay,
                    ignore=shutil.ignore_patterns('__pycache__', '*.py[cod]', 'rifki_pet.py', 'rifki_scene.py', 'rifki_motion.py', 'rig', 'envelopes.json', 'intro-full.wav', 'hello.wav', 'help.wav', 'disk.wav', 'talk-blink.png'))
    for name in pi_config.PC_ONLY:
        path = overlay / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    info = {'schema': 1, 'platform': 'arm', 'arch': 'arm64', 'suite': 'trixie',
            'device_profile': identifier, 'status': 'experimental-overlay-not-boot-image'}
    (overlay / 'etc/oguzdows').mkdir(parents=True, exist_ok=True)
    (overlay / 'etc/oguzdows/device.json').write_text(json.dumps({'schema': 1, 'profile': identifier}, indent=2) + '\n')
    (overlay / 'usr/share/oguzdows/build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    wants = overlay / 'etc/systemd/system/multi-user.target.wants'
    wants.mkdir(parents=True, exist_ok=True)
    (wants / 'oguzdows-resource-tune.service').symlink_to('../oguzdows-resource-tune.service')
    shutil.copytree(ROOT / 'native', overlay / 'usr/share/oguzdows/native')
    (overlay / 'usr/share/oguzdows/scripts').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'scripts/build-native.sh', overlay / 'usr/share/oguzdows/scripts/build-native.sh')
    shutil.copy2(ROOT / 'scripts/build-news.sh', overlay / 'usr/share/oguzdows/scripts/build-news.sh')
    (overlay / 'usr/share/oguzdows/scripts/build-news.sh').chmod(0o755)
    shutil.copy2(ROOT / 'scripts/render-assets.py', overlay / 'usr/lib/oguzdows/render-assets.py')
    shutil.copytree(ROOT / 'assets', overlay / 'usr/share/oguzdows/assets')
    shutil.copytree(ROOT / 'boot', overlay / 'usr/share/plymouth/themes/oguzdows')
    docs = overlay / 'usr/share/doc/oguzdows'
    docs.mkdir(parents=True, exist_ok=True)
    for source, target in (('MASAUSTU-VE-BAKIM.md', 'masaustu-ve-bakim.md'), ('CIHAZLAR-VE-UYUMLULUK.md', 'cihazlar-ve-uyumluluk.md'), ('PI-ZERO-OTURUM.md', 'PI-ZERO-OTURUM.md'), ('ELEMENTARY-HABER.md', 'ELEMENTARY-HABER.md')):
        shutil.copy2(ROOT / 'docs' / source, docs / target)
    for directory in ('usr/local/bin', 'usr/local/sbin', 'usr/lib/oguzdows', 'usr/share/oguzdows/scripts'):
        for path in (overlay / directory).iterdir():
            if path.is_file() and path.suffix in ('', '.py', '.sh'):
                path.chmod(0o755)
    packages = []
    for name in ('common', 'arm'):
        for line in (ROOT / 'packages' / (name + '.list')).read_text().splitlines():
            value = line.partition('#')[0].strip()
            if value and value not in packages:
                packages.append(value)
    if profile['phone']:
        packages.append('onboard')
    (output / 'packages.list').write_text('\n'.join(packages) + '\n')
    (output / 'device-profile.json').write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n')
    (output / 'OKU-BENI.md').write_text(f'''# {profile['name']} · deneysel OğuzDows katmanı

**Bu çıktı önyüklenebilir ISO / SD / telefon ROM'u değildir.** Önce kendi cihazında
zaten çalışan, cihazına uygun çekirdek / DTB / firmware ve trixie ARM64 kullanıcı
alanı gerekir. `{profile['boot']}`. Android / iOS bölümlerine yazmayın.

`overlay/` incelenebilir masaüstü dosyalarıdır, `packages.list` aynı tabanın imzalı
paket yöneticisi için paket adlarıdır; çalıştırılabilir kurulum komutu değildir.
Kurulu cihazına körlemesine kopyalamayın. Önce yedek ve ayrı geçici ARM64 rootfs
üzerinde gözden geçirin. Çalışan kernel / boot / kullanıcı hesapları korunmalıdır.

Mimariye uygun C mağazası ve C haber okuyucusu, paketler kurulu ARM64 rootfs içinde
`/usr/share/oguzdows/scripts/build-native.sh /usr/lib/oguzdows/oguzdows-store-native`
ve
`/usr/share/oguzdows/scripts/build-news.sh /usr/lib/oguzdows/oguzdows-news-native`
ile derlenir. `seal-app-store.sh` root sahipliğini / yazma izinlerini mühürler;
`render-assets.py --root /` görselleri üretir ve `update-desktop-database`
MIME açıcılarını kaydeder. Bunlar cihaz üzerinde kendiliğinden çalıştırılmaz.
Hedef rootfs dışında host makinenizde root olarak çalıştırmayın.

Ortak kaynak kararı `/etc/oguzdows/resources.conf` içindedir. Katmanda etkin
`oguzdows-resource-tune.service` ilk açılışta sınırlı LZ4 zram bütçesini yazar;
özel zramswap ve disk swap ayarları korunur. Pi firmware / Pi servisleri eklenmez.

Waydroid / Android imajı eklenmez, servis açılmaz. Xfce varsayılanı X11'dir;
APK için ayrıca Wayland, binder, cihaz uyumlu hazırlanmış Waydroid ve yeterli RAM
şarttır. Modem, görüşme, dokunma, kamera, GPU, pil / askı fiziksel olarak doğrulanmadı.

Bu profil bir portlama başlangıcıdır. "Her ARM / telefon desteklenir" anlamına gelmez.
''')
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=device_support.OVERLAY_PROFILES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    configure(args.device, args.output.resolve())
    print('Deneysel, önyüklenebilir olmayan ARM masaüstü katmanı:', args.output)


if __name__ == '__main__':
    main()
