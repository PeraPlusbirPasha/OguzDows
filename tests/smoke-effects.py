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


def pump(predicate, seconds=10):
    from gi.repository import GLib
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while GLib.MainContext.default().iteration(False):
            pass
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Gerçek GTK görünüm işçisi tamamlanmadı')


def gtk_apply_checks(resources):
    """Gerçek Rehber -> GTK düğmesi -> ortak işlem -> Picom / Xfwm zinciri."""
    from unittest.mock import patch
    import desktop_preferences as shared
    import desktop_state as shared_state
    import effects
    import profiles
    import welcome
    errors = []
    original_hook = sys.excepthook
    def hook(kind, value, trace):
        errors.append(str(value))
        original_hook(kind, value, trace)
    sys.excepthook = hook
    app = None
    try:
        # Yalnız donanım raporunun bu görünüm testinde ilgisiz arka plan işini
        # atla. Gerçek GTK, GApplication / D-Bus, tercihler ve motorlar çalışır.
        with patch.object(welcome.Welcome, 'load_report'), patch.object(shared, 'current_policy', return_value=resources):
            app = welcome.Welcome(); app.register(None); app.activate()
            app.navigate('appearance')
            panel = app.material_panel
            assert not panel.busy and not app.theme_busy and panel.apply_button.get_sensitive()
            with patch.object(shared, 'update_and_apply', side_effect=KeyError('CI unexpected theme failure')):
                app.change_appearance('dark')
                pump(lambda: not app.theme_busy)
            assert 'CI unexpected theme failure' in app.theme_status.get_text()
            assert panel.apply_button.get_sensitive()
            app.ensure_page('styles'); app.profile_reload.set_active(False)
            with patch.object(welcome.threading.Thread, 'start', side_effect=RuntimeError('CI worker start failed')):
                app.change_style('oguzdows')
            assert not app.profile_busy and panel.apply_button.get_sensitive()
            assert 'CI worker start failed' in app.profile_status.get_text()
            # Gerçek kurucu sinyaliyle aynı kapı; sahte disk / root işi açılmaz.
            before = shared_state.load()['revision']
            app.set_external_installing(True)
            assert not panel.apply_button.get_sensitive()
            panel.apply()
            assert not panel.busy and shared_state.load()['revision'] == before
            assert 'Kurulum' in panel.status.get_text()
            app.set_external_installing(False)
            assert panel.apply_button.get_sensitive()
            x11 = effects.X11()
            original_set = profiles.set_property
            directory = effects.state_directory()
            def guarded_set(channel, key, kind, value, execute):
                if channel == 'xfwm4' and key == '/general/use_compositing' and value == 'true':
                    running = effects.owned_state(directory)
                    assert not running or x11.owner() != running['owner'], 'Picom durmadan Xfwm etkinleştirildi'
                return original_set(channel, key, kind, value, execute)
            try:
                previous_effect = None; previous_pid = None
                with patch.object(profiles, 'set_property', side_effect=guarded_set):
                    for requested in ('glass', 'glass', 'aero', 'aero', 'off', 'glass', 'aero'):
                        before = shared_state.load()['revision']
                        panel.effects.set_active_id(requested); panel.motion.set_active_id('smooth'); panel.blur.set_active(False)
                        panel.apply_button.clicked()
                        assert panel.busy and app.theme_busy and not panel.apply_button.get_sensitive()
                        message = panel.status.get_text()
                        panel.apply()  # Yinelenen çağrı ayrı motor veya sahte çakışma üretmez.
                        assert panel.status.get_text() == message
                        pump(lambda: not panel.busy)
                        assert not app.theme_busy and panel.apply_button.get_sensitive(), panel.status.get_text()
                        assert shared_state.load()['revision'] == before + 1, panel.status.get_text()
                        applied = shared_state.read_json(directory / 'status.json')
                        current = effects.owned_state(directory)
                        if requested == 'aero':
                            assert applied['engine'] == 'picom' and current and x11.owner() == current['owner'], applied
                            if previous_effect == requested:
                                assert current['pid'] == previous_pid
                        elif requested == 'glass':
                            assert applied['engine'] == 'xfwm4' and not current and x11.owner() == x11.wm_owner(), applied
                        else:
                            assert applied['engine'] == 'none' and not current and effects.wait_owner(x11, 0) == 0, applied
                        previous_effect = requested; previous_pid = current['pid'] if current else None
            finally:
                x11.close()
            assert not errors, errors
            return {'shared_apply_repeated_glass_aero_off_single_compositor_handoff': True,
                    'real_welcome_gtk_busy_recovery_and_repeated_apply': True,
                    'real_welcome_installation_gate_preserved': True}
    finally:
        if app is not None and app.window is not None:
            app.window.destroy()
        sys.excepthook = original_hook


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
            wm = subprocess.Popen(['/usr/bin/xfwm4', '--compositor=on', '--vblank=off'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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
            # Gerçek xfconf + süreç değişikliği, yalnız son JSON commit arızası
            # taklittir. Başarısız yeni still reçetesi kapanıp daha önce gerçekten
            # çalışan XRender reçetesi geri açılır; ortak varsayılan tahmini yok.
            import desktop_preferences as shared
            import desktop_state as shared_state
            import profiles as shared_profiles
            from unittest.mock import patch
            def native_values():
                return {(channel, key): shared_profiles.read_property(channel, key, kind, shared_profiles.run)
                        for channel, key, kind, _value in shared_profiles.settings('oguzdows', resources=full)}
            before_native = native_values()
            before_config = shared_state.read_json(shared_state.config_path())
            before_status = shared_state.read_json(state / 'status.json')
            previous_recipe = owned.get('config', str(effects.CONFIG))
            atomic = shared_state.atomic_json
            def fail_commit(path, value):
                if Path(path) == shared_state.config_path():
                    raise OSError('CI simulated final preference commit failure')
                atomic(path, value)
            with patch.object(shared_state, 'atomic_json', side_effect=fail_commit):
                try:
                    shared.update_and_apply({'effects': 'aero', 'motion': 'reduced', 'blur': False}, full)
                except OSError:
                    pass
                else:
                    raise AssertionError('Preference commit failure was reported as success')
            restored = effects.owned_state(state)
            assert restored and restored.get('config', str(effects.CONFIG)) == previous_recipe, restored
            assert restored['pid'] != owned['pid'] and effects.identity(restored['pid']) == restored['started']
            assert native_values() == before_native
            assert shared_state.read_json(shared_state.config_path()) == before_config
            assert shared_state.read_json(state / 'status.json') == before_status
            report['real_engine_and_xfconf_rollback_after_simulated_commit_failure'] = True
            owned = restored
            # Yalnız alt motor değil, gerçek Rehber düğmesi ve meşgul kapısı.
            report.update(gtk_apply_checks(full))
            owned = effects.owned_state(state)
            assert owned
            # Gerçek xfconfd, yalnız özel/sentetik monitör anahtarları. Dosya
            # yolu işleminin yarıda hata vermesi taklittir; xfdesktop render testi değil.
            import wallpapers as shared_wallpapers
            picture = directory / 'wallpaper.png'
            from PIL import Image
            Image.new('RGB', (4, 4), '#367fbb').save(picture)
            props = [f'/backdrop/screen0/monitorCI-{name}/workspace0/last-image' for name in ('A', 'B')]
            for prop in props:
                shared_profiles.set_property('xfce4-desktop', prop, 'string', '/home/private/personal.jpg', shared_profiles.run)
                shared_profiles.set_property('xfce4-desktop', prop.removesuffix('last-image') + 'image-style', 'int', '3', shared_profiles.run)
            listing = shared_wallpapers.run(['xfconf-query', '-c', 'xfce4-desktop', '-l'])
            props = sorted(line for line in listing.stdout.splitlines() if line.startswith('/backdrop/') and line.endswith('/last-image'))
            def wallpaper_values():
                return {key: shared_profiles.read_property('xfce4-desktop', key, kind, shared_profiles.run)
                        for prop in props for key, kind in ((prop, 'string'), (prop.removesuffix('last-image') + 'image-style', 'int'))}
            original_wallpaper = wallpaper_values()
            marker = directory / 'wallpaper-selection'; marker.write_text('personal-marker\n\n')
            real_wallpaper_run = shared_wallpapers.run
            failed_native_write = False
            def fail_native_write(command):
                nonlocal failed_native_write
                result = real_wallpaper_run(command)
                if not failed_native_write and '-s' in command and command[command.index('-p') + 1] == '/backdrop/screen0/monitorCI-B/workspace0/image-style' and command[-1] == '5':
                    failed_native_write = True
                    raise OSError('CI simulated failure after real partial xfconf write')
                return result
            with patch.object(shared_wallpapers, 'run', side_effect=fail_native_write):
                try:
                    shared_wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(picture)}], marker)
                except OSError:
                    pass
                else:
                    raise AssertionError('Partial wallpaper failure was reported as success')
            assert failed_native_write and wallpaper_values() == original_wallpaper
            assert marker.read_text() == 'personal-marker\n\n'
            report['real_xfconf_wallpaper_rollback_after_simulated_partial_write_failure'] = True
            report['wallpaper_rendering_verified'] = False
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
            subprocess.run(command, env=env, check=True, timeout=90)
        finally:
            key = hashlib.sha256(env['DISPLAY'].encode()).hexdigest()[:16]
            state = home / '.local/state/oguzdows/effects' / key
            for source in (directory / 'effects.log', directory / 'effects-native.json', directory / 'effects-window.png',
                           state / 'picom.log', state / 'status.json'):
                if source.is_file(): shutil.copy2(source, output / ('picom-' + source.name if source.name in ('picom.log', 'status.json') else source.name))


if __name__ == '__main__':
    main()
