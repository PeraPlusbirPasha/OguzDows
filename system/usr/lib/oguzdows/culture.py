#!/usr/bin/env python3
"""Çay Molası, Türkçe Hızlı Yazım, Heybe ve İmece — yalnızca istek üzerine."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import culture_core as core
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk
from narration import NarrationBar


def label(value):
    return Gtk.Label(label=value, xalign=0, wrap=True, max_width_chars=80)


class Culture(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.Imece')
        self.window = None
        self.timer = None
        self.remaining = 0
        self.busy = False

    def do_activate(self):
        if self.window is None:
            self.build()
        self.window.present()

    def build(self):
        self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows · İmece')
        self.window.set_icon_name('oguzdows-imece')
        self.window.set_default_size(760, 560)
        self.window.connect('delete-event', self.close)
        header = Gtk.HeaderBar(title='İmece', subtitle='Küçük araçlar · Büyük kolaylık')
        header.set_show_close_button(True)
        self.window.set_titlebar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin=24)
        self.stack = stack = Gtk.Stack()
        box.pack_start(Gtk.StackSwitcher(stack=stack), False, False, 0)
        for title, identifier, factory in [('Çay Molası', 'tea', self.tea_page), ('Türkçe Yazım', 'text', self.text_page),
                                           ('Heybe', 'backup', self.backup_page), ('İmece Paketi', 'share', self.share_page)]:
            stack.add_titled(factory(), identifier, title)
        box.pack_start(stack, True, True, 0)
        self.voicebar = NarrationBar(self.window, 'culture')
        stack.connect('notify::visible-child-name', self.voicebar.refresh)
        box.pack_start(self.voicebar, False, False, 0)
        self.status = label('Çevrimdışı. Dosyalar kendiliğinden taranmaz; ağda paylaşım servisi açılmaz.')
        box.pack_start(self.status, False, False, 0)
        self.window.add(box)
        self.window.show_all()

    def button(self, box, title, callback):
        button = Gtk.Button(label=title)
        button.connect('clicked', callback)
        box.pack_start(button, False, False, 0)
        return button

    def tea_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.pack_start(label('Bir nefes, bir ince belli çay. Zamanlayıcıyı sen başlatırsın; pencere kapanınca durur.'), False, False, 0)
        self.clock = label('Hazır · Arka planda zamanlayıcı yok')
        self.clock.get_style_context().add_class('heading')
        box.pack_start(self.clock, False, False, 0)
        self.button(box, '25 dakika odaklan', lambda *_: self.start_timer(25))
        self.button(box, '5 dakika çay molası', lambda *_: self.start_timer(5))
        self.button(box, 'Zamanlayıcıyı durdur', lambda *_: self.stop_timer())
        return box

    def start_timer(self, minutes):
        self.stop_timer()
        self.remaining = minutes * 60
        self.clock.set_text(f'{minutes:02}:00')
        self.timer = GLib.timeout_add_seconds(1, self.tick)

    def tick(self):
        self.remaining -= 1
        self.clock.set_text(f'{self.remaining // 60:02}:{self.remaining % 60:02}')
        if self.remaining <= 0:
            self.timer = None
            self.clock.set_text('Vakit doldu · Ellerine sağlık!')
            self.send_notification('tea', Gio.Notification.new('Çay Molası · Vakit doldu. Ellerine sağlık!'))
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def stop_timer(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        if hasattr(self, 'clock'):
            self.clock.set_text('Hazır · Arka planda zamanlayıcı yok')

    def text_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.pack_start(label('I / ı ve İ / i ayrımını koruyan Türkçe dönüşüm. Panonu veya yazdığın tuşları dinlemez.'), False, False, 0)
        self.editor = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll = Gtk.ScrolledWindow(min_content_height=180)
        scroll.add(self.editor)
        box.pack_start(scroll, True, True, 0)
        row = Gtk.Box(spacing=8)
        self.button(row, 'BÜYÜK HARF', lambda *_: self.transform(core.turkish_upper))
        self.button(row, 'küçük harf', lambda *_: self.transform(core.turkish_lower))
        self.button(row, 'Panoya kopyala', self.copy_text)
        box.pack_start(row, False, False, 0)
        letters = Gtk.Box(spacing=4)
        for letter in 'çğıöşüÇĞİÖŞÜ':
            self.button(letters, letter, lambda _button, value=letter: self.editor.get_buffer().insert_at_cursor(value))
        box.pack_start(letters, False, False, 0)
        self.button(box, 'Kibar ileti şablonu ekle', lambda *_: self.editor.get_buffer().insert_at_cursor('Merhaba,\n\n\nİlginiz için teşekkür ederim.\nİyi çalışmalar.\n'))
        return box

    def transform(self, function):
        buffer = self.editor.get_buffer()
        buffer.set_text(function(buffer.get_text(*buffer.get_bounds(), True)))

    def copy_text(self, *_):
        buffer = self.editor.get_buffer()
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(buffer.get_text(*buffer.get_bounds(), True), -1)
        self.status.set_text('Yalnızca bu metin panoya kopyalandı.')

    def backup_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.pack_start(label('Heybe · Belgelerini yanına al.'), False, False, 0)
        box.pack_start(label('Bir klasörü seç, tercihen başka bir diske .tar.gz yedeği ve SHA-256 doğrulama dosyası oluştur. Kaynak silinmez. Gizli dosyalar, bilinen anahtar dizinleri ve sembolik bağlantılar dışlanır. Şifreleme yoktur; hassas içeriği sen gözden geçir. Tek işlem sınırı 2 GiB.'), False, False, 0)
        self.button(box, 'Klasör seç ve Heybe’ye koy…', self.backup)
        return box

    def share_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.pack_start(label('İmece · Birlikte üretelim.'), False, False, 0)
        box.pack_start(label('Seçtiğin en fazla 100 dosyayı taşınabilir ZIP paketine koyar; her dosyanın SHA-256 özeti eklenir. Sunucu açılmaz, otomatik gönderim yapılmaz. Paylaşmadan önce içeriği sen kontrol et. Şifreleme yoktur; sınır 2 GiB.'), False, False, 0)
        self.button(box, 'Dosyaları seç ve paylaşım paketi oluştur…', self.share)
        return box

    def choose(self, title, folders=False, multiple=False):
        dialog = Gtk.FileChooserDialog(title=title, transient_for=self.window,
                                       action=Gtk.FileChooserAction.SELECT_FOLDER if folders else Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Vazgeç', Gtk.ResponseType.CANCEL, 'Seç', Gtk.ResponseType.OK)
        dialog.set_select_multiple(multiple)
        result = dialog.get_filenames() if dialog.run() == Gtk.ResponseType.OK else []
        dialog.destroy()
        return result

    def backup(self, *_):
        if self.busy:
            return
        source = self.choose('Heybe · Kaynak klasör', folders=True)
        target = self.choose('Heybe · Başka bir diskte hedef klasör', folders=True) if source else []
        if target:
            self.work(lambda: core.heybe(Path(source[0]), Path(target[0])))

    def share(self, *_):
        if self.busy:
            return
        files = self.choose('İmece · Paylaşılacak dosyalar', multiple=True)
        target = self.choose('İmece · Paketin kaydedileceği klasör', folders=True) if files else []
        if target:
            self.work(lambda: core.imece([Path(item) for item in files], Path(target[0])))

    def work(self, function):
        self.busy = True
        self.status.set_text('Yerel paket hazırlanıyor… Kaynak dosyalar silinmez. Pencereyi kapatmayın.')
        def task():
            try:
                message = 'Hazır: ' + str(function()) + ' · SHA-256 dosyası yanında.'
            except (OSError, ValueError, RuntimeError) as error:
                message = 'Tamamlanamadı: ' + str(error)
            GLib.idle_add(self.finished, message)
        threading.Thread(target=task, daemon=True).start()

    def finished(self, message):
        self.busy = False
        self.status.set_text(message)
        return GLib.SOURCE_REMOVE

    def close(self, *_):
        if self.busy:
            self.status.set_text('Dosya işlemi sürüyor; bitmesini bekleyin.')
            return True
        self.stop_timer()
        return False


if __name__ == '__main__':
    raise SystemExit(Culture().run(sys.argv))
