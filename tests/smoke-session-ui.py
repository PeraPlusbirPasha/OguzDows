#!/usr/bin/env python3
"""Gerçek GTK başlangıç / gerçek oturum seçici arayüzü; APT ve AS taklittir."""
import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from support import ROOT, load
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=('desktops', 'light'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not Gtk.init_check()[0]:
        raise RuntimeError('Özel Xvfb ekranı gerekli.')
    errors = []
    calls = []
    original = sys.excepthook
    def exception(kind, value, trace):
        errors.append(str(value))
        original(kind, value, trace)
    sys.excepthook = exception
    # Yeni CSS gerçekten GTK tarafından ayrıştırılır; tema adı varlığı yetmez.
    for name in ('OguzDowsAero', 'OguzDowsAeroDark', 'OguzDowsEleven', 'OguzDowsElevenDark'):
        provider = Gtk.CssProvider()
        provider.load_from_path(str(ROOT / 'system/usr/share/themes' / name / 'gtk-3.0/gtk.css'))
    with tempfile.TemporaryDirectory(prefix='oguzdows-session-ui-') as temporary:
        os.environ.update(XDG_STATE_HOME=temporary, XDG_CONFIG_HOME=temporary, OGUZDOWS_TESTING='1')
        def no_spawn(*_args, **_kwargs):
            raise AssertionError('Arayüz testi gerçek yardımcı / uygulama / ağ başlatamaz.')
        if args.component == 'light':
            module = load('session_light_ui', 'system/usr/lib/oguzdows/welcome_start.py')
            def inspect():
                try:
                    windows = [window for window in Gtk.Window.list_toplevels() if window.get_visible()]
                    assert len(windows) == 1
                    buttons = [widget for widget in windows[0].get_child().get_children() if isinstance(widget, Gtk.Button)]
                    assert 'welcome' not in sys.modules and 'PIL' not in sys.modules
                    next(button for button in buttons if button.get_label().startswith('Tam rehberi')).clicked()
                    assert calls == [[]], calls
                    windows[0].close()
                except Exception as error:
                    errors.append(str(error))
                    Gtk.main_quit()
                return GLib.SOURCE_REMOVE
            GLib.timeout_add(400, inspect)
            GLib.timeout_add_seconds(10, lambda: errors.append('Hafif pencere kapanmadı') or Gtk.main_quit())
            with patch('sys.argv', ['welcome', '--autostart']), patch.object(module, 'current_policy', return_value={'profile': 'mini'}), \
                    patch.object(module, 'full', side_effect=calls.append), patch('pi_support.is_pi', return_value=False), \
                    patch('hardware.is_live', return_value=False), patch.object(subprocess, 'Popen', side_effect=no_spawn):
                module.main()
            assert (Path(temporary) / 'oguzdows/light-start-installed-seen').is_file()
        else:
            module = load('session_desktops_ui', 'system/usr/lib/oguzdows/desktops.py')
            loop = GLib.MainLoop()
            plan = {'request': 'desktop:kde', 'token': 'a' * 64, 'changes': [{'package': 'plasma-desktop', 'version': '1'}],
                    'detail': 'Test planı: gerçek paket kurulmaz.', 'note': 'İmzalı kaynak taklidi.'}
            def execute(command, **_kwargs):
                assert command[:2] == module.HELPER
                calls.append(command[2:])
                return subprocess.CompletedProcess(command, 0, json.dumps(plan if command[2] == 'plan' else {'message': 'Test işlemi tamamlandı.'}), '')
            chosen = []
            with patch.object(module.maintenance, 'build_desktop_info', return_value={'arch': 'arm64', 'suite': 'bookworm'}), \
                    patch.object(module, 'current_policy', return_value={'memory_kib': 4194304, 'legacy_cpu': False}), \
                    patch.object(module.desktop_sessions, 'select', side_effect=chosen.append), \
                    patch.object(subprocess, 'run', side_effect=execute), patch.object(subprocess, 'Popen', side_effect=no_spawn):
                app = module.Desktops()
                app.register(None)
                app.activate()
                assert not calls and app.plan is None
                app.choice.set_active_id('kde')
                app.confirm = lambda *_: False
                app.select()
                assert not chosen and not calls
                app.preview()
                stage = [0]
                def check():
                    if app.busy:
                        return GLib.SOURCE_CONTINUE
                    try:
                        if stage[0] == 0:
                            assert app.plan == plan and calls == [['plan', 'desktop:kde']]
                            app.apply()  # Vazgeç; yeni çağrı yok.
                            assert len(calls) == 1
                            app.confirm = lambda *_: True
                            app.apply()
                            stage[0] = 1
                            return GLib.SOURCE_CONTINUE
                        if stage[0] == 1:
                            assert calls[-1] == ['apply', 'desktop:kde', 'a' * 64]
                            app.select()
                            stage[0] = 2
                            return GLib.SOURCE_CONTINUE
                        assert chosen == ['kde']
                        app.window.destroy()
                        app.quit()
                        loop.quit()
                    except Exception as error:
                        errors.append(str(error))
                        loop.quit()
                    return GLib.SOURCE_REMOVE
                GLib.timeout_add(150, check)
                GLib.timeout_add_seconds(10, lambda: errors.append('Oturum arayüzü testi bitmedi') or loop.quit())
                loop.run()
    sys.excepthook = original
    report = {'component': args.component, 'gtk': True, 'new_themes_parsed': 4,
              'apt_and_accountsservice_mocked': True, 'physical_boot': False, 'performance_claim': False,
              'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'errors': errors}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / ('session-ui-' + args.component + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Oturum GTK ' + args.component + '::' + json.dumps(report, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
