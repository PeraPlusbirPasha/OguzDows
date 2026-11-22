"""Gerçek X11 oturumlarını Xfce görünümünden ayırır; serbest Exec çalıştırmaz."""
from __future__ import annotations

import configparser
import os
import tempfile
from pathlib import Path

SESSIONS = {
    'xfce': ('OğuzDows · hafif Xfce', ('oguzdows',)),
    'kde': ('Gerçek KDE Plasma · X11', ('plasmax11', 'plasma')),
    'gnome': ('Gerçek GNOME · X11', ('gnome-xorg', 'gnome')),
}


BINARIES = {'xfce': '/usr/bin/startxfce4', 'kde': '/usr/bin/startplasma-x11', 'gnome': '/usr/bin/gnome-session'}


def installed(directory=Path('/usr/share/xsessions'), executable=None):
    executable = (lambda path: os.access(path, os.X_OK)) if executable is None else executable
    result = {}
    for identifier, (title, candidates) in SESSIONS.items():
        if not executable(BINARIES[identifier]):
            continue
        for name in candidates:
            path = directory / (name + '.desktop')
            if not path.is_file() or path.stat().st_size > 65536:
                continue
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            try:
                parser.read_string(path.read_text())
                section = parser['Desktop Entry']
                if section.get('Type') != 'Application' or not section.get('Exec') or section.get('Hidden', 'false').lower() == 'true':
                    continue
            except (OSError, ValueError, KeyError, configparser.Error):
                continue
            result[identifier] = {'title': title, 'session': name}
            break
    return result


def accounts_session(name):
    """AccountsService varsa kullanıcının son oturumunu da güncelle.

    Hizmet yoksa LightDM .dmrc okuyucusuna düşülür. Yetki / D-Bus hatası sessizce
    başarı sayılmaz; giriş ekranından elle seçme yönergesi gösterilir.
    """
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        reply = bus.call_sync('org.freedesktop.Accounts', '/org/freedesktop/Accounts',
                              'org.freedesktop.Accounts', 'FindUserById', GLib.Variant('(x)', (os.getuid(),)),
                              GLib.VariantType.new('(o)'), Gio.DBusCallFlags.NONE, 4000, None)
        bus.call_sync('org.freedesktop.Accounts', reply.unpack()[0], 'org.freedesktop.Accounts.User',
                      'SetXSession', GLib.Variant('(s)', (name,)), None, Gio.DBusCallFlags.NONE, 4000, None)
    except GLib.Error as error:
        remote = Gio.DBusError.get_remote_error(error) or ''
        if remote not in ('org.freedesktop.DBus.Error.ServiceUnknown', 'org.freedesktop.DBus.Error.NameHasNoOwner'):
            raise RuntimeError('Oturum tercihi AccountsService ile kaydedilemedi. Giriş ekranındaki oturum menüsünden elle seçin. ' + str(error)) from error


def select(identifier, choices=None, home=None, update_accounts=accounts_session):
    choices = installed() if choices is None else choices
    if identifier not in SESSIONS or identifier not in choices:
        raise ValueError('Bu gerçek oturum kurulu değil. Xfce görünümü kurulu oturum yerine sayılamaz.')
    name = choices[identifier]['session']
    if name not in SESSIONS[identifier][1]:
        raise ValueError('İzin verilmeyen oturum kimliği.')
    home = Path.home() if home is None else Path(home)
    path = home / '.dmrc'
    if path.is_symlink() or path.exists() and (not path.is_file() or path.stat().st_size > 65536):
        raise ValueError('.dmrc normal bir kullanıcı dosyası olmalı; değiştirilmedi.')
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    if path.exists():
        try:
            parser.read_string(path.read_text())
        except configparser.Error as error:
            raise ValueError('.dmrc biçimi okunamadı; kişisel ayar değiştirilmedi.') from error
    if not parser.has_section('Desktop'):
        parser.add_section('Desktop')
    parser['Desktop']['Session'] = name
    fd, filename = tempfile.mkstemp(prefix='.oguzdows-session-', dir=home)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, 'w') as stream:
            parser.write(stream)
        temporary.chmod(0o600)
        # AS başarısızsa yerel tercihi de yarım değiştirme. Genel yönetici
        # izni / parola toplama yok; yalnızca kişinin kendi XSession değeri.
        update_accounts(name)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return name
