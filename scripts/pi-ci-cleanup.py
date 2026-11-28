#!/usr/bin/env python3
"""Stop only processes in the private Pi build GUI chroot before unmounting.

Host build tool, never installed in the Pi image. No pkill/killall, lazy unmount,
rootfs deletion or signal based on a command-name match. Both the exact chroot
root AND one of this test's two HOME paths must match. pidfds prevent PID reuse.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import stat
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Scope:
    rootfs: Path
    inside: str
    uids: frozenset[int]

    @property
    def homes(self):
        return {self.inside + '/home', self.inside + '/nonroot/home'}


def checked_scope(rootfs, runtime):
    rootfs, runtime = Path(rootfs), Path(runtime)
    if (rootfs.is_symlink() or runtime.is_symlink() or not rootfs.is_dir() or not runtime.is_dir()
            or rootfs != rootfs.resolve() or runtime != runtime.resolve()
            or rootfs.name != 'rootfs' or rootfs.parent.name != 'stage-oguzdows'
            or runtime.parent != rootfs / 'run'
            or not re.fullmatch(r'oguzdows-ci\.[A-Za-z0-9]{8}', runtime.name)
            or runtime.stat().st_uid != os.geteuid() or stat.S_IMODE(runtime.stat().st_mode) != 0o700):
        raise ValueError('Only the owned mktemp runtime in the Pi desktop build rootfs is accepted.')
    identity = rootfs / 'etc/oguzdows/pi-image.json'
    if (identity.is_symlink() or not identity.is_file() or identity.stat().st_size > 16384
            or not identity.resolve().is_relative_to(rootfs)):
        raise ValueError('Private Pi build identity is missing or unsafe.')
    data = json.loads(identity.read_text())
    if not isinstance(data, dict) or data.get('platform') != 'raspberrypi' or data.get('arch') not in ('armhf', 'arm64'):
        raise ValueError('Not a Pi image build rootfs.')
    return Scope(rootfs, '/' + str(runtime.relative_to(rootfs)), frozenset({os.geteuid(), 65534}))


def read_process(directory, scope, *, private_only=True):
    """A missing/inaccessible/changing process is never a reason to signal it."""
    try:
        pid = int(directory.name)
        if pid <= 1 or pid in (os.getpid(), os.getppid()):
            return None
        if os.readlink(directory / 'root') != str(scope.rootfs):
            return None
        if private_only:
            if directory.stat().st_uid not in scope.uids:
                return None
            with (directory / 'environ').open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                return None
            environment = dict(item.split(b'=', 1) for item in raw.split(b'\0') if b'=' in item)
            if environment.get(b'HOME') not in {home.encode() for home in scope.homes}:
                return None
        # /proc/pid/stat field 22, after the parenthesized comm (may contain ')').
        fields = (directory / 'stat').read_text().rsplit(') ', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return {'pid': pid, 'start_ticks': int(fields[19]), 'name': (directory / 'comm').read_text().strip()[:64]}
    except (OSError, ValueError, IndexError):
        return None


def processes(scope, proc=Path('/proc'), *, private_only=True):
    result = []
    for directory in proc.glob('[0-9]*'):
        record = read_process(directory, scope, private_only=private_only)
        if record is not None:
            result.append(record)
            if len(result) > 256:
                raise ValueError('Private GUI process budget exceeded; no broad process kill was attempted.')
    return result


def signal_process(record, scope, signum):
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Safe Pi GUI cleanup requires Linux pidfd support; runtime was preserved.')
    try:
        descriptor = os.pidfd_open(record['pid'])
    except ProcessLookupError:
        return False
    try:
        current = read_process(Path('/proc') / str(record['pid']), scope)
        if current is None or current['start_ticks'] != record['start_ticks']:
            return False
        signal.pidfd_send_signal(descriptor, signum)
        return True
    except ProcessLookupError:
        return False
    finally:
        os.close(descriptor)


def stop(scope, *, term_seconds=5, kill_seconds=5, interval=.1):
    sent = {}

    def result():
        # An unexpected HOME or UID is NOT permission to kill another process.
        # It blocks success/deletion instead, even when all owned children left.
        remaining = processes(scope, private_only=False)
        return {'scope': 'exact-private-chroot-and-HOME-with-pidfd', 'remaining': remaining,
                'processes': list(sent.values()), 'passed': not remaining}

    for signum, seconds in ((signal.SIGTERM, term_seconds), (signal.SIGKILL, kill_seconds)):
        deadline = time.monotonic() + seconds
        while True:
            pending = processes(scope)
            if not pending:
                return result()
            for record in pending:
                key = (record['pid'], record['start_ticks'], signum)
                if key not in sent and signal_process(record, scope, signum):
                    sent[key] = {**record, 'signal': signum.name}
            if time.monotonic() >= deadline:
                break
            time.sleep(interval)
    return result()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Only the root Pi build host may clean its private GUI chroot.')
    try:
        scope = checked_scope(args.rootfs, args.runtime)
        report = stop(scope)
        if not report['passed']:
            raise RuntimeError('Private GUI processes did not exit: ' + json.dumps(report, ensure_ascii=True))
        print('::notice title=Pi private GUI process cleanup::' + json.dumps(report, ensure_ascii=True), flush=True)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        text = str(error)[-3000:].replace('%', '%25').replace('\n', '%0A').replace('\r', '%0D')
        print('::error title=Pi private GUI cleanup failed::' + text, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
