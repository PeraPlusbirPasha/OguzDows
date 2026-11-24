#!/usr/bin/env python3
"""Tek seferlik Xfce efekt kararı; kalıcı Python denetleyicisi yoktur.

Yalnızca kendi başlattığı, UID / argv / PID doğum zamanı eşleşen Picom'u durdurur.
Başka kompozitör değiştirilmez. Zero / düşük RAM / nomodeset daima statiktir.
"""
from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profiles import atomic_text, effect_selection, read_state, state_directory as profile_directory
from resource_policy import current_policy
from aero import CONFIGS, plan as aero_plan

BINARY = Path('/usr/bin/picom')
CONFIG = Path('/usr/share/oguzdows/picom.conf')


class X11:
    def __init__(self):
        self.lib = ctypes.CDLL('libX11.so.6')
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XOpenDisplay.restype = ctypes.c_void_p
        self.lib.XDefaultScreen.argtypes = [ctypes.c_void_p]
        self.lib.XDefaultScreen.restype = ctypes.c_int
        self.lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.XInternAtom.restype = ctypes.c_ulong
        self.lib.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.lib.XGetSelectionOwner.restype = ctypes.c_ulong
        self.lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise ValueError('X11 ekranı açılamadı; geçiş açılmadı.')
        screen = self.lib.XDefaultScreen(self.display)
        self.atom = self.lib.XInternAtom(self.display, f'_NET_WM_CM_S{screen}'.encode(), 0)
        self.wm_atom = self.lib.XInternAtom(self.display, f'WM_S{screen}'.encode(), 0)

    def owner(self):
        return int(self.lib.XGetSelectionOwner(self.display, self.atom))

    def wm_owner(self):
        # Xfwm 4.18 / 4.20: CM ve WM seçimi aynı xfwm4_win'i kullanır.
        # Pencere yok edilişiyle yarışan özellik sorgusu gerekmez.
        return int(self.lib.XGetSelectionOwner(self.display, self.wm_atom))

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None


def state_directory():
    base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oguzdows/effects'
    if base.is_symlink():
        raise ValueError('Efekt üst veri dizini sembolik bağ olamaz.')
    # Aynı hesabın başka X ekranı / oturumu kendi kompozitörünü korur.
    key = hashlib.sha256(os.environ.get('DISPLAY', '').encode()).hexdigest()[:16]
    directory = base / key
    if directory.is_symlink():
        raise ValueError('Efekt veri dizini sembolik bağ olamaz.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.stat().st_uid != os.getuid():
        raise ValueError('Efekt veri dizini bu kullanıcıya ait olmalı.')
    directory.chmod(0o700)
    return directory


def identity(pid, proc=Path('/proc')):
    if type(pid) is not int or pid <= 1:
        return None
    path = proc / str(pid)
    try:
        if path.stat().st_uid != os.getuid():
            return None
        fields = (path / 'stat').read_text().rsplit(') ', 1)[1].split()
        argv = (path / 'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
        if (fields[0] == 'Z' or len(argv) != 3 or argv[:2] != [os.fsencode(BINARY), b'--config']
                or argv[2] not in {os.fsencode(path) for path in CONFIGS}):
            return None
        return fields[19]  # /proc stat field 22, PID reuse guard.
    except (OSError, ValueError, IndexError):
        return None


def owned_state(directory):
    path = directory / 'picom.json'
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2048:
            return None
        value = json.loads(path.read_text())
        if (isinstance(value, dict) and type(value.get('pid')) is int and isinstance(value.get('started'), str)
                and type(value.get('owner')) is int and value['owner'] > 0
                and identity(value['pid']) == value['started']):
            return value
    except (OSError, ValueError, TypeError):
        pass
    return None


def stop_instance(value):
    # Çağıran /proc kimliğini hemen önce doğrular; genel PID sinyali yok.
    if value:
        try:
            os.kill(value['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 2
        while identity(value['pid']) == value['started'] and time.monotonic() < deadline:
            time.sleep(.04)
        # Süreç kapanmadıysa sahiplik kaydını silip ikinci motor açma.
        if identity(value['pid']) == value['started']:
            raise RuntimeError('OğuzDows Picom motoru henüz durmadı; sahiplik kaydı korundu.')
        # Mevcut veya başka kullanıcı sürecine SIGKILL / killall yok.
        try:
            os.waitpid(value['pid'], os.WNOHANG)
        except ChildProcessError:
            pass


def stop_owned(directory):
    stop_instance(owned_state(directory))
    (directory / 'picom.json').unlink(missing_ok=True)


def xfwm(enabled):
    result = subprocess.run(['/usr/bin/xfconf-query', '-c', 'xfwm4', '-p', '/general/use_compositing',
                             '-s', str(enabled).lower()], capture_output=True, text=True, timeout=6, check=False)
    if result.returncode:
        raise ValueError('Pencere yöneticisinin kompozitör tercihi uygulanamadı.')


def wait_owner(x11, expected, seconds=2):
    deadline = time.monotonic() + seconds
    while True:
        current = x11.owner()
        if (current == expected if expected is not None else current != 0):
            return current
        if time.monotonic() >= deadline:
            return current
        time.sleep(.04)


def apply_xfwm(x11, enabled):
    xfwm(enabled)
    if not enabled:
        return 'none'
    # xfconf yazısının kabulü tek başına çalışan kompozitör kanıtı değildir.
    # Örn. kullanıcı xfwm4 --compositor=off ile başlatmış olabilir.
    owner = wait_owner(x11, None)
    return 'xfwm4' if owner and owner == x11.wm_owner() else 'external' if owner else 'none'


def release_owned(directory, current, x11):
    stop_owned(directory)
    # /proc'ta çocuk zombi olmuş olsa bile X sunucusu CM seçimini bir sonraki
    # turda bırakabilir. Kendi kimliğimizi yabancı motor sanıp camı atlama.
    if current and x11.owner() == current['owner']:
        wait_owner(x11, 0)


def spawn(directory, configuration=CONFIG):
    # posix_spawn: uzun yaşayan tek süreç Picom'dur; Popen / Python daemon yok.
    # Sabit sistem config'i; ~/.config/picom.conf veya shell metni çalıştırılmaz.
    configuration = Path(configuration)
    if configuration not in CONFIGS:
        raise ValueError('Efekt reçetesi sistem izin listesinde değil.')
    descriptor = os.open(directory / 'picom.log', os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    null = os.open('/dev/null', os.O_RDONLY)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError('Efekt günlüğü normal dosya olmalı.')
        os.fchmod(descriptor, 0o600)
        return os.posix_spawn(str(BINARY), [str(BINARY), '--config', str(configuration)], os.environ,
                              file_actions=[(os.POSIX_SPAWN_DUP2, null, 0),
                                            (os.POSIX_SPAWN_DUP2, descriptor, 1),
                                            (os.POSIX_SPAWN_DUP2, descriptor, 2)], setsid=True)
    finally:
        os.close(descriptor)
        os.close(null)


@contextmanager
def locked(directory):
    descriptor = os.open(directory / '.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError('Efekt kilidi normal dosya olmalı.')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Başka bir efekt işlemi devam ediyor; ikinci motor başlatılmadı.') from error
        yield


def xfwm_preference():
    from profiles import read_property, run
    value = read_property('xfwm4', '/general/use_compositing', 'bool', run)
    if value not in (None, 'true', 'false'):
        raise ValueError('Xfwm kompozitör tercihi güvenle yedeklenemedi.')
    return value


def restore_xfwm_preference(value):
    from profiles import set_property, run
    set_property('xfwm4', '/general/use_compositing', 'bool', value, run)
    if xfwm_preference() != value:
        raise RuntimeError('Xfwm kompozitör tercihi geri okunarak doğrulanamadı.')


class RuntimeUndo:
    """Tek işlem / sahiplik kanıtı. Eski ortak varsayılanlar tekrar uygulanmaz.

    Picom yeniden açılacaksa yalnız önceden çalışan sabit reçete bir kez açılır;
    PID aynılığı değil aynı sahipli motor / reçete geri yüklenir. Xfwm tercihinin
    tam eski değeri karşılaştırmalı geri alınır; profiles geri alması bunu ezmez.
    """
    def __init__(self, directory, x11, resources, connect):
        from desktop_state import read_json
        self.directory, self.resources, self.connect = directory, resources, connect
        current = owned_state(directory)
        self.before = current if current and current['owner'] == x11.owner() else None
        self.before_status = read_json(directory / 'status.json')
        self.before_preference = xfwm_preference()
        self.after_preference = self.before_preference
        self.after = None
        self.owner = x11.owner()
        self.after_status = None
        self.captured = False

    def capture(self, x11, spawned=None):
        from desktop_state import read_json
        self.owner = x11.owner()
        current = owned_state(self.directory)
        if spawned and identity(spawned['pid']) == spawned['started'] and spawned['owner'] == self.owner:
            current = spawned  # Metadata yazımı arızalı olsa da bu çocuğun kanıtı var.
        self.after = current if current and current['owner'] == self.owner else None
        self.after_preference = xfwm_preference()
        self.captured = True
        self.after_status = read_json(self.directory / 'status.json')

    def __call__(self):
        if not self.captured:
            return
        from desktop_state import read_json, atomic_json
        directory = self.directory
        with locked(directory):
            x11 = self.connect()
            try:
                # Araya başka bir kompozitör / işlem girdiyse ona dokunma.
                if x11.owner() != self.owner or xfwm_preference() != self.after_preference:
                    return
                expected_preference = self.after_preference
                if self.after and identity(self.after['pid']) != self.after['started']:
                    return
                before_config = Path(self.before.get('config', CONFIG)) if self.before else None
                after_config = Path(self.after.get('config', CONFIG)) if self.after else None
                if before_config != after_config:
                    if self.after:
                        stop_instance(self.after)
                        if wait_owner(x11, 0) != 0:
                            raise RuntimeError('İşlemin Picom motoru henüz durmadı; ikinci motor açılmadı.')
                        # Duran PID artık owned_state ile doğrulanamaz. Diskte
                        # yalnız bu işlemin bıraktığı aynı kaydı kaldır.
                        if read_json(directory / 'picom.json') == self.after:
                            (directory / 'picom.json').unlink(missing_ok=True)
                    if self.before:
                        if not self.resources['compositing']:
                            raise RuntimeError('Eski Picom düşük kaynak koruması nedeniyle yeniden açılmadı.')
                        if before_config not in CONFIGS:
                            raise ValueError('Geri alınacak motor reçetesi izin listesinde değil.')
                        if x11.owner() == x11.wm_owner():
                            xfwm(False)
                            expected_preference = 'false'
                        if wait_owner(x11, 0) != 0:
                            raise RuntimeError('Geri alma sırasında başka kompozitör korunuyor.')
                        pid = spawn(directory, before_config)
                        started = identity(pid)
                        owner = wait_owner(x11, None)
                        if not started or not owner:
                            if started: stop_instance({'pid': pid, 'started': started})
                            raise RuntimeError('Önceki Picom reçetesi geri açılamadı.')
                        restored = dict(self.before, pid=pid, started=started, owner=owner)
                        try:
                            atomic_text(directory / 'picom.json', json.dumps(restored) + '\n')
                        except OSError:
                            stop_instance(restored)
                            raise
                if xfwm_preference() == expected_preference:
                    restore_xfwm_preference(self.before_preference)
                if read_json(directory / 'status.json') == self.after_status:
                    if self.before_status is None:
                        (directory / 'status.json').unlink(missing_ok=True)
                    else:
                        atomic_json(directory / 'status.json', self.before_status)
            finally:
                x11.close()


def prepare_undo(resources, *, directory=None, connect=X11):
    directory = state_directory() if directory is None else Path(directory)
    with locked(directory):
        x11 = connect()
        try:
            return RuntimeUndo(directory, x11, resources, connect)
        finally:
            x11.close()


def reconcile(effect=None, resources=None, *, directory=None, connect=X11, preferences=None, capability=None, checkpoint=None):
    if effect is None:
        # İlk giriş / kişisel xfwm ayarı: kullanıcı tercih etmeden kapatma.
        if read_state(profile_directory(), 'effects') not in ('off', 'glass', 'aero'):
            return {'engine': 'unchanged', 'transitions': False, 'message': 'Kayıtlı efekt tercihi yok; kişisel kompozitör ayarı korunur.'}
        effect = effect_selection()
    if effect not in ('off', 'glass', 'aero'):
        raise ValueError('Bilinmeyen efekt tercihi.')
    if os.getuid() == 0:
        return {'engine': 'none', 'transitions': False, 'message': 'Efekt yöneticisi normal kullanıcı oturumunda çalışır.'}
    if (not os.environ.get('DISPLAY') or os.environ.get('XDG_SESSION_TYPE', 'x11') != 'x11'
            or 'XFCE' not in os.environ.get('XDG_CURRENT_DESKTOP', '').upper().split(':')):
        return {'engine': 'unchanged', 'transitions': False, 'message': 'Yalnızca Xfce / X11 oturumu yönetilir; diğer masaüstü korunur.'}
    resources = current_policy() if resources is None else resources
    budget = bool(resources['compositing'])
    if preferences is None:
        from desktop_state import load
        preferences = dict(load(), effects=effect)
    plan = aero_plan(preferences, resources, capability)
    configuration = plan['config']
    directory = state_directory() if directory is None else Path(directory)
    with locked(directory):
        x11 = connect()
        spawned = None
        try:
            current = owned_state(directory)
            if effect != 'aero' or not budget:
                release_owned(directory, current, x11)
                owner = x11.owner()
                if owner and owner != x11.wm_owner():
                    result = {'engine': 'external', 'transitions': False,
                              'message': 'Kişisel kompozitör korunuyor; yalnızca OğuzDows geçiş motoru kapatıldı.'}
                else:
                    # Zaten xfwm'a ait seçim varsa camı KAPATIP açma. Aynı
                    # tercih tekrarlanabilir; dış kompozitöre dokunulmaz.
                    enabled = budget and effect == 'glass'
                    engine = apply_xfwm(x11, enabled)
                    result = {'engine': engine, 'transitions': False,
                              'message': 'Hafif cam; pencere geçişleri kapalı.' if engine == 'xfwm4' else 'Opak / statik görünüm; düşük kaynak koruması veya kompozitör kullanılabilirliği önceliklidir.'}
            elif current and x11.owner() == current['owner'] and current.get('config', str(CONFIG)) == str(configuration):
                result = {'engine': 'picom', 'transitions': preferences['motion'] != 'reduced', 'message': 'Kullanıcının seçtiği tek Picom motoru çalışıyor; metin / üst panel opak.'}
            else:
                release_owned(directory, current, x11)
                owner = x11.owner()
                external = bool(owner and owner != x11.wm_owner())
                if not external:
                    xfwm(False)
                if external or wait_owner(x11, 0) != 0:
                    result = {'engine': 'external', 'transitions': False,
                              'message': 'Başka kompozitör korunuyor; ikinci kompozitör başlatılmadı.'}
                else:
                    pid = None
                    owner = 0
                    # Zengin GLX açılamazsa yalnız BİR sabit XRender denemesi.
                    # Otomatik restart / GPU testi döngüsü / yabancı PID sinyali yok.
                    fallback = CONFIG.parent / 'compositor/still.conf' if preferences['motion'] == 'reduced' else CONFIG
                    candidates = [configuration] + ([fallback] if configuration != fallback else [])
                    for candidate in candidates:
                        if x11.owner() or not BINARY.is_file() or not os.access(BINARY, os.X_OK):
                            break
                        if not candidate.is_file():
                            continue
                        try:
                            pid = spawn(directory) if candidate == CONFIG else spawn(directory, candidate)
                        except OSError:
                            pid = None
                        owner = wait_owner(x11, None) if pid else 0
                        started = identity(pid)
                        if owner and started:
                            value = {'pid': pid, 'started': started, 'owner': owner}
                            if candidate != CONFIG:
                                value['config'] = str(candidate)
                            spawned = value
                            atomic_text(directory / 'picom.json', json.dumps(value) + '\n')
                            configuration = candidate
                            break
                        # Yalnızca az önce bu işçinin oluşturduğu çocuk.
                        if started:
                            os.kill(pid, signal.SIGTERM)
                            wait_owner(x11, 0)
                        if pid:
                            try:
                                os.waitpid(pid, os.WNOHANG)
                            except ChildProcessError:
                                pass
                        pid = None
                    if pid and owner and identity(pid):
                        result = {'engine': 'picom', 'transitions': preferences['motion'] != 'reduced' and configuration.name != 'still.conf',
                                  'message': 'İsteğe bağlı Aero motoru çalışıyor; zengin efektler sürüm / hızlandırma kapısından geçirilir.'}
                    else:
                        engine = apply_xfwm(x11, True) if x11.owner() == 0 else 'external'
                        result = {'engine': engine, 'transitions': False,
                                  'message': 'Geçiş motoru açılamadı; statik Aero / uygun olduğunda xfwm gölgesi korundu. Efekt günlüğünü inceleyebilirsin.'}
            rich_running = result['engine'] == 'picom' and configuration == plan['config']
            result.update({key: bool(plan[key] and rich_running) for key in ('blur_configured', 'spring_configured', 'snap_configured')})
            if plan['note']:
                result['message'] += ' ' + plan['note']
            if result['engine'] == 'picom':
                result['config'] = str(configuration)
            atomic_text(directory / 'status.json', json.dumps({**result, 'physical_gpu_verified': False}, ensure_ascii=False) + '\n')
            return result
        finally:
            try:
                if checkpoint is not None:
                    checkpoint.capture(x11, spawned)
            finally:
                x11.close()


def main():
    if sys.argv[1:] not in ([], ['--session']):
        raise SystemExit('Kullanım: effects.py [--session]')
    try:
        print(json.dumps(reconcile(), ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('OğuzDows efekt işlemi tamamlanamadı: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
