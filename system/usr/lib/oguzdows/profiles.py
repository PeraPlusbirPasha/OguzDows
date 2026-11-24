"""Altı yerel Xfce düzeni; tipli yedek, dar izin listesi ve bağımsız tema/efekt.

İskele Xfce panelidir; yeni shell, sürekli Python çizici veya Plank çalışmaz.
Panel/plugin dizileri Xfce'de girişte yüklenir. Yenileme yalnızca ayrı kullanıcı
onayıyla istenir; tarz seçmek panel sürecini zorla kapatmaz.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

from resource_policy import current_policy

PROFILES = {
    'oguzdows': {'name': 'OğuzDows', 'description': 'Başlat, mavi cam esintili alt çubuk ve turkuaz vurgular.', 'position': 10, 'size': 38, 'layout': 'O|HMC', 'appearance': 'light'},
    'kde': {'name': 'Plasma esintisi · Xfce', 'description': 'Geniş alt görev çubuğu, okunaklı sekmeler ve mavi vurgular.', 'position': 10, 'size': 44, 'layout': 'O|HMC', 'appearance': 'dark'},
    'gnome': {'name': 'Ubuntu / GNOME esintisi · Xfce', 'description': 'Ubuntu esintili sol iskele, üst durum çubuğu ve sıcak vurgular.', 'position': 9, 'size': 32, 'layout': 'O|HMC', 'appearance': 'light'},
    'xfce': {'name': 'Klasik Xfce', 'description': 'İnce üst panel, metinli görevler; en sade yerleşim.', 'position': 9, 'size': 30, 'layout': 'O|HMC', 'appearance': 'light'},
    'windows11': {'name': 'Windows 11 esintisi · Xfce', 'description': 'Gerçekten ortalı Başlat / uygulama grubu ve ayrı ince üst durum şeridi; Windows çalıştırmaz.', 'position': 9, 'size': 28, 'layout': 'O|HMC', 'appearance': 'light'},
    'mac': {'name': 'macOS esintisi · Xfce', 'description': 'elementary esintili ince üst panel, içeriğe oturan ortalı iskele ve renkli sol düğmeler.', 'position': 9, 'size': 30, 'layout': 'CHM|O', 'appearance': 'light'},
}
APPEARANCES = {'light': 'Açık', 'dark': 'Koyu'}
EFFECTS = {'off': 'Efektsiz · en hafif', 'glass': 'Hafif cam · isteğe bağlı',
           'aero': 'Aero esintisi · cam / gölge + kısa pencere geçişi'}
DOCK = 90
DOCK_PROFILES = ('mac', 'gnome', 'windows11')
LAUNCHERS = {90: 'oguzdows-browser.desktop', 91: 'oguzdows-files.desktop',
             92: 'oguzdows-store.desktop', 93: 'oguzdows-terminal.desktop'}
ARRAY_TYPES = {'int-array': 'int', 'double-array': 'double', 'string-array': 'string'}


def theme(identifier, appearance):
    if identifier not in PROFILES or appearance not in APPEARANCES:
        raise ValueError('Bilinmeyen görünüm veya tema.')
    names = {'oguzdows': ('OguzDowsXP', 'OguzDowsXPDark'),
             'mac': ('OguzDowsMac', 'OguzDowsMacDark'),
             'gnome': ('OguzDowsGnome', 'OguzDowsGnomeDark'),
             'windows11': ('OguzDowsEleven', 'OguzDowsElevenDark')}
    return names.get(identifier, ('OguzDowsLight', 'OguzDows'))[appearance == 'dark']


def settings(identifier, appearance=None, effects='off', resources=None):
    if identifier not in PROFILES or effects not in EFFECTS:
        raise ValueError('Bilinmeyen görünüm tarzı / efekti.')
    item = PROFILES[identifier]
    appearance = item['appearance'] if appearance is None else appearance
    gtk = theme(identifier, appearance)  # Aero'da da kimlik / tema girişini doğrula.
    if effects == 'aero' and identifier != 'mac':
        gtk = ('OguzDowsAero', 'OguzDowsAeroDark')[appearance == 'dark']
    dock = identifier in DOCK_PROFILES
    budget = current_policy() if resources is None else resources
    glass = effects in ('glass', 'aero') and budget['compositing']
    transitions = glass and effects == 'aero'
    # Üst çubuk, pencere çerçevesi, içerik ve tüm düğmeler daima opak.
    # Alfa yalnızca alt görev çubuğu / iskelenin ARKA PLAN rengindedir.
    light_panel = appearance == 'light' and (identifier in ('mac', 'windows11') or effects == 'aero')
    rgba = (['0.93', '0.94', '0.96'] if light_panel
            else ['0.09', '0.16', '0.25']) + ['0.94' if glass else '1']
    choices = [
        ('xfce4-panel', '/panels/panel-1/position', 'string', f"p={item['position']};x=0;y=0"),
        ('xfce4-panel', '/panels/panel-1/length', 'double', '100'),
        ('xfce4-panel', '/panels/panel-1/length-adjust', 'bool', 'false'),
        ('xfce4-panel', '/panels/panel-1/size', 'uint', str(item['size'])),
        ('xfce4-panel', '/panels/panel-1/mode', 'uint', '0'),
        ('xfce4-panel', '/panels/panel-1/enter-opacity', 'uint', '100'),
        ('xfce4-panel', '/panels/panel-1/leave-opacity', 'uint', '100'),
        ('xfce4-panel', '/panels/panel-1/background-style', 'uint', '1' if glass and item['position'] == 10 else '0'),
        ('xfce4-panel', '/panels/panel-1/background-rgba', 'double-array', rgba),
        # Durum / saat kümesi merkez grubun dışında; asimetrik sağ alan
        # Başlat + simgeleri sola itemez. Dar ekranda da çakışma olmaz.
        ('xfce4-panel', '/panels/panel-1/plugin-ids', 'int-array', ['3', '4', '5', '6', '7'] if identifier == 'windows11' else ['1', '3', '4', '5', '6', '7'] if dock else ['1', '2', '3', '4', '5', '6', '7']),
        ('xfce4-panel', '/plugins/plugin-1/button-title', 'string', 'Başlat' if identifier == 'oguzdows' else 'Etkinlikler' if identifier == 'gnome' else 'Uygulamalar' if identifier == 'mac' else 'OğuzDows'),
        ('xfce4-panel', '/plugins/plugin-1/button-icon', 'string', 'oguzdows-desktops' if identifier == 'mac' else 'oguzdows'),
        ('xfce4-panel', '/plugins/plugin-1/show-button-title', 'bool', str(identifier != 'windows11').lower()),
        ('xfce4-panel', '/plugins/plugin-1/show-button-icon', 'bool', 'true'),
        ('xfce4-panel', '/plugins/plugin-1/view-mode', 'int', '0'),
        ('xfce4-panel', '/plugins/plugin-2/show-labels', 'bool', str(not dock and identifier != 'windows11').lower()),
        ('xfce4-panel', '/plugins/plugin-2/flat-buttons', 'bool', 'true'),
        ('xfce4-panel', '/plugins/plugin-2/show-handle', 'bool', 'false'),
        ('xsettings', '/Net/ThemeName', 'string', gtk),
        ('xsettings', '/Gtk/ApplicationPreferDarkTheme', 'bool', str(appearance == 'dark').lower()),
        ('xsettings', '/Gtk/CursorThemeName', 'string', 'OguzDowsTespih'),
        ('xsettings', '/Gtk/CursorThemeSize', 'int', '32'),
        ('xsettings', '/Gtk/EnableAnimations', 'bool', str(transitions).lower()),
        ('xsettings', '/Gtk/DecorationLayout', 'string', 'close,minimize,maximize:menu' if identifier == 'mac' else 'menu:minimize,maximize,close'),
        ('xfwm4', '/general/theme', 'string', gtk),
        ('xfwm4', '/general/button_layout', 'string', item['layout']),
        ('xfwm4', '/general/title_alignment', 'string', 'center' if identifier == 'mac' else 'left'),
        # Aero'nun tek kompozitörü Picom; başarısızsa yönetici xfwm'a döner.
        ('xfwm4', '/general/use_compositing', 'bool', str(glass and not transitions).lower()),
        ('xfwm4', '/general/frame_opacity', 'int', '100'),
        ('xfwm4', '/general/inactive_opacity', 'int', '100'),
        ('xfwm4', '/general/popup_opacity', 'int', '100'),
        ('xfwm4', '/general/show_popup_shadow', 'bool', 'false'),
        ('xfwm4', '/general/show_frame_shadow', 'bool', str(glass and effects == 'aero').lower()),
        ('xfwm4', '/general/shadow_opacity', 'int', '20'),
    ]
    dock_values = [('position', 'string', 'p=7;x=0;y=0' if identifier == 'gnome' else 'p=10;x=0;y=0'),
                   ('mode', 'uint', '1' if identifier == 'gnome' else '0'),
                   ('length', 'double', '1'),
                   ('length-adjust', 'bool', 'true'), ('size', 'uint', '50' if identifier == 'gnome' else '48' if identifier == 'windows11' else '54'),
                   ('icon-size', 'uint', '32' if identifier == 'windows11' else '36'), ('nrows', 'uint', '1'), ('position-locked', 'bool', 'true'),
                   ('autohide-behavior', 'uint', '0'), ('enter-opacity', 'uint', '100'), ('leave-opacity', 'uint', '100'),
                   ('background-style', 'uint', '1'), ('background-rgba', 'double-array', rgba),
                   ('plugin-ids', 'int-array', (['1'] if identifier == 'windows11' else []) + ['90', '91', '92', '93', '94', '2'])]
    for key, kind, value in dock_values:
        choices.append(('xfce4-panel', '/panels/panel-90/' + key, kind, value if dock else None))
    for plugin, desktop in LAUNCHERS.items():
        choices.extend([('xfce4-panel', f'/plugins/plugin-{plugin}', 'string', 'launcher' if dock else None),
                        ('xfce4-panel', f'/plugins/plugin-{plugin}/items', 'string-array', ['/usr/share/applications/' + desktop] if dock else None)])
    choices.extend([('xfce4-panel', '/plugins/plugin-94', 'string', 'separator' if dock else None),
                    ('xfce4-panel', '/plugins/plugin-94/style', 'uint', '1' if dock else None),
                    ('xfce4-panel', '/plugins/plugin-94/expand', 'bool', 'false' if dock else None),
                    # En son yayımla; başka kullanıcı panellerini transaction korur.
                    ('xfce4-panel', '/panels', 'int-array', ['1', '90'] if dock else ['1'])])
    return choices


def run(command):
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=12,
                          env={**os.environ, 'LC_ALL': 'C.UTF-8'})


def state_directory():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oguzdows/profiles'


def read_state(directory, name, default=''):
    try:
        return (directory / name).read_text().strip()
    except OSError:
        return default


def selection(directory=None):
    directory = state_directory() if directory is None else directory
    identifier = read_state(directory, 'selected')
    identifier = identifier if identifier in PROFILES else 'oguzdows'
    appearance = read_state(directory, 'appearance')
    return identifier, appearance if appearance in APPEARANCES else PROFILES[identifier]['appearance']


def effect_selection(directory=None):
    value = read_state(state_directory() if directory is None else directory, 'effects')
    return value if value in EFFECTS else 'off'


def atomic_text(path, text):
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def decimal_value(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Xfce sayısal ayarı sonlu değil.')
    return format(number, '.12g')


def read_property(channel, path, kind, execute):
    result = execute(['xfconf-query', '-c', channel, '-p', path])
    if result.returncode:
        return None
    value = result.stdout.strip()
    if kind in ARRAY_TYPES:
        lines = value.splitlines()
        if not lines or not re.fullmatch(r'Value is an array with [0-9]+ items?:', lines[0]):
            raise ValueError('Xfce dizi ayarı güvenle okunamadı: ' + path)
        values = [line.strip() for line in lines[1:] if line.strip()]
        if len(values) != int(lines[0].split()[5]) or not 0 < len(values) <= 128:
            raise ValueError('Xfce dizi ayarının boyutu geçersiz: ' + path)
        # xfconf-query 4.18 double değerlerini %f ile (altı ondalık) yazar.
        return [decimal_value(item) for item in values] if kind == 'double-array' else values
    return decimal_value(value) if kind == 'double' else value


def set_property(channel, path, kind, value, execute):
    base = ['xfconf-query', '-c', channel, '-p', path]
    if value is None:
        if execute([*base, '--reset']).returncode and execute(base).returncode == 0:
            raise RuntimeError('Xfce ayarı geri alınamadı: ' + path)
        return
    arguments = []
    if kind in ARRAY_TYPES:
        arguments.append('--force-array')
        for item in value:
            arguments.extend(['-t', ARRAY_TYPES[kind], '-s', item])
    else:
        arguments.extend(['-t', kind, '-s', value])
    if execute([*base, *arguments]).returncode and execute([*base, '-n', *arguments]).returncode:
        raise RuntimeError('Xfce ayarı uygulanamadı: ' + path)


def transaction(choices, directory, execute, metadata, layout=False, undo=None):
    choices = [tuple(row) for row in choices]
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Başka bir görünüm işlemi devam ediyor.') from error
        previous = [(channel, path, kind, read_property(channel, path, kind, execute))
                    for channel, path, kind, _ in settings('oguzdows')]
        owned = read_state(directory, 'layout-v2') == 'owned'
        wants_dock = any(ch == 'xfce4-panel' and path == '/panels' and value and str(DOCK) in value
                         for ch, path, _kind, value in choices)
        if layout and not owned:
            reserved = any(value is not None for _ch, path, _kind, value in previous
                           if path.startswith(('/panels/panel-90/', '/plugins/plugin-9')))
            reserved = reserved or any(path == '/panels' and value and str(DOCK) in value
                                       for _ch, path, _kind, value in previous)
            if wants_dock and reserved:
                raise ValueError('90–94 numaralı panel / eklenti kullanımda. Kişisel panelin üzerine yazılmadı.')
            if not wants_dock:
                # Tek panel tarzı, bize ait olmayan kişisel iskeleye dokunmaz.
                choices = [row for row in choices if not row[1].startswith(('/panels/panel-90/', '/plugins/plugin-9'))]
        backup = directory / 'before-first-change.json'
        saved = validate_backup(json.loads(backup.read_text())) if backup.exists() else []
        saved_keys = {tuple(row[:2]) for row in saved}
        # Önceki sürümün ilk yedeğini koru; yeni anahtarları ilk değiştirmeden ekle.
        saved.extend(list(row) for row in previous if row[:2] not in saved_keys)
        atomic_text(backup, json.dumps(saved, ensure_ascii=False))
        old_metadata = {name: read_state(directory, name, None) for name in metadata}
        previous_by_key = {(ch, path): value for ch, path, _kind, value in previous}
        if layout:
            current_panels = previous_by_key.get(('xfce4-panel', '/panels')) or ['1']
            panels = [value for value in current_panels if value != str(DOCK) or not (owned or wants_dock)]
            if '1' not in panels:
                panels.insert(0, '1')
            if wants_dock:
                panels.append(str(DOCK))
            plugins = previous_by_key.get(('xfce4-panel', '/panels/panel-1/plugin-ids')) or []
            extras = [value for value in plugins if value not in ('1', '2', '3', '4', '5', '6', '7')]
            choices = [(ch, path, kind,
                        panels if ch == 'xfce4-panel' and path == '/panels' else
                        value[:value.index('3')] + extras + value[value.index('3'):] if
                        ch == 'xfce4-panel' and path == '/panels/panel-1/plugin-ids' else value)
                       for ch, path, kind, value in choices]
        changed = []
        try:
            for row in choices:
                if previous_by_key.get(row[:2]) == row[3]:
                    continue
                changed.append(row[:2])
                set_property(*row, execute)
            for name, value in metadata.items():
                if value is None:
                    (directory / name).unlink(missing_ok=True)
                else:
                    atomic_text(directory / name, value)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            for row in reversed(previous):
                if row[:2] in changed:
                    try:
                        set_property(*row, execute)
                    except (OSError, RuntimeError, subprocess.SubprocessError):
                        pass
            for name, value in old_metadata.items():
                try:
                    if value is None:
                        (directory / name).unlink(missing_ok=True)
                    else:
                        atomic_text(directory / name, value + '\n')
                except OSError:
                    pass
            raise
        if undo is not None:
            rows = [row for row in previous if row[:2] in changed]
            metadata_before = {name: None if value is None else value + '\n' for name, value in old_metadata.items()}
            undo.append(lambda: transaction(rows, directory, execute, metadata_before))


def apply(identifier, directory=None, execute=run, appearance=None):
    directory = state_directory() if directory is None else directory
    if appearance is None:
        value = read_state(directory, 'appearance')
        appearance = value if value in APPEARANCES else None
    transaction(settings(identifier, appearance, effect_selection(directory)), directory, execute,
                {'selected': identifier + '\n', 'layout-v2': 'owned\n' if identifier in DOCK_PROFILES else None}, layout=True)


def set_appearance(appearance, directory=None, execute=run):
    if appearance not in APPEARANCES:
        raise ValueError('Bilinmeyen açık/koyu tema seçimi.')
    directory = state_directory() if directory is None else directory
    identifier, _ = selection(directory)
    keys = {('xsettings', '/Net/ThemeName'), ('xsettings', '/Gtk/ApplicationPreferDarkTheme'), ('xfwm4', '/general/theme')}
    if identifier in DOCK_PROFILES and read_state(directory, 'layout-v2') == 'owned':
        keys.add(('xfce4-panel', '/panels/panel-90/background-rgba'))
    elif effect_selection(directory) == 'aero':
        keys.add(('xfce4-panel', '/panels/panel-1/background-rgba'))
    transaction([row for row in settings(identifier, appearance, effect_selection(directory)) if row[:2] in keys], directory, execute,
                {'appearance': appearance + '\n'})


def set_effects(effects, directory=None, execute=run, resources=None):
    if effects not in EFFECTS:
        raise ValueError('Bilinmeyen efekt seçimi.')
    directory = state_directory() if directory is None else directory
    identifier, appearance = selection(directory)
    keys = {('xsettings', '/Net/ThemeName'), ('xsettings', '/Gtk/EnableAnimations'), ('xfwm4', '/general/theme'),
            ('xfwm4', '/general/show_frame_shadow'), ('xfwm4', '/general/shadow_opacity'),
            ('xfwm4', '/general/use_compositing'), ('xfce4-panel', '/panels/panel-1/background-style'),
            ('xfce4-panel', '/panels/panel-1/background-rgba'), ('xfce4-panel', '/panels/panel-90/background-rgba')}
    choices = [row for row in settings(identifier, appearance, effects, resources) if row[:2] in keys]
    # Daha önce iskele seçilmediyse ayrılmış panel alanına yazma.
    if identifier not in DOCK_PROFILES:
        choices = [row for row in choices if '/panel-90/' not in row[1]]
    transaction(choices, directory, execute, {'effects': effects + '\n'})


def set_shared(preferences, directory=None, execute=run, resources=None, material_theme=None, surface_only=False, undo=None):
    """Ortak temayı uygula; panel dizileri, kısayollar ve imleç değişmez.

    Zengin cam ayrı temadır: yalnız GPU bütçesi + açık blur onayıyla. Eski
    Aero ve düşük kaynak döşemeleri opak kalır; başlık yazısı / düğmeler her
    iki temada da opaktır.
    """
    directory = state_directory() if directory is None else directory
    resources = current_policy() if resources is None else resources
    identifier, _appearance = selection(directory)
    appearance, effect = preferences['appearance'], preferences['effects']
    keys = {('xsettings', '/Net/ThemeName'), ('xsettings', '/Gtk/ApplicationPreferDarkTheme'),
            ('xsettings', '/Gtk/EnableAnimations'), ('xfwm4', '/general/theme'),
            ('xfwm4', '/general/show_frame_shadow'), ('xfwm4', '/general/shadow_opacity'),
            ('xfwm4', '/general/use_compositing'), ('xfce4-panel', '/panels/panel-1/background-style'),
            ('xfce4-panel', '/panels/panel-1/background-rgba')}
    if identifier in DOCK_PROFILES and read_state(directory, 'layout-v2') == 'owned':
        keys.add(('xfce4-panel', '/panels/panel-90/background-rgba'))
    glass = effect == 'aero' and preferences['blur'] and resources['compositing']
    if surface_only:
        keys = {key for key in keys if key[1] in ('/Net/ThemeName', '/general/theme') or key[1].endswith('background-rgba')}
    choices = []
    for channel, path, kind, value in settings(identifier, appearance, effect, resources):
        if (channel, path) not in keys:
            continue
        if glass and identifier != 'mac' and path in ('/Net/ThemeName', '/general/theme'):
            value = material_theme or ('OguzDowsAeroGlassDark' if appearance == 'dark' else 'OguzDowsAeroGlass')
        if path == '/Gtk/EnableAnimations' and preferences['motion'] == 'reduced':
            value = 'false'
        if glass and path.endswith('background-rgba'):
            # Üst durum çubuğuna alfa uygulanmaz. Metin / ikon katmanı opak.
            panel = 1 if '/panel-1/' in path else 90
            if panel == 90 or PROFILES[identifier]['position'] == 10:
                color = [int(preferences['accent'][i:i + 2], 16) / 255 for i in (1, 3, 5)]
                base = .13 if appearance == 'dark' else .94
                value = [decimal_value(.12 * component + .88 * base) for component in color] + ['0.84']
        choices.append((channel, path, kind, value))
    transaction(choices, directory, execute, {'appearance': appearance + '\n', 'effects': effect + '\n'}, undo=undo)


def validate_backup(values):
    allowed = {(channel, path, kind) for channel, path, kind, _ in settings('oguzdows')}
    allowed.add(('xfce4-panel', '/panels/panel-1/length', 'uint'))  # 1.1 ilk yedek biçimi
    if not isinstance(values, list) or len(values) > len(allowed):
        raise ValueError('Görünüm yedeği geçersiz.')
    seen = set()
    for row in values:
        if (not isinstance(row, list) or len(row) != 4 or not all(isinstance(value, str) for value in row[:3])
                or tuple(row[:3]) not in allowed or tuple(row[:2]) in seen):
            raise ValueError('Görünüm yedeği geçersiz; serbest komut çalıştırılmadı.')
        value, kind = row[3], row[2]
        if value is None:
            valid = True
        elif kind in ARRAY_TYPES:
            valid = (isinstance(value, list) and 0 < len(value) <= 128
                     and all(isinstance(item, str) and len(item) <= 4096 for item in value))
        else:
            valid = isinstance(value, str) and len(value) <= 4096
        if not valid:
            raise ValueError('Görünüm yedeği türü geçersiz.')
        seen.add(tuple(row[:2]))
    return values


def restore(directory=None, execute=run):
    directory = state_directory() if directory is None else directory
    values = validate_backup(json.loads((directory / 'before-first-change.json').read_text()))
    transaction(values, directory, execute, {'selected': None, 'appearance': None, 'effects': None, 'layout-v2': None})


def reload_panels(execute=run):
    # Yalnızca ayrı onay düğmesinden. kill / pkill / --quit / root yok.
    if execute(['xfce4-panel', '--restart']).returncode:
        raise RuntimeError('Panel yenilenemedi. Ayarlar kaydedildi; oturumu yeniden açabilirsin.')


def session(execute=run, directory=None, resources=None):
    resources = current_policy() if resources is None else resources
    # Güçlü makinede varsayılanı zorla açma / kullanıcının kompozitörüne dokunma.
    # Düşük RAM veya güvenli grafik kipinde, önceden seçili cam da devre dışıdır.
    if not resources['compositing']:
        for row in [('xfwm4', '/general/use_compositing', 'bool', 'false'),
                    ('xsettings', '/Gtk/EnableAnimations', 'bool', 'false')]:
            set_property(*row, execute)
        if effect_selection(directory) in ('glass', 'aero'):
            identifier, appearance = selection(directory)
            for row in settings(identifier, appearance, 'off'):
                if row[3] is not None and (row[1].endswith('background-rgba') or row[1] == '/panels/panel-1/background-style'):
                    set_property(*row, execute)
    elif effect_selection(directory) in ('glass', 'aero'):
        set_effects(effect_selection(directory), directory, execute, resources)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', action='store_true')
    args = parser.parse_args()
    if args.session:
        session()
