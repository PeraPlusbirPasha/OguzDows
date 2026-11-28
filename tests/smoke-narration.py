#!/usr/bin/env python3
"""Gerçek GTK / D-Bus ses kapısı; oynatıcı ve kurucu asla çalıştırılmaz."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib
from support import ROOT, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('test-results'))
    parser.add_argument('--phone', action='store_true', help='Dar host ekranı; fiziksel telefon / ses testi değil')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    peer = None
    errors = []
    recorded = []
    state = ['initial']
    layout = {}
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as temporary:
        os.environ.update(XDG_CONFIG_HOME=temporary, XDG_STATE_HOME=temporary, OGUZDOWS_TESTING='1')
        module = load('narration_gtk_smoke', 'system/usr/lib/oguzdows/narration.py')
        app = module.Narration()
        assert app.register(None)
        app.activate()
        bar = app.bar
        bar.speaker.assets = ROOT / 'system/usr/share/oguzdows/rifki'
        from rifki_speech import load_manifest
        bar.speaker.clips = load_manifest(bar.speaker.assets)
        def speak(text, _cue=None):
            assert not bar.blocked
            recorded.append(text)
            bar.speaker.notify(True)  # Oynatıcı yerine görünür durum; ses donanımı gerekmez.
            return True
        bar.speaker.speak = speak
        loop = GLib.MainLoop()
        counts = {}
        def send(word):
            peer.stdin.write(word + '\n')
            peer.stdin.flush()
        def step():
            nonlocal peer
            try:
                if time.monotonic() - started > 12:
                    raise RuntimeError('Anlatım GTK / D-Bus kapısı zaman aşımı: ' + state[0])
                if state[0] == 'initial' and bar.gate_ready and not bar.blocked:
                    bar.stop()
                    self_window = app.window
                    app.topic = 'compatibility'
                    app.activate()
                    assert app.window is self_window, 'Tek anlatım penceresi yeniden kullanılmalı'
                    bar.listen()
                    assert recorded[-1] == module.words('compatibility')
                    assert bar.speaker.playing
                    peer = subprocess.Popen([sys.executable, str(Path(__file__).with_name('launcher-peer.py'))],
                                            stdin=subprocess.PIPE, text=True)
                    state[0] = 'busy'
                elif state[0] == 'busy' and bar.gate_ready and bar.blocked:
                    assert not bar.speaker.playing
                    counts['before_busy_listen'] = len(recorded)
                    bar.listen()
                    assert not bar.pending, 'Kurulumda ses daha sonra çalmak üzere sıraya alınmamalı'
                    assert len(recorded) == counts['before_busy_listen']
                    assert not bar.listen_button.get_sensitive()
                    send('finish')
                    state[0] = 'ready'
                elif state[0] == 'ready' and bar.gate_ready and not bar.blocked:
                    assert len(recorded) == counts['before_busy_listen'], 'Kurulum bitince ses kendiliğinden başlamamalı'
                    assert not bar.speaker.playing and bar.listen_button.get_sensitive()
                    bar.listen()
                    assert bar.speaker.playing
                    bar.focus_changed(SimpleNamespace(is_active=lambda: False))
                    assert not bar.speaker.playing, 'Pencere odak kaybında ses sürmemeli'
                    bar.sound.set_active(False)
                    count = len(recorded)
                    bar.listen()
                    assert len(recorded) == count and 'kapalı' in bar.status.get_text()
                    assert json.loads(bar.speaker.preference.read_text())['speech'] is False
                    bar.sound.set_active(True)
                    send('busy')
                    state[0] = 'busy-again'
                elif state[0] == 'busy-again' and bar.blocked:
                    bar.listen()
                    assert not bar.pending
                    send('quit')
                    state[0] = 'vanished'
                elif state[0] == 'vanished' and bar.gate_ready and not bar.blocked:
                    assert bar.group is None
                    assert not bar.speaker.playing
                    # Oturum veri yolu kaybı, 'kurucu yok' ile karıştırılmaz.
                    bar.vanished(None)
                    assert bar.blocked and not bar.listen_button.get_sensitive()
                    assert 'ulaşılamadı' in bar.status.get_text()
                    app.explanation.set_text(module.words('store'))
                    native = app.window.get_window()
                    native.process_updates(True)
                    width, height = app.window.get_size()
                    image = Gdk.pixbuf_get_from_window(native, 0, 0, width, height)
                    assert image is not None
                    image.savev(str(args.output / 'narration.png'), 'png', [], [])
                    screen = app.window.get_screen()
                    layout.update(width=width, height=height, screen_width=screen.get_width(), screen_height=screen.get_height())
                    if args.phone:
                        assert width <= screen.get_width() and height <= screen.get_height(), 'Anlatım penceresi dar ekranın dışına taşmamalı: ' + str(layout)
                    app.window.destroy()
                    assert bar.closed and bar.speaker.closed
                    state[0] = 'complete'
                    loop.quit()
                    return GLib.SOURCE_REMOVE
            except Exception as error:
                errors.append(str(error))
                loop.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        GLib.timeout_add(50, step)
        try:
            loop.run()
        finally:
            if app.window is not None:
                app.window.destroy()
            if peer is not None:
                try:
                    send('quit')
                except (BrokenPipeError, OSError):
                    pass
                try:
                    peer.stdin.close()
                except BrokenPipeError:
                    pass  # Test kurucusu quit'i işleyip boruyu zaten kapatmış olabilir.
                try:
                    code = peer.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    peer.terminate()
                    code = peer.wait(timeout=3)
                if code:
                    errors.append('Test kurucu süreci çıkış kodu: ' + str(code))
    result = {'real_gtk_and_dbus': True, 'real_audio_playback': False, 'real_installer': False,
              'phase': state[0], 'recorded_requests': len(recorded), 'layout': layout, 'errors': errors}
    (args.output / 'narration.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Doğal kayıt GTK ve D-Bus::' + json.dumps(result, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
