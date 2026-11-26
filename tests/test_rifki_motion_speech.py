"""Hareket / ses testleri; pencere veya gerçek ses aygıtı açılmaz."""
import ast
import json
import math
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import ImageChops

from support import ROOT, load

motion=load('rifki_motion_test','system/usr/lib/oguzdows/rifki_motion.py')
scene_module=load('rifki_scene_test','system/usr/lib/oguzdows/rifki_scene.py')
speech=load('rifki_speech_test','system/usr/lib/oguzdows/rifki_speech.py')
model=load('rifki_model_more_tests','system/usr/lib/oguzdows/rifki_model.py')
dialogue=load('rifki_dialogue_tests','system/usr/lib/oguzdows/rifki_dialogue.py')
ASSETS=ROOT/'system/usr/share/oguzdows/rifki'



class MotionTests(unittest.TestCase):
    def test_jump_starts_and_lands_exactly_and_has_an_arc(self):
        a,b=(0.,0.),(100.,10.)
        self.assertEqual(motion.jump_path(a,b,0),a)
        self.assertEqual(motion.jump_path(a,b,1),b)
        self.assertLess(motion.jump_path(a,b,.5)[1],0)
        self.assertEqual(motion.jump_path(a,b,99),b)

    def test_perch_respects_monitor_bounds_titlebar_controls_and_no_space(self):
        for work in (motion.Rect(0,0,1024,768),motion.Rect(-1280,0,1280,1024)):
            result=motion.perch_position(motion.Rect(work.x+90,210,800,520),work)
            self.assertIsNotNone(result)
            self.assertGreaterEqual(result.x,work.x)
            self.assertGreaterEqual(result.y,work.y)
            self.assertLessEqual(result.x+result.width,work.x+work.width)
            self.assertLess(result.x+result.width,work.x+90+800-80)
        self.assertIsNone(motion.perch_position(motion.Rect(0,0,1024,768),motion.Rect(0,0,1024,768)))

    def test_pause_freezes_and_resumes_without_time_jump(self):
        behavior=motion.Behaviour(0)
        behavior.choose('tea',1)
        behavior.set_paused(True,4)
        self.assertEqual(behavior.tick(50),('tea',3))
        behavior.set_paused(False,60)
        self.assertEqual(behavior.tick(61),('tea',4))
        with self.assertRaises(ValueError):
            behavior.choose('execute-command',100)

    def test_reduced_motion_is_not_automatic_and_states_are_finite(self):
        behavior=motion.Behaviour(0,reduced=True)
        self.assertFalse(behavior.automatic)
        self.assertEqual(behavior.tick(1000)[0],'perch')
        for action in motion.ACTIONS:
            for t in (0.,.1,1.,4.,9.,20.,10000.):
                state=motion.pose_state(action,t)
                for value in (state['x'],state['y'],state['scale'],state['paw'],state['tail'],state['breathe']):
                    self.assertTrue(math.isfinite(value))
                self.assertGreater(state['scale'],0)

    def test_all_real_rendered_behaviours_differ_and_keep_alpha(self):
        renderer=scene_module.Scene(ASSETS/'rig')
        outputs=[]
        for action,t in (('perch',1),('jump',1),('tail',1),('feather',3),('tea',9)):
            first=renderer.render(action,t,.4)
            second=renderer.render(action,t+.6,.4)
            self.assertEqual(first.size,(300,224))
            self.assertEqual(first.mode,'RGBA')
            self.assertEqual(first.getpixel((0,0))[3],0)
            self.assertIsNotNone(ImageChops.difference(first,second).getbbox(),action)
            outputs.append(first.tobytes())
        self.assertEqual(len(set(outputs)),len(outputs))
        # Kaynak dosyalar kare başına yeniden açılmaz; sınırlı önbellek kullanılır.
        with patch.object(scene_module.Image,'open',side_effect=AssertionError('Frame IO')):
            for i in range(30):
                renderer.render('tea',i/20)
        self.assertLessEqual(len(renderer.cache),24)

    def test_motion_requests_explain_simplification_without_starting_actions(self):
        for question in ('zıpla','kuyruğunu salla','tüy topuyla oyna','çay demle'):
            answer=model.reply(question)
            self.assertNotIn('motion',answer)
            self.assertIn('yormamak',answer['text'])
            self.assertIsNone(answer['action'])
        self.assertEqual(model.reply('sudo rm -rf /dev/test')['action'],'boot-report')


class SpeechTests(unittest.TestCase):
    def test_every_basic_topic_and_panel_has_a_recorded_natural_voice(self):
        texts=[dialogue.HELLO,dialogue.LIGHT_NOTE,*dialogue.PANELS.values(),*[model.reply(t)['text'] for t in ('disk','boot','internet','sürücü','duvar','pil','kurulum','merhaba')],*[dialogue.STAGES[t][1] for t in ('preparing','ready','bootloader')]]
        for text in texts:
            path=speech.ready_clip(text,ASSETS)
            self.assertIsNotNone(path,text)
            with wave.open(str(path),'rb') as audio:
                self.assertGreater(audio.getnframes(),audio.getframerate())
        for name in speech.CUES.values():
            self.assertTrue((ASSETS/name).is_file(),name)

    def test_unknown_text_never_starts_a_synthesizer_or_guesses_success(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary,'OGUZDOWS_TESTING':''}):
            speaker=speech.Speaker(lambda f,*a:f(*a),assets=ASSETS)
            with patch.object(speech.subprocess,'Popen') as process:
                self.assertFalse(speaker.speak('--option; $(touch /tmp/never) bilinmeyen metin'))
                process.assert_not_called()
            self.assertFalse(hasattr(speech,'synthesize'))
            self.assertFalse(hasattr(speech,'envelope'))
            speaker.close()

    def test_only_a_fixed_audio_player_is_spawned_and_wav_content_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary,'OGUZDOWS_TESTING':''}):
            speaker=speech.Speaker(lambda f,*a:f(*a),assets=ASSETS)
            with patch.object(speech.shutil,'which',return_value='/usr/bin/paplay'), patch.object(speech.subprocess,'Popen') as process, patch.object(speech.threading,'Thread'):
                process.return_value.poll.return_value=None
                self.assertTrue(speaker.speak(dialogue.HELLO))
                self.assertEqual(process.call_args.args[0],['/usr/bin/paplay',str(ASSETS/'intro-light.wav')])
                speaker.stop()
                process.return_value.terminate.assert_called_once()
                process.return_value.wait.assert_not_called()
            speaker.close()

    def test_new_silent_message_stops_the_old_clip_and_a_process_exit_race_is_safe(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary}):
            speaker=speech.Speaker(lambda f,*a:f(*a),assets=ASSETS)
            process=unittest.mock.Mock()
            process.poll.return_value=None
            process.terminate.side_effect=ProcessLookupError('already exited')
            speaker.process=process
            speaker.playing=True
            self.assertFalse(speaker.speak('Bu değişken mesajın kaydı yok.'))
            self.assertFalse(speaker.playing)
            self.assertIsNone(speaker.process)
            process.terminate.assert_called_once()
            process.wait.assert_not_called()
            speaker.close()

    def test_audio_manifest_rejects_traversal_symlinks_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            manifest=root/'speech.json'
            for value in ('../success.wav','/tmp/success.wav',9,{},'success.mp3'):
                manifest.write_text(json.dumps({speech.text_key('mesaj'):value}))
                self.assertIsNone(speech.ready_clip('mesaj',root))
            manifest.write_text('{bad}')
            self.assertIsNone(speech.ready_clip('mesaj',root))
            manifest.write_text(json.dumps({speech.text_key('mesaj'):'link.wav'}))
            (root/'link.wav').symlink_to(ASSETS/'success.wav')
            self.assertIsNone(speech.ready_clip('mesaj',root))

    def test_old_heavy_preferences_cannot_turn_on_the_removed_pet(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary}):
            path=Path(temporary)/'oguzdows/rifki.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'pet':True,'auto':True,'speech':False}))
            speaker=speech.Speaker(lambda f,*a:f(*a))
            self.assertFalse(speaker.options['pet'])
            self.assertFalse(speaker.options['auto'])
            self.assertFalse(speaker.enabled)
            speaker.close()

    def test_muting_and_generation_guard_stale_playback_completion(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary}):
            speaker=speech.Speaker(lambda f,*a:f(*a))
            before=speaker.generation
            speaker.set_enabled(False)
            self.assertGreater(speaker.generation,before)
            self.assertFalse(json.loads(speaker.preference.read_text())['speech'])
            speaker.finished(before,1)
            speaker.close()

    def test_active_entrypoints_import_neither_rig_nor_tts_and_no_cairo_is_needed(self):
        forbidden={'PIL','cairo','rifki_scene','rifki_pet','rifki_motion'}
        for name in ('rifki.py','rifki_speech.py','install_launcher.py','updater.py','culture.py','store.py'):
            tree=ast.parse((ROOT/'system/usr/lib/oguzdows'/name).read_text())
            modules={node.module.split('.')[0] for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) and node.module}
            modules.update(alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names)
            self.assertFalse(modules & forbidden,(name,modules & forbidden))
        packages=(ROOT/'packages/common.list').read_text().splitlines()
        self.assertNotIn('espeak-ng',packages)
        self.assertNotIn('gir1.2-wnck-3.0',packages)


if __name__=='__main__':
    unittest.main()
