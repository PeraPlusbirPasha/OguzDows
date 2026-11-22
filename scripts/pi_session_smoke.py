#!/usr/bin/env python3
"""Geçici CI kökünde root olmayan TAM Xfce oturumu; LightDM/PAM/GPU testi değil.

Yalnızca /run/oguzdows-ci.* altında özel Xauthority ve D-Bus ile çalışır.
İmajın gerçek Xsession girişini kullanır; --version yanıtını açılış saymaz.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

PROCESSES = ('xfwm4', 'xfce4-panel', 'xfdesktop')


def private_home(home):
    home = Path(home)
    if (not str(home).startswith('/run/oguzdows-ci.') or home.name != 'home'
            or home.is_symlink() or not home.is_dir()):
        raise ValueError('Oturum testi yalnızca kendine ait geçici CI evinde çalışır.')
    return home


def owned_processes(home, uid=None):
    uid = os.getuid() if uid is None else uid
    result = {}
    expected = ('HOME=' + str(home)).encode()
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            if int(directory.name) in (os.getpid(), os.getppid()) or directory.stat().st_uid != uid:
                continue
            if expected not in (directory / 'environ').read_bytes().split(b'\x00'):
                continue
            args = (directory / 'cmdline').read_bytes().decode(errors='replace').split('\x00')
            result[int(directory.name)] = {Path(arg).name for arg in args if arg}
        except (OSError, ValueError):
            continue
    return result


def session_child(output, cpu):
    home = private_home(os.environ.get('HOME', ''))
    if os.geteuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS') or not os.environ.get('DISPLAY'):
        raise ValueError('Root olmayan kullanıcı, özel X ve D-Bus oturumu gerekli.')
    report = {'scope': 'non-root-Xfce-on-host-Xvfb', 'uid': os.getuid(),
              'lightdm_pam': False, 'physical_boot': False, 'performance_measurement': False,
              'errors': []}
    prefix = ['/tmp/oguzdows-qemu-static', '-cpu', cpu]
    process = None
    browser = None
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11, Gtk
        if not Gtk.init_check()[0]:
            raise ValueError('Kullanıcı özel Xauthority ile ekran açamadı.')
        with (home.parent / 'xfce.log').open('w') as log:
            process = subprocess.Popen([*prefix, '/usr/bin/python3', '-I', '/usr/lib/oguzdows/session_start.py'],
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 180
            stable = 0
            found = set()
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise ValueError('Gerçek Xfce oturumu erken kapandı: ' + str(process.returncode))
                for _ in range(100):
                    if not Gtk.events_pending():
                        break
                    Gtk.main_iteration_do(False)
                processes = owned_processes(home)
                found = set().union(*processes.values()) if processes else set()
                wm = GdkX11.X11Screen.get_window_manager_name(Gdk.Screen.get_default())
                ready = all(name in found for name in PROCESSES) and wm.lower() == 'xfwm4'
                stable = stable + 1 if ready else 0
                if stable >= 5:
                    break
                time.sleep(1)
            if stable < 5:
                raise ValueError('WM + panel + masaüstü 180 saniyede birlikte hazır olmadı: ' + repr(sorted(found)))
            report.update({name: True for name in PROCESSES})
            report['x11_window_manager'] = wm
            report['stable_samples'] = stable
            # Gerçek non-root Xfconf / oturum kaydı da gerekli.
            query = subprocess.run([*prefix, '/usr/bin/xfconf-query', '-c', 'xfce4-panel', '-p', '/panels'],
                                   check=True, capture_output=True, text=True, timeout=30)
            report['panel_configuration'] = query.stdout.strip()[:500]
            startup = json.loads((home / '.local/state/oguzdows/session/startup.json').read_text())
            if startup.get('uid') != os.getuid():
                raise ValueError('Ürün giriş işçisi kullanıcı kimliği uyuşmuyor.')
            report['startup_profile'] = startup['profile']
            if cpu == 'arm1176':
                # armhf imajında varsayılan başlatıcı gerçekten NetSurf'ü
                # açabilmeli. Ağ / haber sitesi uyumluluğu ölçülmez.
                browser = subprocess.Popen([*prefix, '/usr/bin/python3', '-I', '/usr/lib/oguzdows/browser.py'],
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                for _ in range(8):
                    time.sleep(1)
                    if browser.poll() is not None:
                        raise ValueError('ARMv6 NetSurf varsayılanı erken kapandı: ' + str(browser.returncode))
                names = set().union(*owned_processes(home).values())
                if 'netsurf-gtk' not in names:
                    raise ValueError('ARMv6 web başlatıcısı NetSurf sürecini oluşturmadı.')
                report['browser'] = {'program': 'netsurf-gtk', 'local_start_page_alive': True,
                                     'network_tested': False, 'modern_sites_verified': False}
    except Exception as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        if browser is not None:
            if browser.poll() is None:
                browser.terminate()
            try:
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=10)
        if process is not None:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        # Xfce bazı alt bileşenleri daemonlaştırır. Yalnızca bu özel HOME'a
        # ait aynı UID süreçleri temizle; pkill / killall / host D-Bus yok.
        for pid, names in owned_processes(home).items():
            if names & {'dbus-daemon', 'dbus-run-session'}:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 1 if report['errors'] else 0


def run_nonroot_session(cpu):
    root = Path(os.environ['XDG_RUNTIME_DIR'])
    if os.geteuid() != 0 or not str(root).startswith('/run/oguzdows-ci.') or not root.is_dir():
        raise ValueError('Oturum CI hazırlığı yalnızca geçici hedef chroot içindir.')
    directory = root / 'nonroot'
    home = directory / 'home'
    directory.mkdir(mode=0o700)
    shutil.copytree('/etc/skel', home)
    (directory / 'runtime').mkdir(mode=0o700)
    shutil.copy2(os.environ['XAUTHORITY'], directory / 'Xauthority')
    for path in [directory, *directory.rglob('*')]:
        os.chown(path, 65534, 65534, follow_symlinks=False)
    root.chmod(0o711)  # Yalnızca geçiş; root raporu / evinin içeriği okunamaz.
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
           'HOME': str(home), 'USER': 'nobody', 'LOGNAME': 'nobody',
           'DISPLAY': os.environ['DISPLAY'], 'XAUTHORITY': str(directory / 'Xauthority'),
           'XDG_RUNTIME_DIR': str(directory / 'runtime'),
           'GSETTINGS_BACKEND': 'memory', 'NO_AT_BRIDGE': '1', 'QEMU_CPU': cpu,
           'DBUS_SYSTEM_BUS_ADDRESS': 'unix:path=' + str(directory / 'no-system-bus')}
    prefix = ['/tmp/oguzdows-qemu-static', '-cpu', cpu]
    command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups',
               '/usr/bin/dbus-run-session', '--', *prefix, '/usr/bin/python3', str(Path(__file__).resolve()),
               '--cpu', cpu, '--output', str(directory / 'session.json')]
    try:
        with (directory / 'runner.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
        result = json.loads((directory / 'session.json').read_text())
        if result.get('errors') or result.get('uid') != 65534 or any(result.get(name) is not True for name in PROCESSES):
            raise ValueError('Root olmayan oturum kapısı başarısız: ' + str(result))
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        logs = '\n'.join(path.read_text(errors='replace')[-3500:] for path in
                         (directory / 'runner.log', directory / 'xfce.log', directory / 'session.json') if path.is_file())
        raise ValueError('Root olmayan tam Xfce oturumu başarısız: ' + str(error) + '\n' + logs) from error
    finally:
        # timeout'ta dbus-run-session'ın çocuğu kalmış olsa da başka kullanıcının
        # sürecini öldürme. Yalnızca bu testin tam HOME + UID eşleşmesi.
        for pid in owned_processes(home, uid=65534):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        root.chmod(0o700)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', choices=('arm1176', 'cortex-a53'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(session_child(args.output, args.cpu))
