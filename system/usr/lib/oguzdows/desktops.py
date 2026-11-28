#!/usr/bin/env python3
"""İstek üzerine gerçek masaüstü kur / seç; etkin oturumu zorla kapatmaz."""
import json
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_sessions
import maintenance
from resource_policy import current_policy
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk
from narration import NarrationBar

HELPER = ['/usr/bin/pkexec', '/usr/local/sbin/oguzdows-maintenance']


class Desktops(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.Oturumlar', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.busy = False
        self.plan = None

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if args not in ([], ['--desktop', 'kde'], ['--desktop', 'gnome']):
            return 2
        self.activate()
        if args:
            self.choice.set_active_id(args[1])
        return 0

    def do_activate(self):
        if self.window is None:
            self.build()
        self.window.present()

    def build(self):
        self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows · Gerçek oturumlar')
        import ui_theme
        ui_theme.setup(self.window)
        self.window.set_default_size(650, 530)
        self.window.connect('delete-event', lambda *_: self.busy)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
        note = Gtk.Label(xalign=0, wrap=True, label='Xfce düzeni ≠ KDE Plasma / GNOME oturumu.\n\nmacOS ve Windows 11 esintili kartlar yalnızca Xfce düzenleridir. Gerçek Plasma / GNOME burada ayrıca kurulur ve sonraki girişte seçilir. Bu seçim açık uygulamaları kapatmaz. Ancak normal çıkışta uygulamalar kapanır; kaydedilmemiş belge belleği başka kabuğa taşınamaz. Önce kaydet. Ortak tema / renk / galeri tercihleri korunur; paneller ve kısayollar kabuğa özeldir.\n\nGerçek oturumlar: amd64 / ARM64, en az 2 GiB sınıfı cihaz; 4 GiB ve çalışan 3B sürücü önerilir. 600 MB hedefi bu oturumları kapsamaz. Pi Zero / armhf / 512 MiB / 1 GiB için hafif Xfce korunur.')
        note.set_max_width_chars(76)
        box.pack_start(note, False, False, 0)
        self.choice = Gtk.ComboBoxText()
        for identifier, (title, _names) in desktop_sessions.SESSIONS.items():
            self.choice.append(identifier, title)
        self.choice.set_active_id('xfce')
        self.choice.connect('changed', self.changed)
        box.pack_start(self.choice, False, False, 0)
        self.buttons = []
        for title, callback in (
            ('Kurulu oturumu sonraki giriş için seç', self.select),
            ('1 · İmzalı paket listelerini yenile…', lambda *_: self.backend(['desktop-refresh'])),
            ('2 · Gerçek oturumun kurulum planını göster…', self.preview),
            ('3 · Planı onayla ve kur…', self.apply)):
            button = Gtk.Button(label=title)
            button.connect('clicked', callback)
            self.buttons.append(button)
            box.pack_start(button, False, False, 0)
        self.detail = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll = Gtk.ScrolledWindow(min_content_height=130)
        scroll.add(self.detail)
        box.pack_start(scroll, True, True, 0)
        self.status = Gtk.Label(xalign=0, wrap=True, label='Kurulum / oturum değiştirme henüz yapılmadı.')
        box.pack_start(self.status, False, False, 0)
        box.pack_start(NarrationBar(self.window, lambda: 'styles'), False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(box)
        self.window.add(scroll)
        self.window.show_all()
        self.changed()

    def changed(self, *_):
        self.plan = None
        self.buttons[-1].set_sensitive(False)
        choices = desktop_sessions.installed()
        self.status.set_text('Kurulu gerçek oturumlar: ' + (', '.join(item['title'] for item in choices.values()) or 'Yok'))

    def confirm(self, title, detail):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
        dialog.format_secondary_text(detail)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        answer = dialog.run()
        dialog.destroy()
        return answer == Gtk.ResponseType.OK

    def select(self, *_):
        if self.busy:
            return
        identifier = self.choice.get_active_id()
        if identifier != 'xfce':
            try:
                maintenance.build_desktop_info()
                resources = current_policy()
                maintenance.desktop_resources(resources['memory_kib'], resources['legacy_cpu'])
            except ValueError as error:
                self.status.set_text(str(error))
                return
        if not self.confirm('Sonraki girişin gerçek oturumu değişsin mi?', 'Bu düğme açık uygulamaları kapatmaz. Normal çıkışta uygulamalar kapanır: kaydet, sonra çıkış yap; kaydedilmemiş durum diğer kabuğa taşınamaz. Giriş ekranındaki oturum menüsünde bu tercihi doğrula. Sorunda OğuzDows / Xfce oturumuna dönebilirsin.'):
            return
        self.busy = True
        self.sensitive(False)
        def work():
            try:
                desktop_sessions.select(identifier)
                message = 'Tercih kaydedildi. Bu pencere / kart Xfce’yi başka kabuğa dönüştürmez. Normal çıkış yapıp giriş ekranında seçtiğin oturumla giriş yap.'
            except (OSError, ValueError, RuntimeError) as error:
                message = str(error)
            GLib.idle_add(self.finished, {'message': message}, False)
        threading.Thread(target=work, daemon=True).start()

    def preview(self, *_):
        identifier = self.choice.get_active_id()
        if identifier == 'xfce':
            self.status.set_text('Hafif OğuzDows Xfce zaten varsayılandır. Kurulum gerekmez.')
            return
        self.backend(['plan', 'desktop:' + identifier])

    def apply(self, *_):
        if self.plan and self.confirm('Bu gerçek masaüstü kurulsun mu?', 'Ek disk, internet ve yönetici onayı gerekir. Paket kaldırma / depo karıştırma yoktur. İşlem bitene kadar cihazı kapatma. Sonrasında ayrı olarak oturumu seçmelisin.'):
            plan = self.plan
            self.backend(['apply', plan['request'], plan['token']])

    def sensitive(self, active):
        self.choice.set_sensitive(active)
        for button in self.buttons:
            button.set_sensitive(active)
        self.buttons[-1].set_sensitive(active and self.plan is not None)

    def backend(self, args):
        if self.busy:
            return
        try:
            maintenance.build_desktop_info()
            resources = current_policy()
            maintenance.desktop_resources(resources['memory_kib'], resources['legacy_cpu'])
        except ValueError as error:
            self.status.set_text(str(error))
            return
        self.plan = None
        self.busy = True
        self.sensitive(False)
        self.status.set_text('Yönetici onayı / işlem bekleniyor. Paket kilitlerini silme.')
        def work():
            try:
                result = subprocess.run([*HELPER, *args], stdin=subprocess.DEVNULL, capture_output=True,
                                        text=True, errors='replace', check=False)
                data = json.loads(result.stdout)
                if not isinstance(data, dict):
                    raise ValueError('Paket yardımcısının yanıtı okunamadı.')
                if result.returncode:
                    data = {'error': data.get('error', 'İşlem iptal edildi / tamamlanamadı.')}
            except (OSError, ValueError) as error:
                data = {'error': str(error)}
            GLib.idle_add(self.finished, data, args[0] == 'plan')
        threading.Thread(target=work, daemon=True).start()

    def finished(self, data, plan):
        self.busy = False
        if 'error' in data:
            self.status.set_text(data['error'])
        elif plan:
            self.plan = data
            self.detail.get_buffer().set_text(data['detail'] + '\n\n' + data['note'])
            self.status.set_text('Plan hazır. Henüz kurulum yapılmadı.')
        else:
            self.status.set_text(data.get('message', 'Tamamlandı. Oturumu ayrıca seçin.'))
        self.sensitive(True)
        return GLib.SOURCE_REMOVE


if __name__ == '__main__':
    raise SystemExit(Desktops().run(sys.argv))
