#!/usr/bin/env python3
"""Beş düzeni gerçek Xfce panelleriyle özel CI Xvfb / D-Bus'ta açar.

Kurulum, uygulama kısayolu çalıştırma veya fiziksel cihaz kanıtı değildir.
Mevcut masaüstünde çalıştırılmaz; açık Xfce veri yolu varsa baştan reddedilir.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from support import ROOT, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true' or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        parser.error('Yalnızca tek kullanımlık CI içinde özel Xvfb ve yeni dbus-run-session ile çalıştırılır.')
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gio, GLib, Gtk
    from Xlib import X, display, error as xerror

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    names = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                          'org.freedesktop.DBus', 'ListNames', None, None,
                          Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    if any(name.startswith('org.xfce.') for name in names):
        raise RuntimeError('Mevcut Xfce oturumu var; hiçbir ayar / süreç değiştirilmedi.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'host-real-xfce-panels-private-xvfb', 'physical_boot': False,
              'arm_runtime': False, 'performance_test': False, 'package_transaction': False,
              'layouts': []}
    profiles = load('native_panel_profiles', 'system/usr/lib/oguzdows/profiles.py')
    with tempfile.TemporaryDirectory(prefix='oguzdows-private-panels-') as temporary, (output / 'profile-panels.log').open('w') as log:
        home = Path(temporary)
        os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(home / 'config'),
                          XDG_CACHE_HOME=str(home / 'cache'), XDG_STATE_HOME=str(home / 'state'),
                          XDG_DATA_HOME=str(home / 'data'), GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1')
        # D-Bus aktivasyonları sorgu istemcisinin sonradan değişen ortamını
        # kendiliğinden almaz; xfconfd de aynı geçici kökü kullanmalı.
        activation = {name: os.environ[name] for name in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'XDG_DATA_HOME')}
        bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                      'UpdateActivationEnvironment', GLib.Variant('(a{ss})', (activation,)), None,
                      Gio.DBusCallFlags.NONE, 5000, None)
        shutil.copytree(ROOT / 'system/etc/skel/.config', home / 'config')
        if not Gtk.init_check([])[0]:
            raise RuntimeError('Özel Xvfb ekranı açılamadı.')
        connection = display.Display()
        root = connection.screen().root
        screen_width, screen_height = connection.screen().width_in_pixels, connection.screen().height_in_pixels
        dock_atom = connection.intern_atom('_NET_WM_WINDOW_TYPE_DOCK')
        type_atom = connection.intern_atom('_NET_WM_WINDOW_TYPE')
        clients_atom = connection.intern_atom('_NET_CLIENT_LIST')
        settings_process = panel_process = wm_process = sample = None

        def pump():
            for _ in range(50):
                if not Gtk.events_pending():
                    break
                Gtk.main_iteration_do(False)

        def docks():
            result = []
            clients = root.get_full_property(clients_atom, X.AnyPropertyType)
            for identifier in clients.value if clients is not None else ():
                window = connection.create_resource_object('window', int(identifier))
                try:
                    kind = window.get_full_property(type_atom, X.AnyPropertyType)
                    identity = ' '.join(window.get_wm_class() or ()).casefold()
                    if not kind or dock_atom not in kind.value or 'xfce4-panel' not in identity:
                        continue
                    geometry = window.get_geometry()
                    if window.get_attributes().map_state == X.IsViewable and min(geometry.width, geometry.height) > 20:
                        x, y, ancestor = geometry.x, geometry.y, window.query_tree().parent
                        for _ in range(8):
                            if ancestor.id == root.id:
                                break
                            frame = ancestor.get_geometry()
                            x += frame.x + frame.border_width
                            y += frame.y + frame.border_width
                            ancestor = ancestor.query_tree().parent
                        result.append({'x': x, 'y': y, 'width': geometry.width, 'height': geometry.height})
                except xerror.XError:
                    continue  # Yenileme sırasında eski X penceresi silinmiş olabilir.
            return result

        def geometry_matches(identifier, windows):
            expected = 2 if identifier in ('mac', 'gnome') else 1
            if len(windows) != expected:
                return False
            horizontal = [item for item in windows if item['width'] > item['height']]
            if identifier == 'mac':
                return (len(horizontal) == 2 and any(item['y'] <= 3 for item in windows)
                        and any(item['y'] >= screen_height - item['height'] - 3
                                and abs(item['x'] + item['width'] / 2 - screen_width / 2) <= 4 for item in windows))
            if identifier == 'gnome':
                return (len(horizontal) == 1 and horizontal[0]['y'] <= 3
                        and any(item['x'] <= 3 and item['height'] > item['width'] for item in windows))
            return len(horizontal) == 1

        def capture(identifier, suffix=''):
            deadline = time.monotonic() + 30
            windows = []
            while time.monotonic() < deadline:
                pump()
                windows = docks()
                if geometry_matches(identifier, windows):
                    break
                time.sleep(.05)
            if not geometry_matches(identifier, windows):
                raise RuntimeError('Gerçek panel geometrisi eşleşmedi: ' + identifier + ' ' + json.dumps(windows))
            # Aynı sayıda eski pencerenin yerini yenisi alırken tek karelik yarışı önle.
            start = time.monotonic()
            while time.monotonic() - start < .4:
                pump()
                time.sleep(.02)
            assert sample.get_visible() and sample.get_window() is not None, 'Panel yenileme açık uygulamayı kapatmamalı'
            windows = docks()
            assert geometry_matches(identifier, windows), windows
            assert profiles.read_property('xfce4-panel', '/panels', 'int-array', profiles.run) == (['1', '90'] if identifier in ('mac', 'gnome') else ['1'])
            pixels = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, screen_width, screen_height)
            assert pixels is not None
            pixels.savev(str(output / ('panels-' + identifier + suffix + '.png')), 'png', [], [])
            report['layouts'].append({'profile': identifier, 'variant': suffix or 'light', 'windows': windows,
                                      'xfconf_arrays': True, 'sample_application_stayed_open': True})

        try:
            wm_process = subprocess.Popen(['xfwm4', '--compositor=off'], stdout=log, stderr=subprocess.STDOUT)
            settings_process = subprocess.Popen(['xfsettingsd', '--no-daemon'], stdout=log, stderr=subprocess.STDOUT)
            profiles.apply('mac', appearance='light')
            sample = Gtk.Window(title='OğuzDows · gerçek panel denetimi')
            sample.set_default_size(440, 240)
            sample.move((screen_width - 440) // 2, (screen_height - 240) // 2)
            sample.set_titlebar(Gtk.HeaderBar(title='OğuzDows', subtitle='Gerçek Xfce paneli · paket kurulmaz', show_close_button=True))
            words = Gtk.Label(label='Üst çubuk, iskele ve ayrı açık/koyu tema.\nBu pencere panel yenilenirken açık kalır.')
            words.set_margin_top(30)
            words.set_margin_bottom(30)
            sample.add(words)
            sample.show_all()
            panel_process = subprocess.Popen(['xfce4-panel', '--disable-wm-check'], stdout=log, stderr=subprocess.STDOUT)
            capture('mac')
            for plugin in profiles.LAUNCHERS:
                assert profiles.read_property('xfce4-panel', f'/plugins/plugin-{plugin}', 'string', profiles.run) == 'launcher'
                imported = list((home / 'config/xfce4/panel' / f'launcher-{plugin}').glob('*.desktop'))
                assert imported, 'Paket kısayolu gerçek launcher tarafından içe aktarılmalı'
            profiles.set_appearance('dark')
            capture('mac', '-dark')
            profiles.set_appearance('light')
            for identifier in ('gnome', 'oguzdows', 'kde', 'xfce'):
                profiles.apply(identifier)
                profiles.reload_panels()  # Yalnızca bu testin özel veri yolu.
                capture(identifier)
            profiles.restore()
            report['restored'] = True
            print('::notice title=Gerçek Xfce panel düzenleri::' + json.dumps(report, ensure_ascii=False), flush=True)
        except Exception as error:
            report['error'] = str(error)
            print('::error title=Gerçek Xfce panel düzenleri::' + str(error), flush=True)
            raise
        finally:
            (output / 'profile-layouts.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            if sample is not None:
                sample.destroy()
            if panel_process is not None:
                subprocess.run(['xfce4-panel', '--quit'], stdout=log, stderr=subprocess.STDOUT, timeout=12, check=False)
                if panel_process.poll() is None:
                    panel_process.wait(timeout=12)
            if settings_process is not None and settings_process.poll() is None:
                settings_process.terminate()
                settings_process.wait(timeout=12)
            if wm_process is not None and wm_process.poll() is None:
                wm_process.terminate()
                wm_process.wait(timeout=12)
            connection.close()


if __name__ == '__main__':
    main()
