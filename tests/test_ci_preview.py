"""Visual CI evidence stays bounded and restricted to disposable fixtures."""
import io
import os
import random
import subprocess
import sys
import unittest

from PIL import Image
from support import ROOT, load

previewer = load('ci_preview_test', 'scripts/ci-preview.py')


class PreviewTests(unittest.TestCase):
    def test_image_is_bounded_decodable_and_not_a_product_screenshot_claim(self):
        noise = random.Random(7).randbytes(1000 * 710 * 3)
        data = previewer.preview(Image.frombytes('RGB', (1000, 710), noise))
        self.assertLessEqual(len(data), previewer.MAX_BYTES)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertLessEqual(image.width, 900)
            self.assertLessEqual(image.height, 700)

    def test_excessive_dimensions_are_rejected_before_encoding(self):
        with Image.new('RGB', (3000, 3000)) as image, self.assertRaises(ValueError):
            previewer.preview(image)

    def test_no_real_user_path_or_non_ci_file_is_read(self):
        for ci in ('false', 'true'):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/ci-preview.py'), '/home/user/private.png'],
                                    env={**os.environ, 'CI': ci}, capture_output=True, text=True, timeout=8)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Only checkout test-results', result.stderr)
            self.assertNotIn('FileNotFoundError', result.stderr)


if __name__ == '__main__':
    unittest.main()
