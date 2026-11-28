"""GNOME'un kimliğini koruyan GSettings / Shell arka ucu (43 ve 45–48)."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from desktop_runtime import dbus

UUID = 'oguzdows-glass@oguzdows.local'
SCHEMA = 'org.oguzdows.desktop'
KEYS = {
    'gtk-theme': ('org.gnome.desktop.interface', 'gtk-theme', 's'),
    'color-scheme': ('org.gnome.desktop.interface', 'color-scheme', 's'),
    'animations': ('org.gnome.desktop.interface', 'enable-animations', 'b'),
    'native-accent': ('org.gnome.desktop.interface', 'accent-color', 's'),
    'picture-uri': ('org.gnome.desktop.background', 'picture-uri', 's'),
    'picture-uri-dark': ('org.gnome.desktop.background', 'picture-uri-dark', 's'),
    'picture-options': ('org.gnome.desktop.background', 'picture-options', 's'),
    'glass-enabled': (SCHEMA, 'glass-enabled', 'b'),
    'motion': (SCHEMA, 'motion', 's'), 'snap-animation': (SCHEMA, 'snap-animation', 'b'),
    'accent': (SCHEMA, 'accent', 's'), 'dark': (SCHEMA, 'dark', 'b'),
    # Bu token tüm uzantı listesini değil, yalnız kendi üyeliğimizi temsil eder.
    'extension-enabled': ('org.gnome.shell', 'enabled-extensions', 'b'),
}


class GnomeSettings:
    name = 'gnome'
    keys = set(KEYS)

    def __init__(self, source=None):
        import gi
        gi.require_version('Gio', '2.0')
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.source = source or Gio.SettingsSchemaSource.get_default()
        self.settings = {}

    def setting(self, token):
        schema, key, _signature = KEYS[token]
        if schema not in self.settings:
            definition = self.source.lookup(schema, True) if self.source else None
            if not definition:
                raise ValueError('GNOME ayar şeması kurulu değil: ' + schema)
            self.settings[schema] = self.Gio.Settings.new_full(definition, None, None)
        value = self.settings[schema]
        if not value.props.settings_schema.has_key(key):
            raise ValueError('GNOME bu ayarı desteklemiyor: ' + key)
        return value, key

    def supports(self, token):
        try:
            self.setting(token)
            return True
        except ValueError:
            return False

    def validate(self, token, value):
        if token not in self.keys:
            raise ValueError('İzin verilmeyen GNOME ayarı.')
        signature = KEYS[token][2]
        if value is not None and not (type(value) is bool if signature == 'b' else isinstance(value, str) and len(value) < 4096 and '\0' not in value):
            raise ValueError('GNOME ayarının veri türü geçersiz.')

    def read(self, token):
        settings, key = self.setting(token)
        if token == 'extension-enabled':
            return UUID in settings.get_strv(key)
        value = settings.get_user_value(key)
        # GLib.Variant(False) ve Variant('') Python'da falsy'dir; yok
        # sayılmaları write/readback ve karşılaştırmalı geri almayı bozar.
        return value.unpack() if value is not None else None

    def write(self, token, value):
        self.validate(token, value)
        settings, key = self.setting(token)
        if not settings.is_writable(key):
            raise RuntimeError('Bu GNOME ayarı yönetim ilkesiyle kilitli: ' + key)
        if token == 'extension-enabled':
            extension_enabled(bool(value))
        elif value is None:
            settings.reset(key)
        elif not settings.set_value(key, self.GLib.Variant(KEYS[token][2], value)):
            raise RuntimeError('GNOME ayarı uygulanamadı: ' + key)
        self.Gio.Settings.sync()


def closest_accent(color):
    # libadwaita / GNOME 47+ yalnız bu adlandırılmış yerel vurgu renklerini sunar.
    colors = {'blue': '#3584e4', 'teal': '#2190a4', 'green': '#3a944a',
              'yellow': '#c88800', 'orange': '#ed5b00', 'red': '#e62d42',
              'pink': '#d56199', 'purple': '#9141ac', 'slate': '#6f8396'}
    rgb = lambda value: tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    sample = rgb(color)
    return min(colors, key=lambda name: math.dist(sample, rgb(colors[name])))


def changes(preferences, resources, backend):
    motion = preferences['motion'] if resources['compositing'] and preferences['effects'] != 'off' else 'reduced'
    result = {'gtk-theme': 'OguzDows' if preferences['appearance'] == 'dark' else 'OguzDowsLight',
              'color-scheme': 'prefer-dark' if preferences['appearance'] == 'dark' else 'default',
              'animations': motion != 'reduced', 'native-accent': closest_accent(preferences['accent']),
              'glass-enabled': preferences['effects'] == 'aero' and preferences['blur'] and resources['compositing'],
              'motion': motion, 'snap-animation': preferences['snap_animation'] and motion == 'spring',
              'accent': preferences['accent'], 'dark': preferences['appearance'] == 'dark',
              # Yerel menü / bildirim D-Bus köprüsü efektler kapalıyken de
              # çalışır. Blur / animasyon anahtarları yukarıda ayrı bütçelidir.
              'extension-enabled': True}
    return {key: value for key, value in result.items() if backend.supports(key)}


def extension_enabled(enabled):
    """Yalnız bizim UUID; diğer uzantılar / disable-user-extensions korunur.

    Yeni kopyalanmış uzantı Shell tarafından bilinmiyorsa bir sonraki girişte
    yüklenir. Alt+F2 r, Shell restart veya oturum kapatma yapılmaz.
    """
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio
    settings = Gio.Settings.new('org.gnome.shell')
    values = settings.get_strv('enabled-extensions')
    if enabled and UUID not in values:
        values.append(UUID)
    elif not enabled:
        values = [value for value in values if value != UUID]
    if not settings.set_strv('enabled-extensions', values):
        raise RuntimeError('OğuzDows uzantı tercihi kilitli / kaydedilemedi.')
    Gio.Settings.sync()
    try:
        method = 'EnableExtension' if enabled else 'DisableExtension'
        accepted = dbus('org.gnome.Shell', '/org/gnome/Shell', 'org.gnome.Shell.Extensions', method, '(s)', (UUID,))
        return bool(accepted and accepted[0])
    except RuntimeError:
        return False


def status():
    try:
        version = dbus('org.gnome.Shell', '/org/gnome/Shell', 'org.freedesktop.DBus.Properties',
                       'Get', '(ss)', ('org.gnome.Shell', 'ShellVersion'))[0]
        # Gio Variant sözlükteki varyantları unpack() içinde açar.
        version = version.unpack() if hasattr(version, 'unpack') else version
        info = dbus('org.gnome.Shell', '/org/gnome/Shell', 'org.gnome.Shell.Extensions', 'GetExtensionInfo', '(s)', (UUID,))[0]
        state = info.get('state', 0)
        state = state.unpack() if hasattr(state, 'unpack') else state
        return {'shell': str(version), 'extension_active': state == 1,
                'blur_scope': 'GNOME paneli ve açılır Shell menüleri; tüm üçüncü taraf pencereler değil.'}
    except (RuntimeError, IndexError, TypeError):
        return {'extension_active': False, 'message': 'Shell uzantısı etkinliği doğrulanamadı; sonraki giriş / uzantı yöneticisini kontrol edin.'}


def wallpaper_changes(path, backend):
    uri = Path(path).resolve().as_uri()
    return {key: value for key, value in {'picture-uri': uri, 'picture-uri-dark': uri,
            'picture-options': 'zoom'}.items() if backend.supports(key)}


def extension_metadata(version):
    """Derleme katmanı kaynak dosyasını kopyalar; çalışırken internetten uzantı yok."""
    if version == 'bookworm':
        return 'legacy', ['43', '44']
    if version == 'trixie':
        return 'modern', ['45', '46', '47', '48']
    raise ValueError('GNOME Shell uyumluluğu bu taban için doğrulanmadı.')


def shell_state(value):
    if not isinstance(value, str) or len(value) > 8192:
        raise ValueError('Shell yanıtı boyut sınırında değil.')
    result = json.loads(value)
    if not isinstance(result, dict) or not re.fullmatch(r'#[a-fA-F0-9]{6}', result.get('accent', '')):
        raise ValueError('Shell yanıtı geçersiz.')
    return result
