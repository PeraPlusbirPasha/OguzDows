"""Xfce's live XSettings + GTK config / portal appearance, one reversible choice.

GTK4/libadwaita read the standard color-scheme portal, NOT a GTK3 CSS theme.
Only named keys are edited; other settings/comments and custom bindings survive.
No environment-wide GTK_THEME override, Qt daemon, polling or privileged writes.
"""
from __future__ import annotations

import configparser
import os
import re
import stat
import tempfile
from pathlib import Path

import desktop_state as state

LIMIT = 65536
FILES = {'gtk3-theme': ('gtk-3.0', 'gtk-theme-name'),
         'gtk3-dark': ('gtk-3.0', 'gtk-application-prefer-dark-theme')}


def read_ini(path):
    path = Path(path)
    if path.parent.is_symlink():
        raise ValueError('GTK ayar dizini bağlantı; kişisel dosyaya dokunulmadı.')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return ''
    with os.fdopen(descriptor, 'r', encoding='utf-8', newline='') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > LIMIT:
            raise ValueError('GTK ayarı bu kullanıcıya ait, sınırlı normal dosya olmalı.')
        value = stream.read(LIMIT + 1)
    if len(value.encode()) > LIMIT:
        raise ValueError('GTK ayarı okuma sınırını aştı.')
    parser = configparser.ConfigParser(interpolation=None)
    if value.strip():
        parser.read_string(value)
    return value


def edit_key(text, name, value):
    """Keep unrelated lines/comments byte-for-byte, including other sections."""
    lines = text.splitlines(keepends=True)
    output, inside, found_section, written = [], False, False, False
    for line in lines:
        section = re.match(r'\s*\[([^\]]+)\]', line)
        if section:
            if inside and not written and value is not None:
                output.append(f'{name}={value}\n'); written = True
            inside = section[1].strip() == 'Settings'
            found_section |= inside
        if inside and re.match(r'\s*' + re.escape(name) + r'\s*[=:]', line, re.I):
            if value is not None and not written:
                output.append(f'{name}={value}\n')
            written = True
        else:
            output.append(line)
    if value is not None and not written:
        if output and not output[-1].endswith('\n'):
            output[-1] += '\n'
        if not found_section:
            output.append('[Settings]\n')
        # Insert into Settings, not into a later arbitrary section.
        output.append(f'{name}={value}\n')
    return ''.join(output)


class AppearanceSettings:
    name = 'xfce-appearance'
    keys = {*FILES, 'color-scheme'}

    def __init__(self, root=None, settings=None):
        self.root = Path(root) if root is not None else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
        self.settings = settings
        if settings is None:
            try:
                from gi.repository import Gio
                source = Gio.SettingsSchemaSource.get_default()
                schema = source.lookup('org.gnome.desktop.interface', True) if source else None
                if schema and schema.has_key('color-scheme'):
                    self.settings = Gio.Settings.new_full(schema, None, None)
            except (ImportError, ValueError):
                pass

    def validate(self, key, value):
        if key not in self.keys:
            raise ValueError('İzin verilmeyen görünüm anahtarı.')
        if value is None:
            return
        if key == 'color-scheme':
            valid = value in ('default', 'prefer-dark', 'prefer-light')
        elif key.endswith('-dark'):
            valid = value in ('0', '1')
        else:
            valid = isinstance(value, str) and 0 < len(value) <= 200 and not any(c in value for c in '\n\r\0')
        if not valid:
            raise ValueError('GTK / portal görünüm değeri geçersiz.')

    def read(self, key):
        self.validate(key, None)
        if key == 'color-scheme':
            value = self.settings.get_user_value('color-scheme') if self.settings else None
            return value.unpack() if value is not None else None
        folder, name = FILES[key]
        parser = configparser.ConfigParser(interpolation=None)
        text = read_ini(self.root / folder / 'settings.ini')
        if text.strip():
            parser.read_string(text)
        value = parser.get('Settings', name, fallback=None)
        if key.endswith('-dark') and value is not None:
            value = '1' if parser.getboolean('Settings', name) else '0'
        self.validate(key, value)
        return value

    def write(self, key, value):
        self.validate(key, value)
        if key == 'color-scheme':
            if self.settings is None:
                raise ValueError('Standart renk tercihi şeması bu sistemde yok.')
            if value is None:
                self.settings.reset('color-scheme')
            elif not self.settings.set_string('color-scheme', value):
                raise RuntimeError('Standart renk tercihi yazılamadı.')
            self.settings.sync()
            return
        folder, name = FILES[key]
        path = self.root / folder / 'settings.ini'
        text = read_ini(path)
        updated = edit_key(text, name, value)
        if updated == text:
            return
        if path.parent.is_symlink() or self.root.is_symlink():
            raise ValueError('GTK ayar yolu bağlantı; değiştirilmedi.')
        path.parent.mkdir(parents=True, exist_ok=True)
        info = path.parent.stat()
        if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode):
            raise ValueError('GTK dizini bu kullanıcıya ait olmalı.')
        if value is None and updated.strip() in ('', '[Settings]'):
            path.unlink(missing_ok=True)
            return
        if len(updated.encode()) > LIMIT:
            raise ValueError('GTK ayarı yazma sınırını aşıyor.')
        descriptor, temporary = tempfile.mkstemp(prefix='.oguzdows-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(updated); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def changes(self, preferences, theme):
        # libadwaita explicitly warns on GTK4's prefer-dark GtkSettings key.
        # The standard color-scheme transport below is its supported API.
        values = {'gtk3-theme': theme, 'gtk3-dark': '1' if preferences['appearance'] == 'dark' else '0'}
        if self.settings:
            values['color-scheme'] = 'prefer-dark' if preferences['appearance'] == 'dark' else 'prefer-light'
        notes = [] if self.settings else ['Standart renk tercihi şeması yok; GTK4 / libadwaita senkronu için gsettings-desktop-schemas ve xdg-desktop-portal-gtk gerekli.']
        for key in list(values):
            try:
                self.read(key)
            except (OSError, ValueError, configparser.Error) as error:
                del values[key]
                notes.append('Kişisel GTK ayarı korunuyor: ' + str(error))
        return values, notes


def apply(preferences, theme, directory, undo=None):
    backend = AppearanceSettings()
    changes, notes = backend.changes(preferences, theme)
    state.Journal(backend, directory).apply(changes, undo=undo)
    return notes


def restore(directory):
    return state.Journal(AppearanceSettings(), directory).restore()
