#!/usr/bin/env python3
"""Flathub onayı ve istek üzerine mağaza; tam çıkış da açık kullanıcı kararıdır."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store_core import setup_flathub
from store_lifecycle import Visibility, X11Windows


class Store(Gtk.Application):
    def __init__(self, mode='overview', force_setup=False):
        super().__init__(application_id='org.oguzdows.Magaza', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.mode, self.force_setup = mode, force_setup
        self.window = None
        self.busy = False
        self.monitor = None
        self.watch = self.startup_timer = self.close_pending = self.recheck = None
        self.held = False
        self.visibility = Visibility()
        self.state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oguzdows/store-choice'

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if args not in ([], ['--updates'], ['--setup'], ['--quit']):
            return 2
        if args == ['--quit']:
            if not self.busy:
                self.safe_quit()
            return 0
        self.mode = 'updates' if args == ['--updates'] else 'overview'
        self.force_setup = args == ['--setup']
        self.activate()
        return 0

    @staticmethod
    def reap(process, _pid, status):
        # GLib çocuğu toplar; Popen ikinci kez waitpid / uyarı üretmesin.
        process.returncode = os.waitstatus_to_exitcode(status)
        if process.returncode or os.environ.get('OGUZDOWS_STORE_DEBUG') == '1':
            print('OğuzDows Mağaza: native alt süreç', process.pid,
                  'çıkış kodu', process.returncode, file=sys.stderr, flush=True)

    def spawn(self, arguments, **kwargs):
        process = subprocess.Popen(['/usr/bin/gnome-software', *arguments], start_new_session=True, **kwargs)
        GLib.child_watch_add(process.pid, lambda pid, status: self.reap(process, pid, status))

    def open_store(self):
        try:
            if not self.held:
                if os.environ.get('DISPLAY') and os.environ.get('XDG_SESSION_TYPE') != 'wayland':
                    try:
                        self.monitor = X11Windows()
                        self.monitor.windows()  # EWMH desteklenmiyorsa açık kontrol penceresine dön.
                    except Exception:
                        if self.monitor:
                            self.monitor.close()
                        self.monitor = None
                self.hold()
                self.held = True
                if self.monitor:
                    self.watch = GLib.io_add_watch(self.monitor.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.window_event)
                    self.startup_timer = GLib.timeout_add_seconds(90, self.not_mapped)
                else:
                    self.controller('Bu oturumda otomatik pencere kapanışı izlenemiyor. Mağazayı bitirince aşağıdan güvenle tamamen kapatın.')
            environment = dict(os.environ)
            if self.monitor:
                environment['GDK_BACKEND'] = 'x11'
            self.spawn(['--mode=' + self.mode], env=environment)
            if self.monitor:
                if self.window:
                    self.window.destroy()
                    self.window = None
                if self.recheck is None:
                    self.recheck = GLib.idle_add(self.inspect_windows)
        except OSError as error:
            self.controller('Mağaza açılamadı: ' + str(error))

    def window_event(self, _fd, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            self.watch = None
            self.stop_monitor()
            self.controller('Pencere bağlantısı kapandı. Mağazayı buradan güvenle tamamen kapatabilirsiniz.')
            return GLib.SOURCE_REMOVE
        try:
            if self.monitor.consume() and self.recheck is None:
                self.recheck = GLib.timeout_add(150, self.inspect_windows)
        except Exception:
            self.watch = None
            self.stop_monitor()
            self.controller('Pencere durumu okunamadı. Mağazayı buradan güvenle tamamen kapatabilirsiniz.')
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def inspect_windows(self):
        self.recheck = None
        try:
            windows = self.monitor.windows()
        except Exception:
            self.stop_monitor()
            self.controller('Pencere durumu doğrulanamadı. Mağazayı buradan güvenle tamamen kapatabilirsiniz.')
            return GLib.SOURCE_REMOVE
        closed = self.visibility.closed(windows)
        if windows:
            for name in ('startup_timer', 'close_pending'):
                source = getattr(self, name)
                if source is not None:
                    GLib.source_remove(source)
                    setattr(self, name, None)
        elif closed and self.close_pending is None:
            self.close_pending = GLib.timeout_add(1500, self.close_if_hidden)
        return GLib.SOURCE_REMOVE

    def close_if_hidden(self):
        self.close_pending = None
        try:
            if self.monitor and not self.monitor.windows():
                # GNOME --quit, iptal edilebilir aktif işlere de iptal gönderir.
                # Sırf pencere gizlendi diye kullanıcının indirmesini kesmeyelim.
                self.stop_monitor()
                self.controller('Mağaza penceresi kapandı. İndirme / kurulum arka planda sürüyor olabilir. İşlemlerin tamamlandığını mağazada kontrol edin; ardından tam çıkışı siz onaylayın.')
        except Exception:
            self.stop_monitor()
            self.controller('Pencere durumu doğrulanamadı; zorla kapatma yapılmadı.')
        return GLib.SOURCE_REMOVE

    def not_mapped(self):
        self.startup_timer = None
        if not self.visibility.seen:
            self.stop_monitor()
            self.controller('Mağaza penceresi 90 saniyede görülmedi. Yeniden gösterin veya güvenle tam çıkış isteyin.')
        return GLib.SOURCE_REMOVE

    def controller(self, message):
        if self.window:
            self.window.destroy()
        self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows Mağaza · Güvenli çıkış')
        self.window.set_default_size(500, 240)
        self.window.connect('delete-event', self.confirm_quit)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin=24)
        self.message = Gtk.Label(label=message + '\n\nTam çıkış, GNOME Yazılımlar’ın kendi kapatma/temizleme akışıdır; iptal edilebilir işleri durdurabilir. İşlemler bitmeden onaylamayın. Süreç zorla öldürülmez.', wrap=True, xalign=0, max_width_chars=62)
        box.pack_start(self.message, True, True, 0)
        for title, callback in (('Mağazayı yeniden göster', lambda *_: self.open_store()),
                                ('İşlemler bitti · Mağazayı tamamen kapat', lambda *_: self.safe_quit())):
            button = Gtk.Button(label=title)
            button.connect('clicked', callback)
            box.pack_start(button, False, False, 0)
        self.window.add(box)
        self.window.show_all()

    def confirm_quit(self, *_):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL, text='Mağazadaki bütün işlemler tamamlandı mı?')
        dialog.format_secondary_text('Tam çıkış, iptal edilebilir indirme / işlemleri durdurabilir. Kurulumların bittiğini kontrol ettikten sonra onaylayın.')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        approved = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if approved:
            self.safe_quit()
        return True

    def safe_quit(self):
        try:
            # Yalnızca açık tamamlandı düğmesi / --quit / onaylı kapatma.
            # GNOME'un iptal ve temizleme protokolü; SIGTERM/SIGKILL yok.
            self.spawn(['--quit'])
        except OSError as error:
            self.controller('Tam çıkış isteği gönderilemedi: ' + str(error))
            return
        self.stop_monitor()
        if self.window:
            self.window.destroy()
            self.window = None
        self.quit()

    def stop_monitor(self):
        for name in ('watch', 'startup_timer', 'close_pending', 'recheck'):
            source = getattr(self, name)
            if source is not None:
                GLib.source_remove(source)
                setattr(self, name, None)
        if self.monitor:
            self.monitor.close()
            self.monitor = None

    def do_shutdown(self):
        self.stop_monitor()
        if self.held:
            self.release()
            self.held = False
        Gtk.Application.do_shutdown(self)

    def remember(self):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text('asked\n')

    def do_activate(self):
        if self.state.exists() and not self.force_setup:
            self.open_store()
            return
        if self.window:
            self.window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows Mağaza')
        self.window.set_icon_name('oguzdows-store')
        self.window.set_default_size(540, 320)
        self.window.connect('delete-event', lambda *_: self.busy)
        header = Gtk.HeaderBar(title='Mağazan hazır', subtitle='GNOME Yazılımlar · Sistem + Flatpak')
        header.set_show_close_button(True)
        self.window.set_titlebar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin=24)
        self.message = Gtk.Label(xalign=0, wrap=True, max_width_chars=66,
            label='Sistem uygulamaları zaten kullanılabilir. Flathub’u da eklemek ister misin? Kaynak yalnızca hesabına eklenir; imza anahtarı resmî HTTPS tanımından alınır. Bu, ayrı bir bağımsız anahtar doğrulaması değildir. Uygulamaların izinlerini mağazada incele.\n\nMağaza açılışta başlatılmaz; otomatik güncelleme indirmesi varsayılan kapalıdır. i386 / eski ARM cihazlarda Flathub desteği varsayılmaz.')
        box.pack_start(self.message, True, True, 0)
        self.enable = Gtk.Button(label='Flathub’u ekle ve mağazayı aç')
        self.enable.connect('clicked', self.setup)
        box.pack_start(self.enable, False, False, 0)
        self.skip = Gtk.Button(label='Yalnızca sistem uygulamalarıyla devam et')
        self.skip.connect('clicked', self.only_system)
        box.pack_start(self.skip, False, False, 0)
        self.window.add(box)
        self.window.show_all()

    def only_system(self, *_):
        try:
            self.remember()
            self.open_store()
        except OSError as error:
            self.message.set_text(str(error))

    def setup(self, *_):
        if self.busy:
            return
        self.busy = True
        self.enable.set_sensitive(False)
        self.skip.set_sensitive(False)
        self.message.set_text('Mimari ve kaynak denetleniyor… Flathub HTTPS tanımı alınıyor. Hiçbir uygulama kurulmaz.')
        def work():
            try:
                setup_flathub()
                self.remember()
                GLib.idle_add(self.done, None)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                GLib.idle_add(self.done, str(error))
        threading.Thread(target=work, daemon=True).start()

    def done(self, error):
        self.busy = False
        if error:
            self.message.set_text(error + '\n\nSistem uygulamalarıyla devam edebilirsin. Daha sonra Güncelleyici → Depolar bölümünden yeniden deneyebilirsin.')
            self.enable.set_sensitive(True)
            self.skip.set_sensitive(True)
        else:
            self.open_store()
        return GLib.SOURCE_REMOVE


if __name__ == '__main__':
    if sys.argv[1:] not in ([], ['--updates'], ['--setup'], ['--quit']):
        raise SystemExit('Kullanım: oguzdows-store [--updates|--setup|--quit]')
    raise SystemExit(Store().run(sys.argv))
