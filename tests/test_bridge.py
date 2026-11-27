"""OğuzKöprü protocol/security tests. TLS tests bind loopback and use inert fixture bytes only.

These are not physical PC↔phone/ARM/Wi-Fi or real screen-capture acceptance.
"""
import base64
import io
import json
from pathlib import Path
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from support import ROOT, load

core = load('oguz_bridge_core_test', 'system/usr/lib/oguzdows/bridge_core.py')
capture = load('oguz_bridge_capture_test', 'system/usr/lib/oguzdows/bridge_capture.py')
ui = load('oguz_bridge_ui_test', 'system/usr/lib/oguzdows/bridge.py')


class BridgeRulesTests(unittest.TestCase):
    def test_only_numeric_rfc1918_link_local_and_loopback_invitations(self):
        for host in ('10.0.2.2', '192.168.1.20', '172.16.0.1', '172.31.255.254', '169.254.1.2', '127.0.0.1'):
            code = core.invitation(host, 16000, 'a'*64, 'b'*64)
            self.assertEqual(core.parse_invitation(code)['host'], host)
        for host in ('8.8.8.8', 'localhost', 'example.com', '192.168.001.2', '0.0.0.0', '224.0.0.1', '::1', '172.32.0.1', '192.0.0.1'):
            with self.subTest(host=host), self.assertRaises((ValueError, TypeError)):
                core.invitation(host, 16000, 'a'*64, 'b'*64)
        for port in (80, 65536, True, '12000'):
            with self.assertRaises((ValueError, TypeError)): core.invitation('10.0.0.1', port, 'a'*64, 'b'*64)

    def test_invitation_size_version_unknown_fields_and_pin_are_rejected(self):
        for raw in ('https://192.168.1.1', 'oguzkopru2:any', 'oguzkopru1:'+'a'*1300, 'oguzkopru1:....'):
            with self.assertRaises((ValueError, TypeError)): core.parse_invitation(raw)
        value = dict(host='10.0.0.1', port=10000, pin='a'*64, secret='b'*64, command='sms')
        raw = 'oguzkopru1:' + base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
        with self.assertRaises(ValueError): core.parse_invitation(raw)

    def test_names_and_metadata_cannot_be_paths_controls_or_unbounded(self):
        self.assertEqual(core.safe_name('İmece notları.txt'), 'İmece notları.txt')
        for value in ('../x', 'a/b', 'a\\b', '.', '..', 'a\n.txt', '\u202efile.apk', '\x00', 'x'*161, None):
            with self.assertRaises(ValueError): core.safe_name(value)
        for size in (-1, core.MAX_FILE+1, True, 1.5, '4'):
            with self.assertRaises(ValueError): core.metadata(dict(name='ok', bytes=size, sha256='a'*64))

    def test_drop_accepts_only_local_file_uris(self):
        self.assertEqual(ui.dropped_paths(['file:///tmp/hello%20world.txt']), [Path('/tmp/hello world.txt')])
        for value in ('https://host/file', 'file://other-host/share', 'file:///tmp/a?x=1', 'smb://server/share'):
            with self.assertRaises(ValueError): ui.dropped_paths([value])
        with self.assertRaises(ValueError): ui.dropped_paths([])

    def test_screen_gate_fails_closed_without_real_active_unlocked_x11(self):
        def result(text, code=0): return subprocess.CompletedProcess([], code, text, '')
        env = dict(XDG_SESSION_TYPE='x11', XDG_SESSION_ID='c2')
        self.assertTrue(capture.unlocked_x11(env, lambda *a, **k: result('Active=yes\nLockedHint=no\n')))
        for text in ('Active=no\nLockedHint=no', 'Active=yes\nLockedHint=yes', 'Active=yes', ''):
            self.assertFalse(capture.unlocked_x11(env, lambda *a, **k: result(text)))
        self.assertFalse(capture.unlocked_x11({**env, 'XDG_SESSION_TYPE':'wayland'}, lambda *a, **k: self.fail('must not query/capture')))
        self.assertFalse(capture.unlocked_x11(env, lambda *a, **k: result('Active=yes\nLockedHint=no', 1)))
        with patch.object(capture.subprocess, 'run', side_effect=OSError):
            self.assertFalse(capture.unlocked_x11(env, lambda *a, **k: (_ for _ in ()).throw(OSError())))

    def test_jpeg_bounds_are_checked_before_decoding(self):
        real = (ROOT/'mobile/screenshots/launcher-native-emulator.jpg').read_bytes()
        self.assertEqual(capture.jpeg_dimensions(real), (234, 520))
        malicious = b'\xff\xd8\xff\xc0' + struct.pack('>HBHHB', 8, 8, 65535, 65535, 1)
        for data in (b'not jpeg', malicious, b'\xff\xd8\xff'+b'0'*core.MAX_FRAME):
            with self.assertRaises(ValueError): capture.jpeg_dimensions(data)


class BridgeSessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.session = core.Session(clock=lambda: self.now)
        self.addCleanup(self.session.close)

    def paired(self, name='Fixture'):
        nonce = core.token()
        reply = self.session.pair(dict(name=name, secret=self.session.secret, nonce=nonce))
        self.assertEqual(self.session.pair_status(dict(id=reply['id'], nonce=nonce))['status'], 'pending')
        self.session.approve_pair(reply['id'], True)
        token = self.session.pair_status(dict(id=reply['id'], nonce=nonce))['token']
        return self.session.authenticate('Bearer '+token), token

    def route(self, method, path, token, data=None, raw=None):
        payload = json.dumps(data).encode() if raw is None and data is not None else raw or b''
        headers = {'content-length': str(len(payload)), 'authorization':'Bearer '+token}
        code, mime, body = self.session.route(method, path, headers, io.BytesIO(payload))
        return json.loads(body) if mime == 'application/json' else (code, body)

    def test_no_authority_until_explicit_code_approval_and_nonce_is_not_replayable(self):
        nonce = core.token(); reply = self.session.pair(dict(name='PC', secret=self.session.secret, nonce=nonce))
        with self.assertRaises(core.Denied): self.session.authenticate('Bearer '+self.session.secret)
        with self.assertRaises(core.Denied): self.session.pair_status(dict(id=reply['id'], nonce='0'*64))
        self.session.approve_pair(reply['id'], False)
        self.assertEqual(self.session.pair_status(dict(id=reply['id'], nonce=nonce))['status'], 'rejected')
        key, token = self.paired()
        self.assertIn(key, self.session.peers)
        with self.assertRaises(core.Denied): self.session.pair(dict(name='third', secret=self.session.secret, nonce=core.token()))
        self.session.revoke(key)
        with self.assertRaises(core.Denied): self.session.authenticate('Bearer '+token)

    def test_expiry_rate_limit_and_renewal_do_not_extend_session(self):
        original = self.session.secret
        self.now += 121
        with self.assertRaises(core.Denied): self.session.pair(dict(name='x',secret=original,nonce=core.token()))
        self.session.renew()
        self.assertNotEqual(original, self.session.secret)
        self.now += core.TTL
        with self.assertRaises(core.Denied): self.session.renew()
        self.session.close()
        self.assertFalse(self.session.root.exists())

    def test_pairing_attempts_are_bounded_without_allocating_pending_requests(self):
        for _ in range(6):
            with self.assertRaises(core.Denied): self.session.pair(dict(name='x',secret='bad',nonce=core.token()))
        with self.assertRaises(core.Denied) as result: self.session.pair(dict(name='x',secret=self.session.secret,nonce=core.token()))
        self.assertEqual(result.exception.code, 429)
        self.assertEqual(self.session.pairs, {})

    def test_upload_requires_recipient_approval_real_hash_and_final_save(self):
        key, token = self.paired(); raw = b'inert PC to phone fixture\n'
        reply = self.route('POST','/v1/inbox',token,dict(name='hello.txt',bytes=len(raw),sha256=core.digest(raw)))
        ident = reply['id']
        with self.assertRaises(core.Denied): self.route('PUT','/v1/inbox/'+ident,token,raw=raw)
        self.assertFalse((self.session.root/ident).exists())
        self.session.approve_inbox(ident, True)
        self.assertEqual(self.route('PUT','/v1/inbox/'+ident,token,raw=raw)['status'], 'ready')
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'chosen.txt'
            self.session.save_received(ident, target); self.assertEqual(target.read_bytes(), raw)
            with self.assertRaises(FileExistsError): self.session.save_received(ident, target)
        with self.assertRaises(core.Denied): self.route('PUT','/v1/inbox/'+ident,token,raw=raw)

    def test_hash_failure_partial_file_cleanup_and_peer_isolation(self):
        key, token = self.paired(); other, other_token = self.paired('Other')
        raw = b'bad'; reply = self.route('POST','/v1/inbox',token,dict(name='hello',bytes=3,sha256='0'*64)); ident = reply['id']
        with self.assertRaises(core.Denied): self.route('GET','/v1/inbox/'+ident,other_token)
        self.session.approve_inbox(ident, True)
        with self.assertRaises(ValueError): self.route('PUT','/v1/inbox/'+ident,token,raw=raw)
        self.assertFalse((self.session.root/ident).exists()); self.assertEqual(self.session.inbox[ident]['status'], 'failed')
        self.session.revoke(key)
        self.assertNotIn(ident, self.session.inbox)
        self.assertEqual(self.session.authenticate('Bearer '+other_token), other)
        with self.assertRaises(core.Denied): self.session.request_inbox(key,dict(name='again',bytes=0,sha256=core.digest(b'')))

    def test_mirror_is_separately_peer_scoped_stale_frames_expire_and_revoke_clears(self):
        key, token = self.paired(); other, other_token = self.paired('Other')
        with self.assertRaises(core.Denied): self.route('GET','/v1/frame',token)
        self.session.set_frame(key,b'\xff\xd8\xffprotocol-fixture-not-a-capture')
        self.assertEqual(self.route('GET','/v1/frame',token)[0], 200)
        with self.assertRaises(core.Denied): self.route('GET','/v1/frame',other_token)
        self.now += 4; self.assertEqual(self.route('GET','/v1/frame',token), (204, b''))
        self.session.revoke(key); self.assertIsNone(self.session.viewer); self.assertEqual(self.session.frame,b'')

    def test_offer_uses_only_immutable_selected_files_and_never_symlinks_or_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            chosen = Path(tmp)/'chosen.txt'; chosen.write_bytes(b'original')
            ident = self.session.offer(chosen); chosen.write_bytes(b'changed')
            self.assertEqual((self.session.root/ident).read_bytes(), b'original')
            link = Path(tmp)/'link'; link.symlink_to(chosen)
            with self.assertRaises(OSError): self.session.offer(link)
            with self.assertRaises((ValueError, OSError)): self.session.offer(Path(tmp))

    def test_file_count_budget_and_unknown_remote_actions_are_bounded(self):
        key, token = self.paired()
        for i in range(core.MAX_ITEMS): self.route('POST','/v1/inbox',token,dict(name=str(i),bytes=0,sha256=core.digest(b'')))
        with self.assertRaises(core.Denied): self.route('POST','/v1/inbox',token,dict(name='ninth',bytes=0,sha256=core.digest(b'')))
        for path in ('/v1/messages/send','/v1/call/place','/v1/shell','/v1/contacts','/v1/install','/v1/input'):
            with self.assertRaises(core.Denied) as result: self.route('POST',path,token,{})
            self.assertEqual(result.exception.code,404)


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL is required for actual loopback TLS tests')
class BridgeTlsTests(unittest.TestCase):
    def setUp(self):
        self.session=core.Session('TLS fixture'); self.server=core.Server(self.session, host='127.0.0.1').start()
        self.addCleanup(self.server.close)
        self.client=core.Client(core.invitation('127.0.0.1',self.server.port,self.server.pin,self.session.secret))

    def pair(self):
        reply=self.client.pair('CI only')
        self.assertEqual(self.client.poll_pair()['status'],'pending')
        self.session.approve_pair(reply['id'],True)
        self.assertEqual(self.client.poll_pair()['status'],'approved')

    def test_real_pinned_tls_pair_and_download_hash_no_overwrite(self):
        self.pair()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.txt';source.write_bytes(b'actual TLS transfer\x00\xff')
            self.session.offer(source)
            files=self.client.state()['files'];self.assertEqual(len(files),1)
            target=Path(tmp)/'receive.txt';self.client.receive(files[0],target)
            self.assertEqual(target.read_bytes(),source.read_bytes())
            with self.assertRaises(FileExistsError): self.client.receive(files[0],target)
            self.assertEqual(target.read_bytes(),source.read_bytes())
            tampered={**files[0],'sha256':'0'*64}
            with self.assertRaises(ValueError):self.client.receive(tampered,Path(tmp)/'bad.txt')
            self.assertFalse((Path(tmp)/'bad.txt').exists())
            self.assertEqual(list(Path(tmp).glob('.oguzkopru-*')),[])

    def test_wrong_pin_is_rejected_before_invitation_or_peer_name_is_sent(self):
        self.client.invite['pin']='0'*64
        with self.assertRaises(ssl.SSLError):self.client.pair('must not arrive')
        self.assertEqual(self.session.pairs,{})
        self.assertEqual(self.session.attempts,[])

    def test_real_upload_approval_and_disconnect_revoke(self):
        self.pair();raw=b'real upload fixture'
        reply=self.client.request('POST','/v1/inbox',dict(name='upload',bytes=len(raw),sha256=core.digest(raw)))
        self.session.approve_inbox(reply['id'],True)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'chosen';source.write_bytes(raw)
            self.assertEqual(self.client.request('PUT','/v1/inbox/'+reply['id'],source=source)['status'],'ready')
        self.assertEqual((self.session.root/reply['id']).read_bytes(),raw)
        self.assertTrue(self.client.request('POST','/v1/bye')['stopped'])
        with self.assertRaises(core.Denied):self.client.state()

    def test_browser_origin_duplicate_headers_and_unknown_path_are_rejected(self):
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
        for headers in ('Origin: https://hostile.example\r\n','Content-Length: 0\r\nContent-Length: 0\r\n','Transfer-Encoding: chunked\r\n'):
            with socket.create_connection(('127.0.0.1',self.server.port)) as raw, context.wrap_socket(raw,server_hostname='127.0.0.1') as sock:
                sock.sendall(('POST /v1/pair HTTP/1.1\r\nHost: localhost\r\n'+headers+'\r\n').encode())
                self.assertIn(b' 400 ',sock.recv(2048))
        self.assertEqual(self.session.pairs,{})


if __name__ == '__main__':
    unittest.main()
