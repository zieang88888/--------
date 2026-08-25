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


if __name__ == "__main__":
    unittest.main()
