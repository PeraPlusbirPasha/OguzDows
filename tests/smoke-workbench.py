#!/usr/bin/env python3
"""Real GTK actions + private real files; never a user's home, packages or network.

Parent creates a disposable unprivileged home/Xauthority, child drives actual
widgets and production workers. Preanswered confirmations affect only this
child's explicitly selected temporary files, not the installed application.
"""
import argparse
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from support import ROOT


def pump(predicate, seconds=12):
    from gi.repository import GLib
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while GLib.MainContext.default().iteration(False):
            pass
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Atölye GTK isteği süre sınırında tamamlanmadı.')


def child(directory, appearance):
    if (os.getuid() == 0 or directory.parent != Path(tempfile.gettempdir()) or not directory.name.startswith('oguzdows-workbench-ci-')
            or Path.home() != directory / 'home' or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        raise ValueError('Yalnız özel Xvfb / normal kullanıcılı tek kullanımlık CI evi.')
    sys.path.insert(0, str(ROOT / 'system/usr/lib/oguzdows'))
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, GLib, Gtk
    assert Gtk.init_check([])[0]
    import workbench
    import workbench_core as core
    import desktop_state
    import ui_theme
    from PIL import Image
    ui_theme.CSS = ROOT / 'system/usr/share/oguzdows/ui/modern.css'
    desktop_state.atomic_json(desktop_state.config_path(), {**desktop_state.DEFAULTS, 'appearance': appearance})
    settings = Gtk.Settings.get_default()
    settings.set_property('gtk-application-prefer-dark-theme', appearance == 'dark')
    errors = []
    def exception(*value):
        errors.append(value); sys.__excepthook__(*value)
    sys.excepthook = exception
    app = workbench.application()
    assert app.register(None)
    app.activate()
    pump(lambda: app.window is not None and app.window.get_realized())
    # Consent is preanswered ONLY in this private-file test process.
    app.confirm = lambda *_: True
    selected = directory / 'selected'; selected.mkdir()
    (selected / 'a.txt').write_text('Türkçe test dosyası\n')
    (selected / 'b.txt').write_text('başka test\n')
    with Image.new('RGB', (200, 100), '#257b88') as image:
        image.save(directory / 'input.png')
    output = directory / 'output'; output.mkdir()
    main_thread = threading.get_ident()
    worker_threads = []
    original_update = app.lib.update
    def update(*arguments, **keywords):
        worker_threads.append(threading.get_ident())
        return original_update(*arguments, **keywords)
    app.lib.update = update

    def descendants(widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for item in widget.get_children(): yield from descendants(item)

    def widgets():
        return list(descendants(app.stack))

    def entry(name):
        return next(item for item in widgets() if isinstance(item, Gtk.Entry) and item.get_accessible().get_name() == name)

    def buffer(name):
        return next(item.get_buffer() for item in widgets() if isinstance(item, Gtk.TextView) and item.get_accessible().get_name() == name)

    def combo(name):
        return next(item for item in widgets() if isinstance(item, Gtk.ComboBox) and item.get_accessible().get_name() == name)

    def click(name):
        next(item for item in widgets() if isinstance(item, Gtk.Button) and item.get_label() == name).clicked()
        pump(lambda: not app.busy)
        assert not errors, errors

    def navigate(name):
        app.navigate(name)
        pump(lambda: not app.busy)
        pump(lambda: app.stack.get_allocated_width() > 0)
        assert app.current_tool == name, app.status.get_text()
        assert not errors, errors
        screen = app.window.get_screen()
        width, height = app.window.get_size()
        assert width <= screen.get_width() and height <= screen.get_height(), (name, width, height)

    def contains(text):
        return any(isinstance(item, Gtk.Label) and text in item.get_text() for item in widgets())

    def capture(name):
        # Complete pending allocations, without screenshots of mock HTML.
        loop = GLib.MainLoop(); GLib.timeout_add(100, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1]); loop.run()
        surface = app.window.get_window()
        image = Gdk.pixbuf_get_from_window(surface, 0, 0, surface.get_width(), surface.get_height())
        assert image is not None
        image.savev(str(directory / name), 'png', [], [])

    visited = []
    for name, _, _, _ in core.TOOLS:
        navigate(name); visited.append(name)
    navigate('home'); capture('workbench-home.png')
    navigate('tasks')
    entry('Başlık').set_text('ARM dahil yeni görev')
    entry('Son tarih · isteğe bağlı').set_text('2026-11-20')
    combo('Öncelik').set_active(1)
    click('Kaydet · Ctrl+S')
    tasks = app.lib.read()['tasks']
    assert tasks[0]['priority'] == 'high' and tasks[0]['due'] == '2026-11-20'
    next(item for item in widgets() if isinstance(item, Gtk.CheckButton) and item.get_label() == 'Tamamlandı').set_active(True)
    click('Kaydet · Ctrl+S')
    assert app.lib.read()['tasks'][0]['done']
    capture('workbench-tasks.png')
    navigate('notes')
    entry('Başlık').set_text('Yerel defter')
    buffer('Metin / ayrıntı').set_text('Notlar bu cihazda kalır.\nTürkçe: ı İ ğ ş ç ö ü')
    click('Kaydet · Ctrl+S')
    assert 'Türkçe' in app.lib.read()['notes'][0]['body']
    navigate('snippets')
    entry('Başlık').set_text('Elle eklenen metin')
    buffer('Metin / ayrıntı').set_text('Açık istekle kopyala')
    click('Kaydet · Ctrl+S'); click('Metni kopyala')
    assert Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() == 'Açık istekle kopyala'
    navigate('folders')
    entry('Başlık').set_text('Seçilen klasör')
    buffer('Klasör yolu').set_text(str(selected)); click('Kaydet · Ctrl+S')
    assert app.lib.read()['folders'][0]['body'] == str(selected)
    navigate('find')
    entry('Aranacak klasör').set_text(str(selected))
    entry('Dosya adında geçen').set_text('a.txt'); click('Bu klasörde ara')
    assert contains('a.txt')
    navigate('checksum')
    entry('Doğrulanacak dosya').set_text(str(selected / 'a.txt'))
    digest = hashlib.sha256((selected / 'a.txt').read_bytes()).hexdigest()
    entry('Beklenen özet · boşsa yalnız hesapla').set_text(digest)
    click('Özeti hesapla / doğrula')
    assert 'EŞLEŞTİ' in app.value(buffer('Sonuç'))
    capture('workbench-checksum.png')
    navigate('rename')
    entry('Yalnızca bu klasörün görünür dosyaları').set_text(str(selected))
    entry('Önek · {n} sıralı numaradır').set_text('Test-{n}-')
    click('1 · Önizle')
    assert (selected / 'a.txt').exists()
    click('2 · Onayla ve uygula…')
    assert (selected / 'Test-001-a.txt').exists()
    click('Son işlemi geri al…')
    assert (selected / 'a.txt').exists() and not (selected / 'Test-001-a.txt').exists()
    navigate('image')
    entry('Kaynak görsel · en fazla 8 megapiksel').set_text(str(directory / 'input.png'))
    entry('Yeni dosyanın klasörü').set_text(str(output))
    click('Yeni görsel oluştur')
    assert (output / 'Hazir-gorsel.jpg').is_file()
    navigate('diff')
    buffer('Önce').set_text('önce\n'); buffer('Sonra').set_text('sonra\n')
    click('Karşılaştır'); assert '+sonra' in app.value(buffer('Satır farkı · − silinen / + eklenen'))
    navigate('json')
    buffer('JSON girdisi').set_text('{"ad":"Oğuz"}')
    click('Doğrula ve düzenle')
    assert json.loads(app.value(buffer('Doğrulanmış sonuç'))) == {'ad': 'Oğuz'}
    navigate('calculator')
    entry('Aritmetik ifade').set_text('0.1 + 0.2')
    click('Hesapla'); assert contains('0.3')
    navigate('units')
    combo('Kategori').set_active(list(core.UNITS).index('Veri'))
    combo('Kaynak birim').set_active(list(core.UNITS['Veri']).index('MiB'))
    combo('Hedef birim').set_active(0)
    click('Dönüştür'); assert contains('1048576')
    navigate('colors')
    entry('Metin rengi').set_text('#000000')
    click('Kontrastı ölç'); assert contains('21.00:1')
    click('Metin rengini palete ekle')
    assert app.lib.read()['palettes'][0]['body'] == '#000000'
    capture('workbench-colors.png')
    navigate('clocks'); assert app.clock_id is not None
    app.window.hide(); pump(lambda: app.clock_id is None)
    app.window.show(); pump(lambda: app.clock_id is not None)
    navigate('text'); assert app.clock_id is None
    buffer('Kaynak metin').set_text('istanbul ığdır')
    click('Uygula'); assert app.value(buffer('Sonuç')) == 'İSTANBUL IĞDIR'
    system = directory / 'system-autostart'; system.mkdir()
    original = '[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/false\n'
    (system / 'fixture.desktop').write_text(original)
    user = Path(os.environ['XDG_CONFIG_HOME']) / 'autostart'
    startup_entries = core.startup_entries
    core.startup_entries = lambda: startup_entries(user, (system,))
    original_toggle = core.toggle_startup
    core.toggle_startup = lambda identifier, enabled: original_toggle(identifier, enabled, system_directories=(system,))
    navigate('startup')
    listing = next(item for item in widgets() if isinstance(item, Gtk.ListBox))
    listing.select_row(listing.get_row_at_index(0))
    click('Etkinleştir / devre dışı bırak…')
    assert 'Hidden=true' in (user / 'fixture.desktop').read_text()
    assert (system / 'fixture.desktop').read_text() == original
    listing.select_row(listing.get_row_at_index(0))
    click('Özgün ayarı geri al…')
    assert not (user / 'fixture.desktop').exists()
    navigate('home')
    app.search.set_text('doğrula'); app.filter_tools()
    app.search_activate(); pump(lambda: not app.busy)
    assert app.current_tool == 'checksum'
    navigate('home'); app.search.set_text(''); app.filter_tools()
    assert worker_threads and all(thread != main_thread for thread in worker_threads)
    before = resource.getrusage(resource.RUSAGE_SELF)
    loop = GLib.MainLoop()
    GLib.timeout_add(800, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1]); loop.run()
    after = resource.getrusage(resource.RUSAGE_SELF)
    idle_ms = (after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime) * 1000
    assert idle_ms < 400, idle_ms  # Detect a busy loop, not a hardware speed claim.
    assert not app.busy and app.clock_id is None
    report = {'scope': 'private-nonroot-real-GTK-real-files', 'tools_built': visited, 'tools_count': len(visited),
              'real_widget_actions': True, 'library_roundtrip': True, 'clipboard_explicit_copy': True,
              'rename_preview_apply_undo': True, 'real_image_export': True, 'startup_user_only_restore': True,
              'single_worker_not_gtk_thread': True, 'clock_stops_on_page_leave': True, 'appearance': appearance,
              'screen': [app.window.get_screen().get_width(), app.window.get_screen().get_height()],
              'window': list(app.window.get_size()), 'idle_sample_ms': 800, 'idle_cpu_ms': round(idle_ms, 2),
              'peak_rss_kib': after.ru_maxrss, 'physical_arm_or_gpu_verified': False,
              'not_a_hardware_performance_benchmark': True}
    app.window.destroy()
    pump(lambda: not any(thread.name.startswith('Atolye') for thread in threading.enumerate()))
    assert not errors, errors
    (directory / 'workbench.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Atölye real GTK::' + json.dumps(report, ensure_ascii=False).replace('%', '%25'), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--appearance', choices=('light', 'dark'), default='light')
    parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true': parser.error('Yalnız tek kullanımlık CI / özel Xvfb ekranı.')
    if args.child:
        child(args.child, args.appearance)
        return
    if not args.output or not os.environ.get('XAUTHORITY'): parser.error('--output ve özel xvfb-run Xauthority gerekli.')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-workbench-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'; home.mkdir(mode=0o700)
        (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key != 'DBUS_SESSION_BUS_ADDRESS'}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
                   XDG_STATE_HOME=str(home / '.local/state'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE',
                   XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()), '--child', str(directory), '--appearance', args.appearance]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try:
            subprocess.run(command, env=env, check=True, timeout=100)
        finally:
            for path in directory.iterdir():
                if path.suffix in ('.png', '.json'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
