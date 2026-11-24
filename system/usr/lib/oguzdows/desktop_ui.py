"""Karşılayıcı ve bağımsız Masaüstü Merkezi'nin ortak yerel GTK bileşenleri."""
from __future__ import annotations

import logging
import subprocess
import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk, Pango

import desktop_preferences as preferences
import desktop_runtime as runtime
import desktop_state as state


def note(text, title=False):
    label = Gtk.Label(label=text, xalign=0, wrap=True)
    label.set_max_width_chars(78)
    label.get_style_context().add_class('title' if title else 'subtitle')
    return label


class PreferencesPanel(Gtk.Box):
    def __init__(self, parent=None, allowed=lambda: True, on_busy=lambda _busy: None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.parent_window, self.allowed, self.on_busy = parent, allowed, on_busy
        self.busy, self.closed = False, False
        self.connect('destroy', lambda *_: setattr(self, 'closed', True))
        if parent is not None:
            # Gtk.ScrolledWindow Python tarafında çocuk referansını tutabilir;
            # üst pencere yok edildikten sonra yeni işçi başlatmak yine yasak.
            parent.connect('destroy', lambda *_: setattr(self, 'closed', True))
        self.pack_start(note('Aero · ortak tercihler', True), False, False, 0)
        self.pack_start(note('Xfce, GNOME ve Plasma arasında renk / tema / duvar kâğıdı seçimi ortak; her kabuğun paneli, widget düzeni ve kısayolları kendi yerinde kalır. Yeni efektler kendiliğinden açılmaz.'), False, False, 0)
        try:
            value = state.load()
            error = ''
        except (OSError, ValueError) as failure:
            value, error = state.DEFAULTS, str(failure)
        self.appearance = self.combo('Açık / koyu tema', {'light': 'Açık', 'dark': 'Koyu'}, value['appearance'])
        self.effects = self.combo('Efekt düzeyi', {'off': 'Kapalı · en hafif', 'glass': 'Hafif cam', 'aero': 'Aero · gelişmiş seçenekler'}, value['effects'])
        self.motion = self.combo('Hareket', {'reduced': 'Azaltılmış · animasyon yok', 'smooth': 'Kısa / yerel geçişler', 'spring': 'Yay · desteklenen kompozitörde'}, value['motion'])
        self.blur = Gtk.CheckButton(label='Gerçek arka plan bulanıklığını açıkça etkinleştir (GPU gerektirir)')
        self.blur.set_active(value['blur']); self.blur.get_child().set_line_wrap(True)
        self.pack_start(self.blur, False, False, 0)
        self.snap = Gtk.CheckButton(label='Deneysel geometri / Aero Snap animasyonu · sürüklemeyi de etkileyebilir')
        self.snap.set_active(value['snap_animation']); self.snap.get_child().set_line_wrap(True)
        self.pack_start(self.snap, False, False, 0)
        self.source = self.combo('Cam rengi', {'theme': 'Seçtiğim vurgu rengi', 'wallpaper': 'Seçili galeri görselinden tek seferlik çıkar'}, value['accent_source'])
        row = Gtk.Box(spacing=10)
        row.pack_start(note('Vurgu rengi'), True, True, 0)
        self.color = Gtk.ColorButton()
        color = Gdk.RGBA(); color.parse(value['accent']); self.color.set_rgba(color)
        self.color.set_use_alpha(False); self.color.set_title('OğuzDows vurgu rengi')
        row.pack_end(self.color, False, False, 0); self.pack_start(row, False, False, 0)
        self.feedback = Gtk.CheckButton(label='Başarılı başlatmada kısa sesli geri bildirim · varsayılan kapalı')
        self.feedback.get_child().set_line_wrap(True); self.feedback.set_active(value['feedback'])
        self.pack_start(self.feedback, False, False, 0)
        self.pack_start(note('Gerçek blur: Xfce/Picom 9+ hızlandırılmış GLX; GNOME Shell 43/44 veya 45–48 uzantısı; Plasma/KWin. GNOME uygulama çerçeveleri evrensel olarak blur almaz; Plasma’da kurulu Aurorae için özgün cam kenarlar üretilir; CSD uygulamalar kendi blur bölgesini bildirmelidir. Üst çubuk yazıları ve kapatma düğmeleri opaktır. Picom yayı 12+ ister. 2 GiB ve altı / ARMv6 / nomodeset / bilinmeyen GPU statik kalır. Wayland’ın zorunlu kompozitörü kapatılmaz.'), False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.apply_button = Gtk.Button(label='Ortak tercihleri uygula')
        self.apply_button.get_style_context().add_class('suggested-action')
        self.apply_button.connect('clicked', self.apply)
        self.restore_button = Gtk.Button(label='Bu masaüstünün önceki ayarlarını geri al…')
        self.restore_button.connect('clicked', self.restore)
        for button in (self.apply_button, self.restore_button):
            button.get_child().set_line_wrap(True)
            button.get_child().set_max_width_chars(32)
        row.pack_start(self.apply_button, True, True, 0); row.pack_start(self.restore_button, True, True, 0)
        self.pack_start(row, False, False, 0)
        self.status = note(error or 'Henüz değişiklik yapılmadı. Donanım / fiziksel animasyon doğrulaması bu pencereden iddia edilmez.')
        self.pack_start(self.status, False, False, 0)
        if error:
            self.apply_button.set_sensitive(False)

    def combo(self, title, choices, selected):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        row.pack_start(note(title), False, False, 0)
        combo = Gtk.ComboBoxText()
        for identifier, label in choices.items():
            combo.append(identifier, label)
        combo.set_active_id(selected)
        for cell in combo.get_cells():
            cell.set_property('ellipsize', Pango.EllipsizeMode.END)
            cell.set_property('max-width-chars', 23)
        row.pack_end(combo, False, False, 0)
        self.pack_start(row, False, False, 0)
        return combo

    def finished(self, message):
        self.busy = False
        try:
            self.on_busy(False)
        except Exception:
            logging.exception('Masaüstü görünüm kilidi geri bildirimi başarısız')
        if not self.closed:
            self.apply_button.set_sensitive(True); self.restore_button.set_sensitive(True)
            self.status.set_text(message)
        return GLib.SOURCE_REMOVE

    def work(self, operation):
        if self.closed:
            return
        if self.busy or not self.allowed():
            self.status.set_text('Başka bir görünüm / kurulum işlemi bitmeden yeni efekt uygulanmaz.')
            return
        self.busy = True
        self.apply_button.set_sensitive(False); self.restore_button.set_sensitive(False)
        self.status.set_text('Yalnız bu hesabın masaüstü ayarları uygulanıyor…')
        def run():
            try:
                result = operation()
                message = result['message'] + ('\n' + '\n'.join(result['notes']) if result.get('notes') else '')
                if result.get('preserved_external_changes'):
                    message += '\nSonradan değiştirdiğin kişisel anahtarlar korunarak atlandı: ' + ', '.join(result['preserved_external_changes'])
            except Exception as error:
                # Beklenmeyen bir arka uç / biçim hatası da busy'yi sonsuza
                # kilitlemez. Hata gizlenmez; konsolda iz, panelde açık uyarı.
                logging.exception('Masaüstü tercih işlemi tamamlanamadı')
                message = 'İşlem tamamlanamadı: ' + str(error)
            GLib.idle_add(self.finished, message)
        try:
            self.on_busy(True)
            threading.Thread(target=run, daemon=True).start()
        except Exception as error:
            logging.exception('Masaüstü tercih işçisi başlatılamadı')
            self.finished('İşlem tamamlanamadı: ' + str(error))

    def apply(self, *_):
        rgba = self.color.get_rgba()
        color = '#' + ''.join(f'{round(component * 255):02x}' for component in (rgba.red, rgba.green, rgba.blue))
        changes = {'appearance': self.appearance.get_active_id(), 'effects': self.effects.get_active_id(),
            'motion': self.motion.get_active_id(), 'blur': self.blur.get_active(),
            'snap_animation': self.snap.get_active(), 'accent': color,
            'accent_source': self.source.get_active_id(), 'feedback': self.feedback.get_active()}
        self.work(lambda: preferences.update_and_apply(changes))

    def restore(self, *_):
        if self.busy or not self.allowed():
            return
        dialog = Gtk.MessageDialog(transient_for=self.parent_window, modal=True,
            message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
            text='Bu masaüstünün yedekli ayarlarına dönülsün mü?')
        dialog.format_secondary_text('GNOME / Plasma: yalnız bizim son değerimiz hâlâ duruyorsa geri alınır; sonradan yaptığın kişisel değişiklik ezilmez. Xfce: mevcut tipli ilk görünüm yedeği kullanılır. Diğer oturumların panelleri ve uygulamalar kapanmaz.')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if accepted:
            self.work(preferences.restore)


def control_grid(parent, status=None):
    grid = Gtk.FlowBox()
    grid.set_selection_mode(Gtk.SelectionMode.NONE)
    grid.set_min_children_per_line(1); grid.set_max_children_per_line(3)
    grid.set_column_spacing(8); grid.set_row_spacing(8)
    for action, title in runtime.ACTIONS.items():
        button = Gtk.Button(label=title)
        button.get_child().set_line_wrap(True)
        button.get_child().set_max_width_chars(24)
        def clicked(_button, identifier=action):
            try:
                runtime.native_control(identifier)
                if status:
                    status.set_text(runtime.ACTIONS[identifier] + ' · yerel araç başlatma isteği gönderildi.')
            except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as failure:
                if status:
                    status.set_text(str(failure))
                else:
                    dialog = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.CLOSE, text=str(failure))
                    dialog.run(); dialog.destroy()
        button.connect('clicked', clicked)
        grid.add(button)
    return grid
