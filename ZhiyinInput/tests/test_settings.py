# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "tools" / "ZhiyinConfig"))

from zhiyin_settings import patch_scalar, update_patch_values  # noqa: E402


class SettingsConfigurationTests(unittest.TestCase):
    def test_patch_scalar_reads_quoted_boolean_and_integer_values(self):
        content = """\
patch:
  "style/horizontal": false
  "style/font_point": 16
  "style/font_face": "Microsoft YaHei UI"
"""

        self.assertFalse(patch_scalar(content, "style/horizontal"))
        self.assertEqual(patch_scalar(content, "style/font_point"), 16)
        self.assertEqual(
            patch_scalar(content, "style/font_face"),
            "Microsoft YaHei UI",
        )

    def test_update_patch_values_preserves_unmanaged_configuration(self):
        content = """\
customization:
  generator: user
patch:
  "style/horizontal": false
  "unmanaged/value": keep
"""

        updated = update_patch_values(
            content,
            {
                "style/horizontal": True,
                "style/font_point": 14,
            },
        )

        self.assertEqual(updated.count("style/horizontal"), 1)
        self.assertIn('"style/horizontal": true', updated)
        self.assertIn('"style/font_point": 14', updated)
        self.assertIn('"unmanaged/value": keep', updated)
        self.assertIn("generator: user", updated)


if __name__ == "__main__":
    unittest.main()
