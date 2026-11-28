"""One-shot, reversible Thunar preview budget for PC / Pi / generic ARM.

No file enumeration, thumbnail decoding, resident process or cache deletion.
Only absent or still-owned preferences change; personal Thunar choices win.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# -I excludes the script directory too. Only this fixed installed helper's
# directory is added, never PYTHONPATH / cwd / a path from preferences.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_state as state
from profiles import read_property, run, set_property

FIELDS = {'thumbnails': ('/misc-thumbnail-mode', 'string'),
          'max-bytes': ('/misc-thumbnail-max-file-size', 'uint64'),
          'frames': ('/misc-thumbnail-draw-frames', 'bool')}
MODES = {'THUNAR_THUMBNAIL_MODE_NEVER', 'THUNAR_THUMBNAIL_MODE_ONLY_LOCAL', 'THUNAR_THUMBNAIL_MODE_ALWAYS'}


class ThunarSettings:
    name = 'thunar-performance'
    keys = set(FIELDS)

    def __init__(self, execute=run):
        self.execute = execute

    def validate(self, key, value):
        if key not in self.keys:
            raise ValueError('İzin verilmeyen Thunar anahtarı.')
        if value is None:
            return
        valid = isinstance(value, str) and (
            value in MODES if key == 'thumbnails' else value in ('true', 'false') if key == 'frames'
            else bool(re.fullmatch(r'[0-9]{1,20}', value)) and int(value) <= 2**64 - 1)
        if not valid:
            raise ValueError('Thunar ayarı beklenen türde değil; kişisel değer korunuyor.')

    def read(self, key):
        self.validate(key, None)
        path, kind = FIELDS[key]
        return read_property('thunar', path, kind, self.execute)

    def write(self, key, value):
        self.validate(key, value)
        path, kind = FIELDS[key]
        set_property('thunar', path, kind, value, self.execute)


def targets(resources):
    memory = max(0, int(resources.get('memory_kib', 0)))
    mini = bool(resources.get('legacy_cpu') or resources.get('profile') == 'mini' or memory <= 786432)
    # A manual full profile never overrides the physical low-memory budget.
    limit = 8 if mini else 16 if memory <= 2097152 else 32
    return {'thumbnails': 'THUNAR_THUMBNAIL_MODE_NEVER' if mini else 'THUNAR_THUMBNAIL_MODE_ONLY_LOCAL',
            'max-bytes': str(limit * 1024**2), 'frames': 'false'}


def apply(resources, directory, backend=None):
    directory = Path(directory)
    receipt = state.read_json(directory / 'xfce-applied.json', {})
    if isinstance(receipt, dict) and receipt.get('restored') is True:
        return {'changed': [], 'preserved': [], 'restored': True}
    backend = ThunarSettings() if backend is None else backend
    journal = state.Journal(backend, directory)
    changes, preserved = {}, []
    for key, value in targets(resources).items():
        current = backend.read(key)
        row = journal.rows.get(key)
        if (row is None and current is not None) or (row is not None and current != row['applied']):
            preserved.append(key)
            continue
        if current != value:
            changes[key] = value
    if changes:
        journal.apply(changes)
    return {'changed': sorted(changes), 'preserved': sorted(preserved), 'restored': False}


def restore(directory, backend=None):
    directory = Path(directory)
    if not (directory / (ThunarSettings.name + '-settings.json')).exists():
        return []
    return state.Journal(ThunarSettings() if backend is None else backend, directory).restore()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', action='store_true', required=True)
    parser.parse_args()
    import desktop_runtime as runtime
    from resource_policy import current_policy
    runtime.normal_session()
    if runtime.current() != 'xfce' or runtime.installation_busy():
        return
    with state.locked() as directory:
        print(json.dumps(apply(current_policy(), directory), ensure_ascii=False))


if __name__ == '__main__':
    main()
