# -*- coding: utf-8 -*-

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "tools"))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

from install_dev import install
from zhiyin_support import (
    COLOR_SCHEME_KEYS,
    KNOWN_SCHEMA_IDS,
    LEGACY_T9_SCHEMA_IDS,
    MANAGED_WEASEL_STYLE_KEYS,
    ensure_color_schemes,
    ensure_patch_entries,
    extract_schema_ids,
    replace_color_scheme,
    replace_schema_list,
    schema_list_with_preferred,
)


DEFAULT_CUSTOM = """\
customization:
  generator: test
patch:
  schema_list:
    - {schema: t9_pos}
    - schema: custom_schema
  "menu/page_size": 5
"""

WEASEL_CUSTOM = """\
customization:
  generator: test
patch:
  "style/color_scheme": android
  "style/font_face": "Microsoft YaHei UI"
"""


class ConfigurationTests(unittest.TestCase):
    def test_schema_replacement_preserves_other_settings(self):
        schema_ids = schema_list_with_preferred(
            DEFAULT_CUSTOM,
            ["zhiyin_t9"],
            ["zhiyin_full"],
        )
        updated = replace_schema_list(DEFAULT_CUSTOM, schema_ids)

        self.assertEqual(
            extract_schema_ids(updated),
            [
                "zhiyin_t9",
                "zhiyin_full",
                "t9_pos",
                "custom_schema",
            ],
        )
        self.assertIn('"menu/page_size": 5', updated)
        self.assertIn("generator: test", updated)

    def test_color_replacement_updates_existing_flat_patch(self):
        updated = replace_color_scheme(WEASEL_CUSTOM, "zhiyin_red")

        self.assertEqual(updated.count("style/color_scheme"), 1)
        self.assertIn('"style/color_scheme": zhiyin_red', updated)
        self.assertNotIn("android", updated)

    def test_color_replacement_updates_nested_style(self):
        content = "patch:\n  style:\n    color_scheme: android\n"
        updated = replace_color_scheme(content, "ink_gray")

        self.assertEqual(updated.count("color_scheme"), 1)
        self.assertIn("color_scheme: ink_gray", updated)

    def test_theme_merge_keeps_user_color(self):
        template = (
            PROJECT_DIR
            / "weasel"
            / "data"
            / "zhiyin.weasel.yaml"
        ).read_text(encoding="utf-8")
        updated = ensure_color_schemes(WEASEL_CUSTOM, template)

        self.assertIn('"style/color_scheme": android', updated)
        for scheme in COLOR_SCHEME_KEYS:
            self.assertEqual(
                updated.count(f"preset_color_schemes/{scheme}"),
                1,
            )
        self.assertIn("prevpage_color:", updated)
        self.assertIn("nextpage_color:", updated)

    def test_managed_weasel_style_is_updated_without_changing_theme(self):
        template = (
            PROJECT_DIR
            / "weasel"
            / "data"
            / "zhiyin.weasel.yaml"
        ).read_text(encoding="utf-8")
        updated = ensure_patch_entries(
            WEASEL_CUSTOM + '  "style/horizontal": false\n',
            template,
            MANAGED_WEASEL_STYLE_KEYS,
        )

        self.assertIn('"style/color_scheme": android', updated)
        self.assertIn('"style/horizontal": true', updated)
        self.assertEqual(updated.count("style/horizontal"), 1)
        self.assertIn('"style/layout/max_width": 0', updated)

    def test_installer_merges_existing_user_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            rime_dir = Path(temp_dir)
            default_target = rime_dir / "default.custom.yaml"
            weasel_target = rime_dir / "weasel.custom.yaml"
            default_target.write_text(DEFAULT_CUSTOM, encoding="utf-8")
            weasel_target.write_text(WEASEL_CUSTOM, encoding="utf-8")

            result = install(rime_dir, deploy=False)

            self.assertEqual(result["schema_count"], 4)
            self.assertEqual(result["lua_count"], 5)
            schema_ids = extract_schema_ids(
                default_target.read_text(encoding="utf-8")
            )
            self.assertEqual(schema_ids[0], "custom_schema")
            self.assertTrue(set(KNOWN_SCHEMA_IDS).issubset(schema_ids))
            self.assertFalse(set(LEGACY_T9_SCHEMA_IDS).intersection(schema_ids))
            self.assertIn(
                '"style/color_scheme": android',
                weasel_target.read_text(encoding="utf-8"),
            )
            self.assertIn(
                '"style/horizontal": true',
                weasel_target.read_text(encoding="utf-8"),
            )
            self.assertTrue(
                default_target.with_suffix(
                    ".yaml.zhiyin.bak"
                ).exists()
            )
            self.assertTrue(
                weasel_target.with_suffix(
                    ".yaml.zhiyin.bak"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
