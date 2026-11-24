#!/usr/bin/env python3
"""Picom'un gerçek parser / GLX shader / backdrop blur testi (yalnız CI).

Xvfb + Mesa yazılım GPU'sunda, özel normal kullanıcı evinde ARGB test yüzeyi.
Üretim hızlandırma kapısı ASLA gevşetilmez. Fiziksel GPU / Pi / FPS kanıtı değil.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from support import ROOT


def child(directory):
    home = Path(os.environ.get('HOME', '/')).resolve()
    if (os.getuid() == 0 or directory.parent != Path(tempfile.gettempdir())
            or not directory.name.startswith('oguzdows-aero-ci-') or home != directory / 'home'
            or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        raise ValueError('Yalnız tek kullanımlık normal kullanıcı CI evi.')
    import cairo
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    gi.require_foreign('cairo')
    from gi.repository import Gdk, Gtk
    import aero
    from effects import X11
    import desktop_x11

    def pump(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            while Gtk.events_pending(): Gtk.main_iteration_do(False)
            time.sleep(.008)

    def stop(process):
        if process is not None:
            if process.poll() is None: os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=6)

    def wait_owner(x11, wanted, process=None):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if bool(x11.owner()) == wanted: return
            if process and process.poll() is not None:
                raise AssertionError('Picom / Xfwm erken kapandı: ' + str(process.returncode))
            pump(.04)
        raise AssertionError('X11 compositor seçimi süre sınırında değişmedi')

    background = Gtk.Window(title='OğuzDows · CI checkerboard')
    background.set_decorated(False); background.move(0, 0); background.resize(1024, 768)
    area = Gtk.DrawingArea()
    def checker(widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgb(.06, .12, .20); cr.paint()
        cr.set_source_rgb(.96, .96, .96)
        for y in range(0, widget.get_allocated_height(), 4):
            for x in range(0, widget.get_allocated_width(), 4):
                if (x // 4 + y // 4) % 2: cr.rectangle(x, y, 4, 4)
        cr.fill(); return True
    area.connect('draw', checker); background.add(area)
    front = Gtk.Window(title='OğuzDows · CI ARGB cam')
    visual = front.get_screen().get_rgba_visual(); assert visual is not None
    front.set_visual(visual); front.set_app_paintable(True); front.resize(300, 220); front.move(320, 260)
    def glass(_widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE); cr.set_source_rgba(.18, .36, .48, .22); cr.paint(); return True
    front.connect('draw', glass)
    report = {'scope': 'private-nonroot-Xvfb-real-GLX-software-rendering', 'physical_gpu_verified': False,
              'resource_budget_simulated': True, 'production_acceleration_guard_bypassed': False,
              'recipes_launched_directly_only_by_ci_test': True, 'recipes': {}}
    wm = compositor = None; x11 = None
    try:
        with (directory / 'xfwm.log').open('w') as log:
            wm = subprocess.Popen(['/usr/bin/xfwm4', '--compositor=off', '--vblank=off'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        pump(1); assert wm.poll() is None
        x11 = X11(); assert x11.wm_owner() > 0 and x11.owner() == 0
        subprocess.run(['/usr/bin/xfconf-query', '-c', 'xfwm4', '-p', '/general/theme', '-s', 'OguzDowsAeroGlass'], check=True, capture_output=True, timeout=5)
        background.show_all(); front.show_all(); front.present(); pump(.6)
        version = subprocess.run(['/usr/bin/picom', '--version'], capture_output=True, text=True, check=True, timeout=5).stdout.strip()
        major = int(re.search(r'(\d+)\.', version)[1]); report['picom'] = version
        capability = aero.probe(); report['production_probe'] = capability
        assert capability['accelerated'] is False  # CI llvmpipe, gerçek GPU gibi sunulmaz.
        names = ['still', 'blur9-still', 'blur9'] if major == 9 else ['still', 'blur-still', 'blur']
        if major >= 12: names += ['motion', 'full', 'snap', 'full-snap']
        for name in names:
            config = Path('/usr/share/oguzdows/compositor') / (name + '.conf')
            with (directory / (name + '.log')).open('w') as log:
                compositor = subprocess.Popen(['/usr/bin/picom', '--config', str(config)], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            wait_owner(x11, True, compositor); pump(.8)
            assert compositor.poll() is None
            origin = front.get_window().get_origin()[-2:]
            capture = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), origin[0] + 60, origin[1] + 60, 96, 96)
            assert capture is not None
            pixels = capture.get_pixels(); channels = capture.get_n_channels(); stride = capture.get_rowstride()
            values = [pixels[y * stride + x * channels] for y in range(96) for x in range(96)]
            deviation = statistics.pstdev(values)
            report['recipes'][name] = {'selection_owned': True, 'sample_standard_deviation': round(deviation, 3)}
            if name == 'still': baseline = deviation
            if 'blur' in name or name in ('full', 'full-snap'):
                assert deviation < baseline * .85, (name, deviation, baseline)
                report['recipes'][name]['actual_background_blur_on_argb_fixture'] = True
            if name in ('blur9-still', 'full-snap', 'blur-still'):
                capture = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, 1024, 768)
                capture.savev(str(directory / (name + '.png')), 'png', [], [])
            front.iconify(); pump(.3); front.deiconify(); front.present(); pump(.35)
            if name in ('snap', 'full-snap'):
                desktop_x11.snap('left'); pump(.35)
                desktop_x11.snap('right'); pump(.35)
                desktop_x11.snap('restore'); pump(.35)
                report['recipes'][name]['native_ewmh_snap_requests'] = True
            assert compositor.poll() is None
            stop(compositor); compositor = None; wait_owner(x11, False)
    except Exception:
        for path in directory.glob('*.log'):
            text = path.read_text(errors='replace')[-2400:]
            print('::error title=Picom ' + path.stem + '::' + text.replace('%', '%25').replace('\n', '%0A'), flush=True)
        raise
    finally:
        front.destroy(); background.destroy()
        stop(compositor); stop(wm)
        if x11: x11.close()
        (directory / 'aero.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Gerçek Picom GLX ve ARGB blur sonucu::' + json.dumps(report, ensure_ascii=False).replace('%', '%25'), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path); parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true': parser.error('Yalnız CI / özel Xvfb ekranı.')
    if args.child: child(args.child); return
    if args.output is None or not os.environ.get('XAUTHORITY'): parser.error('--output ve özel xvfb-run Xauthority gerekli.')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-aero-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'
        shutil.copytree(ROOT / 'system/etc/skel', home); (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key != 'DBUS_SESSION_BUS_ADDRESS'}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_STATE_HOME=str(home / '.local/state'),
                   XDG_CACHE_HOME=str(home / '.cache'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE',
                   XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1', LIBGL_ALWAYS_SOFTWARE='1')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()), '--child', str(directory)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try: subprocess.run(command, env=env, check=True, timeout=100)
        finally:
            for path in directory.iterdir():
                if path.is_file() and path.suffix in ('.log', '.json', '.png'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
