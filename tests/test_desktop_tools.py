import copy
import hashlib
import json
import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from support import ROOT, load
from xfconf_fixture import Xfconf

profiles = load('profiles_test', 'system/usr/lib/oguzdows/profiles.py')
culture = load('culture_core_test', 'system/usr/lib/oguzdows/culture_core.py')
store = load('store_core_test', 'system/usr/lib/oguzdows/store_core.py')
lifecycle = load('store_lifecycle_test', 'system/usr/lib/oguzdows/store_lifecycle.py')
memory = load('memory_probe_test', 'system/usr/lib/oguzdows/memory_probe.py')


class ProfileTests(unittest.TestCase):
    def test_five_profiles_only_change_appearance_and_never_reenable_effects(self):
        self.assertEqual(set(profiles.PROFILES), {'oguzdows', 'kde', 'gnome', 'xfce', 'mac'})
        for name in profiles.PROFILES:
            values = {(channel, path): value for channel, path, _kind, value in profiles.settings(name)}
            self.assertEqual(values['xfce4-panel', '/panels/panel-1/enter-opacity'], '100')
            self.assertEqual(values['xfce4-panel', '/panels/panel-1/leave-opacity'], '100')
            self.assertEqual(values['xfwm4', '/general/use_compositing'], 'false')
            self.assertIn('C', values['xfwm4', '/general/button_layout'])
        with self.assertRaises(ValueError):
            profiles.settings('kde; sudo something')

    def test_apply_backs_up_once_and_restore_only_accepts_known_properties(self):
        execute = Xfconf(profiles.settings('oguzdows'))
        calls = execute.calls
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles.apply('kde', root, execute)
            backup = root / 'before-first-change.json'
            before = backup.read_bytes()
            profiles.apply('mac', root, execute)
            self.assertEqual(backup.read_bytes(), before)
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
            self.assertEqual((root / 'selected').read_text().strip(), 'mac')
            profiles.restore(root, execute)
            self.assertTrue(all(command[0] == 'xfconf-query' for command in calls))
            backup.write_text(json.dumps([['channel', '/arbitrary', 'string', 'x']]))
            calls.clear()
            with self.assertRaises(ValueError):
                profiles.restore(root, execute)
            self.assertFalse(calls)
            for invalid in ({}, [1], [[[], '/path', 'string', 'value']]):
                backup.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    profiles.restore(root, execute)
                self.assertFalse(calls)

    def test_failed_apply_rolls_back_existing_and_new_properties(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        xfconf.values.pop(('xfce4-panel', '/panels/panel-1/size'))
        calls = xfconf.calls
        def execute(command):
            if len(command) > 5 and command[4].endswith('button_layout') and command[-1] != 'original':
                calls.append(command)
                return subprocess.CompletedProcess(command, 1, '', '')
            return xfconf(command)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                profiles.apply('mac', root, execute)
            self.assertTrue(any('--reset' in command and command[4].endswith('size') for command in calls))
            self.assertFalse((root / 'selected').exists())


class CultureTests(unittest.TestCase):
    def make_home(self, directory):
        home = Path(directory) / 'home'
        documents = home / 'Belgeler'
        documents.mkdir(parents=True)
        (documents / 'Türkçe.txt').write_text('İmece ile birlikte üretelim.\n')
        target = Path(directory) / 'usb'
        target.mkdir()
        return home, documents, target

    def test_turkish_case_keeps_dotted_and_dotless_i(self):
        self.assertEqual(culture.turkish_upper('istanbul ısparta çığ öşü'), 'İSTANBUL ISPARTA ÇIĞ ÖŞÜ')
        self.assertEqual(culture.turkish_lower('İSTANBUL ISPARTA ÇIĞ ÖŞÜ'), 'istanbul ısparta çığ öşü')

    def test_backup_preserves_source_excludes_hidden_links_and_emits_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            home, source, target = self.make_home(directory)
            (source / '.env').write_text('secret')
            (source / '.ssh').mkdir()
            (source / '.ssh/key').write_text('private')
            (source / 'link').symlink_to('/etc/passwd')
            archive = culture.heybe(source, target, home)
            with tarfile.open(archive) as result:
                self.assertEqual(result.getnames(), ['Belgeler/Türkçe.txt'])
                self.assertTrue(all(member.isfile() for member in result.getmembers()))
                self.assertEqual(result.extractfile(result.getmembers()[0]).read().decode(), 'İmece ile birlikte üretelim.\n')
            self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
            self.assertTrue((source / '.env').is_file())
            self.assertTrue((source / 'Türkçe.txt').is_file())
            self.assertTrue(archive.with_name(archive.name + '.sha256').read_text().startswith(hashlib.sha256(archive.read_bytes()).hexdigest()))
            self.assertNotEqual(archive, culture.heybe(source, target, home))

    def test_backup_never_writes_into_source_or_overwrites_on_failed_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            home, source, target = self.make_home(directory)
            with self.assertRaises(ValueError):
                culture.heybe(source, source, home)
            self.assertEqual(len(list(source.iterdir())), 1)
            with patch.object(culture, 'LIMIT', 1), self.assertRaises(ValueError):
                culture.heybe(source, target, home)
            self.assertFalse(list(target.iterdir()))

    def test_share_has_manifest_is_local_and_rejects_ambiguous_names(self):
        with tempfile.TemporaryDirectory() as directory:
            home, source, target = self.make_home(directory)
            file = source / 'Türkçe.txt'
            archive = culture.imece([file], target, home)
            with zipfile.ZipFile(archive) as result:
                self.assertEqual(set(result.namelist()), {'Dosyalar/Türkçe.txt', 'BASLANGIC.txt', 'Dogrulama.json'})
                metadata = json.loads(result.read('Dogrulama.json'))
                self.assertEqual(metadata[0]['sha256'], hashlib.sha256(file.read_bytes()).hexdigest())
            (home / 'Türkçe.txt').write_text('other')
            with self.assertRaises(ValueError):
                culture.imece([file, home / 'Türkçe.txt'], target, home)
            self.assertEqual(len(list(target.glob('*.zip'))), 1)
            self.assertTrue(file.exists())

    def test_hidden_outside_home_symlinks_and_windows_path_tricks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            home, source, target = self.make_home(directory)
            (home / '.ssh').mkdir()
            (home / '.ssh/id').write_text('private')
            (home / '.settings').write_text('private')
            link = source / 'link'
            link.symlink_to(home / '.ssh/id')
            for file in (home / '.ssh/id', home / '.settings', Path('/etc/passwd'), link):
                with self.subTest(file=file), self.assertRaises(ValueError):
                    culture.imece([file], target, home)
            for name in ('..\\outside', 'name:stream', 'bad\nname'):
                file = source / name
                file.write_text('x')
                with self.assertRaises(ValueError):
                    culture.imece([file], target, home)
            self.assertFalse(list(target.iterdir()))

    def test_changed_source_to_fifo_or_parent_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            home, source, _target = self.make_home(directory)
            fifo = source / 'pipe'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                culture.open_regular(fifo, home)
            moved = home / 'other'
            source.rename(moved)
            source.symlink_to(moved, target_is_directory=True)
            with self.assertRaises(OSError):
                culture.open_regular(source / 'Türkçe.txt', home)


class StoreTests(unittest.TestCase):
    def test_store_visibility_requires_first_window_and_preserves_minimized_clients(self):
        state = lifecycle.Visibility()
        self.assertFalse(state.closed([]))
        self.assertFalse(state.closed([]))
        self.assertFalse(state.closed([123]))
        self.assertFalse(state.closed([123]))  # Küçültülen EWMH istemcisi listede kalır.
        self.assertFalse(state.closed([456]))  # İkinci mağaza/diyalog da korunur.
        self.assertTrue(state.closed([]))
        self.assertFalse(state.closed([789]))  # Yeniden açılış gecikmiş çıkışı durdurur.

    def test_x11_requires_ewmh_and_only_matches_exact_software_identity(self):
        monitor = lifecycle.X11Windows.__new__(lifecycle.X11Windows)
        monitor.X, monitor.error = NS(AnyPropertyType=0), NS(XError=RuntimeError)
        monitor.clients, monitor.application, monitor.supporting = 1, 2, 3
        monitor.root, monitor.connection = Mock(), Mock()
        monitor.root.get_full_property.return_value = None
        with self.assertRaisesRegex(RuntimeError, 'EWMH'):
            monitor.windows()
        monitor.root.get_full_property.side_effect = lambda atom, _kind: NS(value=[123]) if atom == monitor.supporting else None
        self.assertEqual(monitor.windows(), [])
        monitor.root.get_full_property.side_effect = None
        monitor.root.get_full_property.return_value = NS(value=[5, 6, 7])
        objects = {}
        for identifier, app, classes in ((5, None, ('gnome-software', 'Gnome-software')),
                                         (6, b'org.gnome.Software', ('other', 'class')),
                                         (7, b'org.example.Software', ('software', 'AnotherStore'))):
            window = Mock()
            window.get_full_property.return_value = None if app is None else NS(value=app)
            window.get_wm_class.return_value = classes
            objects[identifier] = window
        monitor.connection.create_resource_object.side_effect = lambda _kind, identifier: objects[identifier]
        self.assertEqual(monitor.windows(), [5, 6])

    def test_store_never_autostarts_or_forcibly_kills_package_work(self):
        autostart = (ROOT / 'system/etc/xdg/autostart/org.gnome.Software.desktop').read_text()
        self.assertIn('Hidden=true', autostart)
        source = (ROOT / 'system/usr/lib/oguzdows/store.py').read_text()
        self.assertIn("self.spawn(['--quit'])", source)
        self.assertIn('HANDLES_COMMAND_LINE', source)
        self.assertNotIn('.terminate(', source)
        self.assertNotIn('.kill(', source)
        self.assertNotIn('while True', source)
        self.assertIn('GLib.io_add_watch', source)
        hidden = source.split('def close_if_hidden', 1)[1].split('def not_mapped', 1)[0]
        self.assertNotIn('self.safe_quit(', hidden, 'Pencereyi gizlemek indirmeyi iptal etmemeli.')
        self.assertIn('self.controller(', hidden)
        self.assertIn('İşlemler bitti', source)
        self.assertIn('dialog.set_default_response(Gtk.ResponseType.CANCEL)', source)
        entry = (ROOT / 'system/usr/local/share/applications/org.gnome.Software.desktop').read_text()
        self.assertIn('Exec=/usr/local/bin/oguzdows-store', entry)
        self.assertIn('NoDisplay=true', entry)

    def test_supported_setup_only_uses_user_scope_fixed_https_and_gpg(self):
        execute = Mock(side_effect=['x86_64', '', '', 'flathub\thttps://dl.flathub.org/repo/\tuser'])
        store.setup_flathub(execute)
        command = execute.call_args_list[2].args[0]
        self.assertEqual(command, ['/usr/bin/flatpak', '--user', 'remote-add', '--if-not-exists', '--from', 'flathub', store.FLATHUB_DESCRIPTOR])
        self.assertNotIn('--no-gpg-verify', command)

    def test_existing_official_remote_is_idempotent_and_unknown_arch_is_honest(self):
        execute = Mock(side_effect=['x86_64', 'flathub\thttps://dl.flathub.org/repo/\tuser'])
        store.setup_flathub(execute)
        self.assertEqual(execute.call_count, 2)
        for arch in ('i386', 'arm', 'x86_64\nmalformed'):
            execute = Mock(return_value=arch)
            with self.assertRaises(ValueError):
                store.setup_flathub(execute)
            self.assertEqual(execute.call_count, 1)
        for listing in ('flathub\thttp://untrusted.invalid/\tuser', 'flathub\thttps://dl.flathub.org/repo/\tno-gpg-verify', 'flathub'):
            with self.assertRaises(ValueError):
                store.official_remote(listing)


class MemoryTests(unittest.TestCase):
    def samples(self, used=500_000_000):
        return [{'used_bytes': used, 'method': 'MemTotal − MemAvailable', 'graphical_xfce': True,
                 'known_foreground_or_package_work': [], 'cpu_total_ticks': index * 1000, 'cpu_idle_ticks': index * 990}
                for index in range(6)]

    def test_true_idle_target_uses_decimal_mb_and_is_not_a_single_rss_number(self):
        report = memory.summarize(self.samples(600_000_000), 120, 5, True)
        self.assertTrue(report['valid_idle_measurement'])
        self.assertTrue(report['target_met'])
        self.assertEqual(report['target_bytes'], 600_000_000)
        report = memory.summarize(self.samples(600_000_001), 120, 5, True)
        self.assertFalse(report['target_met'])
        self.assertTrue(report['valid_idle_measurement'])
        instant = memory.memory_report('MemTotal: 1000000 kB\nMemAvailable: 500000 kB\n')
        self.assertEqual(instant['used_bytes'], 512_000_000)
        self.assertEqual(instant['total_bytes'], 1_024_000_000)
        self.assertEqual(instant['available_bytes'], 512_000_000)
        self.assertEqual(instant['measurement'], 'anlık; boşta olduğunuzu tek başına kanıtlamaz')
        samples = self.samples()
        for item in samples:
            item.update(total_bytes=1_024_000_000, available_bytes=524_000_000)
        measured = memory.summarize(samples, 120, 5, True)
        self.assertEqual(measured['reported_total_bytes'], 1_024_000_000)
        self.assertEqual(measured['min_available_bytes'], 524_000_000)
        self.assertEqual(measured['min_available_mb'], 524.0)

    def test_missing_graphics_apps_high_cpu_unsettled_or_no_consent_never_claims_target(self):
        cases = []
        for field, value in (('graphical_xfce', False), ('known_foreground_or_package_work', ['welcome.py']), ('cpu_idle_ticks', 0)):
            samples = copy.deepcopy(self.samples())
            for item in samples:
                item[field] = value
            cases.append((samples, 120, 5, True))
        cases.extend([(self.samples(), 20, 5, True), (self.samples(), 120, 5, False), (self.samples(), 120, 1, True)])
        unstable = self.samples()
        unstable[-1]['used_bytes'] += 50_000_000
        cases.append((unstable, 120, 5, True))
        for args in cases:
            with self.subTest(args=args):
                result = memory.summarize(*args)
                self.assertFalse(result['valid_idle_measurement'])
                self.assertFalse(result['target_met'])
                self.assertTrue(result['invalid_reasons'])

    def test_proc_snapshot_requires_actual_target_user_processes_and_does_not_leak_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / 'proc'
            proc.mkdir()
            (proc / 'meminfo').write_text('MemTotal: 1000000 kB\nMemAvailable: 500000 kB\n')
            (proc / 'stat').write_text('cpu  1 2 3 1000 0 0 0 0\n')
            for index, name in enumerate([*sorted(memory.DESKTOP), 'python3']):
                entry = proc / str(index + 10)
                entry.mkdir()
                (entry / 'status').write_text(f'Name:\t{name}\nUid:\t1000 1000 1000 1000\nVmRSS:\t20 kB\n')
                (entry / 'cmdline').write_bytes(b'python3\x00/usr/lib/oguzdows/updater.py\x00private-argument\x00')
            snapshot = memory.snapshot(1000, proc, root / 'sys')
            self.assertTrue(snapshot['graphical_xfce'])
            self.assertIn('updater.py', snapshot['known_foreground_or_package_work'])
            self.assertNotIn('private-argument', json.dumps(snapshot))
            self.assertFalse(memory.snapshot(2000, proc, root / 'sys')['graphical_xfce'])

    def test_memory_probe_never_drops_caches_or_changes_swap(self):
        text = (ROOT / 'system/usr/lib/oguzdows/memory_probe.py').read_text()
        for forbidden in ('drop_caches', 'swapoff', 'swapon', 'os.system(', 'shell=True'):
            self.assertNotIn(forbidden, text)
        read = Mock(side_effect=[self.samples()[0], *self.samples()])
        sleep = Mock()
        result = memory.collect(read=read, sleep=sleep, idle_confirmed=True)
        self.assertTrue(result['target_met'])
        self.assertEqual(sleep.call_args_list[0].args, (120,))
        self.assertEqual(sleep.call_count, 6)


if __name__ == '__main__':
    unittest.main()
