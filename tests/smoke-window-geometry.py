#!/usr/bin/env python3
"""Real Thunar XShape, GTK CSD state styles and reversible preview budgets.

Private non-root Xvfb only, at real GTK scale 1 or 2, without composition and
with the production Xrender Picom recipe. Not physical GPU / Pi / FPS proof.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from support import ROOT

THEMES = ('OguzDows', 'OguzDowsLight', 'OguzDowsXP', 'OguzDowsXPDark',
          'OguzDowsEleven', 'OguzDowsElevenDark', 'OguzDowsMac', 'OguzDowsMacDark',
          'OguzDowsGnome', 'OguzDowsGnomeDark', 'OguzDowsAero', 'OguzDowsAeroDark',
          'OguzDowsAeroGlass', 'OguzDowsAeroGlassDark')


def coverage(intervals, start, end):
    """Exact union, not a few sample pixels that could miss a broken rail."""
    cursor = start
    for left, right in sorted(intervals):
        if cursor >= end:
            return True
        if left > cursor:
            return False
        cursor = max(cursor, right)
    return cursor >= end


def child(directory, scale):
    if (os.getuid() == 0 or directory.parent != Path(tempfile.gettempdir())
            or not directory.name.startswith('oguzdows-geometry-ci-')
            or Path.home().resolve() != directory / 'home'
            or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        raise ValueError('Only a disposable non-root CI session.')
    import cairo
    import gi
    gi.require_foreign('cairo')
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0'); gi.require_version('GdkX11', '3.0')
    from gi.repository import Gdk, GdkX11, Gtk
    from Xlib import X, XK, display, error, protocol
    from Xlib.ext import shape, xtest
    import desktop_material
    import desktop_state as state
    import effects
    import file_manager
    import profiles
    import ui_theme
    from resource_policy import policy

    processes = []; windows = []
    connection = display.Display(); root = connection.screen().root
    report = {'scope': 'nonroot-Xvfb-real-Thunar-XShape-GTK-CSD', 'gtk_scale': scale,
              'physical_gpu': False, 'physical_pi_boot': False, 'performance_measurement': False,
              'frames': [], 'view_modes': [], 'csd': []}

    def pump(seconds=.04):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for _ in range(60):
                if not Gtk.events_pending(): break
                Gtk.main_iteration_do(False)
            time.sleep(.008)

    def until(predicate, message, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate(): return
            pump()
        raise AssertionError(message)

    def start(name, command):
        with (directory / (name + '.log')).open('w') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process); return process

    def prop(window, name):
        value = window.get_full_property(connection.intern_atom(name), X.AnyPropertyType)
        return list(map(int, value.value)) if value is not None else []

    def clients():
        return [connection.create_resource_object('window', xid) for xid in prop(root, '_NET_CLIENT_LIST')]

    def thunar_window():
        for window in clients():
            if any('thunar' in part.lower() for part in window.get_wm_class() or ()):
                return window
        return None

    def activate(window):
        event = protocol.event.ClientMessage(window=window, client_type=connection.intern_atom('_NET_ACTIVE_WINDOW'),
                                             data=(32, [2, X.CurrentTime, 0, 0, 0]))
        root.send_event(event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        connection.sync()
        until(lambda: prop(root, '_NET_ACTIVE_WINDOW') == [window.id], 'WM did not activate test window')

    def keys(name, control=False):
        key = connection.keysym_to_keycode(XK.string_to_keysym(name))
        modifier = connection.keysym_to_keycode(XK.string_to_keysym('Control_L'))
        assert key
        if control: xtest.fake_input(connection, X.KeyPress, modifier)
        xtest.fake_input(connection, X.KeyPress, key); xtest.fake_input(connection, X.KeyRelease, key)
        if control: xtest.fake_input(connection, X.KeyRelease, modifier)
        connection.sync()

    def screenshot(name):
        pump(.18)
        geometry = root.get_geometry()
        pixels = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, geometry.width, geometry.height)
        assert pixels is not None
        pixels.savev(str(directory / (name + '.png')), 'png', [], [])

    def frame_contract(client, theme, engine, focus):
        frame = client
        while True:
            parent = frame.query_tree().parent
            if parent.id == root.id: break
            frame = parent
        assert frame.id != client.id, 'A real SSD frame, not the client area, is required'
        size = frame.get_geometry()
        extents = prop(client, '_NET_FRAME_EXTENTS')
        assert len(extents) == 4 and 0 < extents[0] <= 2 * scale and 0 < extents[3] <= 2 * scale, extents
        rectangles = frame.shape_get_rectangles(shape.SK.Bounding).rectangles
        # Xfwm constructs its binary mask with alpha == 255, NOT >= 128.
        # These assertions fail on the old alpha 190 / 110 / 90 frame assets.
        bottom = [(r.x, r.x + r.width) for r in rectangles if r.y <= size.height - 1 < r.y + r.height]
        left = [(r.y, r.y + r.height) for r in rectangles if r.x <= 0 < r.x + r.width]
        right = [(r.y, r.y + r.height) for r in rectangles if r.x <= size.width - 1 < r.x + r.width]
        assert coverage(bottom, 0, size.width), (theme, engine, focus, 'bottom XShape rail missing')
        assert coverage(left, extents[2], size.height), (theme, engine, focus, 'left XShape rail missing')
        assert coverage(right, extents[2], size.height), (theme, engine, focus, 'right XShape rail missing')
        report['frames'].append({'theme': theme, 'engine': engine, 'focus': focus, 'extents': extents,
                                 'size': [size.width, size.height], 'complete_side_and_bottom_mask': True})

    def decoration_style(window, square):
        # Exercise GTK's real selector cascade, including the application-
        # priority native provider. Only the test fill is white; it deliberately
        # DOES NOT set a radius, margin or box shadow. This is a style probe,
        # separate from the actual WM maximize / fullscreen checks below.
        path = window.get_style_context().get_path().copy()
        for name in window.get_style_context().list_classes():
            path.iter_add_class(path.length() - 1, name)
        index = path.append_type(Gtk.Widget)
        path.iter_set_object_name(index, 'decoration')
        context = Gtk.StyleContext.new(); context.set_path(path)
        context.set_parent(window.get_style_context())
        fill = Gtk.CssProvider()
        fill.load_from_data(b'decoration { background-color: white; background-image: none; border: 1px solid white; transition: none; }')
        context.add_provider(fill, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 40, 40)
        draw = cairo.Context(surface)
        Gtk.render_background(context, draw, 0, 0, 40, 40)
        Gtk.render_frame(context, draw, 0, 0, 40, 40)
        surface.flush()
        alpha = bytes(surface.get_data())[3 if sys.byteorder == 'little' else 0]
        assert (alpha > 240) if square else (alpha == 0), (path.to_string(), square, alpha)
        margin = context.get_margin(Gtk.StateFlags.NORMAL)
        assert (margin.left, margin.right, margin.top, margin.bottom) == ((0, 0, 0, 0) if square else (6, 6, 6, 6))

    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read('/usr/share/dbus-1/services/org.xfce.Xfconf.service')
        daemon = shlex.split(config['D-BUS Service']['Exec'])
        assert len(daemon) == 1 and Path(daemon[0]).name == 'xfconfd'
        for label, command in (('xfconf', daemon), ('xfwm', ['/usr/bin/xfwm4', '--compositor=off']),
                               ('xsettings', ['/usr/bin/xfsettingsd', '--no-daemon'])):
            process = start(label, command); pump(.4)
            assert process.poll() is None, label
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'accent_source': 'theme', 'motion': 'reduced'})
        with state.locked() as journal:
            first = file_manager.apply(policy(524288), journal)
            assert len(first['changed']) == 3, first
            assert not file_manager.apply(policy(524288), journal)['changed']
            assert file_manager.apply(policy(4194304), journal)['changed']
            profiles.set_property('thunar', '/misc-thumbnail-mode', 'string', 'THUNAR_THUMBNAIL_MODE_ALWAYS', profiles.run)
            assert 'thumbnails' in file_manager.apply(policy(524288), journal)['preserved']
            assert 'thumbnails' in file_manager.restore(journal)
            assert profiles.read_property('thunar', '/misc-thumbnail-mode', 'string', profiles.run) == 'THUNAR_THUMBNAIL_MODE_ALWAYS'
        report['real_xfconf_uint64_budget_idempotence_and_personal_restore'] = True
        version = subprocess.check_output(['/usr/bin/picom', '--version'], text=True, timeout=8).strip()
        match = re.search(r'v?(\d+)\.(\d+)', version)
        assert match, version
        major = int(match[1]); folder = effects.CONFIG.parent / 'compositor'
        recipes = [effects.CONFIG, folder / 'still.conf']
        recipes += [folder / (name + '.conf') for name in (('blur9', 'blur9-still') if major == 9 else ('blur', 'blur-still'))]
        if major >= 12:
            recipes += [folder / (name + '.conf') for name in ('motion', 'full', 'snap', 'full-snap')]
        for recipe in recipes:
            # Parse the installed version's actual production recipes. The CLI
            # backend override only avoids pretending that Xvfb is a real GPU;
            # this diagnostics exit is NOT GLX rendering / animation proof.
            parsed = subprocess.run(['/usr/bin/picom', '--config', str(recipe), '--diagnostics', '--backend', 'xrender'],
                                    capture_output=True, text=True, timeout=12, check=False)
            text = parsed.stdout + parsed.stderr
            (directory / ('parse-' + recipe.stem + '.log')).write_text(text)
            assert parsed.returncode == 0, (recipe, text[-2500:])
            for failure in ('failed to parse', 'failed to compile', 'will have no effect'):
                assert failure not in text.lower(), (recipe, text[-2500:])
        report['picom_recipe_parser'] = {'version': version, 'recipes': [path.name for path in recipes],
                                         'diagnostics_backend_override': 'xrender', 'glx_rendering_verified': False}
        pump(.15)
        profiles.set_property('xsettings', '/Gtk/EnableAnimations', 'bool', 'false', profiles.run)
        profiles.set_property('thunar', '/last-view', 'string', 'ThunarIconView', profiles.run)
        for name in ('Belgeler', 'Görseller'): (Path.home() / name).mkdir()
        for number in range(8): (Path.home() / f'Örnek {number}.txt').write_text('CI fixture only.\n')
        start('thunar', ['/usr/bin/thunar', str(Path.home())])
        until(lambda: thunar_window() is not None, 'Real Thunar did not open')
        thunar = thunar_window()
        thunar.configure(x=50 * scale, y=70 * scale, width=850 * scale, height=560 * scale)
        connection.sync(); pump(.2)
        generated = [desktop_material.install('#3187ac', dark, identifier=identifier, glass=False,
                                              base_theme=profiles.theme(identifier, 'dark' if dark else 'light'))
                     for identifier in ('windows11', 'mac') for dark in (False, True)]
        report['themes'] = list(THEMES) + generated
        for engine in ('none', 'xrender'):
            compositor = None
            if engine == 'xrender':
                compositor = start('picom', ['/usr/bin/picom', '--config', str(effects.CONFIG)])
                until(lambda: Gdk.Screen.get_default().is_composited(), 'Production Xrender Picom did not own composition')
                assert compositor.poll() is None
            sample = Gtk.Window(title='CI · real native CSD geometry')
            windows.append(sample); sample.set_default_size(350, 220); sample.move(600, 90)
            sample.set_titlebar(Gtk.HeaderBar(title='Native CSD', show_close_button=True))
            sample.add(Gtk.Label(label='No GPU / physical Pi performance claim.'))
            ui_theme.setup(sample); sample.show_all(); pump(.2)
            other = connection.create_resource_object('window', GdkX11.X11Window.get_xid(sample.get_window()))
            assert sample.get_scale_factor() == scale, (sample.get_scale_factor(), scale)
            for theme in report['themes']:
                profiles.set_property('xsettings', '/Net/ThemeName', 'string', theme, profiles.run)
                profiles.set_property('xfwm4', '/general/theme', 'string', theme, profiles.run)
                until(lambda: Gtk.Settings.get_default().get_property('gtk-theme-name') == theme, 'GTK theme did not change')
                pump(.08)
                activate(thunar); frame_contract(thunar, theme, engine, 'active')
                activate(other); until(sample.is_active, 'CSD did not take focus')
                frame_contract(thunar, theme, engine, 'inactive')
            for style in ('solid-csd', 'maximized', 'fullscreen', 'tiled', 'tiled-left', 'tiled-right', 'tiled-top', 'tiled-bottom'):
                context = sample.get_style_context()
                was_present = context.has_class(style)
                context.add_class(style); pump(.02)
                decoration_style(sample, True)
                if not was_present: context.remove_class(style)
            report['csd'].append({'engine': engine, 'native_application_priority_square_state_styles': True})
            decoration_style(sample, engine == 'none')
            sample.maximize(); until(lambda: sample.get_window().get_state() & Gdk.WindowState.MAXIMIZED, 'Real CSD did not maximize')
            until(lambda: sample.get_style_context().has_class('maximized'), 'GTK maximized class absent')
            decoration_style(sample, True)
            screenshot(engine + '-native-maximized')
            sample.unmaximize(); until(lambda: not sample.get_window().get_state() & Gdk.WindowState.MAXIMIZED, 'CSD did not unmaximize')
            sample.fullscreen(); until(lambda: sample.get_window().get_state() & Gdk.WindowState.FULLSCREEN, 'Real CSD did not enter fullscreen')
            decoration_style(sample, True)
            sample.unfullscreen(); until(lambda: not sample.get_window().get_state() & Gdk.WindowState.FULLSCREEN, 'CSD did not leave fullscreen')
            sample.hide()
            for mode, theme in (('light', 'OguzDowsEleven'), ('dark', 'OguzDowsElevenDark')):
                profiles.set_property('xsettings', '/Net/ThemeName', 'string', theme, profiles.run)
                profiles.set_property('xfwm4', '/general/theme', 'string', theme, profiles.run)
                pump(.15); activate(thunar)
                for key, view in (('2', 'ThunarDetailsView'), ('3', 'ThunarCompactView'), ('1', 'ThunarIconView')):
                    keys(key, control=True)
                    until(lambda: profiles.read_property('thunar', '/last-view', 'string', profiles.run) == view, 'Real Thunar view shortcut failed: ' + view)
                    frame_contract(thunar, theme, engine, view)
                    screenshot(engine + '-thunar-' + mode + '-' + view)
                    report['view_modes'].append({'engine': engine, 'appearance': mode, 'view': view})
                keys('Menu')
                def menu_visible():
                    types = {connection.intern_atom('_NET_WM_WINDOW_TYPE_' + kind) for kind in ('MENU', 'POPUP_MENU', 'DROPDOWN_MENU')}
                    for item in root.query_tree().children:
                        try:
                            if item.get_attributes().map_state == X.IsViewable and types.intersection(prop(item, '_NET_WM_WINDOW_TYPE')):
                                return True
                        except error.BadWindow:
                            pass
                    return False
                until(menu_visible, 'Real Thunar context menu did not open')
                screenshot(engine + '-thunar-' + mode + '-menu'); keys('Escape')
                until(lambda: not menu_visible(), 'Thunar context menu did not close')
            sample.destroy(); windows.remove(sample)
            if compositor is not None:
                os.killpg(compositor.pid, signal.SIGTERM); compositor.wait(timeout=8)
                until(lambda: not Gdk.Screen.get_default().is_composited(), 'Private Picom did not release composition')
        report['passed'] = True
    finally:
        for window in windows: window.destroy()
        for process in reversed(processes):
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                # Only process groups created by this disposable test. Never a
                # name-wide pkill / user compositor / unverified production PID.
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=8)
                report.setdefault('cleanup_errors', []).append('CI child did not stop on SIGTERM: ' + str(process.args))
        connection.close()
        (directory / 'window-geometry.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        assert not report.get('cleanup_errors'), report.get('cleanup_errors')
    print('::notice title=Real Thunar and window geometry::' + json.dumps({
        key: report[key] for key in ('passed', 'scope', 'gtk_scale', 'themes', 'csd',
                                     'physical_gpu', 'physical_pi_boot', 'performance_measurement', 'picom_recipe_parser',
                                     'real_xfconf_uint64_budget_idempotence_and_personal_restore')
    } | {'complete_frame_masks_checked': len(report['frames']), 'real_view_cases': len(report['view_modes'])}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--scale', type=int, choices=(1, 2), default=1)
    parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true': parser.error('Only disposable CI Xvfb.')
    if args.child: child(args.child, args.scale); return
    if args.output is None or not os.environ.get('XAUTHORITY'): parser.error('--output and private Xauthority required')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-geometry-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'
        shutil.copytree(ROOT / 'system/etc/skel', home)
        (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key not in ('GTK_THEME', 'DBUS_SESSION_BUS_ADDRESS')}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_STATE_HOME=str(home / '.local/state'),
                   XDG_CACHE_HOME=str(home / '.cache'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE',
                   XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='dconf', NO_AT_BRIDGE='1', GIO_USE_VFS='local',
                   GDK_SCALE=str(args.scale), GDK_DPI_SCALE='1', LC_ALL='C.UTF-8')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                   '--child', str(directory), '--scale', str(args.scale)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try: subprocess.run(command, env=env, check=True, timeout=180)
        finally:
            for path in directory.iterdir():
                if path.is_file() and path.suffix in ('.png', '.json', '.log'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
