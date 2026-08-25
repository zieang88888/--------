# -*- coding: utf-8 -*-

import ctypes
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "tools" / "ZhiyinToolbar"))


@unittest.skipUnless(sys.platform == "win32", "Windows-only toolbar tests")
class ToolbarWin32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zhiyin_toolbar

        cls.toolbar = zhiyin_toolbar

    def test_input_structure_has_native_windows_size(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28

        self.assertEqual(ctypes.sizeof(self.toolbar.INPUT), expected)

    def test_existing_toolbar_is_shown_without_stealing_focus(self):
        user32 = mock.Mock()
        user32.FindWindowW.return_value = 123

        with mock.patch.object(self.toolbar, "user32", user32):
            self.assertTrue(self.toolbar.show_existing_instance())

        user32.FindWindowW.assert_called_once_with(
            None,
            self.toolbar.TOOLBAR_WINDOW_TITLE,
        )
        user32.ShowWindow.assert_called_once_with(
            123,
            self.toolbar.SW_SHOWNOACTIVATE,
        )
        user32.SetWindowPos.assert_called_once_with(
            123,
            self.toolbar.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            (
                self.toolbar.SWP_NOMOVE
                | self.toolbar.SWP_NOSIZE
                | self.toolbar.SWP_NOACTIVATE
            ),
        )

    def test_missing_toolbar_window_is_not_reported_as_shown(self):
        user32 = mock.Mock()
        user32.FindWindowW.return_value = 0

        with mock.patch.object(self.toolbar, "user32", user32):
            self.assertFalse(self.toolbar.show_existing_instance())

        user32.ShowWindow.assert_not_called()

    def test_duplicate_startup_shows_the_existing_toolbar(self):
        with mock.patch.object(
            self.toolbar,
            "set_dpi_awareness",
        ), mock.patch.object(
            self.toolbar,
            "acquire_single_instance",
            return_value=None,
        ), mock.patch.object(
            self.toolbar,
            "show_existing_instance",
        ) as show_existing:
            self.toolbar.main()

        show_existing.assert_called_once_with()

    def test_punctuation_chord_is_ctrl_period(self):
        events = self.toolbar.build_hotkey_inputs(
            [self.toolbar.VK_CONTROL],
            self.toolbar.VK_OEM_PERIOD,
        )

        self.assertEqual(len(events), 4)
        self.assertEqual(events[0].ki.wVk, self.toolbar.VK_CONTROL)
        self.assertEqual(events[0].ki.dwFlags, 0)
        self.assertEqual(events[1].ki.wVk, self.toolbar.VK_OEM_PERIOD)
        self.assertEqual(events[1].ki.dwFlags, 0)
        self.assertEqual(events[2].ki.wVk, self.toolbar.VK_OEM_PERIOD)
        self.assertEqual(
            events[2].ki.dwFlags,
            self.toolbar.KEYEVENTF_KEYUP,
        )
        self.assertEqual(events[3].ki.wVk, self.toolbar.VK_CONTROL)
        self.assertEqual(
            events[3].ki.dwFlags,
            self.toolbar.KEYEVENTF_KEYUP,
        )

    def test_modifier_keys_are_released_in_reverse_order(self):
        events = self.toolbar.build_hotkey_inputs(
            [self.toolbar.VK_CONTROL, self.toolbar.VK_SHIFT],
            ord("1"),
        )

        self.assertEqual(
            [event.ki.wVk for event in events],
            [
                self.toolbar.VK_CONTROL,
                self.toolbar.VK_SHIFT,
                ord("1"),
                ord("1"),
                self.toolbar.VK_SHIFT,
                self.toolbar.VK_CONTROL,
            ],
        )
        self.assertEqual(
            [event.ki.dwFlags for event in events],
            [
                0,
                0,
                0,
                self.toolbar.KEYEVENTF_KEYUP,
                self.toolbar.KEYEVENTF_KEYUP,
                self.toolbar.KEYEVENTF_KEYUP,
            ],
        )

    def test_weasel_process_check_uses_raw_tasklist_bytes(self):
        completed = SimpleNamespace(
            stdout=b"WeaselServer.exe  123 Console",
        )

        with mock.patch.object(
            self.toolbar.subprocess,
            "run",
            return_value=completed,
        ) as run:
            self.assertTrue(self.toolbar.weasel_running())

        self.assertNotIn("text", run.call_args.kwargs)

    def test_handwriting_panel_receives_original_input_window(self):
        with mock.patch.object(
            self.toolbar,
            "launch_python_tool",
            return_value=True,
        ) as launch:
            self.assertTrue(self.toolbar.launch_handwrite(321))

        launch.assert_called_once_with(
            self.toolbar.HANDWRITING_SCRIPT,
            "--target",
            321,
        )

    def test_settings_button_launches_graphical_settings(self):
        with mock.patch.object(
            self.toolbar,
            "launch_python_tool",
            return_value=True,
        ) as launch:
            self.assertTrue(self.toolbar.launch_settings())

        launch.assert_called_once_with(self.toolbar.SETTINGS_SCRIPT)


if __name__ == "__main__":
    unittest.main()
