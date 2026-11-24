"""Masaüstü algılama, sabit yerel işlemler ve kısa ömürlü D-Bus çağrıları."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ACTIONS = {
    'settings': 'Sistem ayarları', 'appearance': 'Görünüm', 'display': 'Ekranlar',
    'panels': 'Paneli özelleştir', 'widgets': 'Widget / eklenti ekle',
    'shortcuts': 'Klavye kısayolları', 'windows': 'Pencere yönetimi',
    'audio': 'Ses', 'network': 'Ağ bağlantıları', 'power': 'Pil ve güç',
    'notifications': 'Bildirimler', 'apps': 'Uygulama menüsü',
    'files': 'Dosyalar', 'terminal': 'Uçbirim', 'monitor': 'Canlı performans',
}
COMMANDS = {
    'xfce': {
        'settings': [('xfce4-settings-manager',)], 'appearance': [('xfce4-appearance-settings',)],
        'display': [('xfce4-display-settings',)], 'panels': [('xfce4-panel', '--preferences')],
        'widgets': [('xfce4-panel', '--add-items')], 'shortcuts': [('xfce4-keyboard-settings',)],
        'windows': [('xfwm4-settings',)], 'audio': [('pavucontrol',)],
        'network': [('nm-connection-editor',)], 'power': [('xfce4-power-manager-settings',)],
        'notifications': [('xfce4-notifyd-config',)], 'apps': [('xfce4-popup-whiskermenu',)],
        'files': [('thunar',), ('Thunar',)], 'terminal': [('xfce4-terminal',)],
    },
    'gnome': {
        'settings': [('gnome-control-center',)], 'appearance': [('gnome-control-center', 'background')],
        'display': [('gnome-control-center', 'display')], 'shortcuts': [('gnome-control-center', 'keyboard')],
        'windows': [('gnome-tweaks',)], 'audio': [('gnome-control-center', 'sound')],
        'network': [('gnome-control-center', 'network')], 'power': [('gnome-control-center', 'power')],
        'notifications': [('gnome-control-center', 'notifications')],
        'files': [('nautilus',)], 'terminal': [('gnome-terminal',), ('kgx',)],
        'panels': [('gnome-extensions-app',), ('gnome-shell-extension-prefs',)],
        'widgets': [('gnome-extensions-app',), ('gnome-shell-extension-prefs',)],
    },
    'kde': {
        'settings': [('systemsettings',), ('systemsettings5',)],
        'appearance': [('systemsettings', 'kcm_colors'), ('systemsettings5', 'kcm_colors')],
        'display': [('systemsettings', 'kcm_kscreen'), ('systemsettings5', 'kcm_kscreen')],
        'shortcuts': [('systemsettings', 'kcm_keys'), ('systemsettings5', 'kcm_keys')],
        'windows': [('systemsettings', 'kcm_kwinoptions'), ('systemsettings5', 'kcm_kwinoptions')],
        'audio': [('systemsettings', 'kcm_pulseaudio'), ('systemsettings5', 'kcm_pulseaudio')],
        'network': [('systemsettings', 'kcm_networkmanagement'), ('systemsettings5', 'kcm_networkmanagement')],
        'power': [('systemsettings', 'kcm_powerdevilprofilesconfig'), ('systemsettings5', 'kcm_powerdevilprofilesconfig')],
        'notifications': [('systemsettings', 'kcm_notifications'), ('systemsettings5', 'kcm_notifications')],
        'files': [('dolphin',)], 'terminal': [('konsole',)],
    },
}


def current(environment=None):
    env = os.environ if environment is None else environment
    names = set(env.get('XDG_CURRENT_DESKTOP', '').upper().split(':'))
    # Başka kabuğun içinde xfconf'un kurulu olması Xfce oturumu sayılmaz.
    if names & {'GNOME', 'GNOME-CLASSIC', 'UBUNTU'}:
        return 'gnome'
    if names & {'KDE', 'PLASMA'}:
        return 'kde'
    if 'XFCE' in names:
        return 'xfce'
    return 'unknown'


def normal_session():
    if os.getuid() == 0 or not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise ValueError('Bu işlem normal kullanıcının açık masaüstü oturumunda yapılır.')
    if current() == 'unknown':
        raise ValueError('Masaüstü tanınmadı; başka masaüstünün ayarlarına yazılmadı.')


def installation_busy():
    # Mevcut GTK uygulamalarının dışa açtığı durum. NO_AUTO_START sayesinde
    # bu kontrol kurucuyu / karşılayıcıyı başlatmaz; idle polling yoktur.
    for name, path, action in (
            ('org.oguzdows.HafifKurucu', '/org/oguzdows/HafifKurucu', 'busy'),
            ('org.oguzdows.Rehber', '/org/oguzdows/Rehber', 'installing')):
        try:
            result = dbus(name, path, 'org.gtk.Actions', 'Describe', '(s)', (action,))
        except RuntimeError:
            continue  # Eski / kapalı uygulamada bu isteğe bağlı durum yoktur.
        try:
            # Describe'ın TEK çıkışı (bgav) yapısıdır. GDBus yanıtı bir de
            # dış tuple ile sarar: ((enabled, signature, [state]),).
            # Doğrudan result[2] açık Rehber'de IndexError üretip Uygula'yı
            # daha native ayarlara ulaşmadan durduruyordu.
            (_enabled, _signature, states), = result
            value, = states
            value = value.unpack() if hasattr(value, 'unpack') else value
            if type(value) is not bool:
                raise ValueError('Boolean action state required')
        except (TypeError, ValueError) as error:
            # Bozuk / beklenmeyen bir yanıtı "kurulum yok" sayıp kapıyı aşma.
            raise RuntimeError('Kurulum durumu güvenle okunamadı; görünüm işlemi başlatılmadı.') from error
        if value:
            return True
    return False


def run(command):
    return subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=8, check=False, env={**os.environ, 'LC_ALL': 'C.UTF-8'})


def binary(names):
    for name in names:
        path = Path('/usr/bin') / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def dbus(destination, path, interface, method, signature=None, arguments=(), reply=None):
    # Gio yalnızca gerçek oturum işleminde yüklenir; sorgu kabuğu başlatmaz.
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(destination, path, interface, method,
            GLib.Variant(signature, arguments) if signature else None,
            GLib.VariantType.new(reply) if reply else None,
            Gio.DBusCallFlags.NO_AUTO_START, 3500, None)
        return result.unpack() if result else ()
    except GLib.Error as error:
        raise RuntimeError('Masaüstü hizmeti işlemi kabul etmedi: ' + str(error)) from error


def spawn_command(executable, argv, environment):
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib
    try:
        # GLib'in varsayılan çift-fork yolu çocukları toplar; GTK merkezinde
        # bekleyen Popen / zombi veya kalıcı Python işçisi bırakılmaz.
        return GLib.spawn_async(argv, envp=[key + '=' + value for key, value in environment.items()])[0]
    except GLib.Error as error:
        raise RuntimeError('Yerel araç başlatılamadı: ' + str(error)) from error


def native_control(action, desktop=None, *, spawn=spawn_command):
    if action not in ACTIONS:
        raise ValueError('Bilinmeyen masaüstü işlemi.')
    normal_session()
    desktop = current() if desktop is None else desktop
    if action == 'monitor':
        return spawn('/usr/local/bin/oguzdows-monitor', ['/usr/local/bin/oguzdows-monitor'], os.environ)
    if desktop == 'gnome' and action == 'apps':
        return dbus('org.gnome.Shell', '/org/gnome/Shell', 'org.gnome.Shell', 'ShowApplications')
    if desktop == 'gnome' and action == 'notifications':
        try:
            return dbus('org.gnome.Shell', '/org/oguzdows/Desktop', 'org.oguzdows.Desktop', 'Open', '(s)', ('notifications',))
        except RuntimeError:
            pass  # Uzantı ilk girişte yüklenmediyse yerel bildirim ayarı.
    if desktop == 'kde' and action in ('apps', 'widgets', 'panels'):
        # Sabit yerel Plasma API'leri; kullanıcıdan JS / komut kabul edilmez.
        method = {'apps': 'activateLauncherMenu', 'widgets': 'toggleWidgetExplorer'}.get(action)
        if method:
            return dbus('org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', method)
        script = 'var ps = panels(); for (var i = 0; i < ps.length; ++i) { ps[i].showConfigurationInterface(); }'
        return dbus('org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', '(s)', (script,))
    for candidate in COMMANDS.get(desktop, {}).get(action, []):
        executable = binary((candidate[0],))
        if executable:
            return spawn(executable, [executable, *candidate[1:]], os.environ)
    if desktop == 'gnome' and action in ('panels', 'widgets', 'windows'):
        raise RuntimeError('GNOME bu işlevi Shell uzantılarıyla sunar. Yerel GNOME uzantı / Tweaks aracı kurulu değil; Xfce paneli başlatılmadı.')
    raise RuntimeError(ACTIONS[action] + ' için bu masaüstünün yerel aracı kurulu değil.')


def snap(direction):
    if direction not in ('left', 'right', 'maximize', 'restore', 'minimize'):
        raise ValueError('Bilinmeyen pencere yerleştirme işlemi.')
    normal_session()
    desktop = current()
    if desktop == 'gnome':
        return dbus('org.gnome.Shell', '/org/oguzdows/Desktop', 'org.oguzdows.Desktop', 'Snap', '(s)', (direction,))
    if desktop == 'kde':
        # Yerel Window Maximize kısayolu bir TOGGLE'dır; restore diye
        # çağırmak normal pencereyi büyütür. Sabit dahili KWin köprüsü beş
        # idempotent işlem sunar. Kullanıcı kodu / serbest JS / shell metni yok.
        import desktop_state
        with desktop_state.locked():
            identifier = dbus('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                              'loadScript', '(ss)', ('/usr/share/oguzdows/kwin/snap.js', 'oguzdows-snap-v1'))[0]
            if type(identifier) is not int or not -1 <= identifier < 1000000:
                raise RuntimeError('KWin sabit Snap köprüsünü yükleyemedi.')
            if identifier >= 0:
                try:
                    dbus('org.kde.KWin', '/Scripting/Script' + str(identifier), 'org.kde.kwin.Script', 'run')
                except RuntimeError as error:
                    if 'UnknownObject' not in str(error):
                        raise
                    # KWin 5 Script D-Bus yolu /<id>; 6 /Scripting/Script<id>.
                    dbus('org.kde.KWin', '/' + str(identifier), 'org.kde.kwin.Script', 'run')
            return dbus('org.kde.kglobalaccel', '/component/kwin', 'org.kde.kglobalaccel.Component',
                        'invokeShortcut', '(s)', ('OguzDows Snap ' + direction,))
    from desktop_x11 import snap as x11_snap
    return x11_snap(direction)
