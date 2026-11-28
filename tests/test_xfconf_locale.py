"""CLI locale regressions. Synthetic GNU catalog != real Xfce/device acceptance."""
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import ROOT
import desktop_runtime
import profiles
import wallpapers


RUNNERS = (profiles, desktop_runtime, wallpapers)
ENGLISH = 'Value is an array with %d items:'
TURKISH = 'Değer, %d ögeden oluşan dizidir:'


def write_catalog(path):
    """Minimal synthetic GNU .mo, using upstream xfconf's Turkish header."""
    messages = {'': 'Content-Type: text/plain; charset=UTF-8\nLanguage: tr\n', ENGLISH: TURKISH}
    keys = sorted(messages)
    originals = [key.encode() for key in keys]
    translations = [messages[key].encode() for key in keys]
    start = 28 + len(keys) * 16
    table, strings = [], b''
    for sequence in (originals, translations):
        for value in sequence:
            table.extend((len(value), start + len(strings)))
            strings += value + b'\0'
    path.parent.mkdir(parents=True)
    path.write_bytes(struct.pack('<7I', 0x950412de, 0, len(keys), 28, 28 + len(keys) * 8, 0, 0)
                     + struct.pack('<' + 'I' * len(table), *table) + strings)


class XfconfLocaleTests(unittest.TestCase):
    def test_xfconf_subprocesses_neutralize_language_without_losing_utf8_or_private_bus(self):
        for module in RUNNERS:
            for program in ('xfconf-query', '/usr/bin/xfconf-query'):
                with self.subTest(module=module.__name__, program=program), patch.dict(os.environ, {
                        'LANG': 'tr_TR.UTF-8', 'LANGUAGE': 'tr:en', 'LC_ALL': 'tr_TR.UTF-8',
                        'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/private/test-only-bus'}):
                    before = dict(os.environ)
                    command = [program, '-c', 'xfce4-panel', '-p', '/panels']
                    with patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess(command, 0, '', '')) as call:
                        module.run(command)
                    environment = call.call_args.kwargs['env']
                    self.assertEqual(environment['LC_ALL'], 'C.UTF-8')
                    self.assertEqual(environment['LANGUAGE'], 'C')
                    self.assertEqual(environment['LANG'], 'tr_TR.UTF-8')
                    self.assertEqual(environment['DBUS_SESSION_BUS_ADDRESS'], before['DBUS_SESSION_BUS_ADDRESS'])
                    self.assertEqual(call.call_args.args[0], command)
                    self.assertGreater(call.call_args.kwargs['timeout'], 0)
                    self.assertEqual(dict(os.environ), before)

    def test_gui_panel_restart_and_other_commands_keep_the_users_language(self):
        for module in RUNNERS:
            with self.subTest(module=module.__name__), patch.dict(os.environ, {'LANGUAGE': 'tr:en'}):
                with patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as call:
                    module.run(['xfce4-panel', '--restart'])
                self.assertEqual(call.call_args.kwargs['env']['LANGUAGE'], 'tr:en')
                self.assertEqual(os.environ['LANGUAGE'], 'tr:en')

    def test_real_gnu_gettext_replays_the_inherited_language_bug_in_a_synthetic_cli_transport(self):
        if not hasattr(ctypes.CDLL(None), 'dgettext'):
            self.skipTest('GNU gettext is not provided by this platform')
        child = '''import ctypes,locale,sys
locale.setlocale(locale.LC_ALL, '')
c=ctypes.CDLL(None)
c.bindtextdomain.argtypes=[ctypes.c_char_p,ctypes.c_char_p]
c.dgettext.argtypes=[ctypes.c_char_p,ctypes.c_char_p]; c.dgettext.restype=ctypes.c_char_p
c.bindtextdomain(b'xfconf-unit-fixture',sys.argv[1].encode())
print(c.dgettext(b'xfconf-unit-fixture',b'Value is an array with %d items:').decode('utf-8') % 2)
print('\\n1\\n2')
'''
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_catalog(root / 'tr/LC_MESSAGES/xfconf-unit-fixture.mo')
            command = [sys.executable, '-c', child, str(root)]
            environment = {**os.environ, 'LC_ALL': 'C.UTF-8', 'LANGUAGE': 'tr:en'}
            control = real_run(command, env=environment, capture_output=True, text=True, timeout=10, check=True)
            self.assertEqual(control.stdout.splitlines()[0], TURKISH % 2)
            # Replace only command transport; real GNU locale/catalogue selection
            # runs in a subprocess. Native ARM CI separately uses real xfconf.
            for module in RUNNERS:
                def transport(_command, **kwargs):
                    return real_run(command, **kwargs)
                with self.subTest(module=module.__name__), patch.dict(os.environ, environment, clear=True), \
                        patch.object(module.subprocess, 'run', side_effect=transport):
                    self.assertEqual(profiles.read_property('xfce4-panel', '/panels', 'int-array', module.run), ['1', '2'])

    def test_localized_or_malformed_headers_still_fail_closed_not_guessed_as_valid_arrays(self):
        for text in (TURKISH % 2 + '\n\n1\n2', 'other header\n1\n2', ENGLISH % 3 + '\n\n1\n2'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                profiles.read_property('xfce4-panel', '/panels', 'int-array',
                                       lambda args: subprocess.CompletedProcess(args, 0, text, ''))

    def test_image_uses_the_language_environment_that_triggered_the_regression(self):
        source = (ROOT / 'scripts/configure-pi.py').read_text()
        self.assertIn('LANGUAGE="tr:en"', source)


if __name__ == '__main__':
    unittest.main()
