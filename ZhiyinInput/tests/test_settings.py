# -*- coding: utf-8 -*-

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "tools" / "ZhiyinConfig"))

import zhiyin_settings as settings_module  # noqa: E402
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
                "home": "个人主页",
                "themes": "皮肤中心",
                "services": "扩展服务",
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

            settings.horizontal.set(not settings.horizontal.get())
            self.assertIsNotNone(settings.autosave_job)
            root.after_cancel(settings.autosave_job)
            settings.autosave_job = None
        finally:
            root.destroy()

    def test_setting_change_is_automatically_saved(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                base = Path(temp_dir)
                rime_dir = base / "rime"
                toolbar_config = base / "toolbar.json"
                with (
                    patch.object(settings_module, "RIME_DIR", rime_dir),
                    patch.object(
                        settings_module,
                        "TOOLBAR_CONFIG",
                        toolbar_config,
                    ),
                    patch.object(
                        settings_module,
                        "redeploy_weasel",
                        return_value=True,
                    ) as redeploy,
                ):
                    settings = SettingsWindow(root)
                    settings.page_size.set(5)
                    settings.theme.set("清透青")
                    settings.horizontal.set(False)

                    root.after(900, root.quit)
                    root.mainloop()

                    t9_config = (
                        rime_dir / "zhiyin_t9.custom.yaml"
                    ).read_text(encoding="utf-8")
                    appearance_config = (
                        rime_dir / "weasel.custom.yaml"
                    ).read_text(encoding="utf-8")
                    self.assertIn('"menu/page_size": 5', t9_config)
                    self.assertIn("cyber_cyan", appearance_config)
                    self.assertIn(
                        '"style/horizontal": false',
                        appearance_config,
                    )
                    self.assertEqual(settings.autosave_job, None)
                    self.assertEqual(
                        settings.status.get(),
                        "已自动保存并重新部署",
                    )
                    redeploy.assert_called_once_with(
                        settings_module.PROJECT_DIR
                    )
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
