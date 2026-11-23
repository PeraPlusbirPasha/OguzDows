#!/usr/bin/env python3
"""Gerçek Picom / xfwm / X11 sahipliği, özel non-root CI ekranında.

Bütçe 8 GiB olarak taklittir, GPU / hız ölçümü DEĞİLDİR. Gerçek XRender motoru
ve seçim sahipliği sınanır; Gala spring / zoom eşdeğerliği iddia edilmez.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from support import ROOT, load


def child(directory):
    if os.getuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise ValueError('Özel normal kullanıcı ve D-Bus gerekli.')
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gtk
    effects = load('real_window_effects', 'system/usr/lib/oguzdows/effects.py')
    policy = load('real_window_policy', 'system/usr/lib/oguzdows/resource_policy.py')
    full, mini = policy.policy(8388608), policy.policy(524288)
    report = {'scope': 'host-nonroot-private-Xvfb-real-XRender', 'resource_budget_simulated': True,
              'physical_gpu': False, 'performance_measurement': False, 'gala_parity': False}
    state = effects.state_directory()
    wm = foreign = None
    window = None
    with (directory / 'effects.log').open('w') as log:
        try:
            wm = subprocess.Popen(['/usr/bin/xfwm4', '--compositor=off'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            time.sleep(1)
            assert wm.poll() is None
            first = effects.reconcile('aero', full)
            assert first['engine'] == 'picom' and first['transitions'], first
            owned = effects.owned_state(state)
            assert owned and effects.identity(owned['pid']) == owned['started']
            x11 = effects.X11()
            try:
                assert x11.owner() == owned['owner']
            finally:
                x11.close()
            second = effects.reconcile('aero', full)
            assert second['engine'] == 'picom' and effects.owned_state(state)['pid'] == owned['pid']
            report['one_owned_engine_reused'] = True
            # Gerçek pencere aç / küçült / geri getir. Piksel-zaman benchmark'ı değil.
            window = Gtk.Window(title='OğuzDows · kısa geçiş denetimi')
            window.set_default_size(480, 260)
            window.add(Gtk.Label(label='Metin ve kapatma düğmesi opak kalır.\nÖzel CI XRender denetimi.'))
            window.show_all()
            for operation in (lambda: None, window.iconify, window.deiconify):
                operation()
                deadline = time.monotonic() + .5
                while time.monotonic() < deadline:
                    while Gtk.events_pending(): Gtk.main_iteration_do(False)
                    time.sleep(.02)
            assert window.get_window() is not None
            pixels = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, 1024, 768)
            assert pixels is not None
            pixels.savev(str(directory / 'effects-window.png'), 'png', [], [])
            report['real_window_open_minimize_restore'] = True
            safe = effects.reconcile('aero', mini)
            assert not safe['transitions'] and effects.owned_state(state) is None
            assert effects.identity(owned['pid']) is None
            report['low_memory_override_stopped_owned_engine'] = True
            # xfwm'ın zaten sahip olduğu CM seçimi tekrar 'cam' isteğinde
            # kapanmamalı. Böylece normal cam ve Aero motor değişimi de sınanır.
            glass = effects.reconcile('glass', full)
            assert glass['engine'] == 'xfwm4' and not glass['transitions'], glass
            x11 = effects.X11()
            try:
                owner = effects.wait_owner(x11, None)
                assert owner and owner == x11.wm_owner()
                repeated = effects.reconcile('glass', full)
                assert repeated['engine'] == 'xfwm4' and x11.owner() == owner
                effects.reconcile('off', full)
                assert effects.wait_owner(x11, 0) == 0
                report['glass_selection_reused_without_toggling'] = True
            finally:
                x11.close()
            # Kullanıcının dış kompozitörüymüş gibi ayrı gerçek Picom; sahipliği
            # bizim JSON'a kaydedilmez ve yönetici bu süreci asla öldürmemeli.
            x11 = effects.X11()
            try:
                assert effects.wait_owner(x11, 0) == 0
                foreign = subprocess.Popen(['/usr/bin/picom', '--config', str(effects.CONFIG)], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                owner = effects.wait_owner(x11, None)
                assert owner and foreign.poll() is None
                preserved = effects.reconcile('aero', full)
                assert preserved['engine'] == 'external' and not preserved['transitions'], preserved
                assert foreign.poll() is None and x11.owner() == owner
                effects.reconcile('off', full)
                assert foreign.poll() is None and x11.owner() == owner
                report['foreign_compositor_preserved_no_competing_engine'] = True
            finally:
                x11.close()
            report['picom_version'] = subprocess.check_output(['/usr/bin/picom', '--version'], text=True, timeout=5).strip()
        finally:
            effects.stop_owned(state)
            if window is not None: window.destroy()
            for process in (foreign, wm):
                if process is not None:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
    (directory / 'effects-native.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Gerçek pencere geçiş motoru::' + json.dumps(report, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true':
        parser.error('Yalnızca tek kullanımlık CI / özel Xvfb ekranında çalışır.')
    if args.child:
        child(args.child)
        return
    if args.output is None or not os.environ.get('XAUTHORITY'):
        parser.error('--output ve özel xvfb-run Xauthority gerekli.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-effects-ci-') as temporary:
        directory = Path(temporary)
        home, runtime = directory / 'home', directory / 'runtime'
        shutil.copytree(ROOT / 'system/etc/skel', home)
        runtime.mkdir(mode=0o700)
        authority = directory / 'Xauthority'
        shutil.copy2(os.environ['XAUTHORITY'], authority)
        authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key != 'DBUS_SESSION_BUS_ADDRESS'}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
                   XDG_STATE_HOME=str(home / '.local/state'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_RUNTIME_DIR=str(runtime), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE',
                   XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()), '--child', str(directory)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try:
            subprocess.run(command, env=env, check=True, timeout=40)
        finally:
            key = hashlib.sha256(env['DISPLAY'].encode()).hexdigest()[:16]
            state = home / '.local/state/oguzdows/effects' / key
            for source in (directory / 'effects.log', directory / 'effects-native.json', directory / 'effects-window.png',
                           state / 'picom.log', state / 'status.json'):
                if source.is_file(): shutil.copy2(source, output / ('picom-' + source.name if source.name in ('picom.log', 'status.json') else source.name))


if __name__ == '__main__':
    main()
