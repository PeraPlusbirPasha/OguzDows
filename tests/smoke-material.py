#!/usr/bin/env python3
"""Real GTK parser, event-driven appearance and bounded page transition test.

Resource eligibility is simulated so Xvfb can exercise the GTK animation API.
This is NOT physical GPU / FPS or universal backdrop-blur validation.
"""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk

from support import ROOT
sys.path.insert(0, str(ROOT / 'system/usr/lib/oguzdows'))
import desktop_state
import ui_theme


def pump(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while GLib.MainContext.default().iteration(False):
            pass
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Native material transition / preference event timed out')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assert Gtk.init_check([])[0]
    settings = Gtk.Settings.get_default()
    settings.set_property('gtk-theme-name', 'Adwaita')
    settings.set_property('gtk-enable-animations', True)
    errors = []
    original_hook = sys.excepthook
    def exception(kind, value, trace):
        errors.append(kind.__name__ + ': ' + str(value))
        original_hook(kind, value, trace)
    sys.excepthook = exception
    with tempfile.TemporaryDirectory(prefix='oguz-native-material-') as directory:
        os.environ.update(XDG_CONFIG_HOME=directory, XDG_STATE_HOME=directory)
        path = Path(directory) / 'oguzdows/desktop.json'
        prefs = {**desktop_state.DEFAULTS, 'appearance': 'light', 'motion': 'smooth', 'effects': 'aero', 'blur': True}
        desktop_state.atomic_json(path, prefs)
        # Real CSS parsing is fatal on either target's GTK 3 version.
        css = Gtk.CssProvider()
        css.load_from_path(str(ui_theme.CSS))
        resources = {'animations': True, 'compositing': True}
        with patch('resource_policy.current_policy', return_value=resources):
            window = Gtk.Window(title='OğuzDows · native material test')
            window.set_default_size(480, 320)
            ui_theme.setup(window)
            stack = Gtk.Stack()
            stack.add_named(Gtk.Label(label='First native page'), 'one')
            stack.add_named(Gtk.Label(label='Second native page'), 'two')
            window.add(stack)
            ui_theme.configure_stack(window, stack)
            window.show_all()
            pump(lambda: window.get_mapped())
            context = window.get_style_context()
            assert not context.has_class('oguzdows-glass'), 'No owned Picom -> no alpha even if requested'
            assert stack.get_transition_duration() == 200
            assert stack.get_transition_type() == Gtk.StackTransitionType.CROSSFADE
            stack.set_visible_child_name('two')
            pump(stack.get_transition_running)
            pump(lambda: not stack.get_transition_running())
            # Monitor sees atomic rename, no polling in product code.
            prefs.update(appearance='dark', motion='reduced')
            desktop_state.atomic_json(path, prefs)
            pump(lambda: context.has_class('oguzdows-dark') and context.has_class('reduced-motion'))
            assert stack.get_transition_duration() == 0
            stack.set_visible_child_name('one')
            assert not stack.get_transition_running()
            pixels = Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, *window.get_size())
            assert pixels is not None
            pixels.savev(str(args.output / 'material-dark-reduced.png'), 'png', [], [])
            settings.set_property('gtk-theme-name', 'HighContrast')
            pump(lambda: not context.has_class('oguzdows-modern'))
            window.destroy()
            assert window._oguz_material['closed']
        if errors:
            raise AssertionError('; '.join(errors))
    report = {'real_gtk_css': True, 'real_stack_transition': True, 'duration_ms': 200,
              'live_preference_monitor': True, 'reduced_motion_immediate': True,
              'high_contrast_preserved': True, 'unconfirmed_blur_opaque': True,
              'simulated_resource_policy': True, 'physical_gpu': False}
    (args.output / 'material-native.json').write_text(json.dumps(report, indent=2) + '\n')
    print('::notice title=Native material GTK::' + json.dumps(report))


if __name__ == '__main__':
    main()
