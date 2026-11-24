#!/usr/bin/env python3
"""Masaüstü Merkezi / ortak oturum uzlaştırıcısı. Sürekli servis değildir."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_preferences as preferences
import desktop_runtime as runtime


def gui():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gio, Gtk
    from desktop_ui import PreferencesPanel, control_grid, note

    class Center(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='org.oguzdows.DesktopCenter', flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.window = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows · Masaüstü Merkezi')
            screen = self.window.get_screen()
            self.window.set_default_size(min(760, screen.get_width() - 20), min(660, screen.get_height() - 24))
            self.window.set_size_request(320, 400)
            self.window.set_icon_name('oguzdows-desktop')
            header = Gtk.HeaderBar(title='Masaüstü Merkezi', subtitle=runtime.current().upper() + ' · yerel oturum')
            header.set_show_close_button(True)
            self.window.set_titlebar(header)
            self.window.get_style_context().add_class('oguzdows-modern')
            path = Path('/usr/share/oguzdows/ui/modern.css')
            if path.is_file():
                css = Gtk.CssProvider(); css.load_from_path(str(path))
                Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            notebook = Gtk.Notebook()
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            panel = PreferencesPanel(self.window); panel.set_border_width(20)
            self.window.connect('delete-event', lambda *_: panel.busy)
            scroll.add(panel); notebook.append_page(scroll, Gtk.Label(label='Aero ve görünüm'))
            actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=20)
            actions.pack_start(note('Kabuğun kendi araçları', True), False, False, 0)
            actions.pack_start(note('GNOME: üst çubuk / Etkinlikler ve uzantı sistemi; Plasma: panel düzenleyici / gerçek plasmoid gezgini; Xfce: kendi panel eklentileri. Bir kabuğun widget’ı diğerinin sürecine yüklenmez.'), False, False, 0)
            status = note('Bir işlem seç. Eksik yerel araç varsa başka masaüstünün aracı zorla açılmaz.')
            actions.pack_start(control_grid(self.window, status), False, False, 0)
            for title, command in (('Modern Başlat menüsünü aç', '/usr/local/bin/oguzdows-hub'),
                                   ('Gerçek GNOME / Plasma oturumlarını yönet…', '/usr/local/bin/oguzdows-desktops'),
                                   ('Türkiye duvar kâğıtları…', '/usr/local/bin/oguzdows-welcome')):
                button = Gtk.Button(label=title)
                args = [command, '--wallpapers'] if command.endswith('welcome') else [command]
                def clicked(_button, argv=args):
                    Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
                button.connect('clicked', clicked)
                actions.pack_start(button, False, False, 0)
            actions.pack_start(status, False, False, 0)
            actions.pack_start(note(preferences.status()['session_note']), False, False, 0)
            actions.pack_start(note('Kısayol atamak için yerel kısayol düzenleyicide şu sabit komutlar kullanılabilir: oguzdows-hub · oguzdows-monitor · oguzdows-desktop --snap left / right / maximize / restore / minimize. Mevcut kişisel kısayollar otomatik ezilmez. Bildirimler için mevcut panelin yerel merkezi korunur.'), False, False, 0)
            scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.add(actions); notebook.append_page(scroll, Gtk.Label(label='Yerel araçlar'))
            self.window.add(notebook); self.window.show_all()
    return Center().run([sys.argv[0]])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--session', action='store_true')
    group.add_argument('--effects-session', action='store_true')
    group.add_argument('--status', action='store_true')
    group.add_argument('--restore', action='store_true')
    group.add_argument('--control', choices=tuple(runtime.ACTIONS))
    group.add_argument('--snap', choices=('left', 'right', 'maximize', 'restore', 'minimize'))
    args = parser.parse_args(argv)
    try:
        if args.status:
            result = preferences.status()
        elif args.session or args.effects_session:
            result = preferences.session()
            if args.effects_session and 'engine' not in result:
                import effects
                result = effects.reconcile()
        elif args.restore:
            result = preferences.restore()
        elif args.control:
            runtime.native_control(args.control)
            return 0
        elif args.snap:
            runtime.snap(args.snap)
            return 0
        else:
            return gui()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        print('OğuzDows masaüstü: ' + str(error), file=sys.stderr)
        if args.control or args.snap:
            try:
                import gi
                gi.require_version('Gtk', '3.0')
                from gi.repository import Gtk
                if Gtk.init_check([])[0]:
                    dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CLOSE,
                                               text='Yerel masaüstü işlemi tamamlanamadı')
                    dialog.format_secondary_text(str(error)); dialog.run(); dialog.destroy()
            except ImportError:
                pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
