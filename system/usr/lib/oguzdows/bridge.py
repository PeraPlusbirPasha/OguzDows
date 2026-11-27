#!/usr/bin/env python3
"""OğuzKöprü: explicit LAN file table / read-only screen sharing for OğuzDows PC and ARM."""
import argparse
import ipaddress
import json
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge_core as core
from bridge_capture import jpeg_dimensions, unlocked_x11


def addresses(execute=subprocess.run):
    try:
        result = execute(['ip', '-j', '-4', 'addr', 'show', 'up'], capture_output=True, text=True, timeout=3, check=False)
        if result.returncode:
            return []
        out = []
        for interface in json.loads(result.stdout):
            for info in interface.get('addr_info', []):
                value = info.get('local', '')
                address = ipaddress.IPv4Address(value)
                if core.local_address(value) and not address.is_loopback:
                    out.append((interface['ifname'], value))
        return out
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return []


def dropped_paths(uris):
    if not 1 <= len(uris) <= core.MAX_ITEMS:
        raise ValueError('En çok sekiz seçilmiş dosya')
    result = []
    for uri in uris:
        value = urlsplit(uri)
        if value.scheme != 'file' or value.netloc not in ('', 'localhost') or value.query or value.fragment:
            raise ValueError('Yalnız yerel dosya URI’si')
        result.append(Path(unquote(value.path, errors='strict')))
    return result


def application():
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

    class Bridge(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='org.oguzdows.Bridge', flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.window = None
            self.session = None
            self.server = None
            self.client = None
            self.connected = False
            self.remote = None
            self.uploads = {}
            self.busy = False
            self.polling = False
            self.watching = False
            self.frame_busy = False
            self.capture_busy = False
            self.capture_peer = None
            self.closed = False
            self.generation = 0
            self.signature = None
            self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='oguzkopru-ui')

        def do_activate(self):
            if self.window:
                self.window.present(); return
            self.session = core.Session('OğuzDows PC · ARM')
            self.window = Gtk.ApplicationWindow(application=self, title='OğuzKöprü · Cihazların aynı masada')
            screen = self.window.get_screen()
            self.window.set_default_size(min(680, screen.get_width()-24), min(760, screen.get_height()-24))
            self.window.set_size_request(320, 360)
            self.window.set_icon_name('network-workgroup')
            self.window.connect('destroy', self.shutdown)
            header = Gtk.HeaderBar(title='OğuzKöprü', subtitle='PC · telefon · ARM / yalnız onaylı yerel oturum')
            header.set_show_close_button(True); self.window.set_titlebar(header)
            import ui_theme
            ui_theme.setup(self.window)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=20)
            scroll.add(root); self.window.add(scroll)
            self.root = root
            root.pack_start(self.label('Aynı ağ. Aynı masa. Seçtiğin dosyalar.'), False, False, 0)
            root.pack_start(self.label('Otomatik keşif / bulut yok. Her eşleşmede iki ekrandaki kodu doğrula. Dosyalar otomatik açılmaz; rehber, SMS, terminal, kurulum ve uzaktan kontrol paylaşılmaz.'), False, False, 0)
            self.status = self.label('Bir cihazda masa aç; diğerinde iki dakikalık daveti yapıştır.')
            root.pack_start(self.status, False, False, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            row.pack_start(self.button('Bu cihazda 15 dakikalık masa aç', self.start_host), False, False, 0)
            row.pack_start(self.button('Oturumu kapat', self.stop), False, False, 0)
            root.pack_start(row, False, False, 0)
            self.local = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.local.set_no_show_all(True); root.pack_start(self.local, False, False, 0)
            self.ip = Gtk.ComboBoxText()
            for iface, address in addresses(): self.ip.append(address, f'{iface} · {address}')
            self.ip.set_active(0); self.local.pack_start(self.ip, False, False, 0)
            self.local.pack_start(self.button('Seçili IP için daveti göster / yenile', self.show_invite), False, False, 0)
            self.invite = self.label(''); self.invite.set_selectable(True)
            self.local.pack_start(self.invite, False, False, 0)
            self.local.pack_start(self.button('Daveti gizle', lambda: self.invite.set_text('')), False, False, 0)
            self.entry = Gtk.Entry(); self.entry.set_placeholder_text('Diğer cihazın oguzkopru1: davetini yapıştır')
            self.entry.set_max_length(1200); self.entry.set_visibility(False)
            root.pack_start(self.entry, False, False, 0)
            root.pack_start(self.button('Davetle eşleşme iste', self.connect_peer), False, False, 0)
            self.confirm = self.button('Kod aynı · karşı tarafın onayını denetle', self.confirm_pair)
            self.confirm.set_sensitive(False); root.pack_start(self.confirm, False, False, 0)
            self.peer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root.pack_start(self.peer_box, False, False, 0)
            self.drop = Gtk.EventBox(); self.drop.add(self.label('DOSYAYI BURAYA BIRAK\nMasa: tüm onaylı cihazlara sunulur. İstemci: karşı tarafın kabulü beklenir.'))
            self.drop.set_size_request(-1, 100)
            self.drop.get_style_context().add_class('card')
            targets = [Gtk.TargetEntry.new('text/uri-list', 0, 0), Gtk.TargetEntry.new('application/x-oguzkopru-file', Gtk.TargetFlags.SAME_APP, 1)]
            self.drop.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.COPY)
            self.drop.connect('drag-data-received', self.drop_files)
            root.pack_start(self.drop, False, False, 0)
            root.pack_start(self.button('Sistemden dosya seç / masaya koy…', self.choose), False, False, 0)
            root.pack_start(self.label('En çok 8 dosya, dosya başına 128 MiB / oturum kuyruğunda 256 MiB. Klasör, sembolik bağlantı, arşiv açma veya otomatik çalıştırma yok.'), False, False, 0)
            self.file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root.pack_start(self.file_box, False, False, 0)
            self.inbox_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root.pack_start(self.inbox_box, False, False, 0)
            self.remote_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root.pack_start(self.remote_box, False, False, 0)
            self.watch = self.button('İzinli ekranı görüntüle / görüntülemeyi kapat', self.toggle_watch)
            root.pack_start(self.watch, False, False, 0)
            root.pack_start(self.button('Ekran paylaşımını DURDUR', self.stop_capture), False, False, 0)
            self.image = Gtk.Image(); root.pack_start(self.image, True, True, 0)
            root.pack_start(self.label('Telefon ekranı: taze sistem MediaProjection izni. Bu cihazın ekranı: yalnız doğrulanabilen açık X11 oturumu, açık onay, en çok 1 kare/sn ve 1280 px. Wayland yayını bu sürümde yok. Ses / fare / klavye iletilmez. Kilit/oturum durumu bilinmiyorsa paylaşım başlamaz.'), False, False, 0)
            self.window.show_all(); self.local.hide()
            GLib.timeout_add(1000, self.tick)
            GLib.timeout_add(600, self.frame_tick)

        @staticmethod
        def label(text):
            value = Gtk.Label(label=text, xalign=0)
            value.set_line_wrap(True); value.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR); value.set_max_width_chars(70)
            value.set_selectable(False)
            return value

        @staticmethod
        def button(text, callback):
            value = Gtk.Button(label=text)
            label = value.get_child()
            label.set_line_wrap(True); label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR); label.set_max_width_chars(32)
            value.connect('clicked', lambda *_: callback())
            return value

        def tell(self, message):
            if not self.closed: self.status.set_text(message)

        def work(self, action, done=None):
            if self.busy or self.closed:
                self.tell('Önce açık işlemin tamamlanmasını bekle.'); return
            self.busy = True
            generation = self.generation
            def perform():
                try:
                    value = action(); error = None
                except Exception:
                    value = None; error = 'İşlem tamamlanamadı: ağ, izin, oturum, hedef dosya veya özet uygun değil. Otomatik tekrar yapılmadı.'
                def complete():
                    self.busy = False
                    if self.closed or generation != self.generation:
                        if isinstance(value, core.Server): value.close()
                        return False
                    if error: self.tell(error)
                    elif done: done(value)
                    self.signature = None
                    return False
                GLib.idle_add(complete)
            self.pool.submit(perform)

        def start_host(self):
            if self.server or self.client:
                self.tell('Önce mevcut oturumu kapat.'); return
            def ready(server):
                self.server = server; self.local.show_all()
                self.tell('TLS masası açık. Yerel ağ IP’sini seç, iki dakikalık daveti özel kanaldan aktar.')
            self.work(lambda: core.Server(self.session).start(), ready)

        def show_invite(self):
            try:
                if not self.server: raise ValueError()
                address = self.ip.get_active_id()
                if not address: raise ValueError()
                self.session.renew()
                self.invite.set_text(core.invitation(address, self.server.port, self.server.pin, self.session.secret))
                self.tell('Davet 2 dakika, masa en çok 15 dakika. Kodları iki cihazda da doğrula; isme tek başına güvenme.')
            except Exception: self.tell('Wi-Fi/Ethernet yerel IPv4 adresi bulunamadı veya masa süresi doldu. Oturumu yeniden aç.')

        def connect_peer(self):
            if self.server or self.client:
                self.tell('Önce mevcut oturumu kapat.'); return
            code = self.entry.get_text().strip(); self.entry.set_text('')
            try: client = core.Client(code)
            except Exception: self.tell('Geçersiz OğuzKöprü daveti. Yalnız sayısal yerel IPv4 / sürüm 1 desteklenir.'); return
            def paired(reply):
                self.client = client; self.confirm.set_sensitive(True)
                self.tell(f'KARŞILAŞTIR: {reply["code"]} · Diğer cihaz onayladıktan sonra Kod aynı düğmesine bas.')
            self.work(lambda: client.pair('OğuzDows PC · ARM'), paired)

        def confirm_pair(self):
            if not self.client or self.connected: return
            def approved(reply):
                self.connected = reply['status'] == 'approved'
                self.confirm.set_sensitive(not self.connected)
                self.tell('TLS eşleşmesi açık. Yalnız seçilmiş dosyalar ve ayrıca onaylanan görüntü paylaşılır.' if self.connected else 'Karşı tarafın durumu: ' + reply['status'])
            self.work(self.client.poll_pair, approved)

        def choose(self):
            if self.busy: return
            dialog = Gtk.FileChooserDialog(title='Seçilmiş dosyaları paylaşım masasına koy', transient_for=self.window, action=Gtk.FileChooserAction.OPEN)
            dialog.add_buttons('Vazgeç', Gtk.ResponseType.CANCEL, 'Seç', Gtk.ResponseType.OK)
            dialog.set_select_multiple(True)
            paths = dialog.get_filenames() if dialog.run() == Gtk.ResponseType.OK else []
            dialog.destroy()
            if paths: self.stage(paths)

        def drop_files(self, _widget, context, _x, _y, selection, kind, when):
            try:
                if kind == 1:
                    ident = selection.get_text()
                    if not core.re.fullmatch('[a-f0-9]{32}', ident or ''): raise ValueError()
                    self.propose(ident)
                else: self.stage(dropped_paths(selection.get_uris()))
                Gtk.drag_finish(context, True, False, when)
            except Exception:
                self.tell('Yalnız 1–8 yerel dosya veya kendi seçilmiş dosya kartın bırakılabilir.')
                Gtk.drag_finish(context, False, False, when)

        def stage(self, paths):
            if not 1 <= len(paths) <= core.MAX_ITEMS:
                self.tell('En çok sekiz dosya seç.'); return
            self.work(lambda: [self.session.offer(path) for path in paths],
                      lambda ids: self.tell(f'{len(ids)} dosya özel kopyaya alındı. ' + ('Masada onaylı cihazlara sunuluyor; indirmeyi karşı cihaz seçer.' if self.server else 'Göndermek için kartı cihaza sürükle veya Gönderim öner düğmesini kullan.')))

        def propose(self, ident):
            if not self.client or not self.connected:
                self.tell('Dosya yerel masada; yalnız eşleşen cihazlar ayrıca Al derse alır.'); return
            with self.session.lock: item = dict(self.session.files[ident])
            def proposed(reply):
                self.uploads[ident] = reply['id']; self.tell('Alıcıdan dosya kabulü istendi; dosyanın baytları henüz gönderilmedi.')
            self.work(lambda: self.client.request('POST', '/v1/inbox', {k: item[k] for k in ('name', 'bytes', 'sha256')}), proposed)

        def send_approved(self, ident):
            if not self.client or ident not in self.uploads: return
            remote_id = self.uploads[ident]
            def send():
                value = self.client.request('GET', '/v1/inbox/' + remote_id)
                if value['status'] != 'approved': return value
                return self.client.request('PUT', '/v1/inbox/' + remote_id, source=self.session.root / ident)
            def done(reply):
                self.tell('Alıcı gerçek SHA-256 özetini doğruladı; kalıcı kaydetmeyi kendi ekranında seçer.' if reply['status'] == 'ready' else 'Alıcı durumu: ' + reply['status'] + ' · Onaysız gönderilmedi.')
                if reply['status'] == 'ready': self.uploads.pop(ident, None)
            self.work(send, done)

        def save_dialog(self, name):
            dialog = Gtk.FileChooserDialog(title='Kalıcı kayıt için yeni hedef seç', transient_for=self.window, action=Gtk.FileChooserAction.SAVE)
            dialog.add_buttons('Vazgeç', Gtk.ResponseType.CANCEL, 'Kaydet', Gtk.ResponseType.OK)
            dialog.set_current_name(name)
            target = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
            dialog.destroy(); return target

        def receive(self, item):
            target = self.save_dialog(item['name'])
            if target: self.work(lambda: self.client.receive(item, target), lambda _v: self.tell('Dosya SHA-256 doğrulandı ve yeni hedefe atomik kaydedildi. Otomatik açılmadı; mevcut hedefler ezilmez.'))

        def save_inbox(self, ident, name):
            target = self.save_dialog(name)
            if target: self.work(lambda: self.session.save_received(ident, target), lambda _v: self.tell('Doğrulanmış dosya yeni seçilmiş hedefe yazıldı; çalıştırılmadı.'))

        @staticmethod
        def clear(box):
            for child in box.get_children(): child.destroy()

        def rebuild(self, pairs, peers, files, inbox):
            self.clear(self.peer_box); self.clear(self.file_box); self.clear(self.inbox_box); self.clear(self.remote_box)
            for p in pairs:
                if p['status'] != 'pending': continue
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                row.pack_start(self.label(f'{p["name"]} · KOD {p["code"]} · İki ekranda aynı mı?'), False, False, 0)
                row.pack_start(self.button('Kod aynı · izin ver', lambda i=p['id']: self.session.approve_pair(i, True)), False, False, 0)
                row.pack_start(self.button('Reddet', lambda i=p['id']: self.session.approve_pair(i, False)), False, False, 0)
                self.peer_box.pack_start(row, False, False, 0)
            for p in peers:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                row.pack_start(self.label(p['name'] + ' · ' + p['code']), False, False, 0)
                row.pack_start(self.button('Erişimi kes', lambda i=p['id']: self.session.revoke(i)), False, False, 0)
                row.pack_start(self.button('Bu cihaza ekranımı paylaş…', lambda i=p['id']: self.start_capture(i)), False, False, 0)
                self.peer_box.pack_start(row, False, False, 0)
            for f in files:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                row.pack_start(self.label(f'{f["name"]} · {f["bytes"]} bayt · {f["sha256"][:12]}…'), False, False, 0)
                if self.connected:
                    row.pack_start(self.button('Gönderim öner', lambda i=f['id']: self.propose(i)), False, False, 0)
                    if f['id'] in self.uploads: row.pack_start(self.button('Alıcı onayladıysa gönder', lambda i=f['id']: self.send_approved(i)), False, False, 0)
                row.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [Gtk.TargetEntry.new('application/x-oguzkopru-file', Gtk.TargetFlags.SAME_APP, 1)], Gdk.DragAction.COPY)
                row.connect('drag-data-get', lambda _w, _c, data, _k, _t, i=f['id']: data.set_text(i, -1))
                self.file_box.pack_start(row, False, False, 0)
            for f in inbox:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                row.pack_start(self.label(f'{f["name"]} · {f["bytes"]} bayt · {f["status"]}'), False, False, 0)
                if f['status'] == 'pending':
                    row.pack_start(self.button('Dosyayı kabul et', lambda i=f['id']: self.session.approve_inbox(i, True)), False, False, 0)
                    row.pack_start(self.button('Reddet', lambda i=f['id']: self.session.approve_inbox(i, False)), False, False, 0)
                elif f['status'] == 'ready': row.pack_start(self.button('Yeni hedefe kaydet…', lambda i=f['id'], n=f['name']: self.save_inbox(i, n)), False, False, 0)
                self.inbox_box.pack_start(row, False, False, 0)
            if self.remote:
                self.remote_box.pack_start(self.label(str(self.remote['name']) + ' · seçilmiş dosyalar'), False, False, 0)
                for f in self.remote['files']:
                    self.remote_box.pack_start(self.button(f'{f["name"]} · {f["bytes"]} bayt · Al / Kaydet…', lambda item=dict(f): self.receive(item)), False, False, 0)
                if not self.remote['mirror']:
                    self.image.clear(); self.remote_box.pack_start(self.label('Bu cihaz ekran paylaşımını açmadı. Sahte görüntü yok.'), False, False, 0)
            for box in (self.peer_box, self.file_box, self.inbox_box, self.remote_box): box.show_all()

        def tick(self):
            if self.closed: return False
            try: self.session.live()
            except core.Denied: self.stop(); self.tell('15 dakikalık oturum doldu; tüm eşleşmeler kapatıldı.'); return True
            with self.session.lock:
                pairs = [dict(v) for v in self.session.pairs.values()]
                peers = [dict(v) for v in self.session.peers.values()]
                files = [dict(v) for v in self.session.files.values() if v['ready']]
                inbox = [dict(v) for v in self.session.inbox.values()]
            signature = repr((pairs, peers, files, inbox, self.remote, self.uploads))
            if signature != self.signature:
                self.rebuild(pairs, peers, files, inbox); self.signature = signature
            if self.connected and not self.polling and not self.busy:
                self.polling = True; generation = self.generation; client = self.client
                def poll():
                    try: value = client.state()
                    except Exception: value = None
                    def ready():
                        self.polling = False
                        if not self.closed and generation == self.generation:
                            self.remote = value
                            if value is None: self.image.clear(); self.tell('Cihaza ulaşılamadı; çevrimiçi varsayılmadı. Yeni oturum açabilirsin.')
                        return False
                    GLib.idle_add(ready)
                self.pool.submit(poll)
            self.capture_tick()
            return True

        def start_capture(self, peer):
            if not unlocked_x11():
                self.tell('Açık X11 oturumu / sistem kilit durumu doğrulanamadı. Wayland yayını bu sürümde yok; görüntü alınmadı.'); return
            dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.WARNING,
                                       buttons=Gtk.ButtonsType.OK_CANCEL, text='Ekranının tamamı bu onaylı cihazda görünsün mü?')
            dialog.format_secondary_text('Özel pencereler, parolalar ve kişisel bilgiler görünebilir. En çok 1 kare/sn, 1280 px; ses ve uzaktan kontrol yok. Bu pencereyi kapatınca, sistem kilitlenince veya erişimi geri alınca biter. Tüm oturum kilit durumu her kare öncesi sistemden doğrulanır.')
            accepted = dialog.run() == Gtk.ResponseType.OK; dialog.destroy()
            if accepted:
                with self.session.lock:
                    if peer not in self.session.peers: self.tell('Cihazın erişimi artık yok.'); return
                    self.capture_peer = peer
                self.invite.set_text(''); self.tell('Ekran paylaşımı açık. Ekran paylaşımını DURDUR düğmesiyle kesebilirsin.')

        def stop_capture(self):
            self.capture_peer = None
            if self.session:
                with self.session.lock: self.session.viewer = None; self.session.frame = b''
            self.tell('Bu cihazın ekran paylaşımı kapalı.')

        def capture_tick(self):
            if not self.capture_peer or self.capture_busy: return
            self.capture_busy = True; peer = self.capture_peer; generation = self.generation
            def check():
                unlocked = unlocked_x11()
                def grab():
                    self.capture_busy = False
                    if self.closed or generation != self.generation or self.capture_peer != peer: return False
                    if not unlocked: self.stop_capture(); self.tell('Kilit/etkin oturum doğrulanamadı; ekran paylaşımı durduruldu.'); return False
                    try:
                        root = Gdk.get_default_root_window()
                        if not root: raise ValueError()
                        width, height = root.get_width(), root.get_height()
                        if not 0 < width * height <= 16777216: raise ValueError()
                        pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, width, height)
                        ratio = min(1, 1280 / max(width, height))
                        small = pixbuf.scale_simple(max(1, int(width*ratio)), max(1, int(height*ratio)), GdkPixbuf.InterpType.BILINEAR)
                        success, data = small.save_to_bufferv('jpeg', ['quality'], ['55'])
                        if not success: raise ValueError()
                        self.session.set_frame(peer, bytes(data))
                    except Exception: self.stop_capture(); self.tell('Gerçek ekran karesi alınamadı; paylaşım durduruldu.')
                    return False
                GLib.idle_add(grab)
            self.pool.submit(check)

        def toggle_watch(self):
            self.watching = not self.watching
            if not self.watching: self.image.clear()

        def frame_tick(self):
            if self.closed: return False
            if not self.watching or self.frame_busy or not self.connected or not self.remote or not self.remote.get('mirror'): return True
            self.frame_busy = True; client = self.client; generation = self.generation
            def fetch():
                try:
                    data = client.request('GET', '/v1/frame', limit=core.MAX_FRAME)
                    if data: jpeg_dimensions(data)
                except Exception: data = b''
                def render():
                    self.frame_busy = False
                    if self.closed or generation != self.generation or not self.watching: return False
                    if not data: self.image.clear(); return False
                    try:
                        loader = GdkPixbuf.PixbufLoader.new_with_type('jpeg'); loader.write(data); loader.close()
                        pixbuf = loader.get_pixbuf()
                        width = max(200, min(640, self.window.get_allocated_width()-48))
                        ratio = min(1, width / pixbuf.get_width())
                        self.image.set_from_pixbuf(pixbuf.scale_simple(max(1,int(pixbuf.get_width()*ratio)), max(1,int(pixbuf.get_height()*ratio)), GdkPixbuf.InterpType.BILINEAR))
                    except Exception: self.image.clear()
                    return False
                GLib.idle_add(render)
            self.pool.submit(fetch)
            return True

        def stop(self):
            self.generation += 1
            self.capture_peer = None; self.watching = False; self.image.clear()
            old_session, old_server, old_client = self.session, self.server, self.client
            self.session = core.Session('OğuzDows PC · ARM'); self.server = None; self.client = None
            self.connected = False; self.remote = None; self.uploads.clear(); self.signature = None
            self.invite.set_text(''); self.local.hide(); self.confirm.set_sensitive(False)
            def close():
                if old_server: old_server.close()
                else: old_session.close()
                if old_client:
                    try: old_client.request('POST', '/v1/bye')
                    except Exception: pass
                    old_client.bearer = None
            self.pool.submit(close)
            self.tell('Oturum kapalı. Özel geçici kopyalar silinir, yeni bağlantı için yeni davet gerekir.')

        def shutdown(self, *_args):
            if self.closed: return
            self.closed = True; self.generation += 1
            if self.server: self.server.close()
            elif self.session: self.session.close()
            self.client = None; self.pool.shutdown(wait=False, cancel_futures=True)

    return Bridge()


def gui():
    return application().run([sys.argv[0]])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args(argv)
    if args.version:
        print('OğuzKöprü 0.4 · protocol 1 · explicit LAN TLS / file consent / read-only frames')
        return 0
    return gui()


if __name__ == '__main__':
    raise SystemExit(main())
