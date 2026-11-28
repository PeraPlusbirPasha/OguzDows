#!/usr/bin/env python3
"""Hedef ARM + minimum CPU + gerçek GTK/Xfce; Xvfb ekranı fiziksel Pi değildir.

Paket kurmaz, sistem servisi veya uygulama motoru başlatmaz. Geçici non-root Xfce
oturumu açıp kapatır; LightDM/PAM ve fiziksel GPU açılışını sınamaz. Ürün
özelliklerinin varlığını/hash'ini ve hedefte tema/duvar kâğıdı işlemlerini ölçer;
genel uygulama işlemi veya performans kabulü sayılmaz.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path


# Her iki kapı da bu betiğin yanındaki incelenmiş okuyucuyu kullanır.
# Host verifier bağlı imajın Python modülünü içe aktarmaz.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_contract import checked_path, elf_info, feature_presence, read_json


def package_versions(text, required, arch):
    records = {}
    for line in text.splitlines():
        parts = line.split('\t')
        if len(parts) != 4:
            raise ValueError('dpkg-query çıktısı bozuk.')
        name, architecture, version, status = parts
        # Stock pi-gen karşı mimariyi de kaydeder (ör. 32-bit kökte v8 kernel).
        # Yabancı ek kopya yerel ürün paketinin yerine sayılamaz.
        if architecture not in (arch, 'all'):
            continue
        if name in records:
            raise ValueError('Tekrarlı hedef paket kaydı: ' + name)
        if status != 'installed' or not version:
            raise ValueError('Ürün paketi kurulu değil / sürümü eksik: ' + name)
        records[name] = {'architecture': architecture, 'version': version}
    if set(records) != set(required):
        raise ValueError('Ortak paket listesiyle hedef paketler eşleşmedi.')
    return records


def command(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=90).stdout.strip()


def version_output(xfce, native):
    versions = {'xfce_version': xfce.splitlines()[0][:240] if xfce else '',
                'native_store_version': native.splitlines()[0][:240] if native else ''}
    if 'xfce4-session' not in versions['xfce_version'] or 'OğuzDows' not in versions['native_store_version']:
        raise ValueError('Xfce / yerel mağaza sürüm yanıtı geçersiz: ' + json.dumps(versions, ensure_ascii=False))
    return versions


def gui_check(prefix, native_store):
    # GI geç içe aktarılır: kaynak / ABI regresyonları GTK'sız hostta da çalışır.
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gtk
    initialized = Gtk.init_check()
    if not (initialized[0] if isinstance(initialized, tuple) else initialized) or Gdk.Display.get_default() is None:
        raise ValueError('GTK için gerçek X ekranı açılamadı.')
    window = Gtk.Window(title='OğuzDows ARM · derleme kontrolü')
    try:
        label = Gtk.Label(label='OğuzDows · Türkçe · çay, ı, İ, ğ, ş')
        window.add(label)
        window.set_default_size(360, 180)
        window.show_all()
        Gdk.Display.get_default().sync()
        for _ in range(100):
            if not Gtk.events_pending():
                break
            Gtk.main_iteration_do(False)
        if not window.get_realized() or label.get_layout().get_pixel_size()[0] <= 0:
            raise ValueError('Gerçek GTK pencere / Türkçe yazı düzeni oluşmadı.')
        xfce = command([*prefix, '/usr/bin/xfce4-session', '--version'])
        native = command([*prefix, str(native_store), '--version'])
        return {'gtk_window': True, 'gtk_version': [Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()],
                **version_output(xfce, native)}
    finally:
        window.destroy()


def target_check(arch, cpu, report):
    root = Path('/')
    contract = read_json(root, 'usr/share/oguzdows/pi-contract.json')
    if not isinstance(contract, dict) or type(contract.get('schema')) is not int or contract['schema'] != 1:
        raise ValueError('Pi özellik sözleşmesi sürümü geçersiz.')
    expected = contract['architectures'][arch]
    if contract['arch'] != arch or expected['cpu'] != cpu:
        raise ValueError('Minimum CPU / mimari sözleşmesi uyuşmuyor.')
    report.update(arch=arch, minimum_cpu=cpu, source_revision=contract['source_revision'], pi_gen_commit=contract['pi_gen_commit'])
    report['abi'] = {str(path): elf_info(checked_path(root, str(path).removeprefix('/')), expected) for path in
                     (Path('/usr/bin/python3'), Path('/usr/lib/oguzdows/oguzdows-store-native'), Path('/usr/lib/oguzdows/oguzdows-news-native'))}
    prefix = ['/tmp/oguzdows-qemu-static', '-cpu', cpu]
    command([*prefix, '/bin/true'])
    sys.path.insert(0, '/usr/lib/oguzdows')
    report['python_modules'] = []
    for name in contract['python_modules']:
        if not re.fullmatch('[a-z_]+', name):
            raise ValueError('Sözleşmede geçersiz Python modülü.')
        importlib.import_module(name)
        report['python_modules'].append(name)
    report['feature_presence'] = feature_presence(root, contract)
    required = contract['required_packages']
    if not all(re.fullmatch('[a-z0-9][a-z0-9+.-]*', value) for value in required):
        raise ValueError('Sözleşmede geçersiz paket adı.')
    text = command(['/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Architecture}\t${Version}\t${db:Status-Status}\n', *required])
    report['packages'] = package_versions(text, required, arch)
    report['suite'] = command(['/usr/bin/lsb_release', '-sc'])
    if report['suite'] != contract['suite']:
        raise ValueError('Pi paket aracı gerçek taban kod adını göremiyor.')
    report['gui'] = gui_check(prefix, '/usr/lib/oguzdows/oguzdows-store-native')
    news = command([*prefix, '/usr/lib/oguzdows/oguzdows-news-native', '--version'])
    if 'OğuzDows Haber · GTK ' not in news:
        raise ValueError('Hedef C haber okuyucusu sürümü geçersiz.')
    report['gui']['native_news_version'] = news
    from pi_session_smoke import run_nonroot_session
    report['full_session'] = run_nonroot_session(cpu)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=('armhf', 'arm64'))
    parser.add_argument('--cpu', choices=('arm1176', 'cortex-a53'))
    parser.add_argument('--host-gui', action='store_true', help='Yalnızca ortak GTK / Xfce kapısı; ARM kanıtı değil')
    parser.add_argument('--native-store', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.host_gui:
        if args.arch or args.cpu or args.native_store is None:
            parser.error('--host-gui yalnızca --native-store ve --output ile kullanılır.')
    elif not args.arch or not args.cpu or args.native_store:
        parser.error('Hedef kontrolünde --arch ve --cpu gerekli.')
    report = {'schema': 1, 'scope': 'host-gui-only' if args.host_gui else 'ARM-qemu-user-with-host-Xvfb',
              'physical_boot': False, 'hardware_gpu': False, 'performance_measurement': False,
              'real_package_transactions': False, 'real_audio_playback': False, 'errors': []}
    try:
        if args.host_gui:
            report['gui'] = gui_check([], args.native_store)
        else:
            target_check(args.arch, args.cpu, report)
    except Exception as error:
        detail = type(error).__name__ + ': ' + str(error)
        if isinstance(error, subprocess.CalledProcessError):
            detail += '\n' + ((error.stderr or '') + (error.stdout or ''))[-1800:]
        report['errors'].append(detail)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    summary = {key: report[key] for key in ('scope', 'physical_boot', 'hardware_gpu', 'performance_measurement', 'errors')}
    summary.update(arch=report.get('arch'), minimum_cpu=report.get('minimum_cpu'), gui=report.get('gui'),
                   feature_presence=report.get('feature_presence'), full_session=report.get('full_session'), packages_checked=len(report.get('packages', {})))
    print('::notice title=Pi ABI / GTK / özellik varlığı::' + json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
