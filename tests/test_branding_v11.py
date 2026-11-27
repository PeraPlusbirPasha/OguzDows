"""Ürün yüzü ile korunması gereken teknik depo / telif kimlikleri ayrı kalır."""
import unittest

import yaml

from support import ROOT


class BrandingV11Tests(unittest.TestCase):
    def test_product_frontends_do_not_rebrand_a_third_party_distribution(self):
        paths = [ROOT / 'native/store.c']
        paths += [ROOT / 'system/usr/lib/oguzdows' / (name + '.py') for name in
                  ('welcome', 'welcome_model', 'updater', 'culture', 'devices',
                   'compatibility', 'rifki_dialogue', 'rifki_narration_texts')]
        paths += list((ROOT / 'system/usr/share/applications').glob('oguzdows-*.desktop'))
        paths += list((ROOT / 'system/usr/share/desktop-directories').glob('*.directory'))
        paths += [ROOT / name for name in ('system/usr/share/oguzdows/start.html',
                                          'raspberrypi/system/usr/share/oguzdows/start.html',
                                          'installer/branding/branding.desc')]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                value = path.read_text().casefold()
                self.assertNotIn('pardus', value)
                self.assertNotIn('debian', value)
        # Gerçek imzalı kaynağın adı / URL'si ürün adıyla değiştirilmez.
        source = (ROOT / 'system/etc/apt/sources.list.d/oguzdows-pardus.sources').read_text()
        self.assertIn('https://depo.pardus.org.tr/pardus', source)
        self.assertIn('Enabled: no', source)
        maintenance = (ROOT / 'system/usr/lib/oguzdows/maintenance.py').read_text()
        self.assertIn("origin.origin == 'Pardus'", maintenance)
        self.assertIn("origin.origin == 'Debian'", maintenance)

    def test_source_os_identity_is_1_2_without_rewriting_published_releases(self):
        identity = (ROOT / 'system/usr/share/oguzdows/os-release').read_text()
        self.assertIn('ID=oguzdows\n', identity)
        self.assertIn('VERSION_ID="1.2"', identity)
        self.assertIn('PRETTY_NAME="OğuzDows 1.2 · Ay Yıldız"', identity)
        self.assertIn('https://github.com/PeraPlusbirPasha/OguzDows', identity)
        lsb = (ROOT / 'system/etc/lsb-release').read_text()
        self.assertIn('DISTRIB_RELEASE=1.2', lsb)
        installer = yaml.safe_load((ROOT / 'installer/branding/branding.desc').read_text())['strings']
        self.assertEqual(installer['version'], '1.2')
        self.assertEqual(installer['shortVersion'], '1.2')
        self.assertEqual(installer['bootloaderEntryName'], 'OğuzDows')
        self.assertEqual(installer['productUrl'], 'https://github.com/PeraPlusbirPasha/OguzDows')
        release = (ROOT / 'docs/releases/v1.0.0.md').read_text()
        self.assertIn('1.0', release)
        policy = (ROOT / 'docs/SURUM-POLITIKASI.md').read_text()
        self.assertIn('v1.1', policy)
        self.assertIn('v2.0', policy)
        self.assertIn('v3.0', policy)


if __name__ == '__main__':
    unittest.main()
