#!/usr/bin/env python3
"""Paylaşılan doğal kayıt denetimi. İstek üzerine; kurulum D-Bus kapısıyla.

Yerel uygulamalarda panel düğmesi, C mağazasında kısa ömürlü anlatım penceresi.
Metinler sabittir; sentez / mikrofon / model indirme veya boştayken tarama yok.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rifki_dialogue import PANELS
from rifki_narration_texts import TEXTS
from rifki_speech import Speaker, ready_clip
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk


def words(topic):
    return TEXTS.get(topic, PANELS.get(topic, ''))


class NarrationBar(Gtk.Box):
    def __init__(self, window, topic):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.topic = topic
        self.window = window
        self.speaker = Speaker(GLib.idle_add, self.error)
        self.group = None
        self.signals = []
        self.blocked = True
        self.gate_ready = False
        self.pending = False
        self.closed = False
        if window.get_screen().get_width() < 600:
            self.set_orientation(Gtk.Orientation.VERTICAL)
        controls = Gtk.Box(spacing=6)
        self.listen_button = Gtk.Button(label='Rıfkı’dan dinle')
        self.listen_button.connect('clicked', self.listen)
        controls.pack_start(self.listen_button, False, False, 0)
        stop = Gtk.Button.new_from_icon_name('media-playback-stop-symbolic', Gtk.IconSize.BUTTON)
        stop.set_tooltip_text('Sesi durdur')
        stop.get_accessible().set_name('Rıfkı sesini durdur')
        stop.connect('clicked', lambda *_: self.stop())
        controls.pack_start(stop, False, False, 0)
        self.sound = Gtk.Switch(active=self.speaker.enabled)
        self.sound.set_valign(Gtk.Align.CENTER)
        self.sound.set_tooltip_text('Doğal kayıt sesini aç / kapat')
        self.sound.get_accessible().set_name('Rıfkı sesi açık')
        self.sound.connect('notify::active', lambda button, _pspec: self.speaker.set_enabled(button.get_active()))
        controls.pack_start(self.sound, False, False, 0)
        self.pack_start(controls, False, False, 0)
        self.status = Gtk.Label(label='Doğal yerel kayıt', xalign=0, wrap=True, max_width_chars=36)
        self.pack_start(self.status, True, True, 0)
        self.connect('destroy', self.cleanup)
        window.connect('notify::is-active', self.focus_changed)
        self.watch = Gio.bus_watch_name(Gio.BusType.SESSION, 'org.oguzdows.HafifKurucu',
                                       Gio.BusNameWatcherFlags.NONE, self.appeared, self.vanished)
        self.refresh()

    def key(self):
        return self.topic() if callable(self.topic) else self.topic

    def refresh(self, *_):
        self.stop()
        text = words(self.key())
        self.set_tooltip_text(text)
        self.listen_button.set_sensitive(bool(text) and not self.blocked)

    def error(self, text):
        if not self.closed:
            self.status.set_text(text)

    def stop(self):
        self.pending = False
        self.speaker.stop()

    def listen(self, *_):
        if self.closed:
            return
        if self.blocked:
            self.pending = not self.gate_ready  # İlk D-Bus yanıtını bekle; kurulumda sıraya alma.
            self.status.set_text('Kurulum durumu bekleniyor.' if not self.gate_ready else 'Kurulumda ses duraklatıldı.')
            return
        self.pending = False
        text = words(self.key())
        if not self.speaker.enabled:
            self.status.set_text('Ses kapalı; yanındaki anahtarla açabilirsin.')
        elif ready_clip(text, self.speaker.assets, self.speaker.clips) is None:
            self.status.set_text('Doğal kayıt yok; açıklama yazılı kalır.')
        else:
            self.status.set_text('Rıfkı · Ekranın genel kullanım rehberi')
            self.speaker.speak(text)

    def focus_changed(self, window, *_):
        if not window.is_active():
            self.stop()

    def disconnect_group(self):
        if self.group:
            for signal in self.signals:
                self.group.disconnect(signal)
        self.group, self.signals = None, []

    def appeared(self, connection, name, _owner):
        self.disconnect_group()
        self.gate_ready = False
        self.blocked = True
        self.listen_button.set_sensitive(False)
        self.speaker.stop()
        self.group = Gio.DBusActionGroup.get(connection, name, '/org/oguzdows/HafifKurucu')
        self.signals = [self.group.connect('action-added', self.action_added),
                        self.group.connect('action-state-changed', self.state_changed)]
        self.group.list_actions()

    def action_added(self, group, name):
        if name == 'busy':
            state = group.get_action_state(name)
            if state is not None:
                self.state_changed(group, name, state)

    def state_changed(self, _group, name, state):
        if name == 'busy' and state.is_of_type(GLib.VariantType.new('b')):
            self.gate_ready = True
            self.blocked = state.get_boolean()
            self.listen_button.set_sensitive(not self.blocked and bool(words(self.key())))
            if self.blocked:
                self.stop()
                self.status.set_text('Kurulumda ses duraklatıldı.')
            elif self.pending:
                self.listen()

    def vanished(self, connection, *_):
        self.disconnect_group()
        self.gate_ready = connection is not None
        self.blocked = not self.gate_ready
        if not self.closed:
            self.listen_button.set_sensitive(self.gate_ready and bool(words(self.key())))
            if not self.gate_ready:
                self.stop()
                self.status.set_text('Kurulum durumuna ulaşılamadı; rehber yazılı kalır.')
            elif self.pending:
                self.listen()

    def cleanup(self, *_):
        if self.closed:
            return
        self.closed = True
        Gio.bus_unwatch_name(self.watch)
        self.disconnect_group()
        self.speaker.close()


class Narration(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.Anlatim', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.topic = 'store'

    def do_command_line(self, line):
        args = line.get_arguments()[1:]
        if len(args) != 1 or not words(args[0]):
            return 2
        self.topic = args[0]
        self.activate()
        return 0

    def do_activate(self):
        if self.window is None:
            self.window = Gtk.ApplicationWindow(application=self, title='Rıfkı · Ekran rehberi')
            import ui_theme
            ui_theme.setup(self.window)
            screen = self.window.get_screen()
            self.window.set_default_size(min(560, screen.get_width() - 24), min(350, screen.get_height() - 48))
            self.window.set_size_request(min(320, screen.get_width() - 24), 240)
            self.window.set_icon_name('oguzdows-rifki')
            self.window.connect('destroy', lambda *_: setattr(self, 'window', None))
            self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=18)
            self.explanation = Gtk.Label(xalign=0, wrap=True, max_width_chars=70)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.add(self.explanation)
            self.box.pack_start(scroll, True, True, 0)
            self.bar = NarrationBar(self.window, lambda: self.topic)
            self.box.pack_start(self.bar, False, False, 0)
            self.window.add(self.box)
        # Keep the selected, immutable recording rather than silently revoice it.
        # Its pre-image News wording is explicitly dated in the current UI.
        note = ('Not: Bu ses kaydı görsel desteği öncesindeki okuyucuyu anlatır. Güncel sürümde Yenile, görsel düğmesi açıksa sınırlı küçük resimler de indirir; kapalıysa yalnız metin alır.\n\n'
                if self.topic == 'news' else '')
        self.explanation.set_text(note + words(self.topic))
        self.bar.refresh()
        self.window.show_all()
        self.window.present()
        # Kullanıcı Dinle düğmesiyle bu pencereyi açıkça istedi. D-Bus kapısı
        # hazır değilse istek yalnızca ilk durum yanıtına kadar bekler.
        GLib.idle_add(self.start)

    def start(self):
        self.bar.listen()
        return GLib.SOURCE_REMOVE


if __name__ == '__main__':
    raise SystemExit(Narration().run(sys.argv))
