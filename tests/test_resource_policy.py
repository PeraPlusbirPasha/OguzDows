"""512 MiB / 1 GiB kararları, özel ayarlar ve tüm tariflere ortak yayılım."""
import json
import tempfile
import unittest
from pathlib import Path

from support import ROOT, load
from xfconf_fixture import Xfconf

resources = load('resources_test', 'system/usr/lib/oguzdows/resource_policy.py')
tune = load('resources_tune_test', 'system/usr/lib/oguzdows/resource_tune.py')
profiles = load('resources_profiles_test', 'system/usr/lib/oguzdows/profiles.py')
pc = load('resources_pc_config', 'scripts/configure.py')
pi = load('resources_pi_config', 'scripts/configure-pi.py')
arm = load('resources_arm_config', 'scripts/configure-arm.py')


def write(root, path, text):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text)
    return file


class ResourcePolicyTests(unittest.TestCase):
    def test_512_and_1024_keep_features_but_never_enable_effects_even_with_full_override(self):
        for memory, expected in ((512 * 1024, 'mini'), (1024 * 1024, 'light')):
            self.assertEqual(resources.policy(memory)['profile'], expected)
            for request in resources.PROFILES:
                policy = resources.policy(memory, requested=request)
                self.assertFalse(policy['compositing'])
                self.assertFalse(policy['animations'])
                self.assertLessEqual(policy['zram_mb'], memory // 1024)
                self.assertLessEqual(policy['zram_mb'], 1024)
        self.assertEqual(resources.policy(512 * 1024)['zram_mb'], 384)
        self.assertEqual(resources.policy(1024 * 1024)['zram_mb'], 512)
        for fields in ({'legacy': True}, {'nomodeset': True}):
            self.assertFalse(resources.policy(8 * 1024 * 1024, requested='full', **fields)['compositing'])
        self.assertFalse(resources.policy(0)['compositing'])
        self.assertTrue(resources.policy(8 * 1024 * 1024)['compositing'])

    def test_plain_config_and_exact_kernel_options_never_execute_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root, 'proc/meminfo', 'MemTotal: 4194304 kB\n')
            write(root, 'etc/oguzdows/resources.conf', 'profile=mini\n')
            self.assertEqual(resources.current_policy(root)['profile'], 'mini')
            write(root, 'etc/oguzdows/pi.conf', 'profile=full\n')
            self.assertEqual(resources.current_policy(root)['profile'], 'mini', 'PC Pi ayarı okumamalı')
            write(root, 'proc/cmdline', 'notoguzdows.profile=full')
            self.assertEqual(resources.current_policy(root)['profile'], 'mini')
            write(root, 'proc/cmdline', 'oguzdows.profile=full nomodeset')
            self.assertFalse(resources.current_policy(root)['compositing'])
            write(root, 'proc/cmdline', 'oguzdows.profile=$(touch /tmp/never)')
            self.assertEqual(resources.current_policy(root)['profile'], 'full')
            write(root, 'proc/meminfo', 'MemTotal: bad')
            self.assertFalse(resources.current_policy(root)['compositing'])

    def test_common_zram_is_bounded_idempotent_and_does_not_change_other_services_or_swap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root, 'proc/meminfo', 'MemTotal: 524288 kB\n')
            write(root, 'proc/sys/vm/swappiness', '60\n')
            write(root, 'proc/sys/vm/page-cluster', '3\n')
            swap = write(root, 'etc/fstab', 'user-swap none swap defaults 0 0\n')
            first = tune.apply(root)
            path = root / 'etc/default/zramswap'
            self.assertIn('SIZE=384', path.read_text())
            self.assertTrue(first['zram_config_managed'])
            self.assertEqual((root / 'proc/sys/vm/swappiness').read_text(), '100\n')
            stamp = path.stat().st_mtime_ns
            tune.apply(root)
            self.assertEqual(stamp, path.stat().st_mtime_ns)
            self.assertEqual(swap.read_text(), 'user-swap none swap defaults 0 0\n')
            self.assertFalse(list(root.rglob('.oguzdows-*')))
            self.assertEqual(json.loads((root / 'run/oguzdows/resources.json').read_text())['zram_mb'], 384)

    def test_custom_or_symlinked_zram_is_not_overwritten(self):
        for contents in ('ALGO=zstd\nSIZE=192\n', 'ALGO=lz4\nSIZE=128\nPRIORITY=100\n'):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = write(root, 'etc/default/zramswap', contents)
                vm = write(root, 'proc/sys/vm/swappiness', '60\n')
                self.assertFalse(tune.apply(root)['zram_config_managed'])
                self.assertEqual(path.read_text(), contents)
                self.assertEqual(vm.read_text(), '60\n')
                path.unlink()
                other = write(root, 'custom', contents)
                path.symlink_to(other)
                self.assertFalse(tune.apply(root)['zram_config_managed'])
                self.assertTrue(path.is_symlink())
                self.assertEqual(other.read_text(), contents)

    def test_static_look_remains_when_glass_is_requested_on_low_ram(self):
        for identifier in profiles.PROFILES:
            values = {(ch, path): value for ch, path, _kind, value in profiles.settings(identifier, effects='glass', resources=resources.policy(524288))}
            self.assertEqual(values['xfwm4', '/general/use_compositing'], 'false')
            self.assertEqual(values['xfwm4', '/general/frame_opacity'], '100')
            self.assertEqual(values['xfce4-panel', '/panels/panel-1/enter-opacity'], '100')
        values = {(ch, path): value for ch, path, _kind, value in profiles.settings('mac', effects='glass', resources=resources.policy(8388608))}
        self.assertEqual(values['xfwm4', '/general/use_compositing'], 'true')
        self.assertEqual(values['xfce4-panel', '/panels/panel-1/background-style'], '0')
        self.assertEqual(values['xfce4-panel', '/panels/panel-90/background-rgba'][-1], '0.94')

    def test_default_style_or_login_does_not_force_compositing_on(self):
        commands = []
        profiles.session(execute=lambda command: commands.append(command), resources=resources.policy(8388608))
        self.assertEqual(commands, [])
        xfconf = Xfconf(profiles.settings('oguzdows'))
        profiles.session(execute=xfconf, resources=resources.policy(1048576))
        self.assertEqual(xfconf.values['xfwm4', '/general/use_compositing'], 'false')
        self.assertTrue(all(command[0] == 'xfconf-query' for command in xfconf.calls))

    def test_shared_files_reach_two_pc_two_pi_and_every_arm64_overlay(self):
        required = ['usr/lib/oguzdows/effects.py', 'usr/share/oguzdows/picom.conf',
                    'usr/lib/oguzdows/news_core.py', 'usr/lib/oguzdows/news_service.py',
                    'usr/local/bin/oguzdows-news', 'usr/share/applications/oguzdows-news.desktop',
                    'usr/share/oguzdows/news-sources.json', 'usr/share/oguzdows/own-app-icons.json',
                    'usr/share/themes/OguzDows/gtk-3.0/dock.css', 'usr/lib/oguzdows/session_start.py', 'usr/lib/oguzdows/welcome_start.py',
                    'usr/lib/oguzdows/desktop_sessions.py', 'usr/lib/oguzdows/desktops.py',
                    'usr/share/xsessions/oguzdows.desktop',
                    'usr/share/themes/OguzDowsAero/gtk-3.0/gtk.css', 'usr/share/themes/OguzDowsEleven/gtk-3.0/gtk.css',
                    'usr/lib/oguzdows/resource_policy.py', 'usr/lib/oguzdows/resource_tune.py',
                    'etc/oguzdows/resources.conf', 'etc/systemd/system/oguzdows-resource-tune.service',
                    'usr/share/themes/OguzDowsMac/gtk-3.0/gtk.css', 'usr/share/themes/OguzDowsGnomeDark/gtk-3.0/gtk.css',
                    'usr/share/oguzdows/store-icons.json', 'usr/share/applications/oguzdows-files.desktop']
        recipes = [(pc.configure, name, 'includes.chroot') for name in ('amd64', 'i386')]
        recipes += [(pi.configure, name, 'stage-oguzdows/00-desktop/files/overlay') for name in ('armhf', 'arm64')]
        recipes += [(arm.configure, name, 'overlay') for name in arm.device_support.OVERLAY_PROFILES]
        for configure, name, relative in recipes:
            with self.subTest(recipe=name), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'output'
                configure(name, output)
                for path in required:
                    self.assertEqual((output / relative / path).read_bytes(), (ROOT / 'system' / path).read_bytes())
                if configure is arm.configure:
                    link = output / relative / 'etc/systemd/system/multi-user.target.wants/oguzdows-resource-tune.service'
                    self.assertTrue(link.is_symlink())
                    self.assertTrue(link.resolve().is_file())


if __name__ == '__main__':
    unittest.main()
