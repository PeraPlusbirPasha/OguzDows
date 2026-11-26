"""Yalnızca mağaza açıkken X11 pencere olayları; root, ağ veya tarama döngüsü yok."""


class X11Windows:
    def __init__(self):
        # İçe aktarırken X sunucusuna bağlanılmaz. Eksik Xlib varsa görünür elle-çıkış denetimine dönülür.
        from Xlib import X, display, error
        self.X, self.error = X, error
        self.connection = display.Display()
        self.root = self.connection.screen().root
        self.clients = self.connection.intern_atom('_NET_CLIENT_LIST')
        self.supporting = self.connection.intern_atom('_NET_SUPPORTING_WM_CHECK')
        self.application = self.connection.intern_atom('_GTK_APPLICATION_ID')
        self.root.change_attributes(event_mask=X.PropertyChangeMask | X.SubstructureNotifyMask)
        self.connection.flush()

    def fileno(self):
        return self.connection.fileno()

    def consume(self):
        changed = False
        while self.connection.pending_events():
            event = self.connection.next_event()
            changed |= (event.type in (self.X.MapNotify, self.X.UnmapNotify, self.X.DestroyNotify)
                        or event.type == self.X.PropertyNotify and event.atom == self.clients)
        return changed

    def windows(self):
        # EWMH istemci listesi küçültülen / başka çalışma alanındaki pencereleri
        # de tutar. Unmap olayını doğrudan kapatma saymak HATALI olurdu.
        clients = self.root.get_full_property(self.clients, self.X.AnyPropertyType)
        if clients is None:
            # Xfwm ilk pencereden önce boş liste özelliğini hiç oluşturmuyor.
            # Destekleyen WM varsa bu sadece sıfır istemcidir; WM yoksa ise
            # durumu bilinmiyor say ve görünür, elle çıkış kontrolüne dön.
            if self.root.get_full_property(self.supporting, self.X.AnyPropertyType) is not None:
                return []
            raise RuntimeError('Pencere yöneticisinin EWMH istemci listesi yok.')
        found = []
        for identifier in clients.value:
            window = self.connection.create_resource_object('window', int(identifier))
            try:
                app = window.get_full_property(self.application, self.X.AnyPropertyType)
                app_id = bytes(app.value).rstrip(b'\0').decode(errors='replace') if app is not None else ''
                classes = tuple(value.casefold() for value in (window.get_wm_class() or ()))
                if app_id == 'org.gnome.Software' or any(value in ('gnome-software', 'org.gnome.software') for value in classes):
                    found.append(int(identifier))
            except self.error.XError:
                continue  # Pencere aynı anda kapanmış olabilir.
        return found

    def close(self):
        self.connection.close()


class Visibility:
    """İlk pencere görülmeden veya yalnızca küçültülünce çıkış istenmez."""
    def __init__(self):
        self.seen = False

    def closed(self, windows):
        if windows:
            self.seen = True
        return self.seen and not windows
