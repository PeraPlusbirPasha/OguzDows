#!/usr/bin/env python3
"""İstek üzerine açılan Türkçe bakım arayüzü; pencere kapanınca daemon kalmaz."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maintenance
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk
from narration import NarrationBar

HELPER = ['/usr/bin/pkexec', '/usr/local/sbin/oguzdows-maintenance']


def text(value, style=''):
    widget = Gtk.Label(label=value, xalign=0, wrap=True)
    widget.set_max_width_chars(90)
    if style:
        widget.get_style_context().add_class(style)
    return widget


class Updater(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.Guncelleyici', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.busy = False
        self.plan = None
        self.controls = []

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if args not in ([], ['--desktop', 'kde'], ['--desktop', 'gnome']):
            return 2
        self.activate()
        if args:
            self.request.set_active_id('desktop:' + args[1])
            self.stack.set_visible_child_name('updates')
        return 0

    def do_activate(self):
        if self.window is None:
            self.build()
        self.window.present()

    def build(self):
        self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows Güncelleyici')
        import ui_theme
        ui_theme.setup(self.window)
        self.window.set_icon_name('oguzdows-update')
        self.window.set_default_size(850, 640)
        self.window.set_size_request(540, 380)
        self.window.connect('delete-event', self.closing)
        header = Gtk.HeaderBar(title='OğuzDows Güncelleyici', subtitle='Önce gör · Sonra onayla')
        header.set_show_close_button(True)
        self.window.set_titlebar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=24)
        box.pack_start(text('Güncel kal, kontrol sende kalsın.', 'heading'), False, False, 0)
        box.pack_start(text('Açılışta indirme veya otomatik kurulum yok. Uygulamalar kapalıyken denetle; paket işlemi sürerken bilgisayarı kapatma.', 'muted'), False, False, 0)
        self.stack = Gtk.Stack()
        ui_theme.configure_stack(self.window, self.stack)
        switcher = Gtk.StackSwitcher(stack=self.stack, halign=Gtk.Align.CENTER)
        box.pack_start(switcher, False, False, 0)
        self.stack.add_titled(self.updates_page(), 'updates', 'Güncellemeler')
        self.stack.add_titled(self.drivers_page(), 'drivers', 'Sürücüler')
        self.stack.add_titled(self.sources_page(), 'sources', 'Depolar ve Mağaza')
        box.pack_start(self.stack, True, True, 0)
        self.voicebar = NarrationBar(self.window, lambda: 'hardware' if self.stack.get_visible_child_name() == 'drivers' else 'store' if self.stack.get_visible_child_name() == 'sources' else 'applications')
        self.stack.connect('notify::visible-child-name', self.voicebar.refresh)
        box.pack_start(self.voicebar, False, False, 0)
        self.status = text('Hazır. Henüz ağ isteği yapılmadı.', 'muted')
        box.pack_start(self.status, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(box)
        self.window.add(scroll)
        self.window.show_all()
        self.apply_button.set_sensitive(False)

    def button(self, box, title, callback):
        button = Gtk.Button(label=title)
        button.connect('clicked', callback)
        box.pack_start(button, False, False, 0)
        self.controls.append(button)
        return button

    def updates_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        row = Gtk.Box(spacing=8)
        self.button(row, '1 · Paket listelerini yenile', lambda *_: self.backend(['refresh']))
        self.button(row, 'Mağaza', lambda *_: self.store())
        page.pack_start(row, False, False, 0)
        self.request = Gtk.ComboBoxText()
        for identifier, title in [('upgrade', 'Sistem ve APT uygulamalarını güncelle'),
                                  ('desktop:kde', 'İsteğe bağlı gerçek KDE Plasma oturumu'),
                                  ('desktop:gnome', 'İsteğe bağlı gerçek GNOME oturumu')]:
            self.request.append(identifier, title)
        self.request.set_active_id('upgrade')
        self.request.connect('changed', self.invalidate)
        self.controls.append(self.request)
        page.pack_start(self.request, False, False, 0)
        row = Gtk.Box(spacing=8)
        self.button(row, '2 · İşlem planını göster', lambda *_: self.preview(self.request.get_active_id()))
        self.apply_button = self.button(row, '3 · Planı onayla ve uygula…', self.apply)
        page.pack_start(row, False, False, 0)
        self.detail = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.detail.set_left_margin(12)
        self.detail.set_top_margin(12)
        self.detail.get_buffer().set_text('Güncellemeler burada listelenir.\n\nGerçek KDE/GNOME ek disk ve RAM kullanır; 600 MB hedefi bu oturumlar için geçerli değildir. Hafif görünüm tarzları için Rehber → Masaüstü Tarzları bölümünü kullanın.')
        scroll = Gtk.ScrolledWindow(min_content_height=190)
        scroll.add(self.detail)
        page.pack_start(scroll, True, True, 0)
        self.button(page, 'Flatpak uygulama güncellemelerini mağazada göster', lambda *_: self.store('updates'))
        return page

    def drivers_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.pack_start(text('Önce aygıtı tanı; sürücüyü zorlamayalım.', 'section-title'), False, False, 0)
        page.pack_start(text('Tabanın imzalı firmware paketleri donanım üreticisiyle eşleştirilir. Öneri, sorunun kesin firmware olduğu anlamına gelmez. Çalışan modüller sökülmez; Ubuntu/Kali çekirdek paketleri karıştırılmaz.'), False, False, 0)
        self.button(page, 'Aygıtları tara', lambda *_: self.backend(['drivers'], self.show_drivers))
        self.drivers = Gtk.ComboBoxText()
        self.controls.append(self.drivers)
        page.pack_start(self.drivers, False, False, 0)
        self.button(page, 'Seçilen firmware için plan göster', lambda *_: self.preview('driver:' + (self.drivers.get_active_id() or '')))
        self.driver_note = text('Tarama yalnızca siz başlattığınızda yapılır.')
        page.pack_start(self.driver_note, False, False, 0)
        self.button(page, 'Broadcom / eski Intel lisanslı sürücü rehberini aç', lambda *_: self.launch(['/usr/local/bin/oguzdows-welcome', '--drivers']))
        return page

    def sources_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.pack_start(text('OğuzDows · Uygulama kaynakları', 'section-title'), False, False, 0)
        page.pack_start(text('Sistem paketleri kendi imzalı taban kaynağından gelir. Yeni uygulamalar için isteğe bağlı kullanıcı Flathub’u ekleyebilirsin. Başka dağıtımların çekirdek / libc / GRUB depoları karıştırılmaz. Snap kullanılmaz.'), False, False, 0)
        self.button(page, 'OğuzDows Mağaza’yı aç', lambda *_: self.store())
        self.button(page, 'Flathub kaynağını kur / denetle…', lambda *_: self.store('setup'))
        page.pack_start(text('Mağaza yerel, derlenen GTK arayüzüdür. Otomatik başlangıç / indirme yoktur. i386 ve eski ARM cihazlarda her uygulama bulunmaz. Teknik depo kökeni ve zorunlu lisans / telif bilgileri gizlenmez.'), False, False, 0)
        self.button(page, 'Anlık bellek kullanımını ölç', self.memory)
        self.memory_label = text('600 MB hedefi: temiz açılmış, uygulamaları kapalı varsayılan Xfce oturumu. Donanım ve sürücülere göre ayrıca ölçülür.')
        page.pack_start(self.memory_label, False, False, 0)
        self.button(page, 'Çevrimdışı kullanım ve güvenlik rehberi', lambda *_: self.launch(['/usr/bin/xdg-open', '/usr/share/doc/oguzdows/masaustu-ve-bakim.md']))
        return page

    def invalidate(self, *_):
        self.plan = None
        if hasattr(self, 'apply_button'):
            self.apply_button.set_sensitive(False)

    def preview(self, request):
        self.invalidate()
        self.stack.set_visible_child_name('updates')
        self.backend(['plan', request], self.show_plan)

    def show_plan(self, result):
        self.plan = result
        summary = '\n'.join('• ' + item['package'] + ' → ' + item['version'] for item in result['changes'])
        self.detail.get_buffer().set_text((summary or 'Kurulacak / yükseltilecek paket yok.') + '\n\n' + result['note']
                                         + '\n\nAPT teknik çıktısı (özgün dilinde):\n' + result['detail'])
        self.apply_button.set_sensitive(bool(result['changes']))
        self.status.set_text(str(len(result['changes'])) + ' paketlik plan hazır; henüz kurulum yapılmadı.')

    def show_drivers(self, result):
        self.drivers.remove_all()
        for item in result['drivers']:
            self.drivers.append(item['id'], item['id'] + ' · ' + ', '.join(item['packages'])
                                + (' · firmware kurulu' if item.get('installed') else ' · firmware önerisi')
                                + (' · sürücü bağı görünmüyor' if item['unbound'] else ' · bağlı aygıt'))
        self.drivers.set_active(0)
        self.driver_note.set_text(result['note'])

    def confirm(self, title, message):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
        dialog.format_secondary_text(message)
        result = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        return result

    def apply(self, *_):
        if self.plan and self.confirm('Bu paket planı uygulansın mı?', 'İnternet ve yönetici onayı gerekir. Paket kaldırma yapılmaz. Gerçek masaüstleri ek kaynak tüketir; oturum seçimi giriş ekranındandır. İşlem sırasında bilgisayarı kapatmayın.'):
            plan = self.plan
            self.invalidate()
            self.backend(['apply', plan['request'], plan['token']])

    def memory(self, *_):
        try:
            report = maintenance.memory_report()
            self.memory_label.set_text(f"Şu an: {report['used_mb']} MB ({report['used_mib']} MiB). " + report['method']
                                       + ' Bu, boşta / fiziksel cihaz hedefinin tek başına kanıtı değildir.')
        except (OSError, ValueError) as error:
            self.memory_label.set_text(str(error))

    def backend(self, arguments, callback=None):
        if self.busy:
            return
        if arguments[0] != 'plan':
            self.invalidate()
        self.busy = True
        self.status.set_text('İşlem sürüyor… Yönetici penceresi açılabilir. Kilitleri silmeyin; bilgisayarı kapatmayın.')
        for control in self.controls:
            control.set_sensitive(False)
        def work():
            try:
                process = subprocess.run([*HELPER, *arguments], capture_output=True, text=True, errors='replace',
                                         stdin=subprocess.DEVNULL, check=False, start_new_session=True)
                try:
                    result = json.loads(process.stdout)
                except ValueError:
                    raise RuntimeError('İşlem başlatılamadı veya yönetici onayı verilmedi.\n' + process.stderr[-1500:])
                if not isinstance(result, dict):
                    raise RuntimeError('Bakım yardımcısından geçerli bir yanıt alınamadı.')
                if process.returncode or 'error' in result:
                    raise RuntimeError(result.get('error', 'İşlem başarısız.'))
                GLib.idle_add(self.finished, result, callback, None)
            except (OSError, ValueError, RuntimeError) as error:
                GLib.idle_add(self.finished, None, callback, str(error))
        threading.Thread(target=work, daemon=True).start()

    def finished(self, result, callback, error):
        self.busy = False
        for control in self.controls:
            control.set_sensitive(True)
        self.apply_button.set_sensitive(bool(self.plan and self.plan['changes']))
        if error:
            self.invalidate()
            self.status.set_text('İşlem tamamlanamadı; ayrıntılar aşağıda.')
            self.detail.get_buffer().set_text(error)
            self.stack.set_visible_child_name('updates')
        else:
            self.status.set_text(result.get('message', 'İşlem tamamlandı.'))
            if callback:
                callback(result)
        return GLib.SOURCE_REMOVE

    def launch(self, command):
        try:
            subprocess.Popen(command, start_new_session=True)
        except OSError as error:
            self.status.set_text(str(error))

    def store(self, mode='overview'):
        self.launch(['/usr/local/bin/oguzdows-store', *(['--' + mode] if mode in ('updates', 'setup') else [])])

    def closing(self, *_):
        if self.busy:
            self.status.set_text('Paket işlemi bitmeden pencereyi kapatmayın. İşlem iptal edilmedi.')
            return True
        return False


if __name__ == '__main__':
    raise SystemExit(Updater().run(sys.argv))
