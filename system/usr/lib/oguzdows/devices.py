#!/usr/bin/env python3
"""Cihaz ve uyumluluk merkezi; donanıma yazmaz, servis başlatmaz."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import device_support
import compat_core
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk
from narration import NarrationBar


class Devices(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.Cihazlar')
        self.window = None

    def do_activate(self):
        if self.window is None:
            self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows Cihaz Merkezi')
            self.window.set_icon_name('oguzdows-device')
            screen = self.window.get_screen()
            self.window.set_default_size(min(760, screen.get_width() - 24), min(620, screen.get_height() - 48))
            self.window.set_size_request(320, 350)
            self.window.connect('destroy', lambda *_: setattr(self, 'window', None))
            header = Gtk.HeaderBar(title='Cihaz Merkezi' if screen.get_width() < 600 else 'Aynı masaüstü. Cihazına uygun yol.',
                                   show_close_button=True)
            self.window.set_titlebar(header)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
            report = Gtk.Label(label=device_support.summary(), xalign=0, wrap=True, max_width_chars=85)
            box.pack_start(report, False, False, 0)
            caps = compat_core.capabilities()
            status = ' · '.join(name + ': ' + ('var' if caps[key] else 'yok') for name, key in
                                (('Wine', 'wine'), ('Wine 32 bit', 'wine32'), ('Waydroid', 'waydroid'), ('Wayland', 'wayland'), ('Binder', 'binder')))
            box.pack_start(Gtk.Label(label=status, xalign=0, wrap=True, max_width_chars=85), False, False, 0)
            for title, command in (('EXE / APK incele', ['/usr/local/bin/oguzdows-open', '--manager']),
                                   ('OğuzDows Mağaza', ['/usr/local/bin/oguzdows-store']),
                                   ('Dokunmatik ekran klavyesi (kuruluysa)', ['/usr/bin/onboard']),
                                   ('Cihaz ve uyumluluk rehberi', ['/usr/bin/xdg-open', '/usr/share/doc/oguzdows/cihazlar-ve-uyumluluk.md'])):
                button = Gtk.Button(label=title)
                button.get_child().set_line_wrap(True)
                button.get_child().set_max_width_chars(28)
                button.connect('clicked', lambda _button, value=command: self.launch(value))
                box.pack_start(button, False, False, 0)
            detail = '\n\n'.join(item['name'] + '\n' + item['tier'] + '\n' + item['boot'] for item in device_support.PROFILES.values())
            text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
            text.get_buffer().set_text(detail)
            scroll = Gtk.ScrolledWindow(min_content_height=160)
            scroll.add(text)
            box.pack_start(scroll, True, True, 0)
            self.voicebar = NarrationBar(self.window, 'compatibility')
            box.pack_start(self.voicebar, False, False, 0)
            self.status = Gtk.Label(xalign=0, wrap=True)
            box.pack_start(self.status, False, False, 0)
            outer = Gtk.ScrolledWindow()
            outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            outer.add(box)
            self.window.add(outer)
            self.window.show_all()
        self.window.present()

    def launch(self, command):
        try:
            Gio.Subprocess.new(command, Gio.SubprocessFlags.NONE)
        except Exception as error:
            self.status.set_text('Program açılamadı: ' + str(error))


if __name__ == '__main__':
    raise SystemExit(Devices().run(sys.argv))
