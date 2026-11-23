#!/usr/bin/env python3
"""EXE / APK açma kapısı: incele → riskleri onayla → koşullu çalıştır."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compat_core as core
import device_support
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk
from narration import NarrationBar


class Compatibility(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.Uyumluluk', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.busy = False
        self.receipt = None
        self.caps = None
        self.staged = None
        self.data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'oguzdows/compatibility'

    def do_command_line(self, line):
        args = line.get_arguments()[1:]
        if args[:1] == ['--']:
            args = args[1:]
        if len(args) > 1 or args and args[0].startswith('-') and args[0] != '--manager':
            return 2
        self.activate()
        if args and args != ['--manager']:
            file = Gio.File.new_for_commandline_arg(args[0])
            if not file.is_native():
                self.status.set_text('Önce dosyayı cihazına indir. URL veya uzak dosya otomatik açılmaz.')
            else:
                self.inspect(file.get_path())
        return 0

    def do_activate(self):
        if self.window is None:
            self.build()
        self.window.present()

    def build(self):
        self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows Uyumluluk')
        self.window.set_icon_name('oguzdows-compatibility')
        screen = self.window.get_screen()
        phone = device_support.current()['phone'] or screen.get_width() < 600
        self.window.set_default_size(min(740, screen.get_width() - 24), min(640, screen.get_height() - 48))
        self.window.set_size_request(320 if phone else 460, 350)
        self.window.connect('delete-event', self.close_requested)
        self.window.connect('destroy', lambda *_: setattr(self, 'window', None))
        header = Gtk.HeaderBar(title='Uyumluluk' if phone else 'Önce tanı. Sonra karar ver.',
                               subtitle='EXE / APK' if phone else 'EXE · Wine  /  APK · Waydroid')
        header.set_show_close_button(True)
        self.window.set_titlebar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
        note = Gtk.Label(label='Bir dosyaya çift tıklamak onu doğrudan çalıştırmaz. Kaynağını ve izinlerini incele. Wine bir güvenlik alanı değildir; Windows yazılımı ev dosyalarına ve ağa erişebilir. Waydroid de APK’nın zararsız olduğu garantisi değildir.', xalign=0, wrap=True, max_width_chars=80)
        box.pack_start(note, False, False, 0)
        self.pick_button = Gtk.Button(label='EXE veya APK seç…')
        self.pick_button.connect('clicked', self.choose)
        box.pack_start(self.pick_button, False, False, 0)
        self.detail = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.detail.set_left_margin(10)
        self.detail.set_right_margin(10)
        self.detail.set_top_margin(10)
        self.detail.get_buffer().set_text('Henüz dosya seçilmedi. İnceleme paket kurmaz, dosyayı çalıştırmaz veya başka yere yüklemez.\n\nEXE: yalnızca uygun x86 PC + kurulu Wine. 32-bit desteği ayrıca gerekir.\nAPK: uygun 64-bit cihaz + çalışan Wayland / binder / hazırlanmış Waydroid gerekir.\n\nPi Zero ve eski düşük bellekli ARM cihazlara Windows / Android uyumluluğu vaat edilmez.')
        scroll = Gtk.ScrolledWindow(min_content_height=210)
        scroll.add(self.detail)
        box.pack_start(scroll, True, True, 0)
        self.ack = Gtk.CheckButton(label='Kaynağına güveniyorum; bu dosyayı kendi hesabımda çalıştırmanın riskini anladım.')
        self.ack.get_child().set_line_wrap(True)
        self.ack.connect('toggled', self.update_action)
        box.pack_start(self.ack, False, False, 0)
        self.run_button = Gtk.Button(label='İncelemeden çalıştırma yok')
        self.run_button.get_child().set_line_wrap(True)
        self.run_button.get_child().set_max_width_chars(26 if phone else 50)
        self.run_button.set_sensitive(False)
        self.run_button.get_style_context().add_class('suggested-action')
        self.run_button.connect('clicked', self.approve)
        box.pack_start(self.run_button, False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if phone else Gtk.Orientation.HORIZONTAL, spacing=8)
        for title, command in (('Mağaza · Wine planı', ['/usr/local/bin/oguzdows-store']),
                               ('Cihaz ve ARM rehberi', ['/usr/bin/xdg-open', '/usr/share/doc/oguzdows/cihazlar-ve-uyumluluk.md'])):
            button = Gtk.Button(label=title)
            button.connect('clicked', lambda _button, value=command: self.launch_program(value))
            row.pack_start(button, True, True, 0)
        box.pack_start(row, False, False, 0)
        self.voicebar = NarrationBar(self.window, 'compatibility')
        box.pack_start(self.voicebar, False, False, 0)
        self.status = Gtk.Label(label='Hazır. Otomatik kurulum / indirme / yönetici isteği yok.', wrap=True, xalign=0, max_width_chars=80)
        box.pack_start(self.status, False, False, 0)
        outer = Gtk.ScrolledWindow()
        outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.add(box)
        self.window.add(outer)
        self.window.show_all()

    def launch_program(self, command):
        try:
            Gio.Subprocess.new(command, Gio.SubprocessFlags.NONE)
        except GLib.Error as error:
            self.status.set_text(str(error))

    def choose(self, *_):
        dialog = Gtk.FileChooserNative(title='Yerel bir EXE veya APK seç', transient_for=self.window,
                                       action=Gtk.FileChooserAction.OPEN, accept_label='İncele', cancel_label='Vazgeç')
        dialog.set_local_only(True)
        pattern = Gtk.FileFilter()
        pattern.set_name('Windows / Android dosyaları')
        for value in ('*.exe', '*.EXE', '*.apk', '*.APK'):
            pattern.add_pattern(value)
        dialog.add_filter(pattern)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.inspect(dialog.get_filename())
        dialog.destroy()

    def inspect(self, path):
        if self.busy:
            return
        self.receipt = None
        self.ack.set_active(False)
        self.set_busy(True)
        self.status.set_text('Dosya başlığı, boyutu ve SHA-256 okunuyor… Henüz çalıştırılmıyor.')
        def work():
            try:
                receipt = core.inspect(path)
                caps = core.capabilities()
                reasons = core.availability(receipt, caps, core.runtime_status)
                if os.geteuid() == 0:
                    reasons.append('Root oturumunda çalıştırma kapalıdır. Kendi masaüstü hesabına dön.')
                GLib.idle_add(self.inspected, receipt, caps, reasons, None)
            except (OSError, ValueError, RuntimeError, core.zipfile.BadZipFile, core.subprocess.SubprocessError) as error:
                GLib.idle_add(self.inspected, None, None, [], str(error))
        threading.Thread(target=work, daemon=True).start()

    def inspected(self, receipt, caps, reasons, error):
        self.set_busy(False)
        self.receipt, self.caps = receipt, caps
        self.reasons = reasons
        if error:
            self.detail.get_buffer().set_text(error)
            self.status.set_text('Dosya çalıştırılmadı.')
        else:
            text = (receipt['name'] + '\nTür: ' + receipt['kind'].upper() + '\nMimari: ' + receipt['architecture']
                    + '\nBoyut: ' + str(receipt['size']) + ' bayt\nSHA-256: ' + receipt['sha256']
                    + '\n\n' + receipt['note'] + '\n\n'
                    + ('Hazırlık eksikleri:\n• ' + '\n• '.join(reasons) if reasons else 'Hazırlık koşulları uygun görünüyor. Bu, uygulamanın çalışacağı veya güvenli olduğu garantisi değildir.'))
            self.detail.get_buffer().set_text(text)
            self.status.set_text('İnceleme tamamlandı. Henüz çalıştırılmadı; açık onay bekleniyor.')
        self.update_action()
        return GLib.SOURCE_REMOVE

    def set_busy(self, value):
        self.busy = value
        self.pick_button.set_sensitive(not value)
        self.ack.set_sensitive(not value)
        self.update_action()

    def update_action(self, *_):
        available = bool(self.receipt and not getattr(self, 'reasons', []) and not self.busy)
        self.run_button.set_sensitive(available and self.ack.get_active())
        self.run_button.set_label('Onayla · Wine ile aç' if available and self.receipt['kind'] == 'exe' else
                                  'Onayla · APK’yı Waydroid’e kur' if available else 'Hazırlık koşulları tamamlanmadan çalıştırma yok')
        # Gtk.Button.set_label içteki Gtk.Label'ı yeniden kurabilir. İnceleme /
        # durum değişince kaybolan wrap, telefon penceresini tekrar genişletmesin.
        self.run_button.get_child().set_line_wrap(True)
        self.run_button.get_child().set_max_width_chars(26)

    def approve(self, *_):
        if self.busy or not self.receipt or not self.ack.get_active() or getattr(self, 'reasons', []):
            return
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK_CANCEL, text='Bu dosya kendi hesabında açılsın mı?')
        dialog.format_secondary_text('Dosya yeniden doğrulanıp özel çalışma dizinine kopyalanır. Dijital imza / virüs denetimi yapılmadı. Wine ayrı prefix kullansa da ev dosyalarına / ağa erişebilir. İşletim sistemi bu uygulamanın uyumlu veya zararsız olduğunu onaylamaz.')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if self.window.get_screen().get_width() < 600:
            for child in dialog.get_message_area().get_children():
                if isinstance(child, Gtk.Label):
                    child.set_line_wrap(True)
                    child.set_max_width_chars(24)
            dialog.set_default_size(min(360, self.window.get_screen().get_width() - 24), -1)
        approved = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if not approved:
            self.status.set_text('Vazgeçildi; dosya çalıştırılmadı.')
            return
        self.set_busy(True)
        self.status.set_text('Onaylanan dosya yeniden doğrulanıp kopyalanıyor…')
        receipt = self.receipt
        def work():
            staged = None
            try:
                staged = core.stage(receipt, self.data / 'inbox')
                plan = core.launch_plan(receipt, staged, self.data, core.capabilities(), core.runtime_status)
                GLib.idle_add(self.start_engine, staged, plan, None)
            except (OSError, ValueError, RuntimeError, core.subprocess.SubprocessError) as error:
                if staged:
                    staged.unlink(missing_ok=True)
                GLib.idle_add(self.start_engine, None, None, str(error))
        threading.Thread(target=work, daemon=True).start()

    def start_engine(self, staged, plan, error):
        if error:
            self.set_busy(False)
            self.status.set_text('Çalıştırılmadı: ' + error)
            return GLib.SOURCE_REMOVE
        self.staged = staged
        command, environment, cwd = plan
        try:
            logs = core.private_directory(self.data / 'logs')
            descriptor, name = core.tempfile.mkstemp(prefix='uyumluluk-', suffix='.log', dir=logs)
            launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDERR_MERGE)
            launcher.take_stdout_fd(descriptor)
            for key, value in environment.items():
                launcher.setenv(key, value, True)
            if cwd:
                launcher.set_cwd(cwd)
            process = launcher.spawnv(command)
            self.status.set_text('Uyumluluk motoru başlatıldı; uygulamanın kendi ekranını takip et. Bu, kurulum başarıyla bitti bildirimi değildir. Günlük: ' + name)
            self.ack.set_active(False)
            if self.receipt['kind'] == 'exe':
                # Wine kendi alt süreçlerini yönetir; UI kapanışı onları öldürmez.
                self.set_busy(False)
            process.wait_async(None, self.engine_finished, (self.receipt['kind'], staged, name))
        except (OSError, GLib.Error) as failure:
            staged.unlink(missing_ok=True)
            self.set_busy(False)
            self.status.set_text('Motor başlatılamadı: ' + str(failure))
        return GLib.SOURCE_REMOVE

    def engine_finished(self, process, result, data):
        kind, staged, log = data
        try:
            process.wait_finish(result)
            ok = process.get_if_exited() and process.get_exit_status() == 0
            if self.window:
                self.status.set_text(('Motor işlemi bitti; sonucu uygulamanın kendi arayüzünden doğrula.' if ok else 'Uyumluluk motoru hata ile çıktı. Kurulum başarılı sayılmadı.') + ' Günlük: ' + log)
        except GLib.Error as error:
            if self.window:
                self.status.set_text(str(error))
        if kind == 'apk':
            staged.unlink(missing_ok=True)
            self.set_busy(False)
        # EXE kaynağı Wine alt süreçleri tarafından kullanılabilir; inbox/prefix
        # kullanıcı kaldırana kadar korunur, işlem ortasında otomatik silinmez.

    def close_requested(self, *_):
        if self.busy:
            self.status.set_text('İnceleme / APK işlemi sürüyor. Bitmesini bekle; süreç zorla öldürülmez.')
            return True
        return False


if __name__ == '__main__':
    raise SystemExit(Compatibility().run(sys.argv))
