#!/usr/bin/env python3
"""Xvfb altında gerçek GTK penceresini açar; paket kurmaz ve disk silmez.

CI, önce temayı ve render-assets.py çıktısını /usr/share altına yerleştirir.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from support import ROOT, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("test-results"))
    parser.add_argument("--phone", action="store_true", help="Deneysel dar telefon karşılayıcısı; fiziksel cihaz testi değil")
    parser.add_argument("--live", action="store_true", help="Canlı PC karşılayıcısını denetle")
    parser.add_argument("--pi", action="store_true", help="Pi sayfa dalını host GTK üzerinde denetle; kart taklidi değildir")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not Gtk.init_check([])[0]:
        raise RuntimeError("GTK için bir görüntü sunucusu gerekli; Xvfb ile çalıştırın.")
    errors = []
    original_hook = sys.excepthook
    def report_exception(kind, value, trace):
        if str(value) not in errors:
            errors.append(str(value))
            original_hook(kind, value, trace)
    sys.excepthook = report_exception
    with tempfile.TemporaryDirectory(prefix="oguzdows-ui-") as state:
        os.environ["XDG_STATE_HOME"] = state
        os.environ["XDG_CONFIG_HOME"] = state
        os.environ["OGUZDOWS_TESTING"] = "1"
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-theme-name", "OguzDows")
        settings.set_property("gtk-icon-theme-name", "OguzDows")
        icons = Gtk.IconTheme.get_default()
        for name in ("battery-level-0-symbolic", "battery-level-50-charging-symbolic", "battery-level-100-charged-symbolic"):
            info = icons.lookup_icon(name, 24, 0)
            assert info and '/OguzDows/' in info.get_filename(), name
            assert not info.is_symbolic(), "Nazar PNG renkleri sembolik renge dönüşmemeli"
            assert icons.load_icon(name, 24, 0).get_width() == 24
        assert icons.lookup_icon("battery-missing-symbolic", 24, 0), "Belirsiz pil durumu için ayrı simge olmalı"
        assert icons.lookup_icon("ac-adapter-symbolic", 24, 0), "Pilsiz AC durumu için ayrı fiş simgesi olmalı"
        for name in ('OguzDows', 'OguzDowsLight', 'OguzDowsXP', 'OguzDowsXPDark', 'OguzDowsMac', 'OguzDowsMacDark', 'OguzDowsGnome', 'OguzDowsGnomeDark'):
            provider = Gtk.CssProvider()
            provider.load_from_path(str(ROOT / 'system/usr/share/themes' / name / 'gtk-3.0/gtk.css'))
        notify_provider = Gtk.CssProvider()
        notify_provider.load_from_path(str(ROOT / "system/usr/share/themes/OguzDows/xfce-notify-4.0/gtk.css"))
        welcome = load("oguzdows_welcome_smoke", "system/usr/lib/oguzdows/welcome.py")
        welcome.is_live = lambda: args.live
        if args.phone:
            welcome.device_support.current = lambda: {'id': 'pinephone', 'arch': 'arm64', 'phone': True, 'name': 'PinePhone · host UI', 'tier': 'Deneysel'}
        if args.pi:
            welcome.is_pi = lambda: True
            welcome.pi_model = lambda: "Raspberry Pi · arayüz kontrolü (host)"
            welcome.current_policy = lambda: {"profile": "mini", "animations": False, "thumbnail_pixels": 160}
        app = welcome.Welcome()
        app.register(None)
        app.activate()
        app.mark_on_close = True
        loop = GLib.MainLoop()

        def screenshot(name):
            for _ in range(20):
                if not Gtk.events_pending():
                    break
                Gtk.main_iteration_do(False)
            app.window.get_window().process_updates(True)
            window = app.window.get_window()
            width, height = app.window.get_size()
            pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
            if pixbuf is None:
                raise AssertionError("GTK ekran görüntüsü alınamadı")
            pixbuf.savev(str(args.output / name), "png", [], [])

        def start():
            try:
                assert app.stack.get_visible_child_name() == "welcome"
                assert not app.show_again.get_active()
                assert len(app.sidebar.get_children()) == 7
                assert app.loaded_pages == {'welcome', 'hardware'}, 'Diğer sayfalar ilk ziyaretten önce oluşturulmamalı'
                assert not app.previous_button.get_sensitive()
                assert app.next_button.get_sensitive()
                if not args.pi:
                    assert app.install_button.get_visible() == args.live, 'Kurulu karşılayıcı kurulum kartı göstermemeli'
                if args.pi:
                    assert app.install_button.get_sensitive(), "Pi ayar kartı etkin olmalı"
                    assert not app.broadcom_button.get_visible(), "Pi'de PC STA düğmesi görünmemeli"
                    assert not app.intel_button.get_visible(), "Pi'de PC firmware düğmesi görünmemeli"
                    assert "SD/USB" in app.install_status.get_text()
                if args.phone:
                    assert app.window.get_size()[0] <= app.window.get_screen().get_width(), 'Telefon karşılayıcısı ekran dışına taşmamalı'
                screenshot("welcome.png")
                app.window.resize(min(400, app.window.get_screen().get_width() - 24) if args.phone else 600, 440)
            except Exception as error:
                errors.append(str(error))
            return GLib.SOURCE_REMOVE

        def gallery():
            try:
                screenshot("welcome-small.png")
                assert len(app.wallpaper_buttons)==0, 'Galeri başlangıçta yüklenmemeli'
                app.stack.set_visible_child_name("wallpapers")
                assert len(app.wallpaper_buttons)==20, 'Yirmi görsel yalnızca galeri açılınca yüklenmeli'
            except Exception as error:
                errors.append(str(error))
            return GLib.SOURCE_REMOVE

        def hardware():
            try:
                screenshot('wallpapers.png')
                app.stack.set_visible_child_name('styles')
                assert len(app.profile_choice.get_model()) == 5
                assert len(app.profile_buttons) == 6
                screenshot('desktop-styles.png')
                app.step_page(1)
                assert app.stack.get_visible_child_name() == 'appearance'
                assert app.sidebar.get_selected_row().page_name == 'appearance'
                assert set(app.theme_buttons) == {'light', 'dark'}
                screenshot('appearance.png')
                app.navigate('support')
                assert not app.next_button.get_sensitive()
                app.navigate('applications')
                screenshot('applications.png')
                app.window.resize(min(400, app.window.get_screen().get_width() - 24) if args.phone else 900, 600)
                app.show_drivers()
            except Exception as error:
                errors.append(str(error))
            return GLib.SOURCE_REMOVE

        def closed(*_):
            # Gtk.Window.close() kapanış olayını kuyruğa koyar. Tercih ancak
            # delete-event işlendikten sonra yazılır; önce kontrol etmek yarıştı.
            try:
                assert app.state_file.is_file(), "İlk açılış tercihi kaydedilmedi"
            except Exception as error:
                errors.append(str(error))
            finally:
                loop.quit()

        def finish():
            if app.report_loading:
                return GLib.SOURCE_CONTINUE
            try:
                assert app.stack.get_visible_child_name() == "hardware"
                assert app.report_text, "Donanım raporu üretilmedi"
                assert app.save_button.get_sensitive()
                assert app.intel_button is not None
                assert app.install_status is not None
                # Başlatma hatası sessizce kaybolmasın; gerçek kurucu çağırma.
                original_message = app.message
                messages = []
                app.message = lambda *args: messages.append(args)
                app.install_finished(1, "Kurucu başlatma hata testi")
                assert messages and "Kurucu başlatma hata testi" in messages[0][1]
                assert app.stack.get_visible_child_name() == "install-result"
                assert not app.restart_button.get_visible()
                screenshot("install-failure.png")
                app.install_finished(0, "")
                assert "doğrulanamadı" in app.result_title.get_text()
                data = {"version": 1, "session": "a" * 32, "outcome": "success", "complete": True, "stage": "complete"}
                import json
                app.install_finished(0, "", welcome.installer_state.PREFIX + json.dumps(data))
                assert "başarıyla" in app.result_title.get_text()
                assert app.restart_button.get_visible()
                screenshot("install-success.png")
                app.open_assistant()
                assert set(app.rifki.avatar.frames)=={'idle','blink','talk'}
                assert app.rifki.avatar.timer is None
                assert not app.rifki.motion.get_active()
                assert 'rifki_pet' not in sys.modules and 'rifki_scene' not in sys.modules
                spoken=[]
                original_speak=app.rifki.speaker.speak
                app.rifki.speaker.speak=lambda text,*_:spoken.append(text)
                for topic in ('disk','boot','internet','sürücü','duvar','pil','kurulum','bilinmeyen soru'):
                    app.rifki.ask(topic)
                assert len(spoken)==8 and all(spoken)
                app.rifki.set_installing(True)
                app.rifki.say('Kurulumda sessiz metin')
                app.rifki.repeat()
                assert len(spoken)==8, 'Kurulum sırasında otomatik ses çağrılmamalı'
                app.rifki.set_installing(False)
                app.rifki.narration.set_active(False)
                assert not app.narration_switch.get_active(), 'Aynı otomatik anlatım tercihi paylaşılmalı'
                app.navigate('styles')
                assert len(spoken) == 8, 'Rıfkı açık diye kapalı sayfa anlatımı geri açılmamalı'
                app.rifki.narrate_page('styles', force=True)
                assert len(spoken) == 9 and spoken[-1] == welcome.welcome_model.page_text('styles', app.context)
                app.narration_switch.set_active(True)
                assert app.rifki.narration.get_active()
                app.rifki.speaker.speak=original_speak
                app.rifki.ask("diskten açılmıyor")
                assert app.rifki.action_name == 'boot-report'
                app.rifki.speaker.set_enabled(False)
                app.rifki.avatar.queue_draw()
                def final_close():
                    try:
                        window = app.rifki.get_window()
                        width, height = app.rifki.get_size()
                        pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
                        assert pixbuf is not None
                        pixbuf.savev(str(args.output / 'rifki.png'), 'png', [], [])
                        app.rifki.destroy()
                        app.show_drivers()
                        screenshot("hardware.png")
                        app.message = original_message
                        app.window.connect("destroy", closed)
                        app.window.close()
                    except Exception as error:
                        errors.append(str(error))
                        loop.quit()
                    return GLib.SOURCE_REMOVE
                GLib.timeout_add(450, final_close)
            except Exception as error:
                errors.append(str(error))
                loop.quit()
            return GLib.SOURCE_REMOVE

        def timed_out():
            errors.append("GTK kontrolü 45 saniyede tamamlanmadı.")
            loop.quit()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(350, start)
        GLib.timeout_add(800, gallery)
        GLib.timeout_add(1400, hardware)
        GLib.timeout_add(5000, finish)
        GLib.timeout_add(45000, timed_out)
        loop.run()
    sys.excepthook = original_hook
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("GTK karşılama, küçük ekran, donanım sekmesi ve ilk açılış tercihi doğrulandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
