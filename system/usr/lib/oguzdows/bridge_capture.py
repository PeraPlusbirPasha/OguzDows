"""Fail-closed screen-sharing gates and bounded JPEG headers; no capture on module import."""
import os
import re
import struct
import subprocess


def unlocked_x11(env=None, execute=subprocess.run):
    env = os.environ if env is None else env
    session = env.get('XDG_SESSION_ID', '')
    if env.get('XDG_SESSION_TYPE') != 'x11' or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', session):
        return False
    try:
        reply = execute(['loginctl', 'show-session', session, '--property=Active', '--property=LockedHint'],
                        capture_output=True, text=True, timeout=2, check=False)
        values = dict(line.split('=', 1) for line in reply.stdout.strip().splitlines() if '=' in line)
        return reply.returncode == 0 and values == {'Active': 'yes', 'LockedHint': 'no'}
    except (OSError, subprocess.TimeoutExpired):
        return False


def jpeg_dimensions(data):
    """Reject dimension bombs before a GUI decoder sees authenticated-but-untrusted peer bytes."""
    if not 4 <= len(data) <= 512 * 1024 or not data.startswith(b'\xff\xd8\xff'):
        raise ValueError('JPEG sınırı')
    at = 2
    while at < len(data):
        if data[at] != 255:
            raise ValueError('JPEG işaretçisi')
        while at < len(data) and data[at] == 255:
            at += 1
        if at >= len(data):
            break
        marker = data[at]; at += 1
        if marker in (0xD9, 0xDA):
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if at + 2 > len(data):
            break
        length = struct.unpack('>H', data[at:at+2])[0]
        if length < 2 or at + length > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2):
            if length < 8:
                break
            height, width = struct.unpack('>HH', data[at+3:at+7])
            if not 1 <= width <= 1280 or not 1 <= height <= 1280:
                raise ValueError('JPEG piksel sınırı')
            return width, height
        at += length
    raise ValueError('JPEG boyutu doğrulanamadı')
