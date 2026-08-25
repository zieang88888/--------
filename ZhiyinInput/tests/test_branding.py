# -*- coding: utf-8 -*-

import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
BRANDING_DIR = PROJECT_DIR / "assets" / "branding"


class BrandingAssetTests(unittest.TestCase):
    def test_expected_logo_files_exist(self):
        expected = {
            "zhiyin-logo.svg",
            "zhiyin.ico",
            *(f"zhiyin-logo-{size}.png" for size in (16, 32, 64, 128, 256, 512, 1024)),
        }

        self.assertTrue(expected.issubset({path.name for path in BRANDING_DIR.iterdir()}))

    def test_png_dimensions_and_key_colors(self):
        with Image.open(BRANDING_DIR / "zhiyin-logo-1024.png") as image:
            self.assertEqual(image.size, (1024, 1024))
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(image.getpixel((100, 512))[:3], (201, 79, 69))
            self.assertEqual(image.getpixel((450, 450))[:3], (36, 36, 36))
            self.assertEqual(image.getpixel((512, 512))[:3], (255, 248, 242))

    def test_windows_icon_contains_required_sizes(self):
        with Image.open(BRANDING_DIR / "zhiyin.ico") as image:
            sizes = image.info.get("sizes", set())

        self.assertTrue(
            {(16, 16), (32, 32), (48, 48), (256, 256)}.issubset(sizes)
        )


if __name__ == "__main__":
    unittest.main()
