#!/usr/bin/env python3
"""X11 girişini hafif ve kayıtlı başlatır; kalıcı Python işçisi bırakmaz."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resource_policy import current_policy


def environment(resources, original):
    env = dict(original)
    # Bu giriş yalnızca /usr/share/xsessions/oguzdows.desktop içindir.
    env.update(XDG_SESSION_TYPE='x11', XDG_CURRENT_DESKTOP='XFCE',
               XDG_SESSION_DESKTOP='oguzdows', DESKTOP_SESSION='oguzdows', GDK_BACKEND='x11')
    env.pop('WAYLAND_DISPLAY', None)
    if resources['profile'] in ('mini', 'light'):
        # LLVM yazılım fallback'inin CPU başına işçi / arena büyütmesini sınırla.
        # Donanım GL sürücüsü zorlanmaz / kapatılmaz. Kullanıcı ayarı korunur.
        env.setdefault('LP_NUM_THREADS', '1' if resources['profile'] == 'mini' else '2')
        env.setdefault('MALLOC_ARENA_MAX', '2')
    if resources.get('legacy_cpu'):
        # GTK4 uygulamaları Zero'da GL/Vulkan renderer derlemeye zorlanmasın.
        env.setdefault('GSK_RENDERER', 'cairo')
    return env


def log_start(resources, env, directory=None):
    directory = (Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
                 / 'oguzdows/session' if directory is None else Path(directory))
    if directory.is_symlink():
        raise ValueError('Oturum kayıt dizini bağlantı olamaz.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.stat().st_uid != os.getuid():
        raise ValueError('Oturum kayıt dizini bu kullanıcıya ait değil.')
    directory.chmod(0o700)
    # Ortamın tamamı / parola / D-Bus adresi kaydedilmez.
    summary = {'schema': 1, 'uid': os.getuid(), 'profile': resources['profile'],
               'legacy_cpu': resources.get('legacy_cpu', False),
               'environment': {key: env[key] for key in ('GDK_BACKEND', 'LP_NUM_THREADS',
                                 'MALLOC_ARENA_MAX', 'GSK_RENDERER') if key in env},
               'note': 'Başlangıç isteği; masaüstü açılışı veya RAM tasarrufu kanıtı değildir.'}
    path = directory / 'startup.json'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'w') as out:
        if not stat.S_ISREG(os.fstat(out.fileno()).st_mode):
            raise ValueError('Oturum kaydı normal dosya değil.')
        os.fchmod(out.fileno(), 0o600)
        json.dump(summary, out, ensure_ascii=False)
        out.write('\n')
    return directory


def main():
    if len(sys.argv) != 1:
        raise SystemExit('Bu giriş ek argüman veya komut kabul etmez.')
    resources = current_policy()
    env = environment(resources, os.environ)
    try:
        log_start(resources, env)
    except (OSError, ValueError) as error:
        print('OğuzDows oturum kaydı oluşturulamadı: ' + str(error), file=sys.stderr)
    # Politikayı WM açılmadan uygula; autostart'ta kompozitör tepesini bekleme.
    try:
        import profiles
        profiles.session(resources=resources)
        env['OGUZDOWS_SESSION_PREPARED'] = '1'
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('OğuzDows kaynak görünümü uygulanamadı: ' + str(error), file=sys.stderr)
    # exec: giriş sürecinin yerine Xfce geçer; bir kabuk / Python daemon kalmaz.
    os.execve('/usr/bin/startxfce4', ['/usr/bin/startxfce4'], env)


if __name__ == '__main__':
    main()
