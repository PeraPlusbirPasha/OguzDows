"""Hafif Rıfkı: sabit küçük resim ve hazır doğal sesler; kurucudan bağımsız."""
from __future__ import annotations

from pathlib import Path

import gi

gi.require_version('Gtk','3.0')
from gi.repository import GdkPixbuf, GLib, Gtk

from install_status import description
from rifki_dialogue import HELLO, PANELS, STAGES
from rifki_model import reply
from rifki_speech import Speaker

ASSETS=Path('/usr/share/oguzdows/rifki')


class Avatar(Gtk.Image):
    """Boştayken sıfır zamanlayıcı. İsteğe bağlı ağız hareketi sadece ses çalarken."""
    def __init__(self,speaker=None,reduced=False,size=112):
        super().__init__()
        self.speaker=speaker
        self.reduced=bool(reduced)
        self.timer=None
        self.blink_source=None
        self.allow_motion=False
        self.frozen=False
        self.talking=False
        self.phase=False
        self.frames={}
        for name in ('idle','blink','talk'):
            try:
                self.frames[name]=GdkPixbuf.Pixbuf.new_from_file_at_scale(str(ASSETS/(name+'.png')),min(size,144),min(size,144),True)
            except GLib.Error:
                pass
        self.show_frame('idle')
        self.get_accessible().set_name('Rıfkı, hafif kedi yardımcısı')
        if speaker:
            speaker.listeners.append(self.voice_changed)
        self.connect('map',lambda *_:self.sync())
        self.connect('unmap',lambda *_:self.cancel_motion())
        self.connect('destroy',self.closed)

    def show_frame(self,name):
        frame=self.frames.get(name,self.frames.get('idle'))
        if frame is not None:
            self.set_from_pixbuf(frame)

    def cancel_motion(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer=None
        if self.blink_source is not None:
            GLib.source_remove(self.blink_source)
            self.blink_source=None
        self.show_frame('idle')

    def voice_changed(self,talking):
        self.talking=talking
        self.sync()

    def sync(self):
        if self.talking and self.allow_motion and not self.reduced and not self.frozen and self.get_mapped():
            if self.timer is None:
                self.timer=GLib.timeout_add(500,self.talk_frame)
        else:
            self.cancel_motion()

    def talk_frame(self):
        if not self.talking or not self.allow_motion or self.reduced or self.frozen or not self.get_mapped():
            self.timer=None
            self.show_frame('idle')
            return GLib.SOURCE_REMOVE
        self.phase=not self.phase
        self.show_frame('talk' if self.phase else 'idle')
        return GLib.SOURCE_CONTINUE

    def blink(self):
        if self.reduced or self.frozen or not self.get_mapped():
            return
        self.cancel_motion()
        self.show_frame('blink')
        def finish():
            self.blink_source=None
            self.show_frame('idle')
            self.sync()
            return GLib.SOURCE_REMOVE
        self.blink_source=GLib.timeout_add(140,finish)

    def closed(self,*_):
        self.cancel_motion()
        if self.speaker and self.voice_changed in self.speaker.listeners:
            self.speaker.listeners.remove(self.voice_changed)


class Companion(Gtk.ApplicationWindow):
    def __init__(self,app,callbacks,reduced=False,installing=False,speaker=None):
        super().__init__(application=app)
        self.callbacks=callbacks
        self.installing=bool(installing)
        self.current_page='welcome'
        self.last_panel=''
        self.page_words={}
        self.last_message=''
        self.last_cue=None
        self.status_data={}
        self.last_stage=None
        self.owns_speaker = speaker is None
        self.speaker = Speaker(GLib.idle_add, self.voice_error) if speaker is None else speaker
        self.set_title('Rıfkı · Hafif yardımcı')
        self.set_icon_name('oguzdows-rifki')
        self.set_default_size(354,min(570,self.get_screen().get_height()-80))
        self.get_style_context().add_class('oguzdows-window')
        self.get_style_context().add_class('rifki-window')
        header=Gtk.HeaderBar(title='Rıfkı',subtitle='Hafif · doğal Türkçe kayıtlar')
        header.set_show_close_button(True)
        self.set_titlebar(header)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        body.set_border_width(14)
        self.avatar=Avatar(self.speaker,reduced)
        self.avatar.frozen=self.installing
        self.avatar.set_halign(Gtk.Align.CENTER)
        body.pack_start(self.avatar,False,False,0)
        self.stage_label=Gtk.Label(label='Ben buradayım. Öncelik kurulum.',xalign=0)
        self.stage_label.set_line_wrap(True)
        body.pack_start(self.stage_label,False,False,0)
        self.chat=Gtk.TextView(editable=False,cursor_visible=False,wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.chat.set_left_margin(10)
        self.chat.set_right_margin(10)
        self.chat.set_top_margin(10)
        chat_scroll=Gtk.ScrolledWindow()
        chat_scroll.set_size_request(-1,132)
        chat_scroll.add(self.chat)
        body.pack_start(chat_scroll,True,True,0)
        self.entry=Gtk.Entry()
        self.entry.set_placeholder_text('Disk, açılış, internet…')
        self.entry.set_max_length(1000)
        self.entry.connect('activate',self.entered)
        body.pack_start(self.entry,False,False,0)
        chips=Gtk.FlowBox()
        chips.set_selection_mode(Gtk.SelectionMode.NONE)
        chips.set_min_children_per_line(2)
        chips.set_max_children_per_line(3)
        for title,question in (('Disk seçimi','disk'),('Açılış hatası','boot'),('Sonuç','sonuç'),('İnternet','internet'),('Sürücüler','sürücü'),('Duvar kâğıdı','duvar')):
            button=Gtk.Button(label=title)
            button.connect('clicked',lambda _,q=question:self.ask(q))
            chips.add(button)
        body.pack_start(chips,False,False,0)
        self.action=Gtk.Button()
        self.action.set_no_show_all(True)
        self.action.connect('clicked',self.take_action)
        self.action_name=None
        body.pack_start(self.action,False,False,0)
        speech_buttons=Gtk.Box(spacing=6)
        for title,callback in (('Son mesajı dinle',self.repeat),('Sesi durdur',lambda *_:self.speaker.stop())):
            button=Gtk.Button(label=title)
            button.connect('clicked',callback)
            speech_buttons.pack_start(button,True,True,0)
        body.pack_start(speech_buttons,False,False,0)
        explain=Gtk.Box(spacing=6)
        for title,page in (('Bu paneli anlat',None),('Ayarları anlat','settings')):
            button=Gtk.Button(label=title)
            button.connect('clicked',lambda _,p=page:self.narrate_page(p or self.current_page,force=True))
            explain.pack_start(button,True,True,0)
        body.pack_start(explain,False,False,0)
        self.sound=Gtk.CheckButton(label='Doğal Türkçe ses kayıtlarını çal')
        self.sound.set_active(self.speaker.enabled)
        self.sound.connect('toggled',lambda b:self.speaker.set_enabled(b.get_active()))
        body.pack_start(self.sound,False,False,0)
        self.narration=Gtk.CheckButton(label='Rehber panel açıklamalarını anlat')
        self.narration.set_active(self.speaker.options.get('welcome_narration', True) is not False)
        self.narration.connect('toggled', self.narration_changed)
        body.pack_start(self.narration,False,False,0)
        self.motion=Gtk.CheckButton(label='Yalnızca konuşurken hafif ağız hareketi')
        # Önceki pet/auto tercihleri veya RAM miktarı ağır yolu geri açamaz.
        self.motion.set_active(False)
        self.motion.set_sensitive(not reduced)
        self.motion.set_tooltip_text('Düşük kaynak / azaltılmış hareket profilinde kapalı kalır.')
        self.motion.connect('toggled',self.motion_changed)
        body.pack_start(self.motion,False,False,0)
        hello=Gtk.Button(label='Selam ver')
        hello.connect('clicked',lambda *_:self.greet())
        body.pack_start(hello,False,False,0)
        self.voice_status=Gtk.Label(label='',xalign=0)
        self.voice_status.set_line_wrap(True)
        self.voice_status.get_style_context().add_class('muted')
        body.pack_start(self.voice_status,False,False,0)
        note=Gtk.Label(label='Robotik sentez yok · Mikrofon / ağ yok\nKaydı olmayan değişken ayrıntılar yazılı kalır.\nKurulumda hareket ve otomatik ses durur.',xalign=0)
        note.set_line_wrap(True)
        note.get_style_context().add_class('muted')
        body.pack_start(note,False,False,0)
        scroll=Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.add(body)
        self.add(scroll)
        self.connect('destroy',lambda *_:self.speaker.close() if self.owns_speaker else self.speaker.stop())
        self.say(HELLO)

    def voice_error(self,text):
        self.voice_status.set_text(text)

    def motion_changed(self,button):
        self.avatar.allow_motion=button.get_active()
        self.avatar.sync()

    def narration_changed(self, button):
        value = button.get_active()
        self.speaker.save_option('welcome_narration', value)
        callback = self.callbacks.get('narration')
        if callback:
            callback(value)
        if not value:
            self.speaker.stop()

    def repeat(self, *_):
        if self.installing:
            self.voice_error('Kurulum sürerken ses duraklatıldı; açıklama yazılı kalır.')
            return
        self.speaker.speak(self.last_message, self.last_cue)

    def greet(self):
        self.say(HELLO)
        self.avatar.blink()

    def set_installing(self,value):
        self.installing=bool(value)
        self.avatar.frozen=self.installing
        self.avatar.sync()
        if self.installing:
            self.speaker.stop()
        else:
            self.last_stage=None

    def say(self,text,cue=None):
        buffer=self.chat.get_buffer()
        buffer.insert(buffer.get_end_iter(),'Rıfkı: '+text+'\n\n')
        if buffer.get_char_count()>16000:
            buffer.delete(buffer.get_start_iter(),buffer.get_iter_at_offset(buffer.get_char_count()-12000))
        self.chat.scroll_to_iter(buffer.get_end_iter(),0,False,0,1)
        self.last_message,self.last_cue=text,cue
        if not self.installing:
            self.speaker.speak(text,cue)

    def entered(self,*_):
        text=self.entry.get_text().strip()
        self.entry.set_text('')
        if text:
            self.ask(text)

    def ask(self,text):
        buffer=self.chat.get_buffer()
        buffer.insert(buffer.get_end_iter(),'Sen: '+text[:1000]+'\n')
        answer=reply(text,self.status_data)
        cue=None
        if answer.get('result'):
            cue=self.result_cue(self.status_data)
        self.say(answer['text'],cue)
        self.action_name=answer['action']
        names={'boot-report':'Salt-okunur açılış raporu','network':'Ağ bağlantıları','drivers':'Donanım sekmesi',
               'wallpapers':'Duvar kâğıtları','install':'Karşılayıcı', 'styles':'Tasarım ve tema',
               'store':'OğuzDows Mağaza', 'updates':'Güncelleme / cihaz rehberi',
               'compatibility':'EXE / APK inceleme ekranı', 'culture':'İmece araçları', 'devices':'Cihaz Merkezi'}
        if self.action_name in self.callbacks:
            self.action.set_label(names[self.action_name])
            self.action.show()
        else:
            self.action.hide()
        return True

    def take_action(self,*_):
        callback=self.callbacks.get(self.action_name)
        if callback:
            callback()

    def narrate_page(self,name,force=False,text=None):
        self.current_page=name
        if text:
            self.page_words[name]=text
        words=text or self.page_words.get(name) or PANELS.get(name)
        if not words or (not force and (not self.narration.get_active() or self.last_panel==name)):
            return
        self.last_panel=name
        self.say(words)

    @staticmethod
    def result_cue(data):
        if data.get('outcome')=='success' and data.get('complete') is True:
            return 'warning' if any(item.get('status')!='installed' for item in data.get('optional_drivers',[])) else 'success'
        return 'cancelled' if data.get('outcome')=='cancelled' else 'failure'

    def installation(self,data):
        self.status_data=data
        key=(data.get('session'),data.get('stage'),data.get('outcome'),str(data.get('optional_drivers',[])))
        if key==self.last_stage:
            return
        self.last_stage=key
        if data.get('outcome') in ('success','failed','incomplete','cancelled','unknown'):
            title,text=description(data)
            self.stage_label.set_text(title)
            self.say(title+' '+text,self.result_cue(data))
        else:
            title,text=STAGES.get(data.get('stage'),('Kurucu','Kurucu durumunu izliyorum.'))
            self.stage_label.set_text(title)
            self.say(text,'working' if data.get('stage') in ('partition','copying') else None)
