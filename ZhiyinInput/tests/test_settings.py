# -*- coding: utf-8 -*-

import sys
import tkinter as tk
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "tools" / "ZhiyinConfig"))

from zhiyin_settings import (  # noqa: E402
    SettingsWindow,
    patch_scalar,
    update_patch_values,
)


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

    def test_all_settings_pages_render(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        try:
            settings = SettingsWindow(root)
            pages = {
                "common": "常用",
                "appearance": "外观",
                "dictionary": "词库",
                "keys": "按键",
                "advanced": "高级",
                "about": "关于知音",
            }
            for page_id, title in pages.items():
                settings.show_page(page_id)
                root.update_idletasks()
                self.assertEqual(settings.page_title.cget("text"), title)
                self.assertTrue(settings.body.winfo_children())
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
