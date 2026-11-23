#!/usr/bin/env python3
"""Kedi / galeri / animasyon yüklemeyen bağımsız, hafif kurucu başlatıcısı."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import install_status

import gi

gi.require_version('Gtk','3.0')
from gi.repository import Gio, GLib, Gtk

COMMAND=('/usr/bin/pkexec','/usr/local/sbin/oguzdows-installer')


def run_installer():
    try:
        result=subprocess.run(list(COMMAND),capture_output=True,text=True,errors='replace',check=False)
        return result.returncode,result.stdout,result.stderr[-5000:]
    except OSError as error:
        return 1,'',str(error)


class Installer(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.oguzdows.HafifKurucu')
        self.window=None
        self.busy=False
        self.data={}
        self.starts=0
        # Salt-okunur GApplication durumu: açık rehber sesi/hareketi durdurur.
        # Yeni açılan rehber de mevcut durumu alır; dosya / periyodik tarama yok.
        self.activity=Gio.SimpleAction.new_stateful('busy',None,GLib.Variant('b',False))
        self.activity.set_enabled(False)
        self.add_action(self.activity)

    def set_busy(self,value):
        self.busy=bool(value)
        self.activity.set_state(GLib.Variant('b',self.busy))

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return
        self.window=Gtk.ApplicationWindow(application=self,title='OğuzDows Kurucusu')
        self.window.set_icon_name('oguzdows-install')
        self.window.set_default_size(530,350)
        self.window.get_style_context().add_class('oguzdows-window')
        self.window.connect('delete-event',self.on_close)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16)
        body.set_border_width(24)
        self.title=Gtk.Label(label='Kurucu açılıyor…',xalign=0)
        self.title.set_line_wrap(True)
        self.title.get_style_context().add_class('section-title')
        body.pack_start(self.title,False,False,0)
        self.detail=Gtk.Label(label='Yönetici onayı beklenebilir. Bu başlatıcı kedi, ses motoru veya galeri yüklemez. Kurulum adımlarını kurucunun kendi penceresinden izle.',xalign=0)
        self.detail.set_line_wrap(True)
        body.pack_start(self.detail,False,False,0)
        self.log=Gtk.TextView(editable=False,cursor_visible=False,wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll=Gtk.ScrolledWindow()
        scroll.set_size_request(-1,100)
        scroll.add(self.log)
        body.pack_start(scroll,True,True,0)
        path=Gtk.Label(label='Günlük: /var/log/oguzdows/installer.log',xalign=0)
        path.set_selectable(True)
        path.set_line_wrap(True)
        body.pack_start(path,False,False,0)
        self.restart=Gtk.Button(label='Yeniden başlat…')
        self.restart.set_no_show_all(True)
        self.restart.connect('clicked',self.reboot)
        body.pack_start(self.restart,False,False,0)
        self.close_button=Gtk.Button(label='Kapat')
        self.close_button.set_sensitive(False)
        self.close_button.connect('clicked',lambda *_:self.window.close())
        body.pack_start(self.close_button,False,False,0)
        self.window.add(body)
        self.window.show_all()
        self.set_busy(True)
        self.starts+=1
        def work():
            code,output,detail=run_installer()
            GLib.idle_add(self.finished,code,output,detail)
        threading.Thread(target=work,name='oguzdows-kurucu',daemon=True).start()

    def finished(self,code,output,detail):
        self.set_busy(False)
        self.data=install_status.from_output(code,output)
        title,text=install_status.description(self.data)
        self.title.set_text(title)
        self.detail.set_text(text)
        self.log.get_buffer().set_text(detail or 'Ek hata çıktısı yok. Kurulum sonucu yukarıda; ayrıntılı günlük belirtilen dosyada.')
        self.close_button.set_sensitive(True)
        self.restart.set_visible(self.data.get('outcome')=='success' and self.data.get('complete') is True)
        self.window.present()
        return GLib.SOURCE_REMOVE

    def on_close(self,*_):
        if not self.busy:
            return False
        dialog=Gtk.MessageDialog(transient_for=self.window,modal=True,message_type=Gtk.MessageType.INFO,buttons=Gtk.ButtonsType.CLOSE,text='Kurucu / yetkilendirme işlemi devam ediyor.')
        dialog.format_secondary_text('Önce kurucuyu kendi penceresinden kapat. Disk işlemi sürüyor olabilir; bu pencere işlemi zorla sonlandırmaz.')
        dialog.run()
        dialog.destroy()
        return True

    def reboot(self,*_):
        if self.data.get('outcome')!='success' or self.data.get('complete') is not True:
            return
        dialog=Gtk.MessageDialog(transient_for=self.window,modal=True,message_type=Gtk.MessageType.QUESTION,buttons=Gtk.ButtonsType.YES_NO,text='Şimdi yeniden başlatılsın mı?')
        dialog.format_secondary_text('Açık dosyalarını kaydet. Bilgisayar kapanırken canlı USB’yi çıkar; diskten ilk açılışı ayrıca kontrol et.')
        answer=dialog.run()
        dialog.destroy()
        if answer==Gtk.ResponseType.YES:
            subprocess.Popen(['/usr/bin/xfce4-session-logout','--reboot'])


if __name__=='__main__':
    raise SystemExit(Installer().run(sys.argv))
