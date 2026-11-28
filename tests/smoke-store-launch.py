#!/usr/bin/env python3
"""Özel CI kullanıcısında gerçek Gio başlatma ve kısa ömürlü JSON işçisi.

Zararsız test uygulamasıdır: gerçek APT/Flatpak kurulumu, Flathub erişimi veya
üretim uygulamasının çalışması kanıtı değildir. Paket durumu açık fixture'dır.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load


APPLICATION = '''import json, os, sys, time
from pathlib import Path
marker, stop, done = map(Path, sys.argv[1:])
marker.write_text(json.dumps({'pid': os.getpid(), 'uid': os.geteuid()}))
print('TEST-APPLICATION-STDOUT-NOT-WORKER-JSON', flush=True)
print('TEST-APPLICATION-STDERR-NOT-WORKER-LOG', file=sys.stderr, flush=True)
deadline = time.monotonic() + 12
while not stop.exists() and time.monotonic() < deadline:
    time.sleep(.02)
done.write_text('exited\\n')
'''


def wait_json(path, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            time.sleep(.02)
    raise RuntimeError('Test uygulamasının gerçek başlatma kaydı gelmedi.')


def worker(directory):
    if os.geteuid() == 0:
        raise RuntimeError('Başlatma işçisi gerçek yönetici olmayan kullanıcıyla çalışmalı.')
    if Path.home() != directory / 'home':
        raise RuntimeError('Gio işçisinin HOME yolu özel test köküne ait değil.')
    from gi.repository import GLib
    service = load('real_launch_store_service', 'system/usr/lib/oguzdows/store_service.py')
    original_desktop = service.system_desktop

    def package_fixture(arguments, **_kwargs):
        if arguments != ['/usr/bin/dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Status}\n']:
            raise AssertionError('Testte yalnızca sabit paket durumu sorgulanabilir: ' + repr(arguments))
        return 'gimp\tinstalled\n'

    # Yalnızca güvenilir desktop kökü ve paket durumu fixture'dır; root /
    # sahiplik / izin / izin listesi kontrolleri ve Gio gerçekten çalışır.
    with patch.object(service, 'system_desktop', side_effect=lambda name: original_desktop(name, directory / 'desktop')):
        result = service.launch('gimp', 'system', execute=package_fixture)
    result.update(real_gio_launch=True, uid=os.geteuid(), glib_version=[GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION])
    print(json.dumps(result, ensure_ascii=False), flush=True)


def worker_command(user, home, directory):
    # runuser hedef hesabın HOME'unu kullanır; ebeveyn env'si tek başına yetmez.
    # Özel yolları yetki düşürüldükten SONRA, shell kullanmadan env argv'siyle ver.
    private = {'HOME': str(home), 'USER': user.pw_name, 'LOGNAME': user.pw_name, 'GIO_USE_VFS': 'local',
               'XDG_CONFIG_HOME': str(home / 'config'), 'XDG_CACHE_HOME': str(home / 'cache'),
               'XDG_DATA_HOME': str(home / 'data'), 'XDG_STATE_HOME': str(home / 'state'), 'XDG_RUNTIME_DIR': str(home / 'runtime')}
    return ['runuser', '-u', user.pw_name, '--', '/usr/bin/env', *(key + '=' + value for key, value in private.items()),
            'dbus-run-session', '--', '/usr/bin/python3', '-I', str(Path(__file__).resolve()), '--worker', str(directory)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true':
        parser.error('Yalnızca tek kullanımlık CI konteynerinde çalıştırılır.')
    if args.worker is not None:
        worker(args.worker)
        return
    if args.output is None or os.geteuid() != 0:
        parser.error('--output ve özel test kullanıcısına geçebilen CI konteyneri gerekli.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    user = pwd.getpwnam('nobody')
    report = {'scope': 'host-real-gio-private-user-harmless-application', 'package_state_fixture': True,
              'real_package_installation': False, 'real_flatpak_runtime': False, 'root_application': False}
    with tempfile.TemporaryDirectory(prefix='oguzdows-launch-', dir=output) as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        home = directory / 'home'
        for path in (home, *(home / name for name in ('config', 'cache', 'data', 'state', 'runtime'))):
            path.mkdir()
            path.chmod(0o700)
            os.chown(path, user.pw_uid, user.pw_gid)  # Yalnızca bu özel fixture'ın altı dizini.
        marker, stop, done = (home / name for name in ('started.json', 'stop', 'done'))
        application = directory / 'application.py'
        application.write_text(APPLICATION)
        application.chmod(0o644)
        desktops = directory / 'desktop'
        desktops.mkdir()
        desktop = desktops / 'gimp.desktop'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Zararsız Gio denetimi\nTerminal=false\n'
                           f'Exec=/usr/bin/python3 -I "{application}" "{marker}" "{stop}" "{done}"\n')
        desktop.chmod(0o644)
        environment = {key: value for key, value in os.environ.items() if key != 'DBUS_SESSION_BUS_ADDRESS'}
        environment.update(HOME=str(home), USER=user.pw_name, LOGNAME=user.pw_name, GIO_USE_VFS='local',
                           XDG_CONFIG_HOME=str(home / 'config'), XDG_CACHE_HOME=str(home / 'cache'),
                           XDG_DATA_HOME=str(home / 'data'), XDG_STATE_HOME=str(home / 'state'), XDG_RUNTIME_DIR=str(home / 'runtime'))
        child = None
        started = time.monotonic()
        try:
            arguments = worker_command(user, home, directory)
            with subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment) as process:
                try:
                    stdout, stderr = process.communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    stop.touch()
                    process.kill()
                    stdout, stderr = process.communicate(timeout=5)
                    raise RuntimeError('Başlatılan uygulama JSON borusunu açık tuttu; işçi kısa ömürlü değil. ' + stdout[-1000:] + stderr[-1000:])
            elapsed = time.monotonic() - started
            if process.returncode:
                raise RuntimeError('Gio işçisi başarısız: ' + stdout[-2500:] + stderr[-2500:])
            result = json.loads(stdout)  # Uygulama stdout'u bu tek JSON'a karışmamalı.
            assert 'TEST-APPLICATION-' not in stdout + stderr, 'Uygulama günlükleri işçi borularına sızdı.'
            assert result['real_gio_launch'] and result['uid'] == user.pw_uid
            child = wait_json(marker)
            assert child['uid'] == user.pw_uid and child['uid'] != 0
            assert not done.exists(), 'İşçi döndüğünde test uygulaması hâlâ açık olmalı.'
            os.kill(child['pid'], 0)
            report.update(result, child_uid=child['uid'], worker_seconds=round(elapsed, 3),
                          clean_json=True, child_streams_detached=True, application_alive_after_worker_exit=True)
            print('::notice title=Gerçek kullanıcı Gio başlatma::' + json.dumps(report, ensure_ascii=False), flush=True)
        except Exception as error:
            report['error'] = str(error)
            raise
        finally:
            stop.touch()
            deadline = time.monotonic() + 3
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            if child is None and marker.exists():
                child = wait_json(marker)
            if child and not done.exists():
                process_path = Path('/proc') / str(child['pid'])
                try:
                    if process_path.stat().st_uid == user.pw_uid and str(application).encode() in (process_path / 'cmdline').read_bytes().split(b'\0'):
                        os.kill(child['pid'], signal.SIGTERM)
                except OSError:
                    pass
            (output / 'store-launch.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
