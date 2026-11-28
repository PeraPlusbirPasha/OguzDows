"""Pi APT uyarlaması: kilitli şablon farkı ve gerçek APT ile yerel failover.

Yerel APT testi sentetik trusted=yes DOSYA deposudur; imza kanıtı değildir.
Ağ / sistem kurulumu yoktur. Üretim kaynaklarında bu istisna KULLANILMAZ.
"""
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import ROOT, load

prepare = load('pi_apt_prepare', 'scripts/prepare-pi-apt.py')
ARMHF = ("deb [ arch=armhf ] http://raspbian.raspberrypi.com/raspbian/ RELEASE main contrib non-free rpi\n"
         "# Uncomment line below then 'apt-get update' to enable 'apt-get source'\n"
         "#deb-src http://raspbian.raspberrypi.com/raspbian/ RELEASE main contrib non-free rpi\n")
ARM64 = ("deb http://deb.debian.org/debian RELEASE main contrib non-free non-free-firmware\n"
         "deb http://deb.debian.org/debian-security/ RELEASE-security main contrib non-free non-free-firmware\n"
         "deb http://deb.debian.org/debian RELEASE-updates main contrib non-free non-free-firmware\n"
         "# Uncomment deb-src lines below then 'apt-get update' to enable 'apt-get source'\n"
         "#deb-src http://deb.debian.org/debian RELEASE main contrib non-free non-free-firmware\n"
         "#deb-src http://deb.debian.org/debian-security/ RELEASE-security main contrib non-free non-free-firmware\n"
         "#deb-src http://deb.debian.org/debian RELEASE-updates main contrib non-free non-free-firmware\n")


class PiAptAdaptationTests(unittest.TestCase):
    def test_only_armhf_transport_changes_and_hash_report_follows_verified_upstream(self):
        contract = json.loads((ROOT / 'raspberrypi/upstream-contract.json').read_text())
        for arch, original in (('armhf', ARMHF), ('arm64', ARM64)):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / prepare.SOURCE_LIST
                path.parent.mkdir(parents=True)
                path.write_text(original)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), contract['architectures'][arch]['files'][prepare.SOURCE_LIST])
                result = prepare.prepare(root, arch, root / 'report.json')
                self.assertFalse(result['signature_checks_disabled'])
                self.assertEqual(result['before_sha256'], contract['architectures'][arch]['files'][prepare.SOURCE_LIST])
                if arch == 'armhf':
                    self.assertIn(prepare.MIRROR, path.read_text())
                    self.assertIn('[ arch=armhf ]', path.read_text())
                    self.assertIn('RELEASE main contrib non-free rpi', path.read_text())
                else:
                    self.assertEqual(path.read_text(), original)
                script = root / 'stage0/00-apt-resilience/00-run.sh'
                self.assertTrue(os.access(script, os.X_OK))
                self.assertIn('etc/apt/apt.conf.d/80oguzdows-resilience', script.read_text())
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    prepare.prepare(root, arch, root / 'report.json')
                self.assertEqual(path.read_bytes(), before)

    def test_unknown_template_fails_before_any_file_is_mutated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / prepare.SOURCE_LIST
            path.parent.mkdir(parents=True)
            path.write_text(ARMHF + '# unexpected\n')
            with self.assertRaises(ValueError):
                prepare.prepare(root, 'armhf', root / 'report.json')
            self.assertFalse((root / 'stage0/00-apt-resilience').exists())
            self.assertFalse((root / 'report.json').exists())

    def test_mirrors_are_same_raspbian_archive_and_signature_checks_stay_on(self):
        config = (ROOT / 'raspberrypi/apt/80oguzdows-resilience').read_text()
        self.assertIn('Acquire::Retries "3"', config)
        for key in ('APT::Get::AllowUnauthenticated', 'Acquire::AllowInsecureRepositories', 'Acquire::AllowDowngradeToInsecureRepositories'):
            self.assertIn(key + ' "false"', config)
        mirrors = [line for line in (ROOT / 'raspberrypi/apt/raspbian.mirrors').read_text().splitlines() if line and not line.startswith('#')]
        self.assertEqual(mirrors, ['http://archive.raspbian.org/raspbian/\tpriority:1',
                                   'http://raspbian.raspberrypi.com/raspbian/\tpriority:2'])
        source = (ROOT / 'build-pi.sh').read_text()
        self.assertLess(source.index('audit-pi-upstream.py'), source.index('prepare-pi-apt.py'))
        self.assertLess(source.index('prepare-pi-apt.py'), source.index('./build.sh'))


@unittest.skipUnless(shutil.which('apt-get') and shutil.which('dpkg-deb') and Path('/usr/lib/apt/methods/mirror+file').exists(), 'APT mirror+file ve dpkg-deb gerekli')
class AptMirrorOfflineTests(unittest.TestCase):
    def test_real_apt_uses_second_local_mirror_and_still_rejects_corrupt_archive(self):
        with tempfile.TemporaryDirectory(prefix='oguzdows-mirror-test-') as temporary:
            root = Path(temporary)
            for directory in ('repo', 'source/DEBIAN', 'etc/apt.conf.d', 'etc/sources.list.d', 'etc/preferences.d',
                              'state/lists/partial', 'cache/archives/partial', 'log'):
                (root / directory).mkdir(parents=True)
            (root / 'state/status').touch()
            (root / 'etc/apt.conf').touch()
            fields = 'Package: oguzdows-mirror-fixture\nVersion: 1.0\nArchitecture: all\nMaintainer: Test <test@example.invalid>\nDescription: Local mirror fixture only\n'
            (root / 'source/DEBIAN/control').write_text(fields)
            archive = root / 'repo/oguzdows-mirror-fixture_1.0_all.deb'
            subprocess.run(['dpkg-deb', '-Zgzip', '--build', str(root / 'source'), str(archive)], check=True, capture_output=True, timeout=15)
            data = archive.read_bytes()
            (root / 'repo/Packages').write_text(fields + f'Filename: ./{archive.name}\nSize: {len(data)}\nSHA256: {hashlib.sha256(data).hexdigest()}\n\n')
            mirrors = root / 'mirrors.list'
            mirrors.write_text(f'file:{root}/unavailable/\tpriority:1\nfile:{root}/repo/\tpriority:2\n')
            (root / 'etc/sources.list').write_text(f'deb [trusted=yes] mirror+file:{mirrors} ./\n')
            config = root / 'apt.conf'
            config.write_text(f'''Dir::Etc "{root}/etc";
Dir::Etc::main "apt.conf";
Dir::Etc::parts "apt.conf.d";
Dir::Etc::sourcelist "sources.list";
Dir::Etc::sourceparts "sources.list.d";
Dir::State "{root}/state";
Dir::State::status "{root}/state/status";
Dir::Cache "{root}/cache";
Dir::Log "{root}/log";
Debug::NoLocking "true";
APT::Sandbox::User "{pwd.getpwuid(os.geteuid()).pw_name}";
Acquire::Languages "none";
Acquire::Retries "0";
APT::Get::AllowUnauthenticated "false";
''')
            env = {**os.environ, 'APT_CONFIG': str(config), 'LC_ALL': 'C.UTF-8'}
            def run(*arguments):
                return subprocess.run(['apt-get', *arguments], cwd=root / 'cache/archives', env=env, capture_output=True, text=True, timeout=20)
            result = run('update')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Packages', result.stdout)  # APT açıklamada ilk URI'yi koruyabilir.
            result = run('download', 'oguzdows-mirror-fixture')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / 'cache/archives' / archive.name).read_bytes(), data)
            (root / 'cache/archives' / archive.name).unlink()
            archive.write_bytes(b'not a valid archive' + data[19:])
            result = run('download', 'oguzdows-mirror-fixture')
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Hash Sum mismatch', result.stderr)
            self.assertEqual((root / 'state/status').read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()
