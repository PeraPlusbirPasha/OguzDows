"""Plasma 5/6 KConfig ve KWin; mevcut paneller / plasmoidler silinmez."""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import re
import time
from pathlib import Path

from desktop_runtime import binary, dbus, run
from desktop_state import private_directory

KEYS = {
    'color-scheme': ('kdeglobals', 'General', 'ColorScheme'),
    'accent': ('kdeglobals', 'General', 'AccentColor'),
    'duration': ('kdeglobals', 'KDE', 'AnimationDurationFactor'),
    'blur': ('kwinrc', 'Plugins', 'blurEnabled'),
    'aero-motion': ('kwinrc', 'Plugins', 'oguzdows-aeroEnabled'),
    'snap-motion': ('kwinrc', 'Effect-oguzdows-aero', 'Snap'),
    'scale': ('kwinrc', 'Plugins', 'scaleEnabled'),
    'fading': ('kwinrc', 'Plugins', 'fadeEnabled'),
    'scale5': ('kwinrc', 'Plugins', 'kwin4_effect_scaleEnabled'),
    'fading5': ('kwinrc', 'Plugins', 'kwin4_effect_fadeEnabled'),
    'magiclamp': ('kwinrc', 'Plugins', 'magiclampEnabled'),
    'squash': ('kwinrc', 'Plugins', 'squashEnabled'),
    'squash5': ('kwinrc', 'Plugins', 'kwin4_effect_squashEnabled'),
    'maximize': ('kwinrc', 'Plugins', 'maximizeEnabled'),
    'maximize5': ('kwinrc', 'Plugins', 'kwin4_effect_maximizeEnabled'),
    'theme': ('plasmarc', 'Theme', 'name'),
    'decoration-library': ('kwinrc', 'org.kde.kdecoration2', 'library'),
    'decoration-theme': ('kwinrc', 'org.kde.kdecoration2', 'theme'),
    'gtk-theme': ('gtk-3.0/settings.ini', 'Settings', 'gtk-theme-name'),
    'gtk-dark': ('gtk-3.0/settings.ini', 'Settings', 'gtk-application-prefer-dark-theme'),
    'gtk-animations': ('gtk-3.0/settings.ini', 'Settings', 'gtk-enable-animations'),
}
COLOR_GROUPS = ('Button', 'Complementary', 'Header', 'Header][Inactive', 'Selection', 'Tooltip', 'View', 'Window')
COLOR_KEYS = ('BackgroundAlternate', 'BackgroundNormal', 'DecorationFocus', 'DecorationHover',
              'ForegroundActive', 'ForegroundInactive', 'ForegroundLink', 'ForegroundNegative',
              'ForegroundNeutral', 'ForegroundNormal', 'ForegroundPositive', 'ForegroundVisited')
for _group in COLOR_GROUPS:
    for _key in COLOR_KEYS:
        KEYS['palette:' + _group + ':' + _key] = ('kdeglobals', 'Colors:' + _group, _key)
for _key in ('activeBackground', 'activeBlend', 'activeForeground', 'inactiveBackground', 'inactiveBlend', 'inactiveForeground'):
    KEYS['wm:' + _key] = ('kdeglobals', 'WM', _key)
EFFECT_KEYS = ('Enable', 'ChangeSelectionColor', 'IntensityEffect', 'IntensityAmount', 'ColorEffect',
               'ColorAmount', 'Color', 'ContrastEffect', 'ContrastAmount')
for _group in ('Inactive', 'Disabled'):
    for _key in EFFECT_KEYS:
        KEYS['effect:' + _group + ':' + _key] = ('kdeglobals', 'ColorEffects:' + _group, _key)



def theme_name(preferences):
    key = hashlib.sha256((preferences['accent'] + preferences['appearance']).encode()).hexdigest()[:12]
    return 'oguzdows-glass-' + key


def palette(preferences, directory=Path('/usr/share/color-schemes')):
    path = directory / ('BreezeDark.colors' if preferences['appearance'] == 'dark' else 'BreezeLight.colors')
    if not path.is_file() or path.stat().st_size > 524288:
        raise ValueError('Yerel Breeze renk şeması kurulu değil; eksik Qt paleti uygulanmadı.')
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(path.read_text())
    result = {}
    for token, (filename, group, key) in KEYS.items():
        if filename != 'kdeglobals' or not token.startswith(('palette:', 'wm:', 'effect:')):
            continue
        value = parser.get(group, key, fallback=None)
        if value is not None:
            valid = (re.fullmatch(r'\d{1,3},\d{1,3},\d{1,3}', value) and all(int(part) <= 255 for part in value.split(',')))
            if token.startswith('effect:'):
                valid = valid or re.fullmatch(r'(?:true|false|-?\d+(?:\.\d+)?)', value)
            if not valid:
                raise ValueError('Yerel Qt renk şeması geçersiz.')
        result[token] = value  # Eksik alt-grup eski koyu/açık override'ını temizler.
    rgb = [int(preferences['accent'][i:i + 2], 16) for i in (1, 3, 5)]
    accent = ','.join(map(str, rgb))
    # Seçim metnini renkle birlikte değiştir; açık vurgu üstüne beyaz yazı yok.
    linear = [value / 3294.6 if value <= 10 else ((value / 255 + .055) / 1.055)**2.4 for value in rgb]
    light = .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
    result['palette:Selection:BackgroundNormal'] = accent
    result['palette:Selection:BackgroundAlternate'] = accent
    result['palette:Selection:ForegroundNormal'] = '0,0,0' if light > .179 else '255,255,255'
    result['palette:Selection:ForegroundInactive'] = result['palette:Selection:ForegroundNormal']
    for group in COLOR_GROUPS:
        result['palette:' + group + ':DecorationFocus'] = accent
        result['palette:' + group + ':DecorationHover'] = accent
    return result


class PlasmaSettings:
    name = 'kde'
    keys = set(KEYS) | {'wallpaper'}

    def __init__(self, execute=run):
        self.execute = execute
        self.reader = binary(('kreadconfig6', 'kreadconfig5'))
        self.major = 6 if self.reader and self.reader.endswith('6') else 5
        self.writer = binary(('kwriteconfig' + str(self.major),))
        if not self.reader or not self.writer:
            raise ValueError('Plasma KConfig araçları kurulu değil.')

    def validate(self, token, value):
        if token == 'wallpaper':
            validate_wallpapers(value)
            return
        if token not in self.keys or value is not None and (
                not isinstance(value, str) or len(value) > 4096 or any(c in value for c in '\n\r\0')):
            raise ValueError('İzin verilmeyen Plasma ayarı / türü.')

    def arguments(self, token):
        filename, group, key = KEYS[token]
        config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
        arguments = ['--file', str(config / filename)]
        for item in group.split(']['):
            arguments.extend(['--group', item])
        return [*arguments, '--key', key]

    def read(self, token):
        if token == 'wallpaper':
            return wallpaper_state()
        sentinel = '__OGUZDOWS_ABSENT_15c7b4__'
        value = self.execute([self.reader, *self.arguments(token), '--default', sentinel])
        if value.returncode:
            raise RuntimeError('Plasma ayarı okunamadı: ' + token)
        result = value.stdout.rstrip('\n')
        if result == sentinel:
            return None
        self.validate(token, result)
        return result

    def write(self, token, value):
        self.validate(token, value)
        if token == 'wallpaper':
            return write_wallpapers(value)
        command = [self.writer, *self.arguments(token)]
        command.extend(['--delete'] if value is None else [value])
        result = self.execute(command)
        if result.returncode:
            raise RuntimeError('Plasma ayarı uygulanamadı: ' + token)


def changes(preferences, resources, major=6, decoration=False):
    enabled = resources['compositing'] and preferences['effects'] == 'aero'
    spring = enabled and preferences['motion'] == 'spring'
    rgb = ','.join(str(int(preferences['accent'][i:i + 2], 16)) for i in (1, 3, 5))
    result = {'color-scheme': 'BreezeDark' if preferences['appearance'] == 'dark' else 'BreezeLight',
              'accent': rgb,
              'gtk-theme': 'OguzDows' if preferences['appearance'] == 'dark' else 'OguzDowsLight',
              'gtk-dark': str(preferences['appearance'] == 'dark').lower(),
              'gtk-animations': str(preferences['motion'] != 'reduced' and resources['compositing'] and preferences['effects'] != 'off').lower(),
              'duration': '0' if preferences['motion'] == 'reduced' or not resources['compositing'] or preferences['effects'] == 'off' else '0.8',
              'blur': str(enabled and preferences['blur']).lower(),
              'aero-motion': str(spring).lower(),
              'snap-motion': str(spring and preferences['snap_animation']).lower()}
    if spring:
        # Kendi efektimizle aynı pencerede iki açılma / küçülme animasyonu yok.
        # Bu değişiklikler de günlükten karşılaştırılarak geri alınır.
        result.update({'scale5' if major == 5 else 'scale': 'false',
                       'fading5' if major == 5 else 'fading': 'false', 'magiclamp': 'false',
                       'squash5' if major == 5 else 'squash': 'false'})
        if preferences['snap_animation']:
            result['maximize5' if major == 5 else 'maximize'] = 'false'
    if enabled and preferences['blur']:
        result['theme'] = theme_name(preferences)
        if decoration:
            result.update({'decoration-library': 'org.kde.kwin.aurorae',
                           'decoration-theme': '__aurorae__svg__' + theme_name(preferences)})
    return result


def refresh(preferences, resources):
    dbus('org.kde.KWin', '/KWin', 'org.kde.KWin', 'reconfigure')
    enabled = preferences['effects'] == 'aero' and resources['compositing']
    results = {}
    for name, wanted in (('blur', enabled and preferences['blur']),
                         ('oguzdows-aero', enabled and preferences['motion'] == 'spring')):
        # KWin reconfigure Q_NOREPLY'dır; kendi kısa yeniden yapılandırması
        # sırasında /Effects nesnesi geçici olarak kalkabilir. Yalnız bu
        # duruma en çok 2 saniye tolerans: Shell / compositor başlatma veya
        # yeniden başlatma yok, kalıcı polling / süresiz retry yok.
        deadline = time.monotonic() + 2
        while True:
            try:
                dbus('org.kde.KWin', '/Effects', 'org.kde.kwin.Effects',
                     'loadEffect' if wanted else 'unloadEffect', '(s)', (name,))
                results[name] = bool(dbus('org.kde.KWin', '/Effects', 'org.kde.kwin.Effects',
                                        'isEffectLoaded', '(s)', (name,))[0])
                break
            except RuntimeError as error:
                if 'UnknownObject' not in str(error) or time.monotonic() >= deadline:
                    raise
                time.sleep(.06)
    notify_settings()
    return {'blur_active': results['blur'], 'spring_active': results['oguzdows-aero'],
            'blur_scope': 'Plasma paneli / menüleri; Aurorae varsa OğuzDows cam dekoratif kenarları; diğer blur bölgesi bildiren pencereler. CSD başlıkları değişmez.'}


def notify_settings():
    # KConfig5 kwriteconfig'de --notify yoktur. KConfigWatcher'ın gerçek
    # ConfigChanged(a{saay}) sinyalini, ardından yerel palet bildirimini gönder.
    # Geri alma da aynı sinyali kullanır; bulk şema yeniden uygulayıp kullanıcının
    # sonradan değiştirdiği anahtarları ezmez. Shell restart / replace yok.
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    files = {}
    for filename, group, key in KEYS.values():
        if '/' in filename:
            continue  # GTK dosyası sonraki uygulama açılışında okunur.
        groups = files.setdefault(filename, {})
        groups.setdefault(group.replace('][', '\x1d'), []).append(key.encode())
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    for filename, groups in files.items():
        bus.emit_signal(None, '/' + filename, 'org.kde.kconfig.notify', 'ConfigChanged',
                        GLib.Variant('(a{saay})', (groups,)))
    bus.emit_signal(None, '/KGlobalSettings', 'org.kde.KGlobalSettings', 'notifyChange',
                    GLib.Variant('(ii)', (0, 0)))
    bus.flush_sync(None)


def validate_wallpapers(value):
    if not isinstance(value, list) or not 0 < len(value) <= 64:
        raise ValueError('Plasma duvar kâğıdı yedeği geçersiz.')
    seen = set()
    for row in value:
        if (not isinstance(row, dict) or set(row) != {'id', 'plugin', 'image'}
                or type(row['id']) is not int or not 0 <= row['id'] < 2**31 or row['id'] in seen
                or not isinstance(row['plugin'], str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,160}', row['plugin'])
                or not isinstance(row['image'], str) or len(row['image']) > 4096 or '\0' in row['image']):
            raise ValueError('Plasma duvar kâğıdı kaydı izin listesine uymuyor.')
        seen.add(row['id'])
    return value


def wallpaper_state():
    # Plasma 5/6 scripting; serbest JS yok. evaluateScript'in çıktısı başarı
    # kabul edilmeden JSON olarak ayrıca doğrulanır.
    code = ('var ds = desktops(), out = []; for (var i = 0; i < ds.length; ++i) {'
            'var d = ds[i]; d.currentConfigGroup = ["Wallpaper", d.wallpaperPlugin, "General"];'
            'out.push({id:d.id, plugin:d.wallpaperPlugin, image:String(d.readConfig("Image", ""))}); }'
            'out.sort(function(a,b) {return a.id-b.id;}); print(JSON.stringify(out));')
    output = dbus('org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', '(s)', (code,))[0]
    if not isinstance(output, str) or len(output) > 32768:
        raise ValueError('Plasma duvar kâğıdı yanıtı boyut sınırını aşıyor.')
    return validate_wallpapers(json.loads(output))


def write_wallpapers(values):
    validate_wallpapers(values)
    code = ('var rows = ' + json.dumps(values, ensure_ascii=True) + '; var ds = desktops();'
            'for (var i = 0; i < ds.length; ++i) { for (var j = 0; j < rows.length; ++j) {'
            'if (ds[i].id === rows[j].id) { ds[i].wallpaperPlugin = rows[j].plugin;'
            'ds[i].currentConfigGroup = ["Wallpaper", rows[j].plugin, "General"];'
            'ds[i].writeConfig("Image", rows[j].image); } } }')
    dbus('org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', '(s)', (code,))
    if wallpaper_state() != values:
        raise RuntimeError('Plasma duvar kâğıdı değişikliği geri okunarak doğrulanamadı.')


def theme_svg(accent, dark):
    # Özgün FrameSvg: gerçek alfa, diyagonal yansıma, iç ışık ve iki gölge katı.
    # Plasma bulanıklığı compositordan ister; SVG kendi başına blur taklidi değil.
    from desktop_decoration import colors
    base = colors(accent, dark)
    rectangles = [('center', 16, 16, 32, 32), ('top', 16, 8, 32, 8),
        ('bottom', 16, 48, 32, 8), ('left', 8, 16, 8, 32), ('right', 48, 16, 8, 32),
        ('topleft', 8, 8, 8, 8), ('topright', 48, 8, 8, 8),
        ('bottomleft', 8, 48, 8, 8), ('bottomright', 48, 48, 8, 8)]
    pieces = []
    for name, x, y, width, height in rectangles:
        pieces.append(f'<g id="{name}"><rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{base}" fill-opacity=".82"/>'
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="url(#reflection)"/>'
            f'<path d="M{x},{y + 1}h{width}" stroke="{accent}" stroke-opacity=".25"/></g>')
        pieces.append(f'<rect id="shadow-{name}" x="{x + 80}" y="{y}" width="{width}" height="{height}" fill="#07111e" fill-opacity=".16"/>')
    for edge in ('top', 'bottom', 'left', 'right'):
        pieces.append(f'<rect id="hint-{edge}-margin" width="8" height="8"/>'
                      f'<rect id="shadow-hint-{edge}-margin" width="12" height="12"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="144" height="64" viewBox="0 0 144 64">'
        '<defs><linearGradient id="reflection" x1="0" y1="0" x2="1" y2="1">'
        '<stop stop-color="#fff" stop-opacity=".26"/><stop offset=".38" stop-color="#fff" stop-opacity=".02"/>'
        '<stop offset=".41" stop-color="#fff" stop-opacity=".17"/><stop offset=".58" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity=".03"/></linearGradient></defs>' + ''.join(pieces) + '</svg>\n')


def install_tint(preferences):
    # Yalnız bize ait veri dosyaları; kullanıcı SVG / tema dosyası okunup kod
    # olarak çalıştırılmaz. Mevcut panel/plasmoid dizilimine hiç dokunulmaz.
    base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    name = theme_name(preferences)
    directory = private_directory(base / 'plasma/desktoptheme' / name)
    from profiles import atomic_text
    for category, filename in (('widgets', 'panel-background.svg'), ('dialogs', 'background.svg')):
        target = private_directory(directory / category)
        atomic_text(target / filename, theme_svg(preferences['accent'], preferences['appearance'] == 'dark'))
    atomic_text(directory / 'metadata.desktop', f'[Desktop Entry]\nName=OğuzDows Glass\nX-KDE-PluginInfo-Name={name}\nX-KDE-PluginInfo-Version=1\nX-Plasma-API=5.0\n')
    atomic_text(directory / 'metadata.json', json.dumps({'KPlugin': {'Id': name,
        'Name': 'OğuzDows Glass', 'Version': '1', 'License': 'GPL-3.0-or-later'},
        'X-Plasma-API': '5.0'}))
    atomic_text(directory / 'plasmarc', '[Settings]\nFallbackTheme=default\n[BlurBehindEffect]\nenabled=true\n[ContrastEffect]\nenabled=false\n')
