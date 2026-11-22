#!/usr/bin/env python3
"""Düşük RAM girişinde tam rehber / donanım taramasını istek üzerine yükler."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_policy import current_policy


def full(arguments):
    os.execv('/usr/bin/python3', ['/usr/bin/python3', '-I', '/usr/lib/oguzdows/welcome.py', *arguments])


def main():
    arguments = sys.argv[1:]
    if arguments != ['--autostart'] or current_policy()['profile'] not in ('mini', 'light'):
        full(arguments)
        return
    # Tam rehberin ilk çalıştırma tercihi ayrı kalır. Kısayollar / tüm özellikler
    # hâlâ erişilebilir; yalnızca otomatik açılışta iki büyük pencere yüklenmez.
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oguzdows'
    import welcome_model
    from pi_support import is_pi
    from hardware import is_live
    context = welcome_model.context(live=is_live(), pi=is_pi())
    light_state = state / context.light_state_name
    if light_state.is_file() or (state / context.state_name).is_file():
        return
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    window = Gtk.Window(title='OğuzDows · Hafif başlangıç', border_width=18)
    window.set_default_size(min(380, window.get_screen().get_width() - 24), 180)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    note = Gtk.Label(label='Hoş geldin! Düşük RAM için rehber ve donanım taraması yalnızca istediğinde yüklenir.\n\nBaşlat → OğuzDows Rehberi içinde tarzlar, Rıfkı, sesli paneller ve tüm araçlar yerinde.', wrap=True, xalign=0)
    note.set_max_width_chars(42)
    box.pack_start(note, True, True, 0)
    button = Gtk.Button(label='Tam rehberi ve sesli panelleri aç')
    button.connect('clicked', lambda *_: full([]))
    box.pack_start(button, False, False, 0)
    if context.offers_installer:
        install = Gtk.Button(label='Kurucuyu doğrudan aç')
        install.connect('clicked', lambda *_: os.execv('/usr/local/bin/oguzdows-install', ['/usr/local/bin/oguzdows-install']))
        box.pack_start(install, False, False, 0)
    from gi.repository import GLib
    def narrate(*_):
        try:
            pid, _in, _out, _err = GLib.spawn_async(
                ['/usr/local/bin/oguzdows-narrate', 'welcome'],
                flags=GLib.SpawnFlags.DO_NOT_REAP_CHILD)
            GLib.child_watch_add(pid, lambda child, _status: GLib.spawn_close_pid(child))
        except (OSError, GLib.Error) as error:
            note.set_text('Ses açılamadı: ' + str(error))
    voice = Gtk.Button(label='Karşılama sesini dinle')
    voice.connect('clicked', narrate)
    box.pack_start(voice, False, False, 0)
    close = Gtk.Button(label='Masaüstüne devam et')
    close.connect('clicked', lambda *_: window.close())
    box.pack_start(close, False, False, 0)
    def finish(*_):
        try:
            state.mkdir(parents=True, exist_ok=True)
            light_state.write_text('1\n')
        except OSError:
            pass
        Gtk.main_quit()
    window.connect('destroy', finish)
    for widget in box.get_children():
        if isinstance(widget, Gtk.Button):
            widget.get_child().set_line_wrap(True)
    window.add(box)
    # Xfce WM ilk pencereyi yönetene kadar tam rehberi çalıştırmayız; ufak GTK
    # pencere tek seferliktir ve kapanınca süreç kalmaz. Animasyon / tarama yok.
    Gtk.Settings.get_default().set_property('gtk-enable-animations', False)
    window.show_all()
    GLib.set_application_name('OğuzDows Hafif Başlangıç')
    Gtk.main()


if __name__ == '__main__':
    main()
