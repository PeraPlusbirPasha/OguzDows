#!/usr/bin/env python3
"""Real fixed-app install/remove on an explicitly disposable Trixie CI container.

Never runs on a normal host, live USB, developer machine or published image.
Calls the real isolated privileged helper directly; it does NOT test Polkit's
password UI or pretend the native fixture's approval is real authentication.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'system/usr/local/sbin/oguzdows-maintenance'


def installed(name):
    result = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${db:Status-Status}', name],
                            capture_output=True, text=True, check=False, timeout=10)
    return result.returncode == 0 and result.stdout == 'installed'


def helper(*arguments, success=True):
    result = subprocess.run([sys.executable, '-I', str(HELPER), *arguments],
                            capture_output=True, text=True, check=False, timeout=240)
    data = json.loads(result.stdout)
    if success:
        assert result.returncode == 0 and 'error' not in data, data
    else:
        assert result.returncode != 0 and data.get('error'), data
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-container', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (not args.disposable_container or os.environ.get('CI') != 'true'
            or os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0
            or not Path('/.dockerenv').is_file()):
        parser.error('Only an explicitly disposable GitHub CI container may change test packages.')
    release = Path('/etc/os-release').read_text()
    arch = subprocess.check_output(['/usr/bin/dpkg', '--print-architecture'], text=True).strip()
    if 'VERSION_CODENAME=trixie' not in release or arch != 'amd64':
        parser.error('Real wrapper transaction test is limited to its supported amd64/trixie target.')
    if 'boot=live' in Path('/proc/cmdline').read_text().split() or installed('geany'):
        parser.error('Requires a clean, non-live disposable container with no existing Geany.')
    args.output.mkdir(parents=True, exist_ok=True)
    # Only fixed, reviewed helper modules, exactly from this checkout.
    before = {}
    files = {Path('/usr/lib/oguzdows') / name: ROOT / 'system/usr/lib/oguzdows' / name
             for name in ('maintenance.py', 'app_catalog.py', 'hardware.py', 'pi_support.py', 'resource_policy.py')}
    identity = Path('/usr/share/oguzdows/build-info.json')
    marker = Path('/root/.config/geany') / ('oguz-ci-preserve-' + uuid.uuid4().hex)
    for target, source in files.items():
        if target.exists() and target.read_bytes() != source.read_bytes():
            parser.error('Refusing to replace different installed helper code: ' + str(target))
    for target in (*files, identity):
        before[target] = target.read_bytes() if target.exists() else None
    try:
        for target, source in files.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            target.chmod(0o644)
        identity.parent.mkdir(parents=True, exist_ok=True)
        identity.write_text(json.dumps({'arch': arch, 'suite': 'trixie', 'platform': 'pc',
                                        'source_revision': os.environ.get('GITHUB_SHA', 'unknown')}))
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text('Personal app data must survive remove, not purge.')
        plan = helper('plan', 'app:geany')
        assert plan['changes'] and len(plan['token']) == 64
        helper('apply', 'app:geany', '0' * 64, success=False)
        assert not installed('geany'), 'Wrong token must not install'
        helper('apply', 'app:geany', plan['token'])
        assert installed('geany') and installed('geany-common')
        subprocess.run(['/usr/bin/apt-mark', 'hold', 'geany'], check=True, capture_output=True, timeout=20)
        try:
            held = helper('plan', 'remove-app:geany', success=False)
            assert 'tutulan' in held['error'], held
        finally:
            subprocess.run(['/usr/bin/apt-mark', 'unhold', 'geany'], check=True, capture_output=True, timeout=20)
        with Path('/var/lib/dpkg/lock-frontend').open('r+') as lock:
            fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            conflict = helper('plan', 'remove-app:geany', success=False)
            assert 'Kilit dosyasını silmeyin' in conflict['error'], conflict
        removal = helper('plan', 'remove-app:geany')
        assert removal['intent'] == 'remove'
        assert removal['changes'] and all(row['package'].split(':')[0] == 'geany' for row in removal['changes'])
        helper('apply', 'remove-app:geany', '0' * 64, success=False)
        assert installed('geany'), 'Wrong removal token must not mutate'
        helper('apply', 'remove-app:geany', removal['token'])
        assert not installed('geany')
        assert installed('geany-common'), 'No autoremove of dependencies'
        assert marker.read_text() == 'Personal app data must survive remove, not purge.'
        report = {'isolated_disposable_container': True, 'arch': arch, 'suite': 'trixie',
                  'source_revision': os.environ.get('GITHUB_SHA'), 'real_helper_install': True,
                  'real_exact_dpkg_removal': True, 'held_removal_refused': True,
                  'frontend_lock_conflict_refused': True, 'wrong_token_refused': True,
                  'dependency_preserved': True, 'personal_data_preserved': True,
                  'gui_or_polkit_auth_tested': False, 'physical_device': False}
        (args.output / 'real-store-transaction.json').write_text(json.dumps(report, indent=2) + '\n')
        print('::notice title=Real guarded Store transaction::' + json.dumps(report))
    finally:
        marker.unlink(missing_ok=True)
        for target, payload in before.items():
            if payload is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(payload)


if __name__ == '__main__':
    main()
