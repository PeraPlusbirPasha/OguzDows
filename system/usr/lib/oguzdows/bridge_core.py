#!/usr/bin/env python3
"""OğuzKöprü/1: explicit, short-lived, certificate-pinned LAN sessions. No discovery/cloud/remote input.

Only chosen files and separately granted JPEG screen frames are exposed. Contacts/SMS/shell/APK
installation are deliberately absent from this protocol. Python stdlib + local OpenSSL, PC/ARM.
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import tempfile
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

MAX_FILE = 128 * 1024 * 1024
BUDGET = 256 * 1024 * 1024
MAX_ITEMS = 8
TTL = 15 * 60
MAX_FRAME = 512 * 1024


def token():
    return secrets.token_hex(32)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(value):
    if not isinstance(value, str) or not value.strip() or not 1 <= len(value) <= 160 or value in ('.', '..'):
        raise ValueError('Geçersiz dosya adı')
    if any(ch in '/\\' or unicodedata.category(ch).startswith('C') for ch in value):
        raise ValueError('Dosya adında yol/kontrol karakteri olamaz')
    return value


def metadata(value):
    name = safe_name(value.get('name'))
    size, sha = value.get('bytes'), value.get('sha256')
    if type(size) is not int or not 0 <= size <= MAX_FILE or not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
        raise ValueError('Dosya boyutu/özeti uygun değil')
    return dict(name=name, bytes=size, sha256=sha)


def local_address(host):
    try:
        value = ipaddress.IPv4Address(host)
    except (ValueError, TypeError):
        return False
    return any(value in network for network in (
        ipaddress.IPv4Network('10.0.0.0/8'), ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'), ipaddress.IPv4Network('169.254.0.0/16'),
        ipaddress.IPv4Network('127.0.0.0/8')))


def invitation(host, port, pin, secret):
    if not local_address(host):
        raise ValueError('Yalnız sayısal yerel IPv4 adresi kullan')
    if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(pin, str) or not isinstance(secret, str) or not re.fullmatch('[a-f0-9]{64}', pin) or not re.fullmatch('[a-f0-9]{64}', secret):
        raise ValueError('Geçersiz oturum')
    return 'oguzkopru1:' + base64.urlsafe_b64encode(json.dumps(dict(host=host, port=port, pin=pin, secret=secret), separators=(',', ':')).encode()).decode().rstrip('=')


def parse_invitation(text):
    if not isinstance(text, str) or len(text) > 1200 or not text.startswith('oguzkopru1:'):
        raise ValueError('OğuzKöprü daveti gerekli')
    raw = text.removeprefix('oguzkopru1:')
    if not re.fullmatch('[A-Za-z0-9_-]+', raw):
        raise ValueError('Geçersiz davet kodlaması')
    value = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
    if not isinstance(value, dict) or set(value) != {'host', 'port', 'pin', 'secret'} or type(value['port']) is not int:
        raise ValueError('Bilinmeyen davet sürümü/alanı')
    invitation(**value)
    return value


class Denied(Exception):
    def __init__(self, code=403):
        self.code = code


class Session:
    def __init__(self, name='OğuzDows', clock=time.monotonic):
        self.name = safe_name(name)[:80]
        self.clock = clock
        self.started = clock()
        self.lock = threading.RLock()
        self.root = Path(tempfile.mkdtemp(prefix='oguzkopru-'))
        os.chmod(self.root, 0o700)
        self.secret = token()
        self.invite_until = clock() + 120
        self.pairs, self.peers, self.files, self.inbox = {}, {}, {}, {}
        self.frame = b''
        self.frame_time = 0
        self.viewer = None
        self.closed = False
        self.attempts = []

    def live(self):
        if self.closed or self.clock() - self.started > TTL:
            raise Denied(410)

    def renew(self):
        with self.lock:
            self.live()
            self.secret, self.invite_until = token(), self.clock() + 120
            self.pairs.clear()

    def pair(self, body):
        with self.lock:
            self.live()
            now = self.clock()
            self.attempts = [t for t in self.attempts if now - t < 60]
            if len(self.attempts) >= 6:
                raise Denied(429)
            self.attempts.append(now)
            if now > self.invite_until or not hmac.compare_digest(str(body.get('secret', '')), self.secret):
                raise Denied()
            if len(self.pairs) + len(self.peers) >= 2:
                raise Denied(429)
            name = safe_name(body.get('name'))[:80]
            nonce = body.get('nonce', '')
            if not re.fullmatch('[a-f0-9]{64}', nonce):
                raise ValueError('nonce')
            ident = secrets.token_hex(16)
            code = digest((ident + nonce).encode())[:8].upper()
            self.pairs[ident] = dict(id=ident, name=name, nonce=nonce, code=code, status='pending', until=now+120)
            return dict(id=ident, code=code, status='pending')

    def approve_pair(self, ident, allow):
        with self.lock:
            self.live()
            p = self.pairs[ident]
            if p['until'] < self.clock() or p['status'] != 'pending':
                raise Denied()
            p['status'] = 'approved' if allow else 'rejected'

    def pair_status(self, body):
        with self.lock:
            self.live()
            p = self.pairs.get(body.get('id'))
            if not p or self.clock() > p['until'] or not hmac.compare_digest(p['nonce'], str(body.get('nonce', ''))):
                raise Denied()
            if p['status'] == 'approved':
                raw = token()
                key = digest(raw.encode())
                self.peers[key] = dict(id=key, name=p['name'], code=p['code'])
                del self.pairs[p['id']]
                return dict(status='approved', token=raw, name=self.name)
            return dict(status=p['status'])

    def authenticate(self, authorization):
        self.live()
        if not authorization.startswith('Bearer '):
            raise Denied(401)
        key = digest(authorization[7:].encode())
        if key not in self.peers:
            raise Denied(401)
        return key

    def revoke(self, key):
        with self.lock:
            self.peers.pop(key, None)
            if self.viewer == key:
                self.viewer, self.frame = None, b''
            for ident in [i for i, f in self.inbox.items() if f['peer'] == key]:
                self.inbox.pop(ident)
                (self.root / ident).unlink(missing_ok=True)

    def reserve(self, size):
        if len(self.files)+len(self.inbox) >= MAX_ITEMS or sum(f['bytes'] for f in [*self.files.values(), *self.inbox.values()])+size > BUDGET:
            raise Denied(413)
        if shutil.disk_usage(self.root).free < size + 16 * 1024 * 1024:
            raise Denied(507)

    def offer(self, source):
        source = Path(source)
        name = safe_name(source.name)
        fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | os.O_NONBLOCK)
        ident = secrets.token_hex(16)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:
                raise ValueError('Yalnız seçilmiş normal dosya; en çok 128 MiB')
            with self.lock:
                self.live(); self.reserve(st.st_size)
                # Reserve before IO, then publish only after a complete immutable private copy.
                self.files[ident] = dict(id=ident, name=name, bytes=st.st_size, sha256='', ready=False)
            hasher = hashlib.sha256(); size = 0
            with os.fdopen(fd, 'rb') as src, (self.root / ident).open('xb') as dst:
                fd = -1
                while chunk := src.read(65536):
                    size += len(chunk)
                    if size > st.st_size:
                        raise ValueError('Seçilen dosya değişti')
                    hasher.update(chunk); dst.write(chunk)
            if size != st.st_size:
                raise ValueError('Seçilen dosya değişti')
            with self.lock:
                self.live()
                self.files[ident].update(sha256=hasher.hexdigest(), ready=True)
            return ident
        except Exception:
            with self.lock:
                self.files.pop(ident, None)
            (self.root / ident).unlink(missing_ok=True)
            raise
        finally:
            if fd != -1:
                os.close(fd)

    def request_inbox(self, peer, body):
        value = metadata(body)
        with self.lock:
            self.live()
            if peer not in self.peers:
                raise Denied(401)
            self.reserve(value['bytes'])
            ident = secrets.token_hex(16)
            self.inbox[ident] = dict(value, id=ident, peer=peer, status='pending')
            return dict(id=ident, status='pending')

    def approve_inbox(self, ident, allow):
        with self.lock:
            self.live()
            f = self.inbox[ident]
            if f['status'] != 'pending':
                raise Denied()
            f['status'] = 'approved' if allow else 'rejected'

    def save_received(self, ident, destination):
        with self.lock:
            self.live()
            f = self.inbox[ident]
            if f['status'] != 'ready':
                raise Denied()
            # Never overwrite a path or follow a target symlink, even after a chooser race.
            with Path(destination).open('xb') as dst, (self.root / ident).open('rb') as src:
                shutil.copyfileobj(src, dst, 65536)

    def set_frame(self, peer, data):
        with self.lock:
            self.live()
            if peer not in self.peers or not data.startswith(b'\xff\xd8\xff') or len(data) > MAX_FRAME:
                raise Denied()
            self.viewer, self.frame, self.frame_time = peer, bytes(data), self.clock()

    def route(self, method, path, headers, body):
        """One bounded HTTP request. Body is a length-limited binary stream from the TLS worker."""
        length = int(headers.get('content-length', '0'))
        def read_json():
            if length > 8192:
                raise Denied(413)
            raw = body.read(length)
            if len(raw) != length:
                raise ValueError('Eksik gövde')
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError('JSON nesnesi gerekli')
            return value
        def reply(value, code=200):
            return code, 'application/json', json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        with self.lock:
            self.live()
        if method == 'POST' and path == '/v1/pair':
            return reply(self.pair(read_json()))
        if method == 'POST' and path == '/v1/pair/status':
            return reply(self.pair_status(read_json()))
        with self.lock:
            peer = self.authenticate(headers.get('authorization', ''))
            if method == 'GET' and path == '/v1/state':
                return reply(dict(version=1, name=self.name, files=[{k:v for k,v in f.items() if k!='ready'} for f in self.files.values() if f['ready']], mirror=self.viewer == peer))
            if method == 'POST' and path == '/v1/bye':
                self.revoke(peer); return reply(dict(stopped=True))
            if method == 'GET' and path == '/v1/frame':
                if self.viewer != peer:
                    raise Denied()
                return (200, 'image/jpeg', self.frame) if self.clock()-self.frame_time < 3 and self.frame else (204, 'image/jpeg', b'')
            match = re.fullmatch(r'/v1/files/([a-f0-9]{32})', path)
            if method == 'GET' and match:
                f = self.files.get(match[1])
                if not f or not f['ready']:
                    raise Denied(404)
                return 200, 'application/octet-stream', self.root / f['id']
        if method == 'POST' and path == '/v1/inbox':
            return reply(self.request_inbox(peer, read_json()), 201)
        match = re.fullmatch(r'/v1/inbox/([a-f0-9]{32})', path)
        if match:
            ident=match[1]
            with self.lock:
                self.authenticate(headers.get('authorization', ''))
                f = self.inbox.get(ident)
                if not f or f['peer'] != peer:
                    raise Denied(404)
                if method == 'GET':
                    return reply(dict(id=ident, status=f['status']))
                if method != 'PUT' or f['status'] != 'approved' or length != f['bytes']:
                    raise Denied()
                f['status'] = 'receiving'
            target = self.root / ident
            try:
                hasher = hashlib.sha256(); remaining = length
                with target.open('xb') as dst:
                    while remaining:
                        with self.lock:
                            self.authenticate(headers['authorization'])
                        chunk = body.read(min(65536, remaining))
                        if not chunk:
                            raise ValueError('Eksik dosya')
                        remaining -= len(chunk); dst.write(chunk); hasher.update(chunk)
                if not hmac.compare_digest(hasher.hexdigest(), f['sha256']):
                    raise ValueError('Dosya özeti eşleşmedi')
                with self.lock:
                    self.authenticate(headers['authorization']); f['status'] = 'ready'
                return reply(dict(id=ident, status='ready'), 201)
            except Exception:
                target.unlink(missing_ok=True)
                with self.lock:
                    f['status'] = 'failed'
                raise
        raise Denied(404)

    def close(self):
        with self.lock:
            self.closed=True; self.peers.clear(); self.pairs.clear(); self.frame=b''; self.viewer=None
        shutil.rmtree(self.root, ignore_errors=True)


class Server:
    def __init__(self, session, host='0.0.0.0', port=0):
        self.session=session
        self.identity=Path(tempfile.mkdtemp(prefix='oguzkopru-tls-'));os.chmod(self.identity,0o700)
        cert, key = self.identity/'cert.pem', self.identity/'key.pem'
        try:
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-sha256','-nodes','-days','2',
                            '-subj','/CN=OguzDows local session','-keyout',str(key),'-out',str(cert)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            os.chmod(key,0o600)
            self.pin=digest(ssl.PEM_cert_to_DER_cert(cert.read_text()))
            self.tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); self.tls.minimum_version=ssl.TLSVersion.TLSv1_2
            self.tls.load_cert_chain(cert,key)
            self.socket=socket.socket(); self.socket.bind((host,port)); self.socket.listen(8);self.socket.settimeout(.5)
            self.port=self.socket.getsockname()[1]
            self.pool=ThreadPoolExecutor(max_workers=4, thread_name_prefix='oguzkopru')
            self.slots=threading.BoundedSemaphore(4); self.closed=False; self.active=set();self.lock=threading.Lock()
        except Exception:
            shutil.rmtree(self.identity,ignore_errors=True);raise

    def start(self):
        self.thread=threading.Thread(target=self._accept,name='oguzkopru-listen',daemon=True);self.thread.start()
        return self

    def _accept(self):
        while not self.closed:
            try:
                connection,_=self.socket.accept()
            except socket.timeout:
                if self.session.clock()-self.session.started>TTL:
                    self.close()
                continue
            except OSError:
                break
            if not self.slots.acquire(False):
                connection.close();continue
            with self.lock: self.active.add(connection)
            try:
                self.pool.submit(self._handle,connection)
            except RuntimeError:
                with self.lock: self.active.discard(connection)
                connection.close(); self.slots.release()

    def _handle(self,connection):
        sock=connection
        stream = None
        try:
            connection.settimeout(15)
            with self.lock:self.active.add(connection)
            sock=self.tls.wrap_socket(connection,server_side=True)
            with self.lock:self.active.discard(connection);self.active.add(sock)
            stream=sock.makefile('rb')
            line=stream.readline(2049)
            if len(line)>2048:raise Denied(413)
            match=re.fullmatch(rb'(GET|POST|PUT) (/v1/[A-Za-z0-9/-]+) HTTP/1\.[01]\r\n',line)
            if not match:raise Denied(400)
            method,path=match[1].decode(),match[2].decode()
            headers={}; size=len(line)
            while True:
                line=stream.readline(2049);size+=len(line)
                if size>8192 or not line or len(line)>2048:raise Denied(413)
                if line==b'\r\n':break
                k,sep,v=line.decode('ascii').partition(':')
                k=k.lower()
                if not sep or k in headers or not re.fullmatch('[a-z0-9-]+',k):raise Denied(400)
                headers[k]=v.strip()
            if 'origin' in headers or 'transfer-encoding' in headers or not re.fullmatch(r'\d{1,10}',headers.get('content-length','0')):
                raise Denied(400)
            if int(headers.get('content-length','0'))>MAX_FILE:raise Denied(413)
            code,mime,data=self.session.route(method,path,headers,stream)
            length=data.stat().st_size if isinstance(data,Path) else len(data)
            sock.sendall(f'HTTP/1.1 {code} Response\r\nContent-Type: {mime}\r\nContent-Length: {length}\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n'.encode())
            if isinstance(data,Path):
                with data.open('rb') as source:
                    while chunk:=source.read(65536):
                        with self.session.lock:
                            self.session.authenticate(headers.get('authorization', ''))
                        sock.sendall(chunk)
            else:sock.sendall(data)
        except (Denied,ValueError,KeyError,json.JSONDecodeError,UnicodeError) as error:
            try:sock.sendall(f'HTTP/1.1 {getattr(error,"code",400)} Blocked\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'.encode())
            except OSError:pass
        except (OSError,ssl.SSLError):pass
        finally:
            if stream is not None:
                try: stream.close()
                except OSError: pass
            with self.lock:self.active.discard(connection);self.active.discard(sock)
            sock.close();self.slots.release()

    def close(self):
        if self.closed:return
        self.closed=True;self.socket.close()
        with self.lock:
            for sock in self.active:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                sock.close()
        self.pool.shutdown(wait=True,cancel_futures=True)
        self.session.close();shutil.rmtree(self.identity,ignore_errors=True)


class Client:
    def __init__(self, code):
        self.invite=parse_invitation(code);self.bearer=None;self.pending=None

    def request(self,method,path,value=None,source=None,destination=None,limit=65536):
        if not re.fullmatch(r'/v1/[A-Za-z0-9/-]+',path):raise ValueError('Sabit protokol yolu gerekli')
        cfg=self.invite
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        with socket.create_connection((cfg['host'],cfg['port']),timeout=15) as raw, context.wrap_socket(raw,server_hostname=cfg['host']) as sock, sock.makefile('rb') as stream:
            # Verify the exact out-of-band pin BEFORE sending invitation, bearer, name or file bytes.
            if not hmac.compare_digest(digest(sock.getpeercert(binary_form=True)),cfg['pin']):raise ssl.SSLError('Sertifika parmak izi eşleşmedi')
            body=json.dumps(value,separators=(',',':')).encode() if value is not None else b''
            length=Path(source).stat().st_size if source else len(body)
            if not 0 <= length <= MAX_FILE: raise ValueError('Dosya boyut sınırı')
            headers=f'{method} {path} HTTP/1.1\r\nHost: {cfg["host"]}:{cfg["port"]}\r\nContent-Length: {length}\r\nConnection: close\r\n'
            if self.bearer:headers+='Authorization: Bearer '+self.bearer+'\r\n'
            sock.sendall((headers+'\r\n').encode())
            if source:
                with Path(source).open('rb') as src:
                    while chunk:=src.read(65536):sock.sendall(chunk)
            else:sock.sendall(body)
            line=stream.readline(2048)
            match=re.fullmatch(rb'HTTP/1\.[01] (\d{3}) [^\r\n]*\r\n',line)
            if not match:raise ValueError('Geçersiz yanıt')
            code=int(match[1]);headers={};count=0
            while True:
                line=stream.readline(2049);count+=len(line)
                if count>8192 or not line or len(line)>2048:raise ValueError('Yanıt başlık sınırı')
                if line==b'\r\n':break
                k,_,v=line.decode('ascii').partition(':');k=k.lower()
                if k in headers:raise ValueError('Yinelenen başlık')
                headers[k]=v.strip()
            if not 200<=code<300:raise Denied(code)
            n=int(headers['content-length'])
            if n<0 or n>limit:raise ValueError('Yanıt boyut sınırı')
            if destination:
                target=Path(destination)
                try:
                    with target.open('xb') as out:
                        remaining=n
                        while remaining:
                            chunk=stream.read(min(65536,remaining))
                            if not chunk:raise ValueError('Eksik yanıt')
                            out.write(chunk);remaining-=len(chunk)
                    return None
                except Exception:
                    # Do not unlink an existing file if exclusive creation failed.
                    if 'out' in locals():target.unlink(missing_ok=True)
                    raise
            data=stream.read(n)
            if len(data)!=n:raise ValueError('Eksik yanıt')
            return data if headers.get('content-type')!='application/json' else json.loads(data)

    def pair(self,name):
        safe_name(name)
        nonce=token();reply=self.request('POST','/v1/pair',dict(secret=self.invite['secret'],name=name[:80],nonce=nonce))
        if not re.fullmatch('[a-f0-9]{32}', reply.get('id', '')) or reply.get('code') != digest((reply['id']+nonce).encode())[:8].upper():
            raise ValueError('Eşleşme kodu doğrulanamadı')
        self.pending=dict(id=reply['id'],nonce=nonce)
        return reply

    def poll_pair(self):
        reply=self.request('POST','/v1/pair/status',self.pending)
        if reply['status'] not in ('pending', 'approved', 'rejected'): raise ValueError('Eşleşme durumu')
        if reply['status']=='approved':
            if not re.fullmatch('[a-f0-9]{64}',reply['token']): raise ValueError('Oturum anahtarı')
            self.bearer=reply['token']; self.pending=None
        return reply

    def state(self):
        value = self.request('GET', '/v1/state')
        if value.get('version') != 1 or type(value.get('mirror')) is not bool or not isinstance(value.get('files'), list) or len(value['files']) > MAX_ITEMS:
            raise ValueError('Protokol durumu')
        safe_name(value.get('name'))
        ids = set()
        for item in value['files']:
            metadata(item)
            ident = item.get('id', '')
            if not re.fullmatch('[a-f0-9]{32}', ident) or ident in ids: raise ValueError('Dosya kimliği')
            ids.add(ident)
        return value

    def receive(self,file,destination):
        metadata(file)
        if not re.fullmatch('[a-f0-9]{32}', file.get('id', '')): raise ValueError('Dosya kimliği')
        target=Path(destination)
        if target.exists() or target.is_symlink(): raise FileExistsError(target)
        if shutil.disk_usage(target.parent).free < file['bytes'] + 16*1024*1024: raise Denied(507)
        # Download to a sibling exclusive temporary path; expose only after real SHA-256 verification.
        fd,tmp=tempfile.mkstemp(prefix='.oguzkopru-',dir=target.parent);os.close(fd);os.unlink(tmp)
        try:
            self.request('GET','/v1/files/'+file['id'],destination=tmp,limit=MAX_FILE)
            hasher=hashlib.sha256()
            with open(tmp,'rb') as src:
                while chunk:=src.read(65536):hasher.update(chunk)
            if os.path.getsize(tmp)!=file['bytes'] or not hmac.compare_digest(hasher.hexdigest(),file['sha256']):raise ValueError('Dosya özeti eşleşmedi')
            os.link(tmp,target,follow_symlinks=False)  # Atomic, refuses existing destination.
        finally:Path(tmp).unlink(missing_ok=True)
