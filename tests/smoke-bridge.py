#!/usr/bin/env python3
"""Real GTK, private files, loopback TLS, Xvfb pixels. No production desktop or physical ARM.

Only this disposable child preanswers the desktop-capture warning/unlocked-session gate;
the separate unit tests exercise production's fail-closed loginctl gate.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from support import ROOT


def pump(condition, timeout=15):
    from gi.repository import GLib
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        while GLib.MainContext.default().iteration(False):
            pass
        if condition():return
        time.sleep(.01)
    raise AssertionError('GTK bridge action did not finish within its bound')


def child(directory):
    if (os.getuid()==0 or directory.parent!=Path(tempfile.gettempdir()) or not directory.name.startswith('oguzdows-bridge-ci-')
            or Path.home()!=directory/'home' or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        raise RuntimeError('Only a disposable nonroot CI home / private Xvfb display')
    sys.path.insert(0,str(ROOT/'system/usr/lib/oguzdows'))
    import gi
    gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0')
    from gi.repository import Gdk, Gtk
    import bridge
    import bridge_core as core
    from bridge_capture import jpeg_dimensions
    import ui_theme
    ui_theme.CSS=ROOT/'system/usr/share/oguzdows/ui/modern.css'
    errors=[]
    original_hook=sys.excepthook
    def hook(kind,value,trace):
        errors.append(str(value));original_hook(kind,value,trace)
    sys.excepthook=hook
    app=bridge.application()
    assert app.register(None)
    app.activate();pump(lambda:app.window is not None and app.window.get_realized())
    assert app.server is None and app.client is None, 'Opening the window must not start a listener or discover devices'
    screen=app.window.get_screen();width,height=app.window.get_size()
    assert width<=screen.get_width() and height<=screen.get_height(), (width,height)
    def descendants(widget):
        yield widget
        if isinstance(widget,Gtk.Container):
            for item in widget.get_children():yield from descendants(item)
    def click(label):
        next(w for w in descendants(app.window) if isinstance(w,Gtk.Button) and w.get_label()==label).clicked()
        pump(lambda:not app.busy)
        assert not errors,errors
    click('Bu cihazda 15 dakikalık masa aç')
    assert app.server is not None and app.server.port>1024
    client=core.Client(core.invitation('127.0.0.1',app.server.port,app.server.pin,app.session.secret))
    reply=client.pair('Private GTK fixture')
    assert app.session.pairs[reply['id']]['code']==reply['code']
    assert client.poll_pair()['status']=='pending'
    app.tick();click('Kod aynı · izin ver')
    assert client.poll_pair()['status']=='approved'
    assert not client.state()['mirror']
    selected=directory/'selected.txt';selected.write_bytes(b'real GTK selected file\n')
    app.stage([selected]);pump(lambda:not app.busy);app.tick()
    state=client.state();assert len(state['files'])==1
    downloaded=directory/'downloaded.txt';client.receive(state['files'][0],downloaded)
    assert downloaded.read_bytes()==selected.read_bytes()
    raw=b'real GTK accepted upload\n';upload=directory/'upload.txt';upload.write_bytes(raw)
    request=client.request('POST','/v1/inbox',dict(name=upload.name,bytes=len(raw),sha256=core.digest(raw)))
    app.tick();click('Dosyayı kabul et')
    assert client.request('PUT','/v1/inbox/'+request['id'],source=upload)['status']=='ready'
    assert (app.session.root/request['id']).read_bytes()==raw
    key=next(iter(app.session.peers))
    # Real CI Xvfb has no active logind desktop session. The production gate must deny it.
    app.start_capture(key)
    assert app.capture_peer is None and not client.state()['mirror']
    # Only this process grants the private test display; actual GDK capture and TLS remain real.
    with patch.object(bridge,'unlocked_x11',return_value=True), patch.object(Gtk.MessageDialog,'run',return_value=Gtk.ResponseType.OK):
        app.start_capture(key);assert app.capture_peer==key
        app.capture_tick();pump(lambda:not app.capture_busy and bool(app.session.frame))
        frame=client.request('GET','/v1/frame',limit=core.MAX_FRAME)
        fw,fh=jpeg_dimensions(frame)
        assert frame==app.session.frame and max(fw,fh)<=1280
    app.stop_capture();assert not client.state()['mirror'] and app.session.frame==b''
    root=app.session.root;identity=app.server.identity
    app.tick()
    for _ in range(10):
        while Gtk.events_pending():Gtk.main_iteration_do(False)
    native=app.window.get_window()
    pixbuf=Gdk.pixbuf_get_from_window(native,0,0,native.get_width(),native.get_height())
    assert pixbuf is not None;pixbuf.savev(str(directory/'bridge-gtk.png'),'png',[],[])
    report={'scope':'private nonroot GTK + loopback TLS + Xvfb pixels', 'real_gtk_buttons':True,
            'no_network_on_open':True,'peer_code_approval':True,'selected_file_sha256':True,'recipient_approved_upload':True,
            'production_unknown_lock_denied':True,'capture_gate_fixture_only':True,'real_gdk_capture_and_tls_frame':True,
            'frame_size':[fw,fh],'frame_sha256':core.digest(frame),'screen':[screen.get_width(),screen.get_height()],
            'window':[width,height],'physical_pc_phone_arm_or_wifi_tested':False}
    app.stop();pump(lambda:not root.exists() and not identity.exists())
    assert downloaded.read_bytes()==selected.read_bytes(),'Only session copies should be deleted'
    app.window.destroy()
    assert not errors,errors
    (directory/'bridge-gtk.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('::notice title=OğuzKöprü real GTK::'+json.dumps(report,ensure_ascii=False).replace('%','%25'),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--child',type=Path)
    args=parser.parse_args()
    if os.environ.get('CI')!='true':parser.error('Disposable CI / private Xvfb only')
    if args.child:
        child(args.child);return
    if not args.output or not os.environ.get('XAUTHORITY'):parser.error('--output and private xvfb-run Xauthority required')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-bridge-ci-') as tmp:
        directory=Path(tmp);home=directory/'home';home.mkdir(mode=0o700)
        (directory/'runtime').mkdir(mode=0o700)
        authority=directory/'Xauthority';shutil.copy2(os.environ['XAUTHORITY'],authority);authority.chmod(0o600)
        env={k:v for k,v in os.environ.items() if k!='DBUS_SESSION_BUS_ADDRESS'}
        env.update(HOME=str(home),XDG_CONFIG_HOME=str(home/'.config'),XDG_CACHE_HOME=str(home/'.cache'),
                   XDG_STATE_HOME=str(home/'.local/state'),XDG_DATA_HOME=str(home/'.local/share'),XDG_RUNTIME_DIR=str(directory/'runtime'),
                   XAUTHORITY=str(authority),XDG_CURRENT_DESKTOP='XFCE',XDG_SESSION_TYPE='x11',GSETTINGS_BACKEND='memory',NO_AT_BRIDGE='1')
        command=['/usr/bin/dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--child',str(directory)]
        if os.getuid()==0:
            for path in [directory,*directory.rglob('*')]:os.chown(path,65534,65534,follow_symlinks=False)
            command=['/usr/bin/setpriv','--reuid=65534','--regid=65534','--clear-groups',*command]
        try:subprocess.run(command,env=env,check=True,timeout=90)
        finally:
            for path in directory.iterdir():
                if path.suffix in ('.png','.json'):shutil.copy2(path,output/path.name)


if __name__=='__main__':
    main()
