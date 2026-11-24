#!/usr/bin/env python3
"""OğuzDows rehberi, yerel donanım merkezi ve Türkiye duvar kâğıtları."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hardware import is_live, light_profile, memory_kib, read_text, report, supported_broadcom, supported_intel_legacy
import offline
import wallpapers
import boot_report
import install_status as installer_state
import profiles
import effects
import desktop_preferences
import desktop_runtime
import welcome_model
import device_support
from rifki_speech import Speaker, ready_clip
from pi_support import current_policy, is_pi, model as pi_model

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gio, GLib, Gtk


def label(text: str, style: str = "", width: int = 0) -> Gtk.Label:
    widget = Gtk.Label(label=text, xalign=0)
    widget.set_line_wrap(True)
    if width:
        widget.set_max_width_chars(width)
    if style:
        widget.get_style_context().add_class(style)
    return widget


class Welcome(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="org.oguzdows.Rehber", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        state_home = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
        self.device = device_support.current()
        self.phone = self.device.get('phone', False)
        self.pc = self.device.get('arch') in ('amd64', 'i386') and not is_pi()
        self.context = welcome_model.context(live=is_live() and self.pc, pi=is_pi())
        self.state_file = state_home / 'oguzdows' / self.context.state_name
        self.speaker = None
        self.narration_source = None
        self.sidebar_rows = {}
        self.loaded_pages = set()
        self.page_scrollers = {}
        self.page_builders = {}
        self.theme_busy = False
        self.window = None
        self.driver_busy = False
        self.driver_eligibility = (False,False)
        self.install_busy = False
        self.report_loading = False
        self.report_text = ""
        self.mark_on_close = False
        self.wallpaper_buttons = []
        self.profile_busy = False
        self.rifki = None
        self.install_data = {}
        self.previous_session = None
        self.external_installing = False
        self.launcher_group = None
        self.launcher_signals = []
        self.launcher_watch = None
        self.installing_action = Gio.SimpleAction.new_stateful('installing', None, GLib.Variant('b', False))
        self.add_action(self.installing_action)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        # Bağımsız masaüstü kısayolundan açılan kurucu da açık Rıfkı'yı susturur.
        # D-Bus durum bildirimi kullanılır; boştayken dosya tarayan zamanlayıcı yok.
        self.launcher_watch=Gio.bus_watch_name(
            Gio.BusType.SESSION,'org.oguzdows.HafifKurucu',Gio.BusNameWatcherFlags.NONE,
            self.launcher_appeared,self.launcher_vanished)

    def do_shutdown(self):
        if self.launcher_watch is not None:
            Gio.bus_unwatch_name(self.launcher_watch)
            self.launcher_watch=None
        self.launcher_vanished(None,None)
        self.cancel_narration()
        if self.speaker:
            self.speaker.close()
        Gtk.Application.do_shutdown(self)

    def launcher_appeared(self,connection,name,_owner):
        self.launcher_vanished(None,None)
        self.launcher_group=Gio.DBusActionGroup.get(connection,name,'/org/oguzdows/HafifKurucu')
        self.launcher_signals=[
            self.launcher_group.connect('action-added',self.launcher_action_added),
            self.launcher_group.connect('action-state-changed',self.launcher_state_changed),
        ]
        self.launcher_group.list_actions()  # İlk durum arka planda alınır.

    def launcher_vanished(self,*_):
        if self.launcher_group is not None:
            for signal in self.launcher_signals:
                self.launcher_group.disconnect(signal)
        self.launcher_group=None
        self.launcher_signals=[]
        self.set_external_installing(False)

    def launcher_action_added(self,group,name):
        if name=='busy':
            state=group.get_action_state(name)
            if state is not None:
                self.launcher_state_changed(group,name,state)

    def launcher_state_changed(self,_group,name,state):
        if name=='busy' and state.is_of_type(GLib.VariantType.new('b')):
            self.set_external_installing(state.get_boolean())

    def set_external_installing(self,value):
        self.external_installing=bool(value)
        busy=self.install_busy or self.external_installing
        self.installing_action.set_state(GLib.Variant('b', busy or self.driver_busy))
        if busy:
            self.cancel_narration()
            if self.speaker:
                self.speaker.stop()
        if self.rifki:
            self.rifki.set_installing(busy)
        if self.window is not None and self.pc:
            self.install_button.set_sensitive(not busy and not self.driver_busy and self.can_install())
            for button,eligible in zip((self.broadcom_button,self.intel_button),self.driver_eligibility):
                button.set_sensitive(eligible and self.pc and not busy and not self.driver_busy)
        self.refresh_appearance_controls()

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        args = set(command_line.get_arguments()[1:])
        if args - {"--autostart", "--drivers", "--wallpapers", "--styles", "--install", "--assistant"}:
            print("Kullanım: oguzdows-welcome [--autostart|--drivers|--wallpapers|--styles|--install|--assistant]", file=sys.stderr)
            return 2
        if "--autostart" in args and self.state_file.exists():
            return 0
        self.mark_on_close = self.mark_on_close or not bool(args & {"--drivers", "--wallpapers", "--styles"})
        self.activate()
        if "--drivers" in args:
            self.show_drivers()
        if "--wallpapers" in args:
            self.stack.set_visible_child_name("wallpapers")
        if "--styles" in args:
            self.stack.set_visible_child_name("styles")
        if "--assistant" in args:
            self.open_assistant()
        if "--install" in args:
            self.stack.set_visible_child_name("welcome")
            GLib.idle_add(self.install)
        return 0

    def do_activate(self) -> None:
        if self.window is None:
            self.build_window()
        self.window.present()

    def build_window(self) -> None:
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title(self.context.title)
        self.window.set_icon_name('oguzdows-welcome')
        self.window.get_style_context().add_class('oguzdows-window')
        self.window.set_position(Gtk.WindowPosition.CENTER)
        screen = self.window.get_screen()
        self.window.set_default_size(min(400 if self.phone else 980, screen.get_width() - 24), min(700, screen.get_height() - 48))
        self.window.set_size_request(320 if self.phone else 550, 380)
        self.window.connect('delete-event', self.on_close)
        self.window.connect('destroy', self.window_destroyed)
        self.window.connect('notify::is-active', self.focus_changed)
        header = Gtk.HeaderBar(title='OğuzDows' if self.phone else 'OğuzDows Karşılayıcı',
                               subtitle=None if self.phone else self.context.subtitle)
        header.set_show_close_button(True)
        self.window.set_titlebar(header)
        help_button = (Gtk.Button.new_from_icon_name('help-browser-symbolic', Gtk.IconSize.BUTTON)
                       if self.phone else Gtk.Button(label='Rıfkı’ya sor'))
        help_button.set_tooltip_text('Rıfkı’ya sor')
        help_button.get_accessible().set_name('Rıfkı’ya sor')
        help_button.connect('clicked', lambda *_: self.open_assistant())
        header.pack_end(help_button)
        self.speaker = Speaker(GLib.idle_add, self.voice_error)
        self.stack = Gtk.Stack()
        reduced = not current_policy()['animations'] if is_pi() else light_profile(read_text(Path('/proc/cmdline')), memory_kib())
        self.reduced = reduced or not Gtk.Settings.get_default().get_property('gtk-enable-animations')
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.sidebar = Gtk.ListBox()
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar.set_activate_on_single_click(True)
        self.sidebar.set_size_request(52 if self.phone else 142, -1)
        self.sidebar.get_style_context().add_class('welcome-sidebar')
        builders = {'welcome': self.welcome_page, 'styles': self.styles_page,
                    'appearance': self.appearance_page, 'wallpapers': self.wallpapers_page,
                    'hardware': self.hardware_page, 'applications': self.applications_page,
                    'support': self.support_page}
        self.page_builders = builders
        for identifier, title, icon in welcome_model.PAGES:
            row = Gtk.ListBoxRow()
            row.page_name = identifier
            line = Gtk.Box(spacing=8)
            line.set_border_width(11)
            line.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
            if not self.phone:
                line.pack_start(label(title), True, True, 0)
            row.set_tooltip_text(title)
            row.get_accessible().set_name(title)
            row.add(line)
            self.sidebar.add(row)
            self.sidebar_rows[identifier] = row
            page_scroll = Gtk.ScrolledWindow()
            page_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            page_scroll.set_propagate_natural_width(False)
            self.page_scrollers[identifier] = page_scroll
            self.stack.add_named(page_scroll, identifier)
            # Kurulum / donanım düğmeleri daima hazır. Diğer beş sayfanın
            # GTK ağaçları ilk ziyarette kurulur; özellikler silinmez.
            if identifier in ('welcome', 'hardware'):
                self.ensure_page(identifier)
        self.stack.add_named(self.result_page(), 'install-result')
        self.sidebar.connect('row-selected', self.sidebar_selected)
        content.pack_start(self.sidebar, False, False, 0)
        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        content.pack_start(self.stack, True, True, 0)
        root.pack_start(content, True, True, 0)
        root.pack_start(Gtk.Separator(), False, False, 0)
        root.pack_start(self.narration_bar(), False, False, 0)
        footer = Gtk.Box(spacing=10)
        footer.set_border_width(10)
        self.previous_button = Gtk.Button(label='Önceki')
        self.previous_button.connect('clicked', lambda *_: self.step_page(-1))
        self.next_button = Gtk.Button(label='Sonraki')
        self.next_button.connect('clicked', lambda *_: self.step_page(1))
        footer.pack_start(self.previous_button, True, True, 0)
        footer.pack_start(self.next_button, True, True, 0)
        root.pack_start(footer, False, False, 0)
        self.window.add(root)
        self.stack.connect('notify::visible-child-name', self.page_changed)
        self.window.show_all()
        self.sidebar.select_row(self.sidebar_rows['welcome'])
        self.page_changed()

    def ensure_page(self, identifier):
        if identifier in self.loaded_pages or identifier not in self.page_builders:
            return
        page = self.page_builders[identifier]()
        page.set_border_width(18)
        self.page_scrollers[identifier].add(page)
        self.loaded_pages.add(identifier)
        page.show_all()

    def focus_changed(self, window, *_):
        if not window.is_active() and (self.rifki is None or not self.rifki.get_visible()):
            self.stop_narration()

    def window_destroyed(self, *_):
        self.window = None
        self.cancel_narration()
        if self.speaker:
            self.speaker.close()

    def sidebar_selected(self, _sidebar, row):
        if row is not None and self.stack.get_visible_child_name() != row.page_name:
            self.stack.set_visible_child_name(row.page_name)

    def step_page(self, direction):
        target = welcome_model.adjacent(self.stack.get_visible_child_name(), direction)
        if target:
            self.navigate(target)

    def narration_bar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if self.phone else Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_border_width(10)
        bar.get_style_context().add_class('narration-bar')
        self.narration_status = label('Rıfkı · Hazır doğal kayıtlar.', 'muted', 48)
        self.narration_status.set_hexpand(True)
        bar.pack_start(self.narration_status, True, True, 0)
        controls = Gtk.Box(spacing=8) if self.phone else bar
        if self.phone:
            bar.pack_start(controls, False, False, 0)
        self.listen_button = Gtk.Button.new_from_icon_name('audio-volume-high-symbolic', Gtk.IconSize.BUTTON)
        self.listen_button.set_tooltip_text('Bu sayfayı Rıfkı’dan dinle')
        self.listen_button.get_accessible().set_name('Bu sayfayı dinle')
        self.listen_button.connect('clicked', lambda *_: self.queue_narration(force=True))
        controls.pack_start(self.listen_button, False, False, 0)
        stop = Gtk.Button.new_from_icon_name('media-playback-stop-symbolic', Gtk.IconSize.BUTTON)
        stop.set_tooltip_text('Sesi hemen durdur')
        stop.get_accessible().set_name('Sesi durdur')
        stop.connect('clicked', self.stop_narration)
        controls.pack_start(stop, False, False, 0)
        self.narration_switch = Gtk.Switch()
        self.narration_switch.set_valign(Gtk.Align.CENTER)
        self.narration_switch.set_active(self.speaker.options.get('welcome_narration', True) is not False)
        self.narration_switch.set_tooltip_text('Sayfa değişince Rıfkı anlatsın. Bu anahtarla kapatabilirsin; tercihin korunur.')
        self.narration_switch.get_accessible().set_name('Otomatik sayfa anlatımı')
        self.narration_switch.connect('notify::active', self.narration_toggled)
        controls.pack_start(self.narration_switch, False, False, 0)
        return bar

    def narration_toggled(self, *_):
        self.speaker.save_option('welcome_narration', self.narration_switch.get_active())
        if self.rifki:
            self.rifki.narration.set_active(self.narration_switch.get_active())
        if self.narration_switch.get_active():
            self.queue_narration(force=True)
        else:
            self.stop_narration()

    def cancel_narration(self):
        if self.narration_source is not None:
            GLib.source_remove(self.narration_source)
            self.narration_source = None

    def stop_narration(self, *_):
        self.cancel_narration()
        if self.speaker:
            self.speaker.stop()

    def voice_error(self, text):
        if self.window:
            self.narration_status.set_text(text)

    def queue_narration(self, force=False):
        self.stop_narration()
        if self.install_busy or self.external_installing or not self.window:
            return
        page = self.stack.get_visible_child_name()
        words = welcome_model.page_text(page, self.context)
        if not words:
            return
        self.narration_status.set_tooltip_text(words)
        if not force and not self.narration_switch.get_active():
            return
        if not self.speaker.enabled:
            self.narration_status.set_text('Rıfkı sesi kapalı. Rıfkı ayarlarından açabilirsin.')
            return
        if ready_clip(words, self.speaker.assets, self.speaker.clips) is None:
            self.narration_status.set_text('Bu sayfanın doğal ses kaydı henüz yok; açıklama yazılı yardımda.')
            return
        def play():
            self.narration_source = None
            if (self.window and self.stack.get_visible_child_name() == page
                    and not self.install_busy and not self.external_installing):
                self.speaker.speak(words)
                self.narration_status.set_text('Rıfkı · ' + dict((x[0], x[1]) for x in welcome_model.PAGES)[page])
            return GLib.SOURCE_REMOVE
        # Hızlı gezinmede önceki sayfanın sesi başlamasın; boşta tekrar eden iş yok.
        self.narration_source = GLib.timeout_add(120, play)

    def welcome_page(self) -> Gtk.Box:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if self.phone else Gtk.Orientation.HORIZONTAL, spacing=22)
        image = Gtk.Image()
        try:
            image.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale('/usr/share/oguzdows/rifki/idle.png',128,128,True))
        except GLib.Error:
            image.set_from_icon_name('oguzdows',Gtk.IconSize.DIALOG)
        image.set_valign(Gtk.Align.CENTER)
        hero.pack_start(image, False, False, 0)
        words = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        words.pack_start(label("RIFKI · YANINDAYIM", "eyebrow"), False, False, 0)
        words.pack_start(label("OğuzDows'a hoş geldin.", "heading", 28), False, False, 0)
        words.pack_start(label(self.context.intro, "muted", 46), False, False, 0)
        hero.pack_start(words, True, True, 0)
        page.pack_start(hero, False, False, 12)
        page.pack_start(label("Nasıl başlamak istersin?", "section-title"), False, False, 0)
        choices = Gtk.FlowBox()
        choices.set_selection_mode(Gtk.SelectionMode.NONE)
        choices.set_column_spacing(8)
        choices.set_row_spacing(8)
        choices.set_min_children_per_line(1)
        choices.set_max_children_per_line(3)
        choices.set_homogeneous(True)
        choices.add(self.card("OğuzDows'u dene" if self.context.offers_installer else 'Masaüstüne geç',
                              'Diskine dokunmadan masaüstünü ve uygulamalarını keşfet.' if self.context.offers_installer else 'Karşılayıcıyı kapat ve kendi masaüstünü kullanmaya başla.',
                              'user-desktop-symbolic', lambda *_: self.window.close(), primary=True))
        if is_pi():
            self.install_button = self.card("Pi masaüstü ayarları", "Sistem zaten kurulu. Görünüm, ekran, ses ve güç ayarlarını düzenle.", "preferences-system-symbolic", lambda *_: self.launch(["/usr/local/bin/oguzdows-desktop", "--control", "settings"]))
        else:
            self.install_button = self.card("OğuzDows'u kur", "Canlı USB'den, internet gerekmeden bilgisayarına yerleştir.", "system-software-install-symbolic", self.install)
            self.install_button.set_sensitive(self.can_install())
            if not is_live():
                self.install_button.set_tooltip_text("Kurulum canlı OğuzDows USB'sinden başlatılır.")
        if is_pi() or self.context.offers_installer:
            choices.add(self.install_button)
        else:
            # Kurulu sistemde canlı USB kurulum kartı hiç gösterilmez.
            self.install_button.set_no_show_all(True)
            choices.add(self.card('Masaüstünü kişiselleştir', 'Tarzını, açık/koyu temanı ve duvar kâğıdını seç.',
                                  'preferences-desktop-theme-symbolic', lambda *_: self.navigate('styles')))
        choices.add(self.card("Donanımını tanı", "Aygıtları, yüklü firmware'i ve gömülü ek sürücüleri gör.", "preferences-system-symbolic", lambda *_: self.show_drivers()))
        choices.add(self.card('Masaüstü tarzını seç', 'Altı hafif düzen; gerçek oturumlar ayrıca seçilir. Pencere düğmeleri ve panel daima okunaklı.', 'preferences-desktop-theme-symbolic', lambda *_: self.stack.set_visible_child_name('styles')))
        if not is_pi():
            choices.add(self.card('Uygulamalar ve güncellemeler', 'Mağaza ve Güncelleyici ayrı, anlaşılır düğmelerle.', 'system-software-update-symbolic', lambda *_: self.navigate('applications')))
        choices.add(self.card('İmece araçları', 'Çay Molası · Türkçe Hızlı Yazım · Heybe · Yerel paylaşım paketi.', 'oguzdows-imece', lambda *_: self.launch(['/usr/local/bin/oguzdows-imece'])))
        page.pack_start(choices, False, False, 0)
        setup_note = (f"{pi_model() or 'Raspberry Pi'} · {current_policy()['profile']} profili. Değişikliklerin SD/USB üzerinde kalıcıdır."
                      if is_pi() else ('Kurulum günlüğü: /var/log/oguzdows/installer.log' if self.context.offers_installer
                                       else 'Görünüm seçimlerin bu hesapta saklanır. Cihazına özel destek düzeyini Cihaz Merkezi’nde inceleyebilirsin.'))
        self.install_status = label(setup_note, "muted", 90)
        page.pack_start(self.install_status, False, False, 0)
        page.pack_start(Gtk.Separator(), False, False, 0)
        page.pack_start(label("Türkçe dil ve Q klavye · İstanbul saat dilimi · Hafif Xfce masaüstü", "muted", 80), False, False, 0)
        gallery = Gtk.Button(label='Duvar kâğıtlarını keşfet' if self.phone else 'Türkiye duvar kâğıtlarını keşfet')
        gallery.connect("clicked", lambda *_: self.stack.set_visible_child_name("wallpapers"))
        page.pack_start(gallery, False, False, 0)
        self.show_again = Gtk.CheckButton(label='Sonraki girişte yeniden göster' if self.phone else 'Bir sonraki girişte bu ekranı yeniden göster')
        self.show_again.get_child().set_line_wrap(True)
        page.pack_start(self.show_again, False, False, 0)
        note = "Canlı oturumdaki değişiklikler, kalıcılık ayarlanmadıkça yeniden başlatmada silinir." if is_live() else "Rehbere uygulamalar menüsünden her zaman dönebilirsin."
        page.pack_start(label(note, "muted", 90), False, False, 0)
        return page

    def card(self, title, description, icon, callback, primary=False) -> Gtk.Button:
        button = Gtk.Button()
        button.set_size_request(208, -1)
        button.get_style_context().add_class("card")
        if primary:
            button.get_style_context().add_class("primary")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DIALOG)
        image.set_pixel_size(28)
        image.set_halign(Gtk.Align.START)
        content.pack_start(image, False, False, 0)
        content.pack_start(label(title, "card-title", 24), False, False, 0)
        content.pack_start(label(description, "muted", 25), True, True, 0)
        button.add(content)
        button.connect("clicked", callback)
        return button

    def hardware_page(self) -> Gtk.Box:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.pack_start(label("Önce tanı, sonra kur.", "section-title"), False, False, 8)
        driver_note = ("Pi çekirdekleri ve DTB'leri, VC4/V3D KMS, kartta varsa Broadcom SDIO Wi-Fi / Bluetooth ve USB ağ firmware'i imajdadır. Platform ve SDIO aygıtları da raporlanır; PC için STA sürücüsü Pi Wi-Fi'ına kurulmaz." if is_pi() else "Intel, AMD/ATI, Nouveau; Intel, Realtek, Atheros, Broadcom, Atmel, ZD1211 ve Libertas firmware paketleri ISO'dadır. Aşağıdaki rapor aygıtın gerçekten hangi sürücüye bağlandığını gösterir.")
        if not self.pc and not is_pi():
            driver_note = 'ARM cihazında ekran, güç, modem, ağ ve dokunma sürücüleri cihaz özel çekirdek / DTB / firmware yolundan gelir. Rapor salt okunurdur; PC Broadcom STA veya çekirdek paketi zorlanmaz.'
        page.pack_start(label(driver_note, "muted", 95), False, False, 0)
        page.pack_start(label(device_support.current()['name'] + ' · ' + device_support.current()['tier'], 'muted', 80), False, False, 0)
        self.report_view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        self.report_view.set_left_margin(12)
        self.report_view.set_top_margin(12)
        self.report_view.get_buffer().set_text("Raporu görmek için bu sekmeyi aç.")
        report_scroll = Gtk.ScrolledWindow()
        report_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        report_scroll.set_size_request(-1, 190)
        report_scroll.add(self.report_view)
        page.pack_start(report_scroll, True, True, 0)
        buttons = Gtk.FlowBox()
        buttons.set_selection_mode(Gtk.SelectionMode.NONE)
        buttons.set_min_children_per_line(1)
        buttons.set_max_children_per_line(3)
        buttons.set_column_spacing(8)
        self.refresh_button = Gtk.Button(label="Raporu yenile")
        self.refresh_button.connect("clicked", lambda *_: self.load_report())
        self.save_button = Gtk.Button(label="Raporu kaydet")
        self.save_button.set_sensitive(False)
        self.save_button.connect("clicked", self.save_report)
        network = Gtk.Button(label="Ağ bağlantıları")
        network.connect("clicked", lambda *_: self.launch(["/usr/bin/nm-connection-editor"]))
        for button in (self.refresh_button, self.save_button, network):
            buttons.add(button)
        page.pack_start(buttons, False, False, 0)
        self.broadcom_button = Gtk.Button(label="Gömülü Broadcom STA sürücüsünü kur…")
        self.broadcom_button.set_sensitive(False)
        self.broadcom_button.connect("clicked", lambda *_: self.install_driver("broadcom"))
        page.pack_start(self.broadcom_button, False, False, 0)
        self.intel_button = Gtk.Button(label="Gömülü Intel 2100 / 2200 / 2915 firmware'ini kur…")
        self.intel_button.set_sensitive(False)
        self.intel_button.connect("clicked", lambda *_: self.install_driver("intel-legacy-accept-license"))
        page.pack_start(self.intel_button, False, False, 0)
        if not self.pc:
            for button in (self.broadcom_button, self.intel_button):
                button.set_no_show_all(True)
                button.hide()
            arm_note = ("mini: ARMv6 veya en fazla 768 MiB; light: en fazla 2 GiB; full: daha fazla RAM. LZ4 zram sınırlıdır, SD swap kapalıdır; overclock uygulanmaz. 512 MiB ile modern web/ofis ağırdır. ARMv6 tarayıcısı temel Netsurf'tür (JavaScript yok). Profil: /etc/oguzdows/pi.conf"
                        if is_pi() else 'Deneysel ARM katmanı bir önyükleme imajı değildir. Ekran, modem, kamera, güç yönetimi ve fiziksel performans cihazda ayrıca sınanmalıdır. Pi çekirdeği veya Pi performans ayarları bu cihaza uygulanmaz.')
            page.pack_start(label(arm_note, 'muted', 95), False, False, 0)
        else:
            page.pack_start(label("Bu iki ek paket ve gerekli derleme araçları ISO'ya gömülüdür; eşleşen kartlarda internet gerekmez. Lisans ve yönetici onayı istenir. Canlıda onayladığın seçim disk kurulumuna taşınır. Gri düğme: bu sürücüyle eşleşen kart algılanmadı.", "muted", 95), False, False, 0)
        status = Gtk.Box(spacing=10)
        self.spinner = Gtk.Spinner()
        self.status = label("Donanım bilgilerin cihazında kalır.", "muted", 90)
        status.pack_start(self.spinner, False, False, 0)
        status.pack_start(self.status, True, True, 0)
        page.pack_start(status, False, False, 0)
        return page

    def wallpapers_page(self) -> Gtk.Box:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.pack_start(label("Türkiye'nin renkleri masaüstünde.", "section-title"), False, False, 6)
        page.pack_start(label('20 duvar kâğıdı: Türkiye manzaraları, kediler, çay–simit, halk oyunları ve kültür desenleri. 16 görsel yapay zekâ üretimi, 4 görsel özgün çizimdir; gerçek kamera fotoğrafı değildir. Hepsi sağ altta OğuzDows markalı, çevrimdışı ve küçük önizlemelidir.', 'muted', 90), False, False, 0)
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_min_children_per_line(1)
        grid.set_max_children_per_line(3)
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        self.wallpaper_grid=grid
        page.pack_start(grid, False, False, 0)
        self.wallpaper_status = label("Seçimin SD/USB üzerinde kaydedilir; yeniden başlatınca korunur." if is_pi() else "Seçimin sonraki oturumda korunur. Canlı USB'de kalıcılık yoksa yeniden başlatmada sıfırlanır.", "muted", 90)
        page.pack_start(self.wallpaper_status, False, False, 0)
        return page

    def style_preview(self, identifier):
        """Yerel GTK kutuları; gerçek panel düzeninin şeması, ekran resmi değil."""
        frame = Gtk.Frame()
        frame.set_size_request(156, 98)
        frame.get_style_context().add_class('style-preview')
        frame.get_style_context().add_class('preview-' + identifier)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.add(column)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        workspace = Gtk.Overlay()
        workspace.get_style_context().add_class('preview-workspace')
        workspace.add(Gtk.Box())
        mini = Gtk.Frame()
        mini.get_style_context().add_class('preview-window')
        mini.set_halign(Gtk.Align.CENTER)
        mini.set_valign(Gtk.Align.CENTER)
        mini.set_size_request(78, 42)
        mini.add(Gtk.Label(label='● ● ●' if identifier == 'mac' else '─ □ ×'))
        workspace.add_overlay(mini)
        if identifier == 'gnome':
            side = Gtk.Label(label='▦\n●\n●\n●')
            side.get_style_context().add_class('preview-panel')
            side.set_size_request(18, -1)
            body.pack_start(side, False, False, 0)
        body.pack_start(workspace, True, True, 0)
        panel = Gtk.Box(spacing=8)
        panel.get_style_context().add_class('preview-panel')
        if identifier == 'windows11':
            panel.set_halign(Gtk.Align.CENTER)
        panel.pack_start(Gtk.Label(label='Başlat' if identifier == 'oguzdows' else 'Oğuz'), False, False, 3)
        panel.pack_end(Gtk.Label(label='12:30'), False, False, 3)
        if profiles.PROFILES[identifier]['position'] == 9:
            column.pack_start(panel, False, False, 0)
            column.pack_start(body, True, True, 0)
        else:
            column.pack_start(body, True, True, 0)
            column.pack_start(panel, False, False, 0)
        if identifier in ('mac', 'windows11'):
            dock = Gtk.Label(label='▦  ●  ▣  ▪' if identifier == 'windows11' else '●  ▣  ▦  ▪')
            dock.set_halign(Gtk.Align.CENTER)
            dock.get_style_context().add_class('preview-panel')
            column.pack_end(dock, False, False, 0)
        return frame

    def styles_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.pack_start(label('Masaüstün, senin tarzın.', 'heading'), False, False, 0)
        page.pack_start(label('Kartlar şematik önizlemedir. Bu altı kart hafif Xfce düzenidir; gerçek KDE / GNOME seçimi aşağıda ayrıdır. macOS / Windows kurulmaz. İlk ayarlar yedeklenir.', 'muted', 72), False, False, 0)
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_min_children_per_line(1)
        grid.set_max_children_per_line(3)
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        self.profile_buttons = {}
        self.profile_choice = Gtk.ComboBoxText()
        for identifier, item in profiles.PROFILES.items():
            self.profile_choice.append(identifier, item['name'])
            button = Gtk.Button()
            button.get_style_context().add_class('style-card')
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            content.set_border_width(9)
            content.pack_start(self.style_preview(identifier), False, False, 0)
            content.pack_start(label(item['name'], 'card-title'), False, False, 0)
            button.set_tooltip_text(item['description'])
            button.get_accessible().set_name(item['name'] + ' tarzını seç')
            button.add(content)
            button.connect('clicked', lambda _button, name=identifier: self.profile_choice.set_active_id(name))
            self.profile_buttons[identifier] = button
            grid.add(button)
        page.pack_start(grid, False, False, 0)
        self.profile_choice.connect('changed', self.profile_selected)
        self.profile_choice.set_active_id(profiles.selection()[0])
        page.pack_start(self.profile_choice, False, False, 0)
        self.profile_reload = Gtk.CheckButton(label='Uygularken panelleri de şimdi yenile (açık pencereler kapanmaz)')
        self.profile_reload.set_active(True)
        page.pack_start(self.profile_reload, False, False, 0)
        self.profile_apply = Gtk.Button(label='Seçili tarzı uygula')
        self.profile_apply.get_style_context().add_class('suggested-action')
        self.profile_apply.connect('clicked', lambda *_: self.change_style(self.profile_choice.get_active_id()))
        page.pack_start(self.profile_apply, False, False, 0)
        self.profile_restore = Gtk.Button(label='İlk görünüm ayarlarıma dön')
        self.profile_restore.connect('clicked', lambda *_: self.change_style(None))
        page.pack_start(self.profile_restore, False, False, 0)
        self.profile_status = label('OğuzDows: Başlat. Windows 11: ortalı Başlat / simge grubu, ayrı üst durum şeridi. macOS: üst panel + alt iskele. Ubuntu: üst panel + sol iskele.', 'muted', 75)
        page.pack_start(self.profile_status, False, False, 0)
        reload_button = Gtk.Button(label='Panelleri şimdi yenile…')
        reload_button.connect('clicked', self.reload_panels)
        page.pack_start(reload_button, False, False, 0)
        page.pack_start(label('Yenile kutusu seçiliyse Uygula, paneli de yeniler. İşareti kaldırırsan yeni iskele / eklenti yerleşimi sonraki girişte yüklenir. Pencerelerin kapanmaz. Mac global menüsü veya GNOME kabuğu kurulmaz. Eski Whisker sürümünde menü yazısı sonraki girişte değişebilir.', 'muted', 75), False, False, 0)
        page.pack_start(label('Yerel tespih imleci için ayrı süreç / tıklama dinleyicisi yoktur. Gerçek KDE/GNOME daha fazla kaynak ister ve 600 MB hedefinin dışındadır.', 'muted', 75), False, False, 0)
        self.refresh_appearance_controls()
        # Kurulu oturumları her mimaride göster; kurulum uygunluğu ayrıca denetlenir.
        row = Gtk.Box(spacing=8)
        for identifier, title in (('kde', 'Gerçek KDE Plasma oturumu…'), ('gnome', 'Gerçek GNOME oturumu…')):
            button = Gtk.Button(label=title)
            button.connect('clicked', lambda _button, name=identifier: self.launch(['/usr/local/bin/oguzdows-desktops', '--desktop', name]))
            row.pack_start(button, True, True, 0)
        page.pack_start(row, False, False, 0)
        return page

    def profile_selected(self, *_):
        for identifier, button in self.profile_buttons.items():
            style = button.get_style_context()
            if identifier == self.profile_choice.get_active_id():
                style.add_class('selected-style')
            else:
                style.remove_class('selected-style')

    def appearance_blocked_reason(self):
        if self.install_busy or self.external_installing or self.driver_busy:
            return 'Kurulum / sürücü işlemi sürüyor; tamamlanınca görünüm düğmeleri açılacak.'
        if self.profile_busy:
            return 'Masaüstü tarzı / panel işlemi sürüyor; tamamlanınca efektleri uygulayabilirsin.'
        if self.theme_busy:
            return 'Tema / duvar kâğıdı işlemi sürüyor; tamamlanınca efektleri uygulayabilirsin.'
        return ''

    def refresh_appearance_controls(self):
        if self.window is None:
            return
        available = not self.appearance_blocked_reason()
        for button in getattr(self, 'theme_buttons', {}).values():
            button.set_sensitive(available)
        for name in ('profile_apply', 'profile_restore'):
            button = getattr(self, name, None)
            if button is not None:
                button.set_sensitive(available)
        for button in self.wallpaper_buttons:
            button.set_sensitive(available)
        if hasattr(self, 'material_panel'):
            self.material_panel.refresh_gate()

    def material_busy_changed(self, busy):
        self.theme_busy = busy
        self.refresh_appearance_controls()

    def appearance_worker(self, flag, operation, completed):
        """Bir görünüm işi; başlatma / beklenmeyen hata da kapıyı bırakır.

        Widget'lar yalnız ana GTK iş parçacığında güncellenir. Meşgul bayrağı
        tamamlamadan önce bırakılır; hatayı gizlemek için kilit silinmez.
        """
        def finished(result, error):
            setattr(self, flag, False)
            try:
                if self.window is not None:
                    completed(result, error)
            finally:
                self.refresh_appearance_controls()
            return GLib.SOURCE_REMOVE
        def work():
            result = error = None
            try:
                result = operation()
            except Exception as failure:
                logging.exception('Karşılayıcı görünüm işlemi tamamlanamadı')
                error = str(failure)
            GLib.idle_add(finished, result, error)
        try:
            self.refresh_appearance_controls()
            threading.Thread(target=work, daemon=True).start()
        except Exception as failure:
            logging.exception('Karşılayıcı görünüm işçisi başlatılamadı')
            finished(None, str(failure))

    def appearance_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.pack_start(label('Gündüz de senin, gece de.', 'heading'), False, False, 0)
        page.pack_start(label('Açık veya koyu temayı seç. Tarzın korunur; bu değişiklik yalnızca bu kullanıcıya aittir. Üst panel, başlıklar ve kapatma düğmeleri opak kalır.', 'muted', 75), False, False, 0)
        self.theme_buttons = {}
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if self.phone else Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        for mode, name in profiles.APPEARANCES.items():
            button = Gtk.Button(label=('☀  ' if mode == 'light' else '☾  ') + name)
            button.set_size_request(130, 76)
            button.get_style_context().add_class('style-card')
            button.connect('clicked', lambda _button, value=mode: self.change_appearance(value))
            self.theme_buttons[mode] = button
            row.pack_start(button, True, True, 0)
        page.pack_start(row, False, False, 0)
        self.theme_status = label('Tema etkin Xfce / GNOME / Plasma oturumunun kendi ayarlarına uygulanır. Kendi temasını kullanan uygulamalar farklı görünebilir; tüm üçüncü taraf pencerelere garanti verilmez.', 'muted', 75)
        page.pack_start(self.theme_status, False, False, 0)
        from desktop_ui import PreferencesPanel
        self.material_panel = PreferencesPanel(self.window,
            allowed=lambda: not self.appearance_blocked_reason(),
            on_busy=self.material_busy_changed, blocked_reason=self.appearance_blocked_reason)
        page.pack_start(self.material_panel, False, False, 0)
        self.effect_choice = self.material_panel.effects
        self.effect_apply = self.material_panel.apply_button
        for title, action in (('Görünüm ve yazı tipleri', 'appearance'), ('Ekran ayarları', 'display'),
                              ('Panel / widget / kısayol merkezi', None), ('Canlı CPU / RAM / ağ', 'monitor')):
            button = Gtk.Button(label=title)
            command = ['/usr/local/bin/oguzdows-desktop'] + (['--control', action] if action else [])
            button.connect('clicked', lambda _button, value=command: self.launch(value))
            page.pack_start(button, False, False, 0)
        return page

    def change_effects(self, *_):
        # Tek Uygula yolu: üst kapıyı önceden kapatıp ortak panelin kendi
        # isteğini başka bir tema işlemi sanmasına neden olma.
        self.material_panel.apply()

    def reload_panels(self, *_):
        if desktop_runtime.current() in ('gnome', 'kde'):
            self.launch(['/usr/local/bin/oguzdows-desktop', '--control', 'panels'])
            return
        if self.profile_busy or self.theme_busy or self.install_busy or self.external_installing or self.driver_busy:
            return
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
            text='Panel yerleşimi şimdi yenilensin mi?')
        dialog.format_secondary_text('Görev çubuğu kısa süreliğine kaybolup geri gelir. Açık uygulamalar kapanmaz. İstersen Vazgeç deyip oturumu daha sonra yeniden açabilirsin.')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        answer = dialog.run()
        dialog.destroy()
        if answer != Gtk.ResponseType.OK or self.appearance_blocked_reason():
            return
        self.profile_busy = True
        self.appearance_worker('profile_busy', profiles.reload_panels,
            lambda _result, error: self.style_finished(error if error is not None else
                'Panel yenileme isteği gönderildi; iskele ve görev çubuğunu kontrol et.'))

    def change_appearance(self, mode):
        if self.theme_busy or self.profile_busy or self.install_busy or self.external_installing or self.driver_busy:
            return
        self.theme_busy = True
        for button in self.theme_buttons.values():
            button.set_sensitive(False)
        self.theme_status.set_text('Tema uygulanıyor…')
        self.appearance_worker('theme_busy',
            lambda: desktop_preferences.update_and_apply({'appearance': mode}),
            lambda _result, error: self.appearance_finished(mode, error))

    def appearance_finished(self, mode, error):
        self.theme_busy = False
        for button in self.theme_buttons.values():
            button.set_sensitive(True)
        if error is not None:
            self.theme_status.set_text('Tema değiştirilemedi: ' + error)
        else:
            # Tema XSettings / GSettings arka ucundan gelir. Elle sabit Xfce
            # teması atayıp GNOME / Plasma veya renkli cam adını geri ezme.
            Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', mode == 'dark')
            if hasattr(self, 'material_panel'):
                self.material_panel.appearance.set_active_id(mode)
            self.theme_status.set_text(profiles.APPEARANCES[mode] + ' tema yerel masaüstüne uygulandı. Panel düzeni korundu.')
        return GLib.SOURCE_REMOVE

    def applications_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.pack_start(label('İhtiyacın olan, elinin altında.', 'heading'), False, False, 0)
        if not self.pc:
            page.pack_start(self.card('OğuzDows Mağaza', 'Yerel uygulama seçkisi, cihazının kendi imzalı APT kaynaklarından planlar. ARM64’te isteğe bağlı Flathub.', 'oguzdows-store', lambda *_: self.launch(['/usr/local/bin/oguzdows-store'])), False, False, 0)
        else:
            for title, text, icon, command in (
                    ('OğuzDows Mağaza', 'Uygulamaları keşfet. Mağazayı açmak paket kurmaz.', 'oguzdows-store', ['/usr/local/bin/oguzdows-store']),
                    ('OğuzDows Güncelleyici', 'Önce planı gör; sonra güncelleme ve firmware işlemlerini onayla.', 'oguzdows-update', ['/usr/local/bin/oguzdows-update'])):
                page.pack_start(self.card(title, text, icon, lambda _button, value=command: self.launch(value)), False, False, 0)
        page.pack_start(self.card('EXE / APK uyumluluğu', 'Dosyayı önce incele, sonra açık onay ver. Wine / Waydroid ve donanım koşulları ayrıca gerekir.', 'oguzdows-compatibility', lambda *_: self.launch(['/usr/local/bin/oguzdows-open', '--manager'])), False, False, 0)
        page.pack_start(self.card('Cihaz ve ARM merkezi', 'Pi Zero–5, diğer ARM kartları ve deneysel telefon katmanlarının gerçek sınırları.', 'oguzdows-device', lambda *_: self.launch(['/usr/local/bin/oguzdows-device'])), False, False, 0)
        page.pack_start(self.card('Çay Molası · Heybe · İmece', 'İstek üzerine yerel kültür ve paylaşım araçları.', 'oguzdows-imece', lambda *_: self.launch(['/usr/local/bin/oguzdows-imece'])), False, False, 0)
        page.pack_start(self.card('OğuzDows Haber', 'Hafif RSS / Atom okuyucu. Büyük yazı, çevrimdışı metin ve yalnızca istekle yenileme; webview yok.', 'oguzdows-news', lambda *_: self.launch(['/usr/local/bin/oguzdows-news'])), False, False, 0)
        page.pack_start(self.card('OğuzDows Başlat ve Masaüstü Merkezi', 'Yerel uygulama araması, sabitlenenler ve gerçek masaüstünün panel / widget / kısayol araçları.', 'oguzdows-hub', lambda *_: self.launch(['/usr/local/bin/oguzdows-desktop'])), False, False, 0)
        page.pack_start(self.card('Canlı Sistem İzleyici', 'CPU, RAM ve ağ grafikleri. Küçültünce / performans sekmesi gizlenince örnekleme durur.', 'oguzdows-monitor', lambda *_: self.launch(['/usr/local/bin/oguzdows-monitor'])), False, False, 0)
        page.pack_start(label('Mağaza, derlenen yerel GTK arayüzüdür. Sistem ve Flathub ayrı kaynaklardır; paketler plan ve açık onay olmadan kurulmaz. Açılışta mağaza servisi veya indirme çalışmaz.', 'muted', 75), False, False, 0)
        return page

    def support_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.pack_start(label('Birlikte çözeriz.', 'heading'), False, False, 0)
        page.pack_start(label('Rıfkı çevrimdışı ve konu sınırlı bir rehberdir. Mikrofon açmaz, yazdığın komutları çalıştırmaz, disk seçmez. Dinle düğmesi hazır doğal kayıtları çalar; kaydı olmayan yeni sayfalar için durum açıkça belirtilir.', 'muted', 75), False, False, 0)
        for title, action in (('Rıfkı’ya sor', self.open_assistant),
                              ('Yerel kullanım rehberi', lambda: self.launch(['/usr/bin/xdg-open', '/usr/share/doc/oguzdows/masaustu-ve-bakim.md'])),
                              ('Donanım raporu', self.show_drivers),
                              ('Ağ bağlantıları', lambda: self.launch(['/usr/bin/nm-connection-editor']))):
            button = Gtk.Button(label=title)
            button.connect('clicked', lambda _button, callback=action: callback())
            page.pack_start(button, False, False, 0)
        page.pack_start(label('Sorun bildirirken modelini, ISO sürümünü ve kişisel bilgileri ayıklanmış günlükleri paylaş. Raporlar kendiliğinden gönderilmez. Lisans ve gerekli kaynak atıfları korunur.', 'muted', 75), False, False, 0)
        return page

    def change_style(self, identifier):
        if desktop_runtime.current() in ('gnome', 'kde'):
            self.profile_status.set_text('Bu kartlar yalnız Xfce düzenidir. Etkin kabuğun kendi paneli için Masaüstü Merkezi’ni kullan; gerçek GNOME / Plasma paneli değiştirilmedi.')
            return
        if self.profile_busy or self.theme_busy or self.install_busy or self.external_installing or self.driver_busy:
            return
        reload_now = self.profile_reload.get_active()
        self.profile_busy = True
        self.profile_apply.set_sensitive(False)
        self.profile_restore.set_sensitive(False)
        self.profile_status.set_text('Yalnızca bu hesabın görünümü düzenleniyor…')
        def work():
            if identifier is None:
                # Önce yalnız bizim motoru bırak; en son tipli ilk ayarlar
                # yüklensin. Geri alınan kişisel kompozitör tekrar ezilmez.
                desktop_preferences.restore()
            else:
                # Panel / tema önce uygulanır; kompozitörün tek sahibi
                # aşağıdaki uzlaştırıcıdır. Picom durmadan Xfwm açılmaz.
                profiles.apply(identifier, manage_compositor=False)
                from desktop_state import config_path
                if config_path().exists():
                    desktop_preferences.session()
                else:
                    effects.reconcile()
            if reload_now:
                profiles.reload_panels()
            return ('İlk görünüm ayarların geri yüklendi.' if identifier is None else
                    profiles.PROFILES[identifier]['name'] + (' uygulandı; paneller yenilendi.' if reload_now else
                    ' kaydedildi; yeni iskele sonraki girişte yüklenir.'))
        self.appearance_worker('profile_busy', work,
            lambda result, error: self.style_finished('Görünüm değiştirilemedi: ' + error if error is not None else result))

    def style_finished(self, message):
        self.profile_busy = False
        self.profile_apply.set_sensitive(True)
        self.profile_restore.set_sensitive(True)
        self.profile_status.set_text(message)
        return GLib.SOURCE_REMOVE

    def populate_wallpapers(self):
        if self.wallpaper_buttons:
            return
        grid=self.wallpaper_grid
        for item in wallpapers.catalog():
            button = Gtk.Button()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_border_width(8)
            try:
                pixels = current_policy()['thumbnail_pixels']
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(item["preview"], pixels, pixels * 9 // 16, True)
                box.pack_start(Gtk.Image.new_from_pixbuf(pixbuf), False, False, 0)
            except GLib.Error:
                box.pack_start(Gtk.Image.new_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG), False, False, 0)
            box.pack_start(label(item["name"], "card-title", 25), False, False, 0)
            box.pack_start(label("Masaüstüne uygula", "muted"), False, False, 0)
            button.add(box)
            button.connect("clicked", lambda _, choice=item: self.apply_wallpaper(choice))
            grid.add(button)
            self.wallpaper_buttons.append(button)
        grid.show_all()
        self.refresh_appearance_controls()

    def apply_wallpaper(self, item):
        if self.install_busy or self.external_installing or self.theme_busy or self.profile_busy or self.driver_busy:
            return
        identifier, name = item['id'], item['name']
        self.theme_busy = True
        for button in self.wallpaper_buttons:
            button.set_sensitive(False)
        self.wallpaper_status.set_text("Duvar kâğıdı uygulanıyor…")
        self.appearance_worker('theme_busy', lambda: desktop_preferences.update_and_apply({'wallpaper': identifier}),
            lambda _result, error: self.wallpaper_finished('Duvar kâğıdı uygulanamadı: ' + error if error is not None else
                name + ' uygulandı; seçimin kaydedildi.'))

    def wallpaper_finished(self, text):
        self.theme_busy = False
        self.wallpaper_status.set_text(text)
        if self.rifki:
            self.rifki.say(text)
        for button in self.wallpaper_buttons:
            button.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def page_changed(self, *_):
        page=self.stack.get_visible_child_name()
        self.ensure_page(page)
        if page=='wallpapers':
            self.populate_wallpapers()
        if page == "hardware" and not self.report_text:
            self.load_report()
        row = self.sidebar_rows.get(page)
        if row is not None and self.sidebar.get_selected_row() is not row:
            self.sidebar.select_row(row)
        if row is None:
            self.sidebar.unselect_all()
        self.previous_button.set_sensitive(welcome_model.adjacent(page, -1) is not None)
        self.next_button.set_sensitive(welcome_model.adjacent(page, 1) is not None)
        if self.rifki:
            self.rifki.current_page = page
            self.rifki.page_words[page] = welcome_model.page_text(page, self.context)
        # Tek otomatik anlatım tercihi; yardımcı açık diye kapatılan sesi geri açma.
        self.queue_narration()

    def show_drivers(self):
        self.stack.set_visible_child_name("hardware")

    def load_report(self):
        if self.report_loading or self.driver_busy or self.install_busy or self.external_installing:
            return
        self.report_loading = True
        self.refresh_button.set_sensitive(False)
        self.spinner.start()
        self.status.set_text("Donanım okunuyor…")
        def work():
            try:
                text = report()
                broadcom, intel = ([], []) if not self.pc else (supported_broadcom(), supported_intel_legacy())
            except Exception:
                text, broadcom, intel = "Donanım raporu okunamadı. Yeniden deneyebilirsin.", [], []
            GLib.idle_add(self.report_ready, text, broadcom, intel)
        threading.Thread(target=work, daemon=True).start()

    def report_ready(self, text, broadcom, intel):
        self.report_loading = False
        self.report_text = text
        self.driver_eligibility = (bool(broadcom),bool(intel))
        self.report_view.get_buffer().set_text(text)
        self.spinner.stop()
        self.refresh_button.set_sensitive(True)
        self.save_button.set_sensitive(True)
        self.broadcom_button.set_sensitive(self.pc and bool(broadcom) and not self.driver_busy and not self.install_busy and not self.external_installing)
        self.intel_button.set_sensitive(self.pc and bool(intel) and not self.driver_busy and not self.install_busy and not self.external_installing)
        for button, devices in ((self.broadcom_button, broadcom), (self.intel_button, intel)):
            button.set_tooltip_text("Algılanan uyumlu aygıt: " + ", ".join(devices) if devices else "Bu ek sürücüyle eşleşen bir kart algılanmadı. Raporundaki PCI/USB kimliğini paylaşabilirsin.")
        self.status.set_text("Rapor hazır. SÜRÜCÜ BAĞLI DEĞİL satırları ayrıca incelenmelidir. Bilgilerin gönderilmedi.")
        return GLib.SOURCE_REMOVE

    def save_report(self, *_):
        dialog = Gtk.FileChooserDialog(title="OğuzDows donanım raporunu kaydet", transient_for=self.window, action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons("Vazgeç", Gtk.ResponseType.CANCEL, "Kaydet", Gtk.ResponseType.OK)
        dialog.set_current_name("OguzDows-donanim.txt")
        dialog.set_do_overwrite_confirmation(True)
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                Path(dialog.get_filename()).write_text(self.report_text, encoding="utf-8")
            except OSError:
                self.message("Rapor kaydedilemedi.", "Seçtiğin klasörün yazılabilir olduğundan emin ol.")
        dialog.destroy()

    def can_install(self):
        return self.pc and is_live() and Path("/usr/local/sbin/oguzdows-installer").is_file()

    def install(self, *_):
        if self.install_busy or self.external_installing or self.driver_busy or self.theme_busy or self.profile_busy:
            self.message("Başka bir işlem devam ediyor.", "Kurucu veya sürücü işlemi tamamlanana kadar bekle.")
            return GLib.SOURCE_REMOVE
        if not self.can_install():
            self.message("Kurulum canlı USB'den başlatılır.", "Canlı OğuzDows USB'siyle açıldığından emin ol.")
            return GLib.SOURCE_REMOVE
        self.install_busy = True
        self.refresh_appearance_controls()
        self.installing_action.set_state(GLib.Variant('b', True))
        self.stop_narration()
        self.previous_session = installer_state.read_status().get('session')
        self.install_data = {}
        if self.rifki:
            self.rifki.set_installing(True)
        GLib.timeout_add(800, self.poll_installation)
        self.install_button.set_sensitive(False)
        self.broadcom_button.set_sensitive(False)
        self.intel_button.set_sensitive(False)
        self.install_status.set_text("Yönetici onayı bekleniyor / OğuzDows kurucusu açık…")
        def work():
            try:
                result = subprocess.run(["/usr/bin/pkexec", "/usr/local/sbin/oguzdows-installer"], capture_output=True, text=True, errors="replace", check=False)
                code, detail, output = result.returncode, result.stderr.strip()[-5000:], result.stdout
            except OSError as error:
                code, detail, output = 1, str(error), ''
            GLib.idle_add(self.install_finished, code, detail, output)
        threading.Thread(target=work, daemon=True).start()
        return GLib.SOURCE_REMOVE

    def result_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.result_title = label("Kurulum sonucu", "heading", 40)
        self.result_detail = label("Henüz sonuç yok.", "", 90)
        page.pack_start(self.result_title, False, False, 0)
        page.pack_start(self.result_detail, False, False, 0)
        page.pack_start(label("Günlük: /var/log/oguzdows/installer.log", "muted", 80), False, False, 0)
        self.result_log = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.result_log.set_left_margin(10)
        self.result_log.set_top_margin(10)
        scroll = Gtk.ScrolledWindow()
        scroll.set_size_request(-1, 150)
        scroll.add(self.result_log)
        page.pack_start(scroll, True, True, 0)
        back = Gtk.Button(label="Rehbere dön")
        back.connect("clicked", lambda *_: self.stack.set_visible_child_name("welcome"))
        page.pack_start(back, False, False, 0)
        report = Gtk.Button(label="Salt-okunur disk açılış raporu")
        report.connect("clicked", lambda *_: self.show_boot_report())
        page.pack_start(report, False, False, 0)
        self.restart_button = Gtk.Button(label="Bilgisayarı yeniden başlat…")
        self.restart_button.set_no_show_all(True)
        self.restart_button.connect("clicked", self.restart)
        page.pack_start(self.restart_button, False, False, 0)
        return page

    def restart(self, *_):
        if self.install_data.get('outcome') != 'success' or self.install_data.get('complete') is not True:
            return
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.YES_NO,
                                   text="Kurulum tamamlandı. Şimdi yeniden başlatılsın mı?")
        dialog.format_secondary_text("Açık dosyalarını kaydet. Bilgisayar kapanırken USB'yi çıkar; sonraki açılışta iç diski seç. Bu işlem otomatik yapılmaz.")
        answer = dialog.run()
        dialog.destroy()
        if answer == Gtk.ResponseType.YES:
            self.launch(['/usr/bin/xfce4-session-logout', '--reboot'])

    def poll_installation(self):
        if not self.install_busy:
            return GLib.SOURCE_REMOVE
        data = installer_state.read_status()
        if data and data.get('session') != self.previous_session:
            self.install_data = data
            if self.rifki:
                self.rifki.installation(data)
        return GLib.SOURCE_CONTINUE

    def install_finished(self, code, detail, output=''):
        self.install_busy = False
        self.set_external_installing(self.external_installing)
        data = installer_state.from_output(code, output)
        self.install_data = data
        title, explanation = installer_state.description(data)
        self.install_status.set_text(title)
        self.result_title.set_text(title)
        self.result_detail.set_text(explanation)
        self.result_log.get_buffer().set_text(detail or 'Kurucunun kapanışında ek hata çıktısı yok. Ayrıntılı günlük yukarıdaki yoldadır.')
        success = data.get('outcome') == 'success' and data.get('complete') is True
        self.restart_button.set_visible(success)
        self.stack.set_visible_child_name('install-result')
        self.window.present()
        if self.rifki:
            self.rifki.set_installing(self.external_installing)
            self.rifki.installation(data)
        if not success:
            self.message(title, (explanation + '\n\n' + detail + '\n\nGünlük: /var/log/oguzdows/installer.log').strip(),False)
        return GLib.SOURCE_REMOVE

    def open_assistant(self):
        if self.rifki is None:
            callbacks = {
                'boot-report': self.show_boot_report,
                'network': lambda: self.launch(['/usr/bin/nm-connection-editor']),
                'drivers': self.show_drivers,
                'wallpapers': lambda: self.navigate('wallpapers'),
                'install': lambda: self.navigate('welcome'),
                'narration': lambda value: self.narration_switch.set_active(value),
                'styles': lambda: self.navigate('styles'),
                'store': lambda: self.launch(['/usr/local/bin/oguzdows-store']),
                'updates': lambda: self.launch(['/usr/local/bin/oguzdows-update'] if self.pc else ['/usr/local/bin/oguzdows-device']),
                'compatibility': lambda: self.launch(['/usr/local/bin/oguzdows-open', '--manager']),
                'culture': lambda: self.launch(['/usr/local/bin/oguzdows-imece']),
                'devices': lambda: self.launch(['/usr/local/bin/oguzdows-device']),
            }
            try:
                from rifki import Companion
                self.stop_narration()
                self.rifki = Companion(self,callbacks,reduced=self.reduced,installing=self.install_busy or self.external_installing, speaker=self.speaker)
            except (ImportError,OSError,GLib.Error):
                self.message('Rıfkı açılamadı.','Kurulum yardımcısı bağımsızdır; OğuzDows’u kur düğmesini kullanabilirsin.')
                return
            self.rifki.connect('destroy', self.assistant_closed)
            self.rifki.show_all()
        self.rifki.current_page=self.stack.get_visible_child_name()
        self.rifki.page_words[self.rifki.current_page] = welcome_model.page_text(self.rifki.current_page, self.context)
        self.rifki.set_keep_above(False)
        self.rifki.present()
        if self.install_data:
            self.rifki.installation(self.install_data)

    def navigate(self, page):
        self.stack.set_visible_child_name(page)
        self.window.present()

    def assistant_closed(self, *_):
        self.rifki = None

    def show_boot_report(self):
        if self.report_loading:
            return
        self.report_loading = True
        self.stack.set_visible_child_name('hardware')
        self.status.set_text('Disk ve açılış bilgileri yalnızca okunuyor…')
        def work():
            text = boot_report.report()
            GLib.idle_add(self.boot_report_ready, text)
        threading.Thread(target=work, daemon=True).start()

    def boot_report_ready(self, text):
        self.report_ready(text, [], [])
        self.status.set_text('Salt-okunur açılış raporu hazır. Disk veya firmware ayarı değiştirilmedi; istersen raporu kaydet.')
        return GLib.SOURCE_REMOVE

    def launch(self, command):
        try:
            subprocess.Popen(command)
        except OSError:
            self.message("Uygulama başlatılamadı.", "Gerekli bileşenin kurulu olduğunu kontrol et.")

    def install_driver(self, action):
        if self.driver_busy or self.report_loading or self.install_busy or self.external_installing or self.theme_busy or self.profile_busy:
            return
        text = offline.license_text(action)
        if not text:
            self.message("Gömülü sürücü lisansı bulunamadı.", "Güncel OğuzDows ISO'sunu kullan; paket lisansı olmadan kurulum başlatılmadı.")
            return
        ready = offline.payload(action) is not None and (action != "broadcom" or offline.headers_available())
        if not ready and action != "broadcom":
            self.message("Gömülü paket doğrulanamadı.", "ISO bütünlüğünü SHA-256 ile denetle. Hiçbir değişiklik yapılmadı.")
            return
        title = "Broadcom STA sürücüsü" if action == "broadcom" else "Intel 2100 / 2200 / 2915 firmware'i"
        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.add_button("Vazgeç", Gtk.ResponseType.CANCEL)
        confirm = dialog.add_button("Onayla ve kur", Gtk.ResponseType.OK)
        confirm.set_sensitive(False)
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_border_width(16)
        note = "ISO'daki paket kullanılacak; internet gerekmez." if ready else "Çekirdeğin değişmiş: internetten eşleşen başlıklar ve STA indirilecek."
        content.pack_start(label(note + " Mevcut açık sürücünün yerini alabilir. Canlıda onayladığın seçim disk kurulumuna taşınır.", "", 75), False, False, 0)
        view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_size_request(460, 240)
        scroll.add(view)
        content.pack_start(scroll, True, True, 0)
        consent = Gtk.CheckButton(label="Yukarıdaki özgün lisansı okudum ve kabul ediyorum.")
        consent.connect("toggled", lambda button: confirm.set_sensitive(button.get_active()))
        content.pack_start(consent, False, False, 0)
        dialog.show_all()
        answer = dialog.run()
        agreed = consent.get_active()
        dialog.destroy()
        if answer != Gtk.ResponseType.OK or not agreed:
            return
        self.driver_busy = True
        self.refresh_appearance_controls()
        self.installing_action.set_state(GLib.Variant('b', True))
        self.broadcom_button.set_sensitive(False)
        self.intel_button.set_sensitive(False)
        self.refresh_button.set_sensitive(False)
        self.install_button.set_sensitive(False)
        self.spinner.start()
        self.status.set_text("Yönetici onayı bekleniyor / sürücü kuruluyor. Birkaç dakika sürebilir…")
        def work():
            try:
                command = ["/usr/bin/pkexec", "/usr/local/sbin/oguzdows-driver-helper", action]
                if ready:
                    command.append("--offline")
                result = subprocess.run(command, capture_output=True, text=True, errors="replace", check=False)
                message = result.stdout.strip() if result.returncode == 0 else "Sürücü işlemi tamamlanmadı veya yetkilendirme iptal edildi. " + result.stderr.strip()[-1200:]
            except OSError:
                message = "Sürücü yardımcısı başlatılamadı."
            GLib.idle_add(self.driver_finished, message)
        threading.Thread(target=work, daemon=True).start()

    def driver_finished(self, text):
        if self.rifki:
            self.rifki.say(text)
        self.driver_busy = False
        self.spinner.stop()
        self.refresh_button.set_sensitive(True)
        self.set_external_installing(self.external_installing)
        self.status.set_text(text)
        return GLib.SOURCE_REMOVE

    def message(self, title, detail, narrate=True):
        if self.rifki and narrate:
            self.rifki.say(title+' '+detail)
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CLOSE, text=title)
        dialog.format_secondary_text(detail)
        dialog.run()
        dialog.destroy()

    def on_close(self, *_):
        if self.driver_busy or self.install_busy or self.profile_busy or self.theme_busy:
            self.message('Kurucu / ayar işlemi devam ediyor.', 'İşlemi yarıda kesmemek için önce kurucuyu kapat veya sürücü / görünüm işleminin bitmesini bekle.')
            return True
        if self.mark_on_close:
            try:
                welcome_model.save_autostart_preference(
                    self.state_file.parent, self.context, self.show_again.get_active())
            except OSError:
                print("OğuzDows karşılama tercihi kaydedilemedi.", file=sys.stderr)
        self.stop_narration()
        if self.rifki:
            self.rifki.destroy()
        if self.speaker:
            self.speaker.close()
        self.window = None
        return False


if __name__ == "__main__":
    raise SystemExit(Welcome().run(sys.argv))
