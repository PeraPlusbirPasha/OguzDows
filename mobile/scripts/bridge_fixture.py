"""Disposable-emulator↔runner peer fixture. No discovery, real contacts, SIM or user files.

The temporary invitation files are deleted and never included in uploaded evidence.
"""
import importlib.util
from pathlib import Path
import tempfile
import time

from acceptance import INTEROP_PAYLOADS

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location('oguz_bridge_ci_peer', ROOT/'system/usr/lib/oguzdows/bridge_core.py')
core = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(core)
PACKAGE = 'org.oguzdows.mobile'
FOLDER = f'/sdcard/Android/data/{PACKAGE}/files'
MARKERS = ('bridge-native-invitation.txt', 'bridge-desktop-invitation.txt', 'bridge-pc-verified', 'bridge-interop-complete')


def clean(adb):
    for name in MARKERS:
        adb('shell', 'rm', '-f', FOLDER+'/'+name, check=False)


def exercise(adb, process):
    if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != '1':
        raise RuntimeError('Device-link fixture refuses non-QEMU targets')

    def wait(label, condition, timeout=60):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            if process.poll() is not None:
                raise RuntimeError('Native instrumentation exited before '+label)
            value = condition()
            if value:
                return value
            time.sleep(.15)
        raise RuntimeError('Timed out: '+label)

    server = None
    client = None
    forwarded = None
    try:
        code = wait('native TLS invitation', lambda: (lambda v: v if v.startswith('oguzkopru1:') else None)(
            adb('shell', 'cat', FOLDER+'/bridge-native-invitation.txt', check=False).strip()), timeout=90)
        native = core.parse_invitation(code)
        # adb forward is just the test wire. TLS still verifies the native AndroidKeyStore certificate.
        forwarded = int(adb('forward', 'tcp:0', 'tcp:'+str(native['port'])).strip())
        client = core.Client(core.invitation('127.0.0.1',forwarded,native['pin'],native['secret']))
        client.pair('CI PC ARM client')
        wait('native owner approval', lambda: client.poll_pair()['status']=='approved')
        with tempfile.TemporaryDirectory(prefix='oguzkopru-ci-') as temporary:
            folder = Path(temporary)
            state = client.state()
            if len(state['files'])!=1 or state['files'][0]['name']!='native-to-desktop.txt':
                raise RuntimeError('Wrong native file selection')
            target = folder/'native-download'
            client.receive(state['files'][0],target)
            if target.read_bytes()!=INTEROP_PAYLOADS['native-to-desktop.txt']:
                raise RuntimeError('Native-host download bytes differ')
            incoming = INTEROP_PAYLOADS['desktop-upload.txt']
            upload = folder/'desktop-upload.txt';upload.write_bytes(incoming)
            request = client.request('POST','/v1/inbox',dict(name=upload.name,bytes=len(incoming),sha256=core.digest(incoming)))
            wait('native recipient file approval', lambda: client.request('GET','/v1/inbox/'+request['id'])['status']=='approved')
            if client.request('PUT','/v1/inbox/'+request['id'],source=upload)['status']!='ready':
                raise RuntimeError('Native upload hash not confirmed')
            session = core.Session('CI PC ARM server')
            server = core.Server(session).start()
            published = folder/'desktop-to-native.txt';published.write_bytes(INTEROP_PAYLOADS['desktop-to-native.txt'])
            session.offer(published)
            config = folder/'invitation-private.txt'
            config.write_text(core.invitation('10.0.2.2',server.port,server.pin,session.secret))
            adb('push',str(config),FOLDER+'/bridge-desktop-invitation.txt')
            def pending_pair():
                with session.lock:
                    return next((p['id'] for p in session.pairs.values() if p['status']=='pending'),None)
            ident = wait('native client TLS pair',pending_pair)
            session.approve_pair(ident,True)
            def pending_file():
                with session.lock:
                    return next((f['id'] for f in session.inbox.values() if f['status']=='pending'),None)
            ident = wait('native client upload proposal',pending_file)
            session.approve_inbox(ident,True)
            def uploaded():
                with session.lock:
                    item = session.inbox.get(ident)
                    if not item or item['status']!='ready':return None
                    return dict(item)
            item = wait('Python independently verified native upload',uploaded)
            raw = (session.root/ident).read_bytes()
            if item['name']!='native-upload.txt' or raw!=INTEROP_PAYLOADS['native-upload.txt'] or item['sha256']!=core.digest(raw):
                raise RuntimeError('Native-client upload bytes/hash differ')
            adb('shell','touch',FOLDER+'/bridge-pc-verified')
            wait('native final protocol assertions',lambda: adb('shell','cat',FOLDER+'/bridge-interop-complete',check=False).strip()=='bidirectional TLS and SHA256 verified')
            return {'protocol':1,'native_host_python_client':True,'python_host_native_client':True,
                    'files_verified':4,'pinned_tls':True,'sha256_verified':True,
                    'file_sha256':{'native-to-desktop.txt':core.digest(target.read_bytes()),
                                   'desktop-upload.txt':core.digest(upload.read_bytes()),
                                   'desktop-to-native.txt':core.digest(published.read_bytes()),
                                   'native-upload.txt':core.digest(raw)},
                    'transport':'QEMU virtual Ethernet + adb forward','physical_devices':False}
    finally:
        if server is not None:server.close()
        if client is not None:client.bearer=None
        if forwarded is not None:adb('forward','--remove','tcp:'+str(forwarded),check=False)
        clean(adb)
