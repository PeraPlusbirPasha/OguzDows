"""Shared GTK3 material / bounded native page transitions, without a new daemon.

The C equivalent lives in native/ui.c; both consume desktop.json, modern.css
and the existing resource / compositor contracts. Importing this module does
not import GTK, touch configuration, query hardware or start a worker.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / 'share/oguzdows/ui/modern.css'


def motion_allowed(preferences, resources, animations):
    return bool(animations and resources.get('animations') and preferences.get('motion') != 'reduced')


def blur_confirmed(screen, preferences, resources):
    """Fail closed: alpha is not itself proof of an active blur compositor."""
    if (not resources.get('compositing') or preferences.get('effects') != 'aero'
            or not preferences.get('blur') or not screen.is_composited()
            or os.environ.get('XDG_SESSION_TYPE') == 'wayland'):
        return False
    import desktop_state
    import effects
    key = hashlib.sha256(os.environ.get('DISPLAY', '').encode()).hexdigest()[:16]
    base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oguzdows/effects' / key
    try:
        status = desktop_state.read_json(base / 'status.json') or {}
        owner = effects.owned_state(base)
        if status.get('engine') != 'picom' or status.get('blur_configured') is not True or not owner:
            return False
        x11 = effects.X11()
        try:
            return x11.owner() == owner['owner']
        finally:
            x11.close()
    except (OSError, ValueError, RuntimeError):
        return False


def setup(window):
    """Install once per window; refresh only on preferences/settings events.

    Content and title controls are opaque even when the root is real ARGB.
    Unknown compositor / GNOME CSD / Wayland -> opaque, no fake blur claim.
    The compositor owns window open/close; this module never double-animates it.
    """
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gio, GLib, Gtk
    import desktop_state
    from resource_policy import current_policy

    if getattr(window, '_oguz_material', None) is not None:
        window._oguz_material['refresh']()
        return
    screen = window.get_screen()
    visual = screen.get_rgba_visual()
    if visual is not None and not window.get_realized():
        window.set_visual(visual)
    css = Gtk.CssProvider()
    if CSS.is_file():
        css.load_from_path(str(CSS))
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    tint = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_screen(screen, tint, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    settings = Gtk.Settings.get_default()
    context = window.get_style_context()
    state = {'stacks': [], 'signals': [], 'monitor': None, 'closed': False}

    def refresh(*_args):
        if state['closed']:
            return
        try:
            prefs = desktop_state.load()
        except (OSError, ValueError):
            prefs = dict(desktop_state.DEFAULTS, motion='reduced', effects='off')
        resources = current_policy()
        animations = settings.get_property('gtk-enable-animations')
        motion = motion_allowed(prefs, resources, animations)
        theme = settings.get_property('gtk-theme-name') or ''
        for name, enabled in (('oguzdows-modern', 'HighContrast' not in theme),
                              ('oguzdows-dark', prefs['appearance'] == 'dark'),
                              ('reduced-motion', not motion),
                              ('oguzdows-glass', blur_confirmed(screen, prefs, resources))):
            (context.add_class if enabled else context.remove_class)(name)
        # desktop_state.validate accepts exactly #RRGGBB; not free CSS.
        tint.load_from_data(('@define-color og_accent ' + prefs['accent'] + ';').encode())
        state['motion'] = motion
        for stack in state['stacks']:
            stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE if motion else Gtk.StackTransitionType.NONE)
            stack.set_transition_duration(200 if motion else 0)

    def changed(_monitor, file, _other, event):
        if file.get_basename() == 'desktop.json' and event in (
                Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                Gio.FileMonitorEvent.DELETED, Gio.FileMonitorEvent.MOVED_IN):
            refresh()

    for signal in ('notify::gtk-enable-animations', 'notify::gtk-application-prefer-dark-theme', 'notify::gtk-theme-name'):
        state['signals'].append((settings, settings.connect(signal, refresh)))
    state['signals'].append((screen, screen.connect('composited-changed', refresh)))
    directory = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'oguzdows'
    try:
        state['monitor'] = Gio.File.new_for_path(str(directory)).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        state['monitor'].connect('changed', changed)
    except GLib.Error:
        pass

    def destroyed(*_args):
        state['closed'] = True
        if state['monitor']:
            state['monitor'].cancel()
        for obj, handler in state['signals']:
            obj.disconnect(handler)
        state['stacks'].clear()
        Gtk.StyleContext.remove_provider_for_screen(screen, css)
        Gtk.StyleContext.remove_provider_for_screen(screen, tint)

    state['refresh'] = refresh
    window._oguz_material = state
    window.connect('destroy', destroyed)
    refresh()


def configure_stack(window, stack):
    setup(window)
    state = window._oguz_material
    if stack not in state['stacks']:
        state['stacks'].append(stack)
    state['refresh']()
