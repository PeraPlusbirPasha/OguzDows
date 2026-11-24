#!/usr/bin/env python3
"""Yeni yerel araçlar, gerçek GTK/GSettings/KConfig. Yalnız özel CI hesabı.

Bu bir kurulu OS, GNOME/KWin kompozitör veya fiziksel cihaz testi DEĞİLDİR.
Ağ kullanmaz, paket kurmaz, host kullanıcısının evine / paneline yazmaz.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from support import ROOT


def pump(predicate, seconds=4):
    from gi.repository import GLib
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while GLib.MainContext.default().iteration(False): pass
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('GTK işlemi süre sınırında tamamlanmadı')


def child(directory, binaries, appearance):
    home = Path(os.environ.get('HOME', '/')).resolve()
    if (os.getuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            or directory.parent != Path(tempfile.gettempdir()) or not directory.name.startswith('oguzdows-desktop-ci-')
            or home != directory / 'home' or home.is_symlink()):
        raise ValueError('Yalnız tek kullanımlık, normal kullanıcılı CI evi kabul edilir.')
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gio, Gtk
    import desktop_state as state
    import desktop_gnome as gnome
    import desktop_plasma as plasma
    import desktop_runtime as runtime
    from desktop_ui import PreferencesPanel
    from resource_policy import policy
    state.atomic_json(state.config_path(), {**state.DEFAULTS, 'appearance': appearance})
    report = {'scope': 'host-private-nonroot-real-GTK-GSettings-KConfig', 'physical_device': False,
              'compositor_rendering_verified': False, 'performance_benchmark': False}
    provider = Gtk.CssProvider(); provider.load_from_path(str(ROOT / 'system/usr/share/oguzdows/ui/modern.css'))
    for target in ('monitor', 'hub'):
        subprocess.run([str(binaries / (target + '-test')), '--smoke-test', str(directory)],
                       check=True, timeout=20, env={**os.environ, 'G_DEBUG': 'fatal-warnings'})
        data = json.loads((directory / (target + '.json')).read_text())
        assert data['native'] is True, data
        from PIL import Image
        with Image.open(directory / (target + '.png')) as image:
            assert image.width <= Gdk.Screen.get_default().get_width(), (target, image.size)
            assert image.height <= Gdk.Screen.get_default().get_height(), (target, image.size)
            data['window_size'] = list(image.size)
        report[target] = data
    # Gerçek bellek GSettings arka ucu: başka uzantı üyelikleri korunur.
    shell = Gio.Settings.new('org.gnome.shell')
    shell.set_strv('enabled-extensions', ['another-extension@example.test'])
    gsettings = gnome.GnomeSettings()
    journal = state.Journal(gsettings, directory)
    changes = gnome.changes({**state.DEFAULTS, 'appearance': 'dark', 'effects': 'aero', 'blur': True}, policy(8388608), gsettings)
    journal.apply(changes)
    assert set(shell.get_strv('enabled-extensions')) == {'another-extension@example.test', gnome.UUID}
    gsettings.write('gtk-theme', 'PersonalAfterOguzDows')
    preserved = journal.restore()
    assert 'gtk-theme' in preserved
    assert gsettings.read('gtk-theme') == 'PersonalAfterOguzDows'
    assert shell.get_strv('enabled-extensions') == ['another-extension@example.test']
    report['real_gsettings_compare_restore'] = True
    report['gnome_extension_not_run'] = True
    # Gerçek KConfig5/6 araçları. Bildirim a{saay} imzası da gerçek session
    # bus'a gönderilir; Shell / KWin başlatıldığı iddia edilmez.
    backend = plasma.PlasmaSettings()
    journal = state.Journal(backend, directory)
    preferences = {**state.DEFAULTS, 'appearance': 'dark', 'accent': '#74c8d5'}
    changes = {**plasma.palette(preferences), **plasma.changes(preferences, policy(524288), backend.major)}
    journal.apply(changes); plasma.notify_settings()
    assert backend.read('color-scheme') == 'BreezeDark'
    assert backend.read('palette:Selection:BackgroundNormal') == '116,200,213'
    assert backend.read('blur') == 'false'
    backend.write('palette:Window:BackgroundNormal', '11,22,33')
    preserved = journal.restore(); plasma.notify_settings()
    assert preserved == ['palette:Window:BackgroundNormal'], preserved
    assert backend.read('palette:Window:BackgroundNormal') == '11,22,33'
    report['real_kconfig_compare_restore'] = True; report['kconfig_major'] = backend.major
    assert runtime.installation_busy() is False
    # Zaman aşımı da busy'yi bırakmalı; normal GTK thread'i bloklanmaz.
    record = []
    window = Gtk.Window(title='OğuzDows · Yerel Aero tercihleri')
    screen = window.get_screen(); width = screen.get_width()
    window.set_default_size(min(740, width - 20), min(680, screen.get_height() - 24))
    window.get_style_context().add_class('oguzdows-modern')
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    panel = PreferencesPanel(window, on_busy=record.append); panel.set_border_width(14)
    scroll.add(panel); window.add(scroll); window.show_all()
    panel.work(lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired('fixture', 1)))
    pump(lambda: not panel.busy)
    assert record == [True, False], record
    assert 'tamamlanamadı' in panel.status.get_text()
    assert panel.apply_button.get_sensitive()
    with patch('desktop_ui.threading.Thread.start', side_effect=RuntimeError('CI thread start failed')):
        panel.work(lambda: {'message': 'başlamamalı'})
    assert not panel.busy and record == [True, False, True, False]
    assert 'CI thread start failed' in panel.status.get_text()
    panel.work(lambda: (_ for _ in ()).throw(KeyError('CI unexpected backend error')))
    pump(lambda: not panel.busy)
    assert record == [True, False] * 3
    assert 'CI unexpected backend error' in panel.status.get_text()
    panel.allowed = lambda: False
    panel.work(lambda: (_ for _ in ()).throw(AssertionError('installer gate ignored')))
    assert not panel.busy and record == [True, False] * 3
    pump(lambda: window.get_allocated_width() > 0)
    assert window.get_allocated_width() <= width, (window.get_allocated_width(), width)
    surface = window.get_window()
    image = Gdk.pixbuf_get_from_window(surface, 0, 0, surface.get_width(), surface.get_height())
    assert image is not None
    image.savev(str(directory / 'preferences.png'), 'png', [], [])
    release = threading.Event()
    panel.allowed = lambda: True
    panel.work(lambda: (release.wait(5), {'message': 'CI completed after close'})[1])
    window.destroy(); release.set()
    pump(lambda: not panel.busy)
    assert record == [True, False] * 4
    panel.work(lambda: (_ for _ in ()).throw(AssertionError('closed panel started worker')))
    assert record == [True, False] * 4
    report['preferences_gtk_timeout_recovery_and_install_gate'] = True
    report['worker_start_unexpected_error_and_destroy_recovery'] = True
    report['preferences_fits_screen'] = width
    (directory / 'desktop-native.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Gerçek yerel GTK ve ayar API sonucu::' + json.dumps(report, ensure_ascii=False).replace('%', '%25'), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binaries', type=Path, required=True)
    parser.add_argument('--appearance', choices=('light', 'dark'), default='light')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true':
        parser.error('Yalnız tek kullanımlık CI / özel Xvfb ekranı.')
    if args.child:
        child(args.child, args.binaries.resolve(), args.appearance); return
    if args.output is None or not os.environ.get('XAUTHORITY'):
        parser.error('--output ve xvfb-run tarafından oluşturulan özel Xauthority gerekli.')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-desktop-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'; home.mkdir(mode=0o700)
        (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key != 'DBUS_SESSION_BUS_ADDRESS'}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
            XDG_STATE_HOME=str(home / '.local/state'), XDG_DATA_HOME=str(home / '.local/share'),
            XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='GNOME',
            XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                   '--child', str(directory), '--binaries', str(args.binaries.resolve()), '--appearance', args.appearance]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try:
            subprocess.run(command, env=env, check=True, timeout=90)
        finally:
            for name in ('desktop-native.json', 'monitor.json', 'hub.json', 'monitor.png', 'hub.png', 'preferences.png'):
                source = directory / name
                if source.is_file(): shutil.copy2(source, output / name)


if __name__ == '__main__':
    main()
