#!/usr/bin/env python3
"""Real engine/GNOME Software installation in disposable GitHub containers only.

Uses the exact production allowlist, signed-origin check, token replan and root
helper. Does not test interactive Polkit, Flathub access or physical hardware.
Never enable this on an installed user system or a live image.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from support import ROOT, load


HELPER = ROOT / 'system/usr/local/sbin/oguzdows-maintenance'
MODULES = ('maintenance.py', 'app_catalog.py', 'hardware.py', 'pi_support.py', 'resource_policy.py')


def command(arguments, seconds=300):
    return subprocess.run(arguments, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          errors='replace', timeout=seconds, check=False,
                          env={**os.environ, 'LC_ALL': 'C.UTF-8', 'LANG': 'C.UTF-8'})


def helper(*arguments, success=True):
    result = command([sys.executable, '-I', str(HELPER), *arguments], seconds=600)
    try:
        value = json.loads(result.stdout)
    except ValueError as error:
        raise AssertionError((result.returncode, result.stdout[-5000:], result.stderr[-5000:])) from error
    assert isinstance(value, dict), value
    if success:
        assert result.returncode == 0 and 'error' not in value, value
    else:
        assert result.returncode != 0 and value.get('error'), value
    return value


def installed(packages):
    result = command(['/usr/bin/dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Status}\n', *packages])
    assert result.returncode == 0, result.stderr
    rows = {row.split('\t')[0].split(':')[0]: row.split('\t')[1] for row in result.stdout.splitlines()}
    assert all(rows.get(name) == 'installed' for name in packages), rows
    return sorted(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-container', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (not args.disposable_container or os.environ.get('CI') != 'true' or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.geteuid() != 0 or not Path('/.dockerenv').is_file()):
        parser.error('Only an explicitly disposable GitHub CI container may install the two fixed bundles.')
    arch = command(['/usr/bin/dpkg', '--print-architecture']).stdout.strip()
    release = dict(row.split('=', 1) for row in Path('/etc/os-release').read_text().splitlines() if '=' in row)
    suite = release.get('VERSION_CODENAME', '').strip('"')
    if (arch, suite) not in (('amd64', 'trixie'), ('arm64', 'bookworm'), ('arm64', 'trixie')):
        parser.error('Unsupported actual architecture/suite; no simulated build identity.')
    if 'boot=live' in Path('/proc/cmdline').read_text().split(): parser.error('Live session is never modified.')
    platform = 'pc' if arch == 'amd64' else 'raspberrypi' if suite == 'bookworm' else 'arm'
    info = {'arch': arch, 'suite': suite, 'platform': platform, 'source_revision': os.environ.get('GITHUB_SHA')}
    if platform == 'arm': info['device_profile'] = 'arm64-uefi'
    modules = {Path('/usr/lib/oguzdows') / name: ROOT / 'system/usr/lib/oguzdows' / name for name in MODULES}
    identity = Path('/usr/share/oguzdows/build-info.json')
    for target, source in modules.items():
        if target.exists() and target.read_bytes() != source.read_bytes(): parser.error('Refuse to replace different code: ' + str(target))
    before = {target: target.read_bytes() if target.exists() else None for target in (*modules, identity)}
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        for target, source in modules.items():
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes()); target.chmod(0o644)
        identity.parent.mkdir(parents=True, exist_ok=True); identity.write_text(json.dumps(info))
        helper('store-refresh')
        core = load('real_bootstrap_catalog', 'system/usr/lib/oguzdows/app_catalog.py')
        results = {}
        for name in ('flatpak-support', 'software-center'):
            plan = helper('plan', 'app:' + name)
            assert len(plan['token']) == 64 and plan['changes'], ('Needs a clean container with missing engine components', name, plan)
            rejected = helper('apply', 'app:' + name, '0' * 64, success=False)
            assert rejected.get('error')
            result = helper('apply', 'app:' + name, plan['token'])
            packages = installed(core.packages(name))
            after = helper('plan', 'app:' + name)
            assert not after['changes'], after
            results[name] = {'real_approved_install': True, 'packages': packages,
                             'resolved_changes': len(plan['changes']), 'after_plan_empty': True,
                             'wrong_token_refused': True, 'message': result.get('message', '')}
        flatpak_arch = command(['/usr/bin/flatpak', '--default-arch']).stdout.strip()
        assert flatpak_arch == ('x86_64' if arch == 'amd64' else 'aarch64'), flatpak_arch
        result = command([sys.executable, '-I', '-c', "import gi;gi.require_version('Flatpak','1.0');from gi.repository import Flatpak;assert Flatpak.get_default_arch()"])
        assert result.returncode == 0, result.stderr
        assert Path('/usr/share/xml/iso-codes/iso_639.xml').is_file()
        assert Path('/usr/bin/gnome-software').is_file()
        report = {'scope': 'real-signed-APT-bootstrap-in-disposable-container', **info, 'bundles': results,
                  'actual_dpkg_arch': arch, 'actual_flatpak_arch': flatpak_arch, 'libflatpak_gi_loads': True,
                  'iso639_language_data': True, 'real_store_refresh': True, 'physical_device': False,
                  'interactive_polkit_tested': False, 'flathub_download_tested': False,
                  'source_hashes': {name: hashlib.sha256(source.read_bytes()).hexdigest() for name, source in
                                    (('helper', HELPER), *[(target.name, source) for target, source in modules.items()])}}
        (args.output / 'real-store-bootstrap.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print('::notice title=Real Flatpak and GNOME Software bootstrap::' + json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        for target, contents in before.items():
            if contents is None: target.unlink(missing_ok=True)
            else: target.write_bytes(contents)


if __name__ == '__main__':
    main()
