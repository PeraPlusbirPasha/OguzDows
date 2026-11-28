"""1.1 doğal kayıt kapsamı / kökeni / çevrimdışı paketleme sözleşmesi."""
import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from support import ROOT, load

speech = load('narration_v11_speech', 'system/usr/lib/oguzdows/rifki_speech.py')
texts = load('narration_v11_texts', 'system/usr/lib/oguzdows/rifki_narration_texts.py')
welcome = load('narration_v11_welcome', 'system/usr/lib/oguzdows/welcome_model.py')
dialogue = load('narration_v11_dialogue', 'system/usr/lib/oguzdows/rifki_dialogue.py')
model = load('narration_v11_model', 'system/usr/lib/oguzdows/rifki_model.py')
prepare = load('narration_v11_prepare', 'scripts/prepare-narration.py')
ASSETS = ROOT / 'system/usr/share/oguzdows/rifki'


class NarrationV11Tests(unittest.TestCase):
    def test_all_seven_welcome_pages_have_exact_recordings_in_all_three_sessions(self):
        manifest = speech.load_manifest(ASSETS)
        for session in (welcome.context(live=True), welcome.context(), welcome.context(pi=True)):
            for page in welcome.PAGE_IDS:
                with self.subTest(session=session.kind, page=page):
                    self.assertIsNotNone(speech.ready_clip(welcome.page_text(page, session), ASSETS, manifest))
        self.assertEqual(welcome.page_text('install-result', welcome.context()), '')
        self.assertNotEqual(welcome.page_text('welcome', welcome.context(live=True)),
                            welcome.page_text('welcome', welcome.context()))
        self.assertEqual(welcome.page_text('hardware', welcome.context(pi=True)), texts.TEXTS['hardware-pi'])

    def test_selected_voice_clips_match_text_hash_bytes_and_pcm_provenance(self):
        provenance = json.loads((ROOT / 'artwork/rifki-narration.json').read_text())
        self.assertIn('Explicitly selected', provenance['voice_selection'])
        self.assertTrue(provenance['not_a_human_studio_recording'])
        self.assertFalse(provenance['runtime_synthesis'])
        self.assertEqual({clip['topic'] for clip in provenance['clips']}, set(texts.TEXTS))
        self.assertEqual(len(provenance['clips']), 11)
        total = 0
        for clip in provenance['clips']:
            with self.subTest(topic=clip['topic']):
                self.assertEqual(clip['text'], texts.TEXTS[clip['topic']])
                self.assertEqual(clip['text_key'], speech.text_key(clip['text']))
                path = speech.ready_clip(clip['text'], ASSETS)
                self.assertEqual(path.name, clip['file'])
                self.assertEqual(path.stat().st_size, clip['bytes'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), clip['sha256'])
                total += path.stat().st_size
                with wave.open(str(path), 'rb') as audio:
                    self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()),
                                     (1, 2, 24000, 'NONE'))
                    self.assertEqual(audio.getnframes(), clip['frames'])
                    self.assertAlmostEqual(audio.getnframes() / audio.getframerate(), clip['duration_seconds'])
                    self.assertLess(clip['duration_seconds'], 90)
                    self.assertGreater(clip['duration_seconds'], 5)
        self.assertLess(total, 20_000_000)

    def test_no_old_six_wallpaper_or_top_tabs_record_can_be_selected(self):
        values = set(speech.load_manifest(ASSETS).values())
        self.assertFalse(values & prepare.OBSOLETE)
        self.assertEqual(model.reply('duvar')['text'], texts.TEXTS['wallpapers'])
        self.assertIn('Yirmi', dialogue.PANELS['wallpapers'])
        self.assertNotIn('üstten', dialogue.PANELS['welcome'])
        for filename in prepare.OBSOLETE:
            self.assertFalse((ASSETS / filename).exists())

    def test_other_window_guides_are_recorded_but_not_dynamic_error_or_success_texts(self):
        for topic in ('applications', 'store', 'culture', 'compatibility', 'support', 'news'):
            self.assertIsNotNone(speech.ready_clip(texts.TEXTS[topic], ASSETS))
        for text in ('Dosya başarıyla kuruldu', 'Sürücü hatası 1234', '/home/örnek/gizli.apk'):
            self.assertIsNone(speech.ready_clip(text, ASSETS))

    def test_new_questions_only_offer_fixed_windows_and_use_exact_recordings(self):
        tasks = {'APK kurmak istiyorum': ('compatibility', 'compatibility'),
                 'dosya.exe': ('compatibility', 'compatibility'),
                 'Mağaza': ('store', 'store'), 'Flatpak': ('store', 'store'),
                 'koyu tema': ('styles', 'appearance'), 'tasarım': ('styles', 'appearance'),
                 'güncellemeler': ('updates', 'applications'),
                 'Çay Molası': ('culture', 'culture'), 'Heybe yedek': ('culture', 'culture'),
                 'PinePhone': ('devices', 'compatibility')}
        for question, (action, topic) in tasks.items():
            with self.subTest(question=question):
                answer = model.reply(question)
                self.assertEqual(answer['action'], action)
                self.assertEqual(answer['text'], texts.TEXTS[topic])
                self.assertIsNotNone(speech.ready_clip(answer['text'], ASSETS))
                self.assertNotIn('command', answer)
        for question in ('sudo wine dosya.exe', 'mkfs /dev/test APK', 'rm -rf /dev/test mağaza'):
            self.assertEqual(model.reply(question)['action'], 'boot-report')

    def sources(self, root):
        source = root / 'source'
        source.mkdir()
        for filename in prepare.FILES.values():
            # Geliştirme aracının biçim testi, konuşma veya kalite kanıtı değil.
            with wave.open(str(source / filename), 'wb') as audio:
                audio.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\x01\x00' * 24000)
        return source

    def test_offline_packaging_preserves_basic_clips_and_retires_only_stale_panels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.sources(root)
            destination = root / 'overlay/usr/share/oguzdows/rifki'
            destination.mkdir(parents=True)
            (destination / 'speech.json').write_text(json.dumps({'basic': 'intro-light.wav', 'stale': 'panel-wallpapers.wav'}))
            (destination / 'intro-light.wav').write_bytes(b'basic stays')
            (destination / 'panel-wallpapers.wav').write_bytes(b'old')
            prepare.prepare(source, root / 'overlay', root / 'metadata.json')
            manifest = json.loads((destination / 'speech.json').read_text())
            self.assertEqual(manifest['basic'], 'intro-light.wav')
            self.assertNotIn('stale', manifest)
            self.assertEqual((destination / 'intro-light.wav').read_bytes(), b'basic stays')
            self.assertEqual(len(manifest), len(texts.TEXTS) + 1)
            self.assertFalse((destination / 'panel-wallpapers.wav').exists())
            for text in texts.TEXTS.values():
                self.assertIsNotNone(speech.ready_clip(text, destination))

    def test_replacing_a_clip_retires_old_text_key_but_preserves_unrelated_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.sources(root)
            destination = root / 'overlay/usr/share/oguzdows/rifki'
            destination.mkdir(parents=True)
            old_key = speech.text_key('Eski beş kart açıklaması')
            (destination / 'speech.json').write_text(json.dumps({old_key: 'panel-appearance.wav', 'basic': 'intro-light.wav'}))
            (destination / 'intro-light.wav').write_bytes(b'unchanged')
            prepare.prepare(source, root / 'overlay', root / 'metadata.json')
            manifest = speech.load_manifest(destination)
            self.assertNotIn(old_key, manifest)
            self.assertEqual(manifest[speech.text_key(texts.TEXTS['appearance'])], 'panel-appearance.wav')
            self.assertEqual(len(manifest), len(texts.TEXTS) + 1)
            self.assertEqual((destination / 'intro-light.wav').read_bytes(), b'unchanged')

    def test_bad_pcm_or_truncated_record_changes_nothing(self):
        for damage in ('stereo', 'truncated'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = self.sources(root)
                target = source / prepare.FILES['culture']
                if damage == 'stereo':
                    with wave.open(str(target), 'wb') as audio:
                        audio.setparams((2, 2, 24000, 0, 'NONE', 'not compressed'))
                        audio.writeframes(b'\0' * 96000)
                else:
                    target.write_bytes(target.read_bytes()[:-10])
                overlay = root / 'overlay'
                overlay.mkdir()
                with self.assertRaises(ValueError):
                    prepare.prepare(source, overlay, root / 'metadata.json')
                self.assertEqual(list(overlay.iterdir()), [])
                self.assertFalse((root / 'metadata.json').exists())

    def test_running_system_and_symlink_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.sources(root)
            with self.assertRaises(ValueError):
                prepare.prepare(source, Path('/'), root / 'metadata.json')
            target = source / prepare.FILES['culture']
            original = target.read_bytes()
            target.unlink()
            (root / 'outside.wav').write_bytes(original)
            target.symlink_to(root / 'outside.wav')
            with self.assertRaises(ValueError):
                prepare.prepare(source, root / 'overlay', root / 'metadata.json')
            self.assertFalse((root / 'overlay').exists())


if __name__ == '__main__':
    unittest.main()
