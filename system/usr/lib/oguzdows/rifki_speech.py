"""Yalnızca önceden hazırlanmış doğal Türkçe kayıtları çalar.

Çalışma zamanında ses sentezi, WAV tarama / genlik hesabı, model indirme veya
CPU yoğun işçi yoktur. Kaydı olmayan değişken ayrıntılar yazılı kalır.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

ASSETS = Path('/usr/share/oguzdows/rifki')
CUES = {
    'working':'working.wav', 'success':'success.wav', 'failure':'failure.wav',
    'cancelled':'result-cancelled.wav', 'warning':'result-warning.wav',
}


def canonical(text):
    return ' '.join(str(text).split())[:12000]


def text_key(text):
    return hashlib.sha256(('tr-v1\n'+canonical(text)).encode()).hexdigest()


def load_manifest(assets=ASSETS):
    try:
        path = assets / 'speech.json'
        if path.stat().st_size > 65536:
            return {}
        result = json.loads(path.read_text())
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def ready_clip(text, assets=ASSETS, manifest=None):
    try:
        manifest = load_manifest(assets) if manifest is None else manifest
        name=manifest.get(text_key(text))
        if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.wav'):
            return None
        path=assets/name
        return path if path.is_file() and not path.is_symlink() else None
    except (OSError,ValueError,TypeError,AttributeError):
        return None


class Speaker:
    def __init__(self, dispatch, on_error=None, assets=ASSETS):
        self.dispatch=dispatch
        self.on_error=on_error or (lambda _:None)
        self.assets=assets
        # Açılışta bir kez oku; her sayfa değişiminde JSON/klasör taraması yok.
        self.clips=load_manifest(assets)
        self.process=None
        self.generation=0
        self.closed=False
        self.listeners=[]
        self.playing=False
        self.last_text=''
        self.last_cue=None
        self.preference=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'oguzdows/rifki.json'
        try:
            self.options=json.loads(self.preference.read_text())
            if not isinstance(self.options,dict):
                self.options={}
        except (OSError,ValueError):
            self.options={}
        self.enabled=self.options.get('speech',True) is not False
        # Ağır önceki tercihleri etkinleştirme. Yeni varsayılan bütün cihazlarda hafif.
        self.options.update(version=3,pet=False,auto=False)

    def notify(self,playing):
        self.playing=playing
        for callback in tuple(self.listeners):
            callback(playing)

    def stop(self):
        self.generation+=1
        process,self.process=self.process,None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                # poll ile terminate arasında oynatıcı kendisi bitmiş olabilir.
                pass
            # GUI'yi wait/kill zaman aşımıyla bekletme; çocuk bekçisi süreci toplar.
        self.notify(False)

    def speak(self,text,cue=None):
        self.last_text=canonical(text)
        self.last_cue=cue
        # Yeni metnin kaydı yoksa da önceki (özellikle başarı) sesi sürmesin.
        self.stop()
        if not self.enabled or self.closed or not self.last_text:
            return False
        path=ready_clip(self.last_text,self.assets,self.clips)
        if path is None and cue in CUES:
            candidate=self.assets/CUES[cue]
            if candidate.is_file() and not candidate.is_symlink():
                path=candidate
        if path is None:
            # Robotik bir motora düşme, yanlış bir başarı kaydını da tahmin etme.
            return False
        if os.environ.get('OGUZDOWS_TESTING')=='1':
            return False
        player=shutil.which('paplay') or shutil.which('aplay')
        if not player:
            self.on_error('Ses oynatıcısı bulunamadı. Metin ve kurulum kullanılabilir.')
            return False
        generation=self.generation
        try:
            process=subprocess.Popen([player,str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except OSError:
            self.on_error('Ses çıkışı açılamadı. Metin ve kurulum kullanılabilir.')
            return False
        self.process=process
        self.notify(True)
        def wait_for_playback():
            try:
                code=process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                code=process.wait()
            self.dispatch(self.finished,generation,code)
        threading.Thread(target=wait_for_playback,name='rifki-kayit',daemon=True).start()
        return True

    def finished(self,generation,code):
        if generation!=self.generation or self.closed:
            return False
        self.process=None
        self.notify(False)
        if code:
            self.on_error('Ses çıkışı kullanılamadı. Metin ve kurulum kullanılabilir.')
        return False

    def save_option(self,key,value):
        self.options[key]=value
        temporary=None
        try:
            self.preference.parent.mkdir(parents=True,exist_ok=True)
            fd,name=tempfile.mkstemp(prefix='.rifki-',dir=self.preference.parent)
            temporary=Path(name)
            with os.fdopen(fd,'w') as stream:
                json.dump(self.options,stream)
                stream.write('\n')
            os.replace(temporary,self.preference)
        except OSError:
            pass
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def set_enabled(self,value):
        self.enabled=bool(value)
        self.save_option('speech',self.enabled)
        if not self.enabled:
            self.stop()

    def close(self):
        self.closed=True
        self.stop()
        self.listeners.clear()
