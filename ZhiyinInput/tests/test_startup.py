# -*- coding: utf-8 -*-

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

import start_zhiyin  # noqa: E402


class StartupTests(unittest.TestCase):
    def test_installation_requires_all_schemas_and_weasel_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            rime_dir = Path(temporary)
            self.assertFalse(start_zhiyin.installation_complete(rime_dir))

            for schema_id in start_zhiyin.KNOWN_SCHEMA_IDS:
                (rime_dir / f"{schema_id}.schema.yaml").write_text(
                    "schema:\n",
                    encoding="utf-8",
                )
            (rime_dir / "weasel.custom.yaml").write_text(
                "patch:\n",
                encoding="utf-8",
            )

            self.assertTrue(start_zhiyin.installation_complete(rime_dir))

    def test_first_run_file_is_used_when_registry_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "zhiyin_first_run.yaml"
            marker.write_text(
                "first_run_completed: true\n",
                encoding="utf-8",
            )

            with mock.patch.object(start_zhiyin, "FIRST_RUN_FILE", marker):
                with mock.patch("winreg.OpenKey", side_effect=FileNotFoundError):
                    self.assertTrue(start_zhiyin.first_run_completed())

    def test_dry_run_does_not_launch_programs(self):
        output = io.StringIO()
        with mock.patch.object(
            start_zhiyin,
            "get_rime_user_dir",
            return_value=Path("Rime"),
        ), mock.patch.object(
            start_zhiyin,
            "installation_complete",
            return_value=True,
        ), mock.patch.object(
            start_zhiyin,
            "first_run_completed",
            return_value=True,
        ), mock.patch.object(
            start_zhiyin,
            "start_toolbar",
        ) as start_toolbar, redirect_stdout(output):
            result = start_zhiyin.main(["--dry-run"])

        self.assertEqual(result, 0)
        self.assertIn("后台启动知音悬浮工具栏", output.getvalue())
        start_toolbar.assert_not_called()

    def test_brand_option_runs_elevated_branding_tool(self):
        with mock.patch.object(
            start_zhiyin,
            "get_rime_user_dir",
            return_value=Path("Rime"),
        ), mock.patch.object(
            start_zhiyin,
            "installation_complete",
            return_value=True,
        ), mock.patch.object(
            start_zhiyin,
            "first_run_completed",
            return_value=True,
        ), mock.patch.object(
            start_zhiyin,
            "run_branding",
            return_value=0,
        ) as run_branding, mock.patch.object(
            start_zhiyin,
            "start_toolbar",
        ) as start_toolbar:
            result = start_zhiyin.main(["--brand", "--no-toolbar"])

        self.assertEqual(result, 0)
        run_branding.assert_called_once_with()
        start_toolbar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
