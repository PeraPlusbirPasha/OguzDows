#!/usr/bin/env python3
"""Host APT/Python-APT simülasyonu; hiçbir paket kurmaz, kaynağı etkinleştirmez."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import apt
from support import ROOT, load

core = load('native_maintenance_contract', 'system/usr/lib/oguzdows/maintenance.py')
helper = load('native_maintenance_helper', 'system/usr/local/sbin/oguzdows-maintenance')
helper.core = core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('bookworm', 'trixie'), required=True)
    parser.add_argument('--output', type=Path, default=Path('test-results'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    arch = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    info = {'arch': arch, 'suite': args.suite}
    report = {'host_suite': args.suite, 'host_arch': arch, 'package_installation_tested': False, 'plans': {}}
    cache = apt.Cache()
    def execute(command):
        result = subprocess.run(command, env=core.ENV, capture_output=True, text=True, errors='replace', check=False, timeout=180)
        if command[0] == '/usr/bin/apt-get':
            (args.output / ('apt-plan-' + request.replace(':', '-') + '.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise core.MaintenanceError(result.stdout[-3000:] + result.stderr[-3000:])
        return result.stdout + result.stderr
    # Bookworm burada amd64 hosttur: Pi ARM64 oturumu / işlem kanıtı değil,
    # fakat her iki tabandaki sabit paket adları ve imzalı adaylar zorunludur.
    requests = ['upgrade', 'desktop:kde', 'desktop:gnome']
    for request in requests:
        print('Gerçek APT planı: ' + request, flush=True)
        plan = core.make_plan(request, info, execute, cache)
        report['plans'][request] = {'changes': len(plan['changes']), 'token': plan['token'], 'all_origins_verified': True}
        (args.output / ('apt-plan-' + request.replace(':', '-') + '.log')).write_text(plan['detail'])
    # Aynı aday ve Origin nesnelerini gerçek Python-APT ile ayrıca sınar;
    # boş bir upgrade planı denetimi yanlışlıkla atlatamaz.
    candidate = cache['base-files'].candidate
    core.verify_origins([{'package': 'base-files', 'version': candidate.version}], cache, 'upgrade', info)
    if args.suite == 'trixie':
        key = ROOT / 'system/usr/share/keyrings/oguzdows-pardus.asc'
        preferences = ROOT / 'system/etc/apt/preferences.d/oguzdows-pardus'
        core.channel_controls(info, key, preferences)
        core.PARDUS_KEY = key
        try:
            signed = helper.verify_pardus(execute)
            core.validate_pardus_release(signed)
            report['pardus'] = {'current_signature_verified': True, 'fingerprint': core.PARDUS_FINGERPRINT,
                                'inrelease_sha256': hashlib.sha256(signed.encode()).hexdigest(),
                                'source_enabled': False, 'package_installation_tested': False}
            print('::notice title=Pardus 25 imza denetimi::Güncel InRelease, sabit üretim anahtarıyla gpgv üzerinden doğrulandı. Kaynak açılmadı, paket kurulmadı.')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            # İsteğe bağlı dış sunucunun kesintisi çalışan PC kurucusunu bozmaz.
            # Üretim yardımcısı da aynı koşulda kanalı açmayı REDDEDER.
            report['pardus'] = {'current_signature_verified': False, 'source_enabled': False, 'error': str(error)}
            print('::warning title=Pardus isteğe bağlı kanalı::Güncel çevrimiçi imza doğrulanamadı; kanal kapalı kalır. ' + str(error).replace('\n', ' ')[:800])
    (args.output / 'maintenance-native.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Bakım gerçek APT planları::' + json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
