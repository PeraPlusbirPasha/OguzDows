"""Real stdlib/Pillow file tools in private temp dirs; no user's data or packages."""
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from support import ROOT, load

core = load('workbench_test_core', 'system/usr/lib/oguzdows/workbench_core.py')


class WorkbenchContractTests(unittest.TestCase):
    def test_import_and_headless_inventory_load_neither_gtk_pillow_nor_worker(self):
        script = '''import importlib.util,sys,threading
from pathlib import Path
spec=importlib.util.spec_from_file_location('inventory',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert 'gi' not in sys.modules and 'PIL' not in sys.modules
assert len(threading.enumerate()) == 1
assert len(module.core.TOOLS)==16
'''
        result = subprocess.run([sys.executable, '-I', '-c', script, str(ROOT / 'system/usr/lib/oguzdows/workbench.py')], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'system/usr/lib/oguzdows/workbench.py'), '--list-tools'], capture_output=True, text=True, timeout=10)
        tools = json.loads(result.stdout)
        self.assertEqual(len(tools), 16)
        self.assertEqual(len({tool['id'] for tool in tools}), 16)
        self.assertEqual({tool['id'] for tool in tools}, {tool[0] for tool in core.TOOLS})

    def test_portable_launcher_and_on_demand_contract(self):
        entry = (ROOT / 'system/usr/share/applications/oguzdows-workbench.desktop').read_text()
        self.assertIn('Exec=/usr/local/bin/oguzdows-workbench', entry)
        wrapper = ROOT / 'system/usr/local/bin/oguzdows-workbench'
        self.assertTrue(wrapper.stat().st_mode & stat.S_IXUSR)
        self.assertIn('/usr/bin/python3 -I', wrapper.read_text())
        gui = (ROOT / 'system/usr/lib/oguzdows/workbench.py').read_text()
        self.assertIn('ThreadPoolExecutor(max_workers=1', gui)
        self.assertIn('GLib.idle_add(finished', gui)
        self.assertIn('GLib.source_remove(self.clock_id)', gui)
        self.assertIn('self.pool.shutdown(', gui)
        for forbidden in ('shell=True', 'eval(', 'os.system(', 'subprocess.Popen(', 'requests.', 'http.client'):
            self.assertNotIn(forbidden, gui)
            self.assertNotIn(forbidden, (ROOT / 'system/usr/lib/oguzdows/workbench_core.py').read_text())
        for directory in ('system/etc/xdg/autostart', 'system/etc/systemd'):
            self.assertFalse(any('workbench' in str(path) for path in (ROOT / directory).rglob('*')))

    def test_turkish_search_handles_dotted_and_dotless_i(self):
        self.assertEqual(core.normalized('IĞDIR İSTANBUL Şişli'), 'igdir istanbul sisli')


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'private'
        self.library = core.Library(self.root)

    def test_empty_library_is_read_only_until_first_explicit_save(self):
        value = self.library.read()
        self.assertEqual(value['tasks'], [])
        self.assertFalse(self.root.exists())

    def test_task_create_edit_complete_and_delete_are_persistent_and_scoped(self):
        row = self.library.update('tasks', title='Sürümü dene', body='ARM dahil', due='2026-11-20', priority='high', done=False)
        self.assertEqual(self.library.read()['tasks'][0], row)
        changed = self.library.update('tasks', identifier=row['id'], title='Tamamlandı', done=True)
        self.assertTrue(changed['done'])
        self.assertEqual(changed['body'], 'ARM dahil')
        self.library.update('tasks', identifier=row['id'], delete=True)
        self.assertEqual(self.library.read()['tasks'], [])
        with self.assertRaises(ValueError):
            self.library.update('tasks', identifier=row['id'], title='Stale')

    def test_notes_snippets_folder_bookmarks_and_palettes_survive_reopen(self):
        for kind, body in (('notes', 'Türkçe özel not'), ('snippets', 'Yalnız elle eklenir'), ('folders', str(Path(self.temporary.name))), ('palettes', '#173c53')):
            self.library.update(kind, title='Örnek', body=body)
        new = core.Library(self.root).read()
        self.assertEqual(new['notes'][0]['body'], 'Türkçe özel not')
        self.assertEqual(new['snippets'][0]['title'], 'Örnek')
        self.assertEqual(new['folders'][0]['body'], self.temporary.name)
        self.assertEqual(new['palettes'][0]['body'], '#173c53')
        self.assertEqual(stat.S_IMODE((self.root / 'library.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)

    def test_invalid_dates_priorities_types_and_oversize_fields_never_replace_data(self):
        self.library.update('notes', title='Koru', body='Özgün')
        before = (self.root / 'library.json').read_bytes()
        for fields in ({'due': '2026-02-30', 'done': False, 'priority': 'high'},
                       {'due': '', 'done': 1, 'priority': 'normal'},
                       {'due': '', 'done': False, 'priority': 'root'}):
            with self.assertRaises(ValueError): self.library.update('tasks', title='Geçersiz', **fields)
        for fields in ({'title': ''}, {'title': 'x' * 161}, {'title': 'Not', 'body': 'x' * 65537}):
            with self.assertRaises(ValueError): self.library.update('notes', **fields)
        self.assertEqual((self.root / 'library.json').read_bytes(), before)

    def test_corrupt_or_foreign_schema_is_preserved_not_silently_reset(self):
        self.root.mkdir()
        for text in ('broken', '[]', '{"schema":2}', '{"schema":1,"tasks":[{}]}'):
            (self.root / 'library.json').write_text(text)
            with self.assertRaises((ValueError, TypeError)):
                self.library.update('notes', title='Yeni', body='Yazma')
            self.assertEqual((self.root / 'library.json').read_text(), text)

    def test_state_symlink_and_nonregular_files_are_never_followed(self):
        self.root.mkdir()
        outside = Path(self.temporary.name) / 'outside'
        outside.write_text('koru')
        path = self.root / 'library.json'
        path.symlink_to(outside)
        with self.assertRaises(OSError): self.library.read()
        with self.assertRaises((OSError, ValueError)): self.library.update('notes', title='Kötü')
        self.assertEqual(outside.read_text(), 'koru')
        path.unlink(); os.mkfifo(path)
        with self.assertRaises(ValueError): self.library.read()

    def test_busy_or_untrusted_state_lock_does_not_write_or_leak_descriptors(self):
        self.root.mkdir()
        before = len(list(Path('/proc/self/fd').iterdir()))
        (self.root / '.lock').symlink_to(self.root / 'outside')
        with self.assertRaises(OSError): self.library.update('notes', title='Reddedildi')
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), before)
        (self.root / '.lock').unlink()
        with (self.root / '.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.library.update('notes', title='Meşgul')
        self.assertFalse((self.root / 'library.json').exists())
        self.root.chmod(0o777)
        try:
            with self.assertRaises(ValueError): self.library.update('notes', title='Ortak klasör reddi')
        finally: self.root.chmod(0o700)

    def test_record_limit_and_invalid_collection_are_bounded(self):
        with self.assertRaises(ValueError): self.library.update('../notes', title='Kaçış')
        self.assertFalse(self.root.exists())
        for body in ('relative/folder', 'line\nbreak'):
            with self.assertRaises(ValueError): self.library.update('folders', title='Klasör', body=body)
        with self.assertRaises(ValueError): self.library.update('palettes', title='Enjeksiyon', body='red; color: blue')


class FileToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_finder_only_reads_selected_visible_tree_and_does_not_follow_symlinks(self):
        (self.root / 'Belgeler').mkdir()
        (self.root / 'Belgeler/Fatura.txt').write_text('örnek')
        (self.root / '.gizli').mkdir(); (self.root / '.gizli/fatura.txt').write_text('özel')
        (self.root / 'bağlantı').symlink_to(self.root / '.gizli', target_is_directory=True)
        result = core.find_files(self.root, 'fatura')
        self.assertEqual([row['relative'] for row in result['files']], ['Belgeler/Fatura.txt'])
        self.assertFalse(result['limited'])

    def test_finder_has_entry_result_deadline_and_cancellation_limits(self):
        for number in range(12): (self.root / f'file-{number}.txt').touch()
        self.assertEqual(len(core.find_files(self.root, 'file', max_results=3)['files']), 3)
        self.assertTrue(core.find_files(self.root, 'file', max_entries=2)['limited'])
        self.assertTrue(core.find_files(self.root, 'file', seconds=-1)['limited'])
        cancel = threading.Event(); cancel.set()
        with self.assertRaisesRegex(ValueError, 'iptal'): core.find_files(self.root, 'file', cancel)
        with self.assertRaises(ValueError): core.find_files(self.root, '')

    def test_checksum_streams_both_algorithms_and_verifies_not_authenticates(self):
        path = self.root / 'image.bin'
        payload = b'oguzdows\x00' * 100000
        path.write_bytes(payload)
        progress = []
        for algorithm in ('sha256', 'sha512'):
            expected = hashlib.new(algorithm, payload).hexdigest()
            result = core.file_checksum(path, algorithm, expected.upper(), progress=lambda done, total: progress.append((done, total)))
            self.assertEqual(result['digest'], expected)
            self.assertEqual(result['path'], str(path.absolute()))
            self.assertEqual(result['algorithm'], algorithm)
            self.assertEqual(result['expected'], expected)
            self.assertTrue(result['matches'])
        self.assertGreater(len(progress), 2)
        self.assertFalse(core.file_checksum(path, 'sha256', '0' * 64)['matches'])
        self.assertIsNone(core.file_checksum(path)['matches'])

    def test_checksum_detects_changed_input_and_refuses_symlink_fifo_or_wrong_digest(self):
        path = self.root / 'file'; path.write_bytes(b'x' * 700000)
        changed = [False]
        def progress(_done, _total):
            if not changed[0]:
                changed[0] = True
                with path.open('ab') as stream: stream.write(b'mutated')
        with self.assertRaisesRegex(ValueError, 'değişti'): core.file_checksum(path, progress=progress)
        for algorithm, expected in (('md5', ''), ('sha256', 'x' * 64), ('sha512', '0' * 64)):
            with self.assertRaises(ValueError): core.file_checksum(path, algorithm, expected)
        link = self.root / 'link'; link.symlink_to(path)
        with self.assertRaises(OSError): core.file_checksum(link)
        fifo = self.root / 'fifo'; os.mkfifo(fifo)
        with self.assertRaises(ValueError): core.file_checksum(fifo)
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(ValueError): core.file_checksum(path, cancel=cancel)

    def test_export_never_overwrites_and_rejects_path_traversal(self):
        path = Path(core.export_text(self.root, 'Not.txt', 'Türkçe'))
        self.assertEqual(path.read_text(), 'Türkçe')
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError): core.export_text(self.root, 'Not.txt', 'silme')
        for name in ('../escape', '/absolute', '.hidden', 'bad\nname', 'sub/file', 'x' * 241):
            with self.assertRaises(ValueError): core.export_text(self.root, name, 'asla')
        self.assertEqual(path.read_text(), 'Türkçe')


class RenameTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'selected'; self.root.mkdir()
        self.journal = Path(self.temporary.name) / 'private'
        for name in ('a.txt', 'b.txt'): (self.root / name).write_text(name)

    def test_preview_changes_nothing_and_apply_undo_use_the_same_verified_inodes(self):
        plan = core.rename_preview(self.root, 'Gezi-{n}-')
        self.assertEqual(plan['changes'][0]['after'], 'Gezi-001-a.txt')
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['a.txt', 'b.txt'])
        self.assertEqual(core.rename_apply(plan, self.journal), 2)
        self.assertEqual((self.root / 'Gezi-001-a.txt').read_text(), 'a.txt')
        saved = core.rename_history(self.journal)
        self.assertEqual(saved, plan)
        self.assertEqual(core.rename_apply(saved, self.journal, undo=True), 2)
        self.assertEqual((self.root / 'a.txt').read_text(), 'a.txt')
        self.assertFalse((self.journal / 'rename.json').exists())

    def test_preview_bounds_all_entries_including_hidden_and_accepts_cancellation(self):
        (self.root / '.hidden').touch()
        (self.root / 'directory').mkdir()
        for options in ({'max_entries': 1}, {'seconds': -1}):
            with self.assertRaisesRegex(ValueError, 'tarama sınırı'):
                core.rename_preview(self.root, 'new-', **options)
        cancel = threading.Event(); cancel.set()
        with self.assertRaisesRegex(ValueError, 'iptal'):
            core.rename_preview(self.root, 'new-', cancel=cancel)
        self.assertTrue((self.root / 'a.txt').exists())

    def test_literal_replacement_preserves_extension_unless_explicitly_replaced(self):
        plan = core.rename_preview(self.root, find='.txt', replace='.text')
        self.assertEqual(plan['changes'][1]['after'], 'b.text')
        with self.assertRaises(ValueError): core.rename_preview(self.root, '../')

    def test_conflicting_targets_are_rejected_before_any_move(self):
        plan = core.rename_preview(self.root, 'new-')
        (self.root / 'new-b.txt').write_text('kişisel')
        with self.assertRaisesRegex(ValueError, 'üzerine yazılmaz'): core.rename_apply(plan, self.journal)
        self.assertTrue((self.root / 'a.txt').exists())
        self.assertEqual((self.root / 'new-b.txt').read_text(), 'kişisel')
        with self.assertRaises(ValueError): core.rename_preview(self.root, find='b', replace='a')

    def test_changed_input_or_directory_identity_does_not_apply_stale_preview(self):
        plan = core.rename_preview(self.root, 'new-')
        (self.root / 'a.txt').write_text('new contents')
        with self.assertRaisesRegex(ValueError, 'değişmiş'): core.rename_apply(plan, self.journal)
        plan = core.rename_preview(self.root, 'new-'); plan['identity'][1] += 1
        with self.assertRaisesRegex(ValueError, 'Klasör'): core.rename_apply(plan, self.journal)
        self.assertEqual((self.root / 'a.txt').read_text(), 'new contents')

    def test_failed_second_move_rolls_back_without_overwriting_and_keeps_recovery_journal(self):
        plan = core.rename_preview(self.root, 'new-')
        real = core._rename_no_replace
        calls = [0]
        def fail_second(*arguments):
            calls[0] += 1
            if calls[0] == 2: raise OSError('simulated full disk')
            return real(*arguments)
        with patch.object(core, '_rename_no_replace', side_effect=fail_second), self.assertRaises(OSError):
            core.rename_apply(plan, self.journal)
        self.assertTrue((self.root / 'a.txt').exists())
        self.assertTrue((self.root / 'b.txt').exists())
        self.assertTrue((self.journal / 'rename.json').exists())
        self.assertEqual(core.rename_apply(core.rename_history(self.journal), self.journal, undo=True), 0)

    def test_changed_output_blocks_undo_and_forgetting_never_deletes_files(self):
        plan = core.rename_preview(self.root, 'new-')
        core.rename_apply(plan, self.journal)
        (self.root / 'new-a.txt').write_text('güncellenmiş içerik')
        with self.assertRaises(ValueError): core.rename_apply(plan, self.journal, undo=True)
        core.rename_history(self.journal, forget=True)
        self.assertEqual((self.root / 'new-a.txt').read_text(), 'güncellenmiş içerik')

    def test_last_recovery_is_not_overwritten_by_a_second_batch(self):
        core.rename_apply(core.rename_preview(self.root, 'first-'), self.journal)
        second = core.rename_preview(self.root, 'second-')
        with self.assertRaisesRegex(ValueError, 'Önce son'): core.rename_apply(second, self.journal)
        self.assertTrue((self.root / 'first-a.txt').exists())

    def test_concurrent_journal_writer_cannot_overwrite_recovery_or_move_files(self):
        self.journal.mkdir()
        with (self.journal / '.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                core.rename_apply(core.rename_preview(self.root, 'new-'), self.journal)
        self.assertTrue((self.root / 'a.txt').exists())
        self.assertFalse((self.journal / 'rename.json').exists())

    def test_no_unsafe_overwrite_fallback_when_libc_lacks_renameat2(self):
        with patch.object(core.ctypes, 'CDLL', return_value=object()), self.assertRaises(ValueError):
            core.rename_apply(core.rename_preview(self.root, 'new-'), self.journal)
        self.assertEqual((self.root / 'a.txt').read_text(), 'a.txt')


class TextAndMathTests(unittest.TestCase):
    def test_diff_retains_missing_newline_information(self):
        value = core.text_diff('ilk\nson', 'ilk\nyeni')
        self.assertIn('-son\n', value)
        self.assertIn('+yeni\n', value)
        self.assertIn('No newline', value)
        self.assertEqual(core.text_diff('aynı', 'aynı'), 'Metinler aynı.')
        with self.assertRaises(ValueError): core.text_diff('x\n' * 1502, '')

    def test_json_format_minify_unicode_and_duplicate_detection(self):
        value = core.format_json('{"ad":"Oğuz","n":[1,true]}')
        self.assertEqual(json.loads(value)['ad'], 'Oğuz')
        self.assertEqual(core.format_json(value, compact=True), '{"ad":"Oğuz","n":[1,true]}')
        for text in ('{"a":1,"a":2}', '{"n":NaN}', '1e999', '[' * 41 + '0' + ']' * 41, 'bad'):
            with self.assertRaises(ValueError): core.format_json(text)
        self.assertIn('[[[', core.format_json('"[[["'))

    def test_calculator_uses_decimal_not_python_execution(self):
        self.assertEqual(Decimal(core.calculate('0.1 + 0.2')), Decimal('.3'))
        self.assertEqual(Decimal(core.calculate('(1250 * 1.20) / 3 + sqrt(81)')), Decimal(509))
        self.assertEqual(Decimal(core.calculate('abs(-3) ** 2')), Decimal(9))
        self.assertAlmostEqual(float(core.calculate('pi * 2')), 6.283185307179586)
        for expression in ("__import__('os').system('id')", 'open("x")', '[1][0]', '(1).__class__', '2**999999',
                           '1/0', 'sqrt(-1)', '1e999', 'True', '"123"', 'sum(range(5))'):
            with self.subTest(expression=expression), self.assertRaises((ValueError, SyntaxError)):
                core.calculate(expression)

    def test_units_distinguish_si_binary_temperature_and_incompatible_categories(self):
        self.assertEqual(Decimal(core.convert_unit('1', 'Veri', 'MiB', 'B')), Decimal(1048576))
        self.assertEqual(Decimal(core.convert_unit('1', 'Veri', 'MB', 'B')), Decimal(1000000))
        self.assertEqual(Decimal(core.convert_unit('32', 'Sıcaklık', '°F', '°C')), Decimal(0))
        self.assertEqual(Decimal(core.convert_unit('0', 'Sıcaklık', '°C', 'K')), Decimal('273.15'))
        self.assertEqual(Decimal(core.convert_unit('2,5', 'Uzunluk', 'km', 'm')), Decimal(2500))
        for arguments in (('0', 'Kütle', 'kg', 'm'), ('-1', 'Sıcaklık', 'K', '°C'), ('NaN', 'Veri', 'B', 'MB')):
            with self.assertRaises(ValueError): core.convert_unit(*arguments)

    def test_color_contrast_uses_linear_srgb_wcag_not_brightness_guess(self):
        white_black = core.color_info('#ffffff', '#000000')
        self.assertEqual(white_black['ratio'], 21)
        self.assertTrue(white_black['aaa'])
        self.assertEqual(core.color_info('#445566', '#445566')['ratio'], 1)
        self.assertFalse(core.color_info('#888888', '#ffffff')['aa'])
        for value in ('#fff', 'red', '#123456; color: red', '#12345z'):
            with self.assertRaises(ValueError): core.color_info(value, '#ffffff')

    def test_world_clock_uses_real_dst_database_without_network_or_location(self):
        now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        values = {row['zone']: row for row in core.world_times(now=now)}
        self.assertEqual(values['Europe/Istanbul']['time'], '15:00')
        self.assertEqual(values['Europe/London']['time'], '12:00')
        self.assertEqual(values['America/New_York']['time'], '07:00')
        with self.assertRaises(ValueError): core.world_times(('../../etc/passwd',))
        with self.assertRaises(ValueError): core.world_times(now=datetime(2026, 1, 1))

    def test_text_operations_preserve_turkish_letters_and_ordered_deduplication(self):
        self.assertEqual(core.transform_text('istanbul ığdır', 'Türkçe BÜYÜK')['text'], 'İSTANBUL IĞDIR')
        self.assertEqual(core.transform_text('IĞDIR İZMİR', 'Türkçe küçük')['text'], 'ığdır izmir')
        self.assertEqual(core.transform_text('B\nA\nB', 'Tekrarlı satırları kaldır')['text'], 'B\nA')
        result = core.transform_text(' a  \n b ', 'Kenar boşluklarını temizle')
        self.assertEqual(result, {'text': 'a\nb', 'characters': 3, 'words': 2, 'lines': 2})
        with self.assertRaises(ValueError): core.transform_text('x', '__import__')


class ImageToolsTests(unittest.TestCase):
    def test_real_pillow_export_preserves_source_ratio_and_strips_metadata(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'original.jpg'
            exif = Image.Exif(); exif[0x010E] = 'private metadata'
            with Image.new('RGB', (800, 400), '#2a8593') as image:
                image.save(source, exif=exif)
            before = source.read_bytes()
            result = core.prepare_image(source, root, 'new.png', 200, 200, 'PNG')
            self.assertEqual((result['width'], result['height']), (200, 100))
            with Image.open(root / 'new.png') as output:
                self.assertFalse(output.getexif())
                self.assertNotIn('exif', output.info)
            self.assertEqual(source.read_bytes(), before)
            with self.assertRaises(FileExistsError): core.prepare_image(source, root, 'new.png', 200, 200, 'PNG')
            self.assertEqual(source.read_bytes(), before)

    def test_image_tool_rejects_oversize_animations_and_unsupported_formats(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with Image.new('RGB', (3000, 3000)) as image: image.save(root / 'large.png')
            with self.assertRaises(ValueError): core.prepare_image(root / 'large.png', root, 'out.jpg')
            with Image.new('RGB', (20, 20), 'red') as one, Image.new('RGB', (20, 20), 'blue') as two:
                one.save(root / 'animated.gif', save_all=True, append_images=[two])
            with self.assertRaises(ValueError): core.prepare_image(root / 'animated.gif', root, 'out.jpg')
            with self.assertRaises(ValueError): core.prepare_image(root / 'animated.gif', root, 'out.jpg', format_name='SVG')
            self.assertFalse((root / 'out.jpg').exists())


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.system = self.root / 'system'; self.system.mkdir()
        self.user = self.root / 'user'
        self.journal = self.root / 'journal'
        self.original = '[Desktop Entry]\nType=Application\nName=Örnek\nExec=/bin/false --never-executed\nOnlyShowIn=XFCE;\n'
        (self.system / 'example.desktop').write_text(self.original)

    def test_startup_scan_is_read_only_and_never_executes_entries(self):
        values = core.startup_entries(self.user, (self.system,))
        self.assertEqual(len(values), 1)
        self.assertTrue(values[0]['enabled'])
        self.assertEqual(values[0]['only'], 'XFCE;')
        self.assertFalse(self.user.exists())

    def test_system_toggle_writes_only_user_override_and_restore_removes_only_our_override(self):
        core.toggle_startup('example.desktop', False, self.user, self.journal, system_directories=(self.system,))
        self.assertFalse(core.startup_entries(self.user, (self.system,))[0]['enabled'])
        core.toggle_startup('example.desktop', True, self.user, self.journal, system_directories=(self.system,))
        self.assertTrue(core.startup_entries(self.user, (self.system,))[0]['enabled'])
        self.assertIn('Exec=/bin/false --never-executed', (self.user / 'example.desktop').read_text())
        self.assertEqual((self.system / 'example.desktop').read_text(), self.original)
        core.restore_startup('example.desktop', self.user, self.journal)
        self.assertFalse((self.user / 'example.desktop').exists())
        self.assertTrue(core.startup_entries(self.user, (self.system,))[0]['enabled'])

    def test_user_entry_exec_is_preserved_and_exact_original_restored(self):
        self.user.mkdir(); path = self.user / 'example.desktop'; path.write_text(self.original + '# personal comment\n')
        before = path.read_text()
        core.toggle_startup(path.name, False, self.user, self.journal)
        self.assertIn('Exec=/bin/false --never-executed', path.read_text())
        core.toggle_startup(path.name, True, self.user, self.journal)
        core.restore_startup(path.name, self.user, self.journal)
        self.assertEqual(path.read_text(), before)

    def test_later_personal_changes_win_over_toggle_and_restore(self):
        core.toggle_startup('example.desktop', False, self.user, self.journal, system_directories=(self.system,))
        path = self.user / 'example.desktop'; path.write_text(self.original + 'Hidden=false\n# edited elsewhere\n')
        for function, arguments in ((core.restore_startup, ('example.desktop', self.user, self.journal)),
                                    (core.toggle_startup, ('example.desktop', True, self.user, self.journal))):
            with self.assertRaisesRegex(ValueError, 'değişmiş'): function(*arguments)
        self.assertIn('edited elsewhere', path.read_text())

    def test_gnome_disabled_flag_and_exec_survive_enable_and_exact_restore(self):
        self.user.mkdir()
        path = self.user / 'example.desktop'
        original = self.original + 'X-GNOME-Autostart-enabled=false\n'
        path.write_text(original)
        self.assertFalse(core.startup_entries(self.user, (self.system,))[0]['enabled'])
        core.toggle_startup(path.name, True, self.user, self.journal)
        self.assertTrue(core.startup_entries(self.user, (self.system,))[0]['enabled'])
        self.assertIn('X-GNOME-Autostart-enabled=true', path.read_text())
        core.restore_startup(path.name, self.user, self.journal)
        self.assertEqual(path.read_text(), original)

    def test_failed_user_write_can_be_restored_without_touching_vendor_file(self):
        original_atomic = core._atomic_at
        def fail_override(directory, name, data):
            if name.endswith('.desktop'): raise OSError('simulated full disk')
            return original_atomic(directory, name, data)
        with patch.object(core, '_atomic_at', side_effect=fail_override), self.assertRaises(OSError):
            core.toggle_startup('example.desktop', False, self.user, self.journal, system_directories=(self.system,))
        self.assertFalse((self.user / 'example.desktop').exists())
        self.assertTrue((self.journal / 'example.desktop.json').exists())
        core.restore_startup('example.desktop', self.user, self.journal)
        self.assertFalse((self.journal / 'example.desktop.json').exists())
        self.assertEqual((self.system / 'example.desktop').read_text(), self.original)

    def test_missing_vendor_entry_is_not_synthesized_and_scan_can_be_cancelled(self):
        with self.assertRaises(ValueError):
            core.toggle_startup('gone.desktop', True, self.user, self.journal, system_directories=(self.system,))
        self.assertFalse((self.user / 'gone.desktop').exists())
        cancel = threading.Event(); cancel.set()
        with self.assertRaisesRegex(ValueError, 'iptal'):
            core.startup_entries(self.user, (self.system,), cancel=cancel)

    def test_symlinks_traversal_and_arbitrary_command_ids_are_rejected(self):
        self.user.mkdir(); (self.user / 'example.desktop').symlink_to(self.system / 'example.desktop')
        with self.assertRaises(OSError): core.toggle_startup('example.desktop', False, self.user, self.journal, system_directories=(self.system,))
        for identifier in ('../../example.desktop', '--system', 'name.desktop;id', 'space name.desktop'):
            with self.assertRaises(ValueError): core.toggle_startup(identifier, False, self.user, self.journal)
        self.assertEqual((self.system / 'example.desktop').read_text(), self.original)


if __name__ == '__main__':
    unittest.main()
