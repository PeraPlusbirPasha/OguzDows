"""Private Pi build GUI lifecycle; fake /proc + optional real host chroot probes.

This is NOT Pi kernel/LightDM/PAM/GPU/performance evidence. The root probe starts
only bounded disposable children, does not mount anything, and always reaps them.
"""
import io
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import load

cleanup = load('pi_private_gui_cleanup', 'scripts/pi-ci-cleanup.py')


def fixture(parent):
    root = parent / 'build/pi-gen/work/image/stage-oguzdows/rootfs'
    runtime = root / 'run/oguzdows-ci.Test1234'
    runtime.mkdir(parents=True, mode=0o700)
    runtime.chmod(0o700)
    identity = root / 'etc/oguzdows/pi-image.json'
    identity.parent.mkdir(parents=True)
    identity.write_text(json.dumps({'platform': 'raspberrypi', 'arch': 'arm64'}))
    return root, runtime


def fake_process(proc, scope, pid=987654, home=None, root=None, state='S', start=123):
    directory = proc / str(pid)
    directory.mkdir(parents=True)
    (directory / 'root').symlink_to(scope.rootfs if root is None else root, target_is_directory=True)
    home = scope.inside + '/home' if home is None else home
    (directory / 'environ').write_bytes(b'IGNORED_SECRET=not-in-report\0HOME=' + home.encode() + b'\0')
    # Exact field positions, including a comm containing a closing parenthesis.
    fields = [state] + ['0'] * 18 + [str(start)] + ['0'] * 8
    (directory / 'stat').write_text(str(pid) + ' (daemon ) name) ' + ' '.join(fields))
    (directory / 'comm').write_text('scoped-daemon\n')
    return directory


class ScopeTests(unittest.TestCase):
    def test_accepts_only_owned_private_runtime_under_exact_pi_desktop_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runtime = fixture(Path(temporary))
            scope = cleanup.checked_scope(root, runtime)
            self.assertEqual(scope.rootfs, root)
            self.assertEqual(scope.homes, {'/run/oguzdows-ci.Test1234/home', '/run/oguzdows-ci.Test1234/nonroot/home'})
            self.assertEqual(scope.uids, {os.geteuid(), 65534})
            runtime.chmod(0o711)
            with self.assertRaises(ValueError): cleanup.checked_scope(root, runtime)
            runtime.chmod(0o700)
            link = runtime.parent / 'oguzdows-ci.Other123'
            link.symlink_to(runtime, target_is_directory=True)
            with self.assertRaises(ValueError): cleanup.checked_scope(root, link)
            with self.assertRaises(ValueError): cleanup.checked_scope(Path('/'), runtime)

    def test_missing_foreign_oversized_or_escaped_identity_never_grants_a_signal_scope(self):
        for kind in ('missing', 'foreign', 'list', 'oversized', 'escaped'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary)
                root, runtime = fixture(parent)
                identity = root / 'etc/oguzdows/pi-image.json'
                if kind == 'missing': identity.unlink()
                if kind == 'foreign': identity.write_text('{"platform":"host","arch":"amd64"}')
                if kind == 'list': identity.write_text('[]')
                if kind == 'oversized': identity.write_text(' ' * 16385)
                if kind == 'escaped':
                    foreign = parent / 'outside.json'
                    foreign.write_text(identity.read_text())
                    identity.unlink()
                    identity.symlink_to(foreign)
                with self.assertRaises(ValueError): cleanup.checked_scope(root, runtime)

    def test_root_only_cli_rejects_non_root_before_scanning_processes(self):
        with patch.object(cleanup.os, 'geteuid', return_value=1000), \
                patch.object(sys, 'argv',
                             ['pi-ci-cleanup.py', '--rootfs', '/tmp/not-real', '--runtime', '/tmp/not-real']), \
                patch.object(sys, 'stderr', io.StringIO()), patch.object(cleanup, 'checked_scope') as checked:
            with self.assertRaises(SystemExit) as error: cleanup.main()
            self.assertEqual(error.exception.code, 2)
            checked.assert_not_called()


class ProcessTests(unittest.TestCase):
    def test_exact_root_home_uid_and_start_time_are_required_and_secrets_are_not_logged(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root, runtime = fixture(parent)
            scope = cleanup.checked_scope(root, runtime)
            proc = parent / 'proc'
            directory = fake_process(proc, scope)
            record = cleanup.read_process(directory, scope)
            self.assertEqual(record, {'pid': 987654, 'start_ticks': 123, 'name': 'scoped-daemon'})
            self.assertNotIn('not-in-report', json.dumps(record))
            (directory / 'environ').write_bytes(b'HOME=/run/oguzdows-ci.Test1234/nonroot/home\0')
            self.assertEqual(cleanup.read_process(directory, scope), record)
            other_uid = cleanup.Scope(root, scope.inside, frozenset({os.geteuid() + 1234}))
            self.assertIsNone(cleanup.read_process(directory, other_uid))
            (directory / 'environ').write_bytes(b'HOME=/home/another-user\0')
            self.assertIsNone(cleanup.read_process(directory, scope))
            # Unexpected chroot processes block success, but are never signaled.
            self.assertEqual(cleanup.read_process(directory, scope, private_only=False), record)
            (directory / 'environ').write_bytes(b'HOME=' + (scope.inside + '/home').encode() + b'\0')
            (directory / 'root').unlink()
            (directory / 'root').symlink_to('/')
            self.assertIsNone(cleanup.read_process(directory, scope))

    def test_gone_zombie_malformed_and_oversized_processes_are_not_signal_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root, runtime = fixture(parent)
            scope = cleanup.checked_scope(root, runtime)
            directory = fake_process(parent / 'proc', scope, state='Z')
            self.assertIsNone(cleanup.read_process(directory, scope))
            (directory / 'stat').write_text('corrupt')
            self.assertIsNone(cleanup.read_process(directory, scope))
            (directory / 'environ').write_bytes(b'x' * 65537)
            self.assertIsNone(cleanup.read_process(directory, scope))
            self.assertIsNone(cleanup.read_process(parent / 'proc/999999', scope))
            with patch.object(cleanup.os, 'getpid', return_value=987654):
                self.assertIsNone(cleanup.read_process(directory, scope))

    def test_pidfd_signal_rechecks_identity_and_refuses_pid_reuse(self):
        scope = cleanup.Scope(Path('/not-used'), '/run/oguzdows-ci.Test1234', frozenset({0}))
        record = {'pid': 987654, 'start_ticks': 123, 'name': 'scoped-daemon'}
        for current, expected in ((record, True), ({**record, 'start_ticks': 999}, False), (None, False)):
            with self.subTest(current=current), patch.object(cleanup.os, 'pidfd_open', return_value=65) as opened, \
                    patch.object(cleanup.os, 'close') as closed, \
                    patch.object(cleanup.signal, 'pidfd_send_signal') as sent, \
                    patch.object(cleanup, 'read_process', return_value=current):
                self.assertEqual(cleanup.signal_process(record, scope, signal.SIGTERM), expected)
                opened.assert_called_once_with(987654)
                closed.assert_called_once_with(65)
                self.assertEqual(sent.call_count, int(expected))
                if expected: sent.assert_called_once_with(65, signal.SIGTERM)
        with patch.object(cleanup.os, 'pidfd_open', side_effect=ProcessLookupError), \
                patch.object(cleanup.signal, 'pidfd_send_signal') as sent:
            self.assertFalse(cleanup.signal_process(record, scope, signal.SIGTERM))
            sent.assert_not_called()

    def test_cleanup_escalates_only_owned_pids_and_checks_unmatched_chroot_survivors(self):
        scope = cleanup.Scope(Path('/not-used'), '/run/oguzdows-ci.Test1234', frozenset({0}))
        record = {'pid': 987654, 'start_ticks': 123, 'name': 'scoped-daemon'}
        for survivors, expected in (([], True), ([{**record, 'pid': 987655}], False)):
            with self.subTest(survivors=survivors), \
                    patch.object(cleanup, 'processes', side_effect=[[record], [record], survivors]) as processes, \
                    patch.object(cleanup, 'signal_process', return_value=True) as sent:
                result = cleanup.stop(scope, term_seconds=0, kill_seconds=0)
                self.assertEqual(result['passed'], expected)
                self.assertEqual([call.args[2] for call in sent.call_args_list], [signal.SIGTERM, signal.SIGKILL])
                self.assertEqual(processes.call_args.kwargs, {'private_only': False})
                self.assertEqual(result['remaining'], survivors)

    def test_no_owned_process_does_not_mean_an_unknown_chroot_process_may_be_killed(self):
        scope = cleanup.Scope(Path('/not-used'), '/run/oguzdows-ci.Test1234', frozenset({0}))
        other = {'pid': 987655, 'start_ticks': 999, 'name': 'not-owned'}
        with patch.object(cleanup, 'processes', side_effect=[[], [other]]), \
                patch.object(cleanup, 'signal_process') as sent:
            result = cleanup.stop(scope)
            self.assertFalse(result['passed'])
            self.assertEqual(result['remaining'], [other])
            sent.assert_not_called()


class RealHostChrootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = (1 << 18) | (1 << 19)  # CAP_SYS_CHROOT and CAP_SYS_PTRACE
        capabilities = 0
        try:
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith('CapEff:'): capabilities = int(line.split()[1], 16)
        except OSError:
            pass
        available = (os.geteuid() == 0 and capabilities & required == required
                     and hasattr(os, 'chroot') and hasattr(os, 'pidfd_open')
                     and hasattr(signal, 'pidfd_send_signal'))
        if not available:
            if os.environ.get('OGUZDOWS_REQUIRE_PI_CLEANUP_PROBE') == '1':
                raise AssertionError('Mandatory host chroot/pidfd regression requires sudo and Linux capabilities.')
            raise unittest.SkipTest('Private chroot/pidfd integration runs in the explicit privileged Pi CI step.')

    def child(self, root, home, uid=0, *, ignore_term=False):
        script = '''
import os, signal, sys, time
root, uid, ignore = sys.argv[1], int(sys.argv[2]), sys.argv[3] == 'yes'
if root != '-':
    os.chroot(root)
    os.chdir('/')
if uid:
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
if ignore:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.alarm(20)
os.write(1, b'1')
while True:
    time.sleep(.1)
'''
        process = subprocess.Popen([sys.executable, '-c', script, str(root), str(uid), 'yes' if ignore_term else 'no'],
                                   env={**os.environ, 'HOME': home}, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.addCleanup(self.reap, process)
        self.assertTrue(select.select([process.stdout], [], [], 4)[0], 'Disposable probe child did not become ready.')
        self.assertEqual(process.stdout.read(1), b'1')
        return process

    @staticmethod
    def reap(process):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        process.stdout.close()

    def test_real_root_and_nonroot_chroot_children_exit_but_identical_host_home_is_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runtime = fixture(Path(temporary))
            scope = cleanup.checked_scope(root, runtime)
            host = self.child('-', scope.inside + '/home', ignore_term=True)
            ordinary = self.child(root, scope.inside + '/home')
            stubborn = self.child(root, scope.inside + '/nonroot/home', uid=65534, ignore_term=True)
            # Real /proc roots, initial exec HOME, uid drop and real pidfd signals.
            self.assertIsNotNone(cleanup.read_process(Path('/proc') / str(stubborn.pid), scope))
            result = cleanup.stop(scope, term_seconds=.15, kill_seconds=2)
            self.assertTrue(result['passed'], result)
            self.assertIsNone(host.poll(), 'A host process with the same HOME was incorrectly signaled.')
            ordinary.wait(timeout=3)
            stubborn.wait(timeout=3)
            self.assertEqual(ordinary.returncode, -signal.SIGTERM)
            self.assertEqual(stubborn.returncode, -signal.SIGKILL)
            self.assertEqual({row['pid'] for row in result['processes']}, {ordinary.pid, stubborn.pid})

    def test_real_unknown_home_blocks_success_without_signaling_that_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, runtime = fixture(Path(temporary))
            scope = cleanup.checked_scope(root, runtime)
            other = self.child(root, '/home/unrelated', ignore_term=True)
            result = cleanup.stop(scope, term_seconds=.1, kill_seconds=.1)
            self.assertFalse(result['passed'])
            self.assertEqual(result['processes'], [])
            self.assertEqual([row['pid'] for row in result['remaining']], [other.pid])
            self.assertIsNone(other.poll())


if __name__ == '__main__':
    unittest.main()
