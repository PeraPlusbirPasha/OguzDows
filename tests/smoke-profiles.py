#!/usr/bin/env python3
"""Altı düzeni gerçek Xfce panelleriyle özel CI Xvfb / D-Bus'ta açar.

Kurulum, uygulama kısayolu çalıştırma veya fiziksel cihaz kanıtı değildir.
Mevcut masaüstünde çalıştırılmaz; açık Xfce veri yolu varsa baştan reddedilir.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import shutil
import shlex
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from support import ROOT, load


SKELETON = ROOT / 'system/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'


def plugin_manifest(directory=Path('/usr/share/xfce4/panel/plugins'), skeleton=SKELETON):
    """4.18'in eksik eklentiyi silerek testi yanlış geçirmesine izin verme."""
    plugins = {node.attrib['value'] for node in ET.parse(skeleton).getroot().findall('./property[@name="plugins"]/property')
               if node.get('type') == 'string'} | {'launcher', 'separator', 'tasklist'}
    missing = sorted(name for name in plugins if not (directory / (name + '.desktop')).is_file())
    if missing:
        raise RuntimeError('Test ortamında gerekli Xfce eklentileri eksik: ' + ', '.join(missing)
                           + '. Üretim paket listesindeki eklenti paketlerini de kurun; eksik eklenti silinmez / onaylanmaz.')
    return {name: hashlib.sha256((directory / (name + '.desktop')).read_bytes()).hexdigest() for name in sorted(plugins)}



def launcher_import_snapshot(profiles, home, execute):
    """Native import's delayed xfconf write, not merely its file / first frame.

    Xfce launcher imports /usr/share entries and then schedules a one-second
    low-priority items notify. A visible dock / copied file is NOT completion.
    The canonical basename + matching X-XFCE-Source read back from xfconfd is.
    Never repair/write the property in the test or skip the restore assertion.
    """
    snapshot = {}
    for plugin, desktop in profiles.LAUNCHERS.items():
        refs = profiles.read_property('xfce4-panel', f'/plugins/plugin-{plugin}/items', 'string-array', execute)
        if not refs or len(refs) != 1:
            return None
        name = refs[0]
        if Path(name).name != name or not name.endswith('.desktop'):
            return None  # Still the external /usr/share source, import pending.
        path = home / 'config/xfce4/panel' / f'launcher-{plugin}' / name
        if path.is_symlink() or not path.is_file():
            return None
        source = 'X-XFCE-Source=file:///usr/share/applications/' + desktop
        if source not in path.read_text().splitlines():
            return None
        snapshot[str(plugin)] = refs
    return snapshot


def stop_owned_process(process):
    """Yalnızca start_new_session ile bu testin açtığı grubu temizle.

    --restart ile ilk ebeveyn çıkmış olsa bile yeniden açılan panel / eklentiler
    aynı gruptadır. Genel pkill / killall veya başka oturumun PID'i kullanılmaz.
    """
    if process is None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            continue
        # Ebeveyn çıktıysa dahi varsa yalnızca kendi grubumuzdaki torunları temizle.



def icon_pixel_bounds(image):
    """Panel çerçevesi değil, gerçek orta şeritte çizilen glyph/düğme sınırı.

    Opak / tek renk CI iskelesi içindir; duvar kâğıdı veya fiziksel GPU ölçmez.
    Panelin eşit kenar payı, yalnız pencere merkezini sınayan eski boşluğu kapatır.
    """
    from statistics import median
    image = image.convert('RGB')
    width, height = image.size
    if min(width, height) < 22:
        raise ValueError('İkon şeridi çok küçük.')
    background = tuple(int(median(image.getpixel((2, y))[c] for y in (8, height // 2, height - 9))) for c in range(3))
    columns = [x for x in range(2, width - 2) if any(max(abs(a-b) for a, b in zip(image.getpixel((x, y)), background)) > 24
                                                         for y in range(8, height - 8))]
    if not columns:
        raise ValueError('Gerçek iskelede görünür simge bulunamadı.')
    return columns[0], columns[-1] + 1


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
        settings_process = panel_process = wm_process = conf_process = sample = None
        extra_windows = []

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
            expected = 2 if identifier in profiles.DOCK_PROFILES else 1
            if len(windows) != expected:
                return False
            horizontal = [item for item in windows if item['width'] > item['height']]
            if identifier in ('mac', 'windows11'):
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
            if identifier in profiles.DOCK_PROFILES:
                deadline = time.monotonic() + 10
                imported = None
                while time.monotonic() < deadline:
                    pump()
                    imported = launcher_import_snapshot(profiles, home, profiles.run)
                    if imported is not None:
                        break
                    time.sleep(.05)
                assert imported is not None, 'Native launcher import / delayed xfconf save never completed'
            assert sample.get_visible() and sample.get_window() is not None, 'Panel yenileme açık uygulamayı kapatmamalı'
            windows = docks()
            assert geometry_matches(identifier, windows), windows
            assert profiles.read_property('xfce4-panel', '/panels', 'int-array', profiles.run) == (['1', '90'] if identifier in profiles.DOCK_PROFILES else ['1'])
            plugin_names = {node.attrib['name'].removeprefix('plugin-'): node.attrib['value'] for node in
                            ET.parse(SKELETON).getroot().findall('./property[@name="plugins"]/property')}
            if identifier in profiles.DOCK_PROFILES:
                plugin_names.update({str(key): 'launcher' for key in profiles.LAUNCHERS})
                plugin_names['94'] = 'separator'
            for plugin, expected in plugin_names.items():
                actual = profiles.read_property('xfce4-panel', '/plugins/plugin-' + plugin, 'string', profiles.run)
                assert actual == expected, ('Eklenti kayboldu / yüklenmedi', plugin, actual, expected)
            for channel, path, kind, expected in profiles.settings(identifier):
                if channel == 'xfce4-panel' and path.endswith('/plugin-ids') and expected is not None:
                    actual = profiles.read_property(channel, path, kind, profiles.run)
                    assert actual == expected, ('Panel eklenti dizisi değişti', path, actual, expected)
            pixels = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, screen_width, screen_height)
            assert pixels is not None
            path = output / ('panels-' + identifier + suffix + '.png')
            pixels.savev(str(path), 'png', [], [])
            content = None
            if identifier in ('mac', 'windows11'):
                from PIL import Image
                dock = next(item for item in windows if item['y'] > screen_height / 2)
                with Image.open(path) as screenshot:
                    strip = screenshot.crop((dock['x'], dock['y'], dock['x'] + dock['width'], dock['y'] + dock['height']))
                    left, right = icon_pixel_bounds(strip)
                center = dock['x'] + (left + right) / 2
                content = {'left': dock['x'] + left, 'right': dock['x'] + right,
                           'center_error_px': abs(center - screen_width / 2), 'screen_center': screen_width / 2}
                assert content['center_error_px'] <= 12, ('Gerçek simge grubu merkezde değil', content)
                assert dock['width'] < screen_width * .9, ('İskele gereksiz boş alanla dolduruldu', dock)
            report['layouts'].append({'profile': identifier, 'variant': suffix or 'light', 'windows': windows,
                                      'icon_content': content, 'launcher_import_readback_verified': identifier in profiles.DOCK_PROFILES, 'xfconf_arrays': True, 'all_plugins_preserved': True, 'sample_application_stayed_open': True})

        try:
            if connection.get_selection_owner(connection.intern_atom('WM_S0')):
                raise RuntimeError('Mevcut pencere yöneticisi var; özel, boş Xvfb ekranı gerekli.')
            report['plugin_descriptors_sha256'] = plugin_manifest()
            report['xfce_panel_version'] = subprocess.check_output(['xfce4-panel', '--version'], text=True, timeout=8).strip()
            # This daemon belongs only to the just-created private session.
            # Join its final XML flush before TemporaryDirectory cleanup too.
            service = configparser.ConfigParser(interpolation=None)
            service.read('/usr/share/dbus-1/services/org.xfce.Xfconf.service')
            command = shlex.split(service['D-BUS Service']['Exec'])
            assert len(command) == 1 and Path(command[0]).name == 'xfconfd'
            conf_process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 5
            ready = False
            while time.monotonic() < deadline:
                assert conf_process.poll() is None, 'Private foreground xfconfd exited'
                ready = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                    'org.freedesktop.DBus', 'NameHasOwner', GLib.Variant('(s)', ('org.xfce.Xfconf',)),
                    GLib.VariantType.new('(b)'), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]
                if ready:
                    break
                time.sleep(.02)
            assert ready, 'Private foreground xfconfd never became ready'
            wm_process = subprocess.Popen(['xfwm4', '--compositor=off'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            settings_process = subprocess.Popen(['xfsettingsd', '--no-daemon'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            profiles.apply('mac', appearance='light')
            original_native = profiles.validate_backup(json.loads((profiles.state_directory() / 'before-first-change.json').read_text()))
            sample = Gtk.Window(title='OğuzDows · gerçek panel denetimi')
            sample.set_wmclass('oguzdows-layout-primary', 'OguzDowsLayoutPrimary')
            sample.set_icon_name('oguzdows-news')
            sample.set_default_size(440, 240)
            sample.move((screen_width - 440) // 2, (screen_height - 240) // 2)
            sample.set_titlebar(Gtk.HeaderBar(title='OğuzDows', subtitle='Gerçek Xfce paneli · paket kurulmaz', show_close_button=True))
            words = Gtk.Label(label='Üst çubuk, iskele ve ayrı açık/koyu tema.\nBu pencere panel yenilenirken açık kalır.')
            words.set_margin_top(30)
            words.set_margin_bottom(30)
            sample.add(words)
            sample.show_all()
            panel_process = subprocess.Popen(['xfce4-panel', '--disable-wm-check'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            capture('mac')
            for plugin in profiles.LAUNCHERS:
                assert profiles.read_property('xfce4-panel', f'/plugins/plugin-{plugin}', 'string', profiles.run) == 'launcher'
                imported = list((home / 'config/xfce4/panel' / f'launcher-{plugin}').glob('*.desktop'))
                assert imported, 'Paket kısayolu gerçek launcher tarafından içe aktarılmalı'
            profiles.set_appearance('dark')
            capture('mac', '-dark')
            profiles.set_appearance('light')
            for identifier in ('gnome', 'oguzdows', 'kde', 'xfce', 'windows11'):
                profiles.apply(identifier)
                profiles.reload_panels()  # Yalnızca bu testin özel veri yolu.
                capture(identifier)
            # İki ek sınıf ile görev grubu büyürken merkez gerçekten kalmalı.
            before = next(item['width'] for item in docks() if item['y'] > screen_height / 2)
            for index in range(2):
                extra = Gtk.Window(title='Merkez denetimi ' + str(index))
                extra.set_wmclass('oguzdows-layout-extra-' + str(index), 'OguzDowsLayoutExtra' + str(index))
                extra.set_icon_name('oguzdows-imece' if index else 'oguzdows-store')
                extra.set_default_size(240, 150)
                extra.add(Gtk.Label(label='Yalnızca panel merkez denetimi'))
                extra.show_all()
                extra_windows.append(extra)
            # Wnck pencere olayını alsın; süre yalnızca bu özel testte.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                pump()
                if any(item['y'] > screen_height / 2 and item['width'] > before + 20 for item in docks()):
                    break
                time.sleep(.05)
            assert any(item['y'] > screen_height / 2 and item['width'] > before + 20 for item in docks()), 'Gerçek görev grubu yeni pencerelerle büyümeli'
            capture('windows11', '-three-windows')
            profiles.restore()
            for channel, path, kind, previous in original_native:
                actual = profiles.read_property(channel, path, kind, profiles.run)
                assert actual == previous, ('İlk tipli ayar geri alınmadı', channel, path, {'expected': previous, 'actual': actual})
            report['restore_native_readback_verified'] = True
            profiles.reload_panels()
            capture('oguzdows', '-restored')
            report['restored_panel_geometry_verified'] = True
            report['restored'] = True
            summary = {key: value for key, value in report.items() if key != 'plugin_descriptors_sha256'}
            print('::notice title=Gerçek Xfce panel düzenleri::' + json.dumps(summary, ensure_ascii=False), flush=True)
        except Exception as error:
            report['error'] = str(error)
            log.flush()
            report['panel_log_tail'] = (output / 'profile-panels.log').read_text(errors='replace')[-6000:]
            diagnostic = json.dumps({'error': str(error), 'panel_log_tail': report['panel_log_tail'][-1800:]}, ensure_ascii=False)
            print('::error title=Gerçek Xfce panel düzenleri::' + diagnostic.replace('%', '%25'), flush=True)
            try:
                pixels = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, screen_width, screen_height)
                if pixels is not None:
                    pixels.savev(str(output / 'panels-failure.png'), 'png', [], [])
            except Exception as screenshot_error:
                report['failure_screenshot_error'] = str(screenshot_error)
            raise
        finally:
            (output / 'profile-layouts.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            for extra in extra_windows:
                extra.destroy()
            if sample is not None:
                sample.destroy()
            if panel_process is not None:
                try:
                    subprocess.run(['xfce4-panel', '--quit'], stdout=log, stderr=subprocess.STDOUT, timeout=4, check=False)
                except (OSError, subprocess.SubprocessError) as error:
                    print('Özel panel D-Bus temizliği: ' + str(error), file=log, flush=True)
            # Bir modal eklenti uyarısı --quit'e yanıt vermese de asıl hatayı
            # TimeoutExpired ile maskeleme; yalnızca kendi süreç gruplarımız.
            for process in (panel_process, settings_process, wm_process, conf_process):
                stop_owned_process(process)
            connection.close()


if __name__ == '__main__':
    main()
