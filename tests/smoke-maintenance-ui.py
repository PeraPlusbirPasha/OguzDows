#!/usr/bin/env python3
"""Gerçek GTK/xfconf; her uygulama ayrı süreç. APT/pkexec/ağ TAKLİT edilir."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk
from support import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('test-results'))
    parser.add_argument('--component', choices=('updater', 'culture', 'store'), default='updater')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not Gtk.init_check([])[0]:
        raise RuntimeError('Xvfb gerekli.')
    errors = []
    original_hook = sys.excepthook
    def error_hook(kind, value, trace):
        errors.append(str(value))
        original_hook(kind, value, trace)
    sys.excepthook = error_hook
    with tempfile.TemporaryDirectory(prefix='oguzdows-tools-ui-') as directory:
        os.environ.update(XDG_CONFIG_HOME=directory, XDG_STATE_HOME=directory, OGUZDOWS_TESTING='1')
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            'UpdateActivationEnvironment', GLib.Variant('(a{ss})', ({'XDG_CONFIG_HOME': directory, 'XDG_STATE_HOME': directory},)),
            None, Gio.DBusCallFlags.NONE, 5000, None)
        Gtk.Settings.get_default().set_property('gtk-theme-name', 'OguzDows')
        if args.component == 'updater':
            profiles = load('tools_smoke_profiles', 'system/usr/lib/oguzdows/profiles.py')
            # Gerçek komut / D-Bus xfconf; sadece geçici kullanıcı dizini.
            for name in profiles.PROFILES:
                profiles.apply(name)
                for channel, path, _kind, expected in profiles.settings(name):
                    value = profiles.read_property(channel, path, _kind, profiles.run)
                    assert value == expected, (name, path, value, expected)
            profiles.restore()
        module = load('tools_smoke_' + args.component, 'system/usr/lib/oguzdows/' + args.component + '.py')
        app = {'updater': lambda: module.Updater(), 'culture': lambda: module.Culture(),
               'store': lambda: module.Store(force_setup=True)}[args.component]()
        assert app.register(None)
        app.activate()
        assert app.window is not None and not app.busy
        calls = []
        plan = {'request': 'upgrade', 'token': 'a' * 64, 'changes': [{'package': 'firmware-realtek', 'version': '2'}],
                'note': 'Güvenli test planı; kurulum yapılmaz.', 'detail': 'Inst firmware-realtek (2 test [all])'}
        def fake_run(command, **_kwargs):
            assert args.component == 'updater' and command[:2] == module.HELPER, command
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps(plan), '')
        def no_spawn(*_args, **_kwargs):
            raise AssertionError('Bu GTK testi gerçek program / yetkili yardımcı başlatamaz.')
        loop = GLib.MainLoop()
        def screenshot(name):
            app.window.present()
            for _ in range(30):
                if not Gtk.events_pending():
                    break
                Gtk.main_iteration_do(False)
            native = app.window.get_window()
            native.process_updates(True)
            width, height = app.window.get_size()
            image = Gdk.pixbuf_get_from_window(native, 0, 0, width, height)
            assert image is not None
            image.savev(str(args.output / name), 'png', [], [])
        def start():
            try:
                assert not calls, 'Pencereyi açmak APT / ağ çalıştırmamalı'
                if args.component == 'updater':
                    assert app.plan is None and not app.apply_button.get_sensitive()
                    app.show_plan(plan)
                    assert app.apply_button.get_sensitive()
                    app.request.set_active_id('desktop:kde')
                    assert app.plan is None and not app.apply_button.get_sensitive()
                    app.show_plan(plan)
                    app.confirm = lambda *_: False
                    app.apply()
                    assert not calls, 'Onay iptalinde paket çağrısı yapılamaz'
                    app.show_drivers({'drivers': [{'id': 'realtek', 'packages': ['firmware-realtek'], 'installed': True, 'unbound': False}], 'note': 'Aygıt raporu · test'})
                    assert app.drivers.get_active_id() == 'realtek'
                    app.stack.set_visible_child_name('drivers')
                    screenshot('updater-drivers.png')
                    app.stack.set_visible_child_name('sources')
                    app.memory()
                    screenshot('updater-sources.png')
                    app.stack.set_visible_child_name('updates')
                    screenshot('updater-plan.png')
                    app.window.resize(600, 440)
                    app.backend(['plan', 'upgrade'], app.show_plan)
                    assert app.busy and app.closing()
                    GLib.timeout_add(500, finish)
                    return GLib.SOURCE_REMOVE
                if args.component == 'culture':
                    assert app.timer is None
                    app.start_timer(5)
                    assert app.timer is not None
                    app.stop_timer()
                    assert app.timer is None
                    app.editor.get_buffer().set_text('istanbul ısparta')
                    app.transform(module.core.turkish_upper)
                    buffer = app.editor.get_buffer()
                    assert buffer.get_text(*buffer.get_bounds(), True) == 'İSTANBUL ISPARTA'
                    for name in ('tea', 'text', 'backup', 'share'):
                        app.stack.set_visible_child_name(name)
                        screenshot('imece-' + name + '.png')
                    app.start_timer(5)
                    assert app.close() is False and app.timer is None
                if args.component == 'store':
                    screenshot('store-consent.png')
                    opened = []
                    app.open_store = lambda: opened.append('explicit-system-only')
                    app.only_system()
                    assert app.state.is_file() and opened == ['explicit-system-only']
                    app.done('İmza doğrulanamadı · güvenli hata testi')
                    assert app.enable.get_sensitive() and app.skip.get_sensitive()
                    screenshot('store-setup-error.png')
                close()
            except Exception as error:
                errors.append(str(error))
                loop.quit()
            return GLib.SOURCE_REMOVE
        def finish():
            if app.busy:
                return GLib.SOURCE_CONTINUE
            try:
                assert len(calls) == 1 and calls[0][2:] == ['plan', 'upgrade']
                assert app.apply_button.get_sensitive()
                screenshot('updater-small.png')
                app.finished(None, None, 'Yönetici onayı verilmedi · güvenli hata testi')
                assert not app.apply_button.get_sensitive()
                assert app.stack.get_visible_child_name() == 'updates'
                screenshot('updater-auth-cancelled.png')
                close()
            except Exception as error:
                errors.append(str(error))
                loop.quit()
            return GLib.SOURCE_REMOVE
        def close():
            assert not {'PIL', 'cairo', 'rifki_pet', 'rifki_scene'}.intersection(sys.modules)
            app.window.destroy()
            app.quit()
            loop.quit()
        def timeout():
            errors.append('GTK bakım testi 30 saniyede tamamlanmadı.')
            loop.quit()
            return GLib.SOURCE_REMOVE
        with patch.object(subprocess, 'run', side_effect=fake_run), patch.object(subprocess, 'Popen', side_effect=no_spawn):
            GLib.timeout_add(350, start)
            GLib.timeout_add_seconds(30, timeout)
            loop.run()
        (args.output / ('maintenance-ui-' + args.component + '.json')).write_text(json.dumps({'gtk': True, 'component': args.component,
            'native_xfconf_profiles': 5 if args.component == 'updater' else 0, 'apt_mocked': True,
            'package_installation_tested': False, 'network_used': False, 'errors': errors}, ensure_ascii=False, indent=2) + '\n')
    if errors:
        raise AssertionError('\n'.join(errors))
    print(args.component + ': gerçek GTK ve kullanıcı onay akışı doğrulandı. Paket kurulmadı.')


if __name__ == '__main__':
    main()
