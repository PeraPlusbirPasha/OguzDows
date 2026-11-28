import ctypes
import ctypes.util
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from support import ROOT, load

art = load('cursor_art_test', 'scripts/render-assets.py')
prepare = load('landscape_prepare_test', 'scripts/prepare-landscapes.py')


class CursorTests(unittest.TestCase):
    def decode(self, path):
        data = path.read_bytes()
        magic, header, version, count = struct.unpack_from('<4I', data)
        self.assertEqual((magic, header, version), (0x72756358, 16, 0x10000))
        result = []
        for index in range(count):
            kind, size, offset = struct.unpack_from('<3I', data, 16 + 12 * index)
            values = struct.unpack_from('<9I', data, offset)
            self.assertEqual(values[:4], (36, kind, size, 1))
            width, height, xhot, yhot, delay = values[4:]
            self.assertLess(xhot, width)
            self.assertLess(yhot, height)
            pixels = data[offset + 36:offset + 36 + width * height * 4]
            self.assertEqual(len(pixels), width * height * 4)
            for pixel, in struct.iter_unpack('<I', pixels):
                alpha = pixel >> 24
                self.assertLessEqual(max((pixel >> 16) & 255, (pixel >> 8) & 255, pixel & 255), alpha)
            result.append((size, xhot, yhot, delay, pixels))
        return result

    def test_native_cursor_has_distinct_frames_fixed_hotspot_and_three_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            art.render_cursor(root)
            base = root / 'usr/share/icons/OguzDowsTespih'
            self.assertIn('Inherits=Adwaita', (base / 'index.theme').read_text())
            for name in ('left_ptr', 'hand2', 'watch', 'left_ptr_watch'):
                frames = self.decode(base / 'cursors' / name)
                self.assertEqual(len(frames), 30)
                for size in (24, 32, 48):
                    selected = [frame for frame in frames if frame[0] == size]
                    self.assertEqual(len(selected), 10)
                    self.assertEqual(len({frame[1:4] for frame in selected}), 1)
                    self.assertEqual(len({frame[4] for frame in selected}), 10)
            self.assertEqual(len(self.decode(base / 'cursors/xterm')), 3)
            self.assertEqual((base / 'cursors/default').resolve(), (base / 'cursors/left_ptr').resolve())
            self.assertLess(sum(path.stat().st_size for path in (base / 'cursors').iterdir() if not path.is_symlink()), 1_000_000)
            art.render_cursor(root)  # İkinci derleme symlink veya kare biriktirmez.

    def test_bead_geometry_moves_while_pointer_tip_stays_fixed(self):
        frames = [art.cursor_frame(96, phase) for phase in range(10)]
        tips = {frame.crop((0, 0, 14, 36)).tobytes() for frame in frames}
        bead_masks = {frame.getchannel('A').crop((58, 12, 96, 96)).tobytes() for frame in frames}
        self.assertEqual(len(tips), 1)
        self.assertGreater(len(bead_masks), 5)

    @unittest.skipUnless(ctypes.util.find_library('Xcursor'), 'libXcursor yok; CI içinde gerçek okuyucu denenir')
    def test_native_libxcursor_can_read_all_ten_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            art.render_cursor(root)
            class Images(ctypes.Structure):
                _fields_ = [('nimage', ctypes.c_int), ('images', ctypes.c_void_p), ('name', ctypes.c_char_p)]
            library = ctypes.CDLL(ctypes.util.find_library('Xcursor'))
            library.XcursorFilenameLoadImages.argtypes = [ctypes.c_char_p, ctypes.c_int]
            library.XcursorFilenameLoadImages.restype = ctypes.POINTER(Images)
            library.XcursorImagesDestroy.argtypes = [ctypes.POINTER(Images)]
            for name in ('left_ptr', 'hand2', 'watch', 'left_ptr_watch', 'xterm'):
                images = library.XcursorFilenameLoadImages(str(root / 'usr/share/icons/OguzDowsTespih/cursors' / name).encode(), 32)
                self.assertTrue(images, name)
                try:
                    self.assertEqual(images.contents.nimage, 1 if name == 'xterm' else 10)
                finally:
                    library.XcursorImagesDestroy(images)


class LandscapeProvenanceTests(unittest.TestCase):
    def test_every_replacement_matches_provenance_and_logo_is_bottom_right_only(self):
        records = json.loads((ROOT / 'artwork/landscapes.json').read_text())
        self.assertEqual(len(records), 20)
        for item in records:
            path = ROOT / 'system/usr/share/backgrounds/oguzdows' / item['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['packaged_sha256'])
            self.assertIn('not a camera photograph', item['origin'])
            self.assertEqual(item['logo'], 'bottom-right')
        plain = Image.new('RGB', (1920, 1080), 'blue')
        branded = prepare.brand(plain)
        self.assertEqual(branded.crop((0, 0, 1400, 1080)).tobytes(), plain.crop((0, 0, 1400, 1080)).tobytes())
        self.assertEqual(branded.getpixel((1919, 1079)), plain.getpixel((1919, 1079)))
        self.assertNotEqual(branded.crop((1600, 976, 1884, 1048)).tobytes(), plain.crop((1600, 976, 1884, 1048)).tobytes())


if __name__ == '__main__':
    unittest.main()
