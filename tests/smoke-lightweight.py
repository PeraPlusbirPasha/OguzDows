#!/usr/bin/env python3
"""Gerçek GTK: hafif giriş yollarını, boşta yükü ve kurulumda susmayı denetle.

Xvfb üzerinde ölçüm; canlı ISO / donanım performansı veya tam kurulum testi değil.
Kurucu işçisi bilerek Event üzerinde bekletilir. pkexec / disk aracı çağrılmaz.
Her bileşeni ayrı Python sürecinde çalıştırın; ölçümler birbirini kirletmesin.
"""
import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from support import load, native_gtk_imports


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component',choices=('welcome','rifki','installer','coordination'),required=True)
    parser.add_argument('--output',type=Path,default=Path('test-results'))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    errors=[]
    original_hook=sys.excepthook
    def exception(kind,value,trace):
        errors.append(str(value))
        original_hook(kind,value,trace)
    sys.excepthook=exception
    started=time.monotonic()
    main_thread=threading.get_ident()
    with tempfile.TemporaryDirectory(prefix='oguzdows-light-') as temporary:
        os.environ.update(XDG_CONFIG_HOME=temporary,XDG_STATE_HOME=temporary,OGUZDOWS_TESTING='1')
        import gi
        gi.require_version('Gtk','3.0')
        gi.require_version('Gdk','3.0')
        from gi.repository import Gdk, GLib, Gtk
        assert Gtk.init_check([])[0], 'Xvfb gerekli'
        toolkit_imports=native_gtk_imports(Gtk, Gdk)
        settings=Gtk.Settings.get_default()
        settings.set_property('gtk-theme-name','OguzDows')
        settings.set_property('gtk-enable-animations',False)
        loop=GLib.MainLoop()
        release=threading.Event()
        worker_threads=[]
        metrics={'component':args.component,'environment':'CI / Xvfb, privileged worker stubbed, not physical hardware',
                 'gtk_binding_imports_before_application':sorted(toolkit_imports)}
        app=None
        guide=None
        peer=None
        def fake_installer():
            worker_threads.append(threading.get_ident())
            if not release.wait(12):
                raise RuntimeError('Test işçisi zamanında serbest bırakılmadı')
            return 126,'','Deneme: yönetici onayı iptal edildi.'
        if args.component=='welcome':
            module=load('light_welcome_native','system/usr/lib/oguzdows/welcome.py')
            app=module.Welcome()
            app.register(None)
            app.activate()
            window=app.window
        elif args.component=='rifki':
            module=load('light_rifki_native','system/usr/lib/oguzdows/rifki.py')
            app=Gtk.Application(application_id='org.oguzdows.HafifTest')
            app.register(None)
            window=module.Companion(app,{},reduced=False)
            window.show_all()
        elif args.component=='installer':
            module=load('light_installer_native','system/usr/lib/oguzdows/install_launcher.py')
            module.run_installer=fake_installer
            app=module.Installer()
            app.register(None)
            app.activate()
            window=app.window
            app.activate()
            assert app.starts==1, 'Aynı başlatıcı ikinci işçi açmamalı'
        else:
            # İki Gtk.Application aynı süreçte GApplication kaydını paylaşamaz.
            # Üründeki gibi gerçekten iki ayrı süreç kullan; root işi yine stub.
            peer=subprocess.Popen([sys.executable,str(Path(__file__).with_name('launcher-peer.py'))],stdin=subprocess.PIPE,text=True)
            guide_module=load('light_coordination_guide','system/usr/lib/oguzdows/welcome.py')
            guide=guide_module.Welcome()
            guide.register(None)
            guide.activate()
            guide.open_assistant()
            app=guide
            window=guide.window
        def send_peer(word):
            peer.stdin.write(word+'\n')
            peer.stdin.flush()
        metrics['activation_ms']=round((time.monotonic()-started)*1000,2)
        last_heartbeat=[time.monotonic()]
        gaps=[]
        idle={}
        def heartbeat():
            now=time.monotonic()
            gaps.append(now-last_heartbeat[0])
            last_heartbeat[0]=now
            return GLib.SOURCE_CONTINUE
        GLib.timeout_add(100,heartbeat)
        def begin_idle():
            idle.update(wall=time.monotonic(),cpu=time.process_time())
            gaps.clear()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(700,begin_idle)
        def stop_with_error(error):
            errors.append(str(error))
            release.set()
            loop.quit()
        def screenshot():
            native=window.get_window()
            width,height=window.get_size()
            pixbuf=Gdk.pixbuf_get_from_window(native,0,0,width,height)
            assert pixbuf is not None
            pixbuf.savev(str(args.output/('lightweight-'+args.component+'.png')),'png',[],[])
        def finish():
            try:
                elapsed=time.monotonic()-idle['wall']
                cpu=time.process_time()-idle['cpu']
                metrics.update(idle_wall_seconds=round(elapsed,4),idle_cpu_seconds=round(cpu,4),
                               idle_one_core_percent=round(100*cpu/elapsed,2),
                               max_event_loop_gap_ms=round(max(gaps,default=0)*1000,2),
                               max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                assert cpu/elapsed<.20, 'Sabit arayüz boşta tek çekirdeğin %20’sini tüketmemeli'
                assert max(gaps,default=0)<1.5, 'Boşta GTK olay döngüsü 1.5 saniye kilitlenmemeli'
                forbidden={'PIL','cairo','rifki_scene','rifki_motion','rifki_pet'} - toolkit_imports
                assert not forbidden.intersection(sys.modules), str(forbidden.intersection(sys.modules))
                if args.component=='welcome':
                    assert app.loaded_pages == {'welcome', 'hardware'}
                    metrics['initial_loaded_pages'] = sorted(app.loaded_pages)
                    assert app.rifki is None and 'rifki' not in sys.modules
                    assert len(app.wallpaper_buttons)==0, 'Galeri başta decode edilmemeli'
                elif args.component=='rifki':
                    assert set(window.avatar.frames)=={'idle','blink','talk'}
                    assert window.avatar.timer is None and window.avatar.blink_source is None
                    assert not window.motion.get_active()
                    window.avatar.allow_motion=True
                    window.avatar.voice_changed(True)
                    assert window.avatar.timer is not None
                    window.set_installing(True)
                    assert window.avatar.frozen and window.avatar.timer is None
                    window.avatar.voice_changed(True)
                    assert window.avatar.timer is None, 'Kurulumda hareket açılamamalı'
                    window.set_installing(False)
                    window.avatar.voice_changed(False)
                    window.avatar.blink()
                    assert window.avatar.blink_source is not None
                    window.hide()
                    assert window.avatar.timer is None and window.avatar.blink_source is None
                    window.show_all()
                elif args.component=='installer':
                    assert worker_threads and all(t!=main_thread for t in worker_threads)
                    assert app.busy and app.activity.get_state().get_boolean()
                    assert 'rifki' not in sys.modules and 'wallpapers' not in sys.modules
                else:
                    assert peer.poll() is None, 'Test başlatıcı süreci erken kapandı'
                    assert guide.external_installing and guide.rifki.installing
                    assert guide.rifki.avatar.frozen and guide.rifki.avatar.timer is None
                    # Başlatıcı zaten açıkken sonradan açılan kedi de sessiz.
                    guide.rifki.destroy()
                    guide.open_assistant()
                    assert guide.rifki.installing and not guide.rifki.speaker.playing
                screenshot()
                release.set()
                if peer is not None:
                    send_peer('finish')
                if args.component in ('installer','coordination'):
                    GLib.timeout_add(150,after_worker)
                else:
                    window.destroy()
                    loop.quit()
            except Exception as error:
                stop_with_error(error)
            return GLib.SOURCE_REMOVE
        def after_worker():
            try:
                if guide is not None:
                    if guide.external_installing:
                        return GLib.SOURCE_CONTINUE
                    assert not guide.rifki.installing
                    guide.rifki.avatar.reduced=False
                    guide.rifki.avatar.allow_motion=True
                    guide.rifki.avatar.voice_changed(True)
                    assert guide.rifki.avatar.timer is not None
                    send_peer('busy')
                    GLib.timeout_add(200,after_repause)
                else:
                    if app.busy:
                        return GLib.SOURCE_CONTINUE
                    assert not app.activity.get_state().get_boolean()
                    assert app.data['outcome']=='cancelled'
                    assert not app.restart.get_visible() and app.close_button.get_sensitive()
                    window.destroy()
                    loop.quit()
            except Exception as error:
                stop_with_error(error)
            return GLib.SOURCE_REMOVE
        def after_repause():
            try:
                if not guide.external_installing:
                    return GLib.SOURCE_CONTINUE
                assert guide.rifki.installing
                assert guide.rifki.avatar.timer is None
                metrics['dbus_pause_resume_verified']=True
                send_peer('quit')
                guide.rifki.destroy()
                guide.window.destroy()
                loop.quit()
            except Exception as error:
                stop_with_error(error)
            return GLib.SOURCE_REMOVE
        def timeout():
            stop_with_error('Hafif arayüz kontrolü 10 saniyede bitmedi')
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(3200,finish)
        GLib.timeout_add(10000,timeout)
        loop.run()
        if peer is not None:
            try:
                send_peer('quit')
            except (BrokenPipeError,OSError):
                pass
            peer.stdin.close()
            try:
                code=peer.wait(timeout=3)
            except subprocess.TimeoutExpired:
                peer.terminate()
                code=peer.wait(timeout=3)
            if code:
                errors.append('Test başlatıcı süreci hata ile kapandı: '+str(code))
        metrics['errors']=errors
        (args.output/('lightweight-'+args.component+'.json')).write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
        summary=json.dumps(metrics,ensure_ascii=False)
        print(summary)
        # Günlük/artefakt indirme alanı kısıtlı olsa da ölçümler checks API'den okunur.
        print('::notice title=Hafif arayüz '+args.component+'::'+summary.replace('%','%25'))
        release.set()
    sys.excepthook=original_hook
    return 1 if errors else 0


if __name__=='__main__':
    raise SystemExit(main())
