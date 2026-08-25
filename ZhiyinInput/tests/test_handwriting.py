# -*- coding: utf-8 -*-

import ctypes
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(PROJECT_DIR / "tools" / "ZhiyinHandwriting"),
)


@unittest.skipUnless(sys.platform == "win32", "Windows-only handwriting tests")
class HandwritingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zhiyin_handwriting

        cls.handwriting = zhiyin_handwriting

    def test_input_structure_has_native_windows_size(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28

        self.assertEqual(ctypes.sizeof(self.handwriting.INPUT), expected)

    def test_chinese_recognizer_is_selected_by_language_id(self):
        gesture = SimpleNamespace(
            Languages=(),
            Name="Gesture",
        )
        chinese = SimpleNamespace(
            Languages=(4, 2052),
            Name="Chinese",
        )
        recognizers = SimpleNamespace(
            Count=2,
            Item=lambda index: (gesture, chinese)[index],
        )

        selected = self.handwriting.chinese_recognizer(
            lambda _name: recognizers
        )

        self.assertIs(selected, chinese)

    def test_candidate_values_are_unique_and_limited(self):
        values = self.handwriting.deduplicate_candidates(
            ["知", "知", "", "音", "输入"],
            limit=2,
        )

        self.assertEqual(values, ["知", "音"])

    def test_recognition_result_is_unwrapped_from_com_status_tuple(self):
        result = SimpleNamespace(TopString="知")

        self.assertIs(
            self.handwriting.unwrap_recognition_result((result, 0)),
            result,
        )

    def test_unicode_text_is_sent_as_key_down_and_key_up(self):
        user32 = mock.Mock()
        user32.SendInput.side_effect = (
            lambda count, _inputs, _size: count
        )

        with mock.patch.object(
            self.handwriting,
            "focus_window",
            return_value=True,
        ), mock.patch.object(
            self.handwriting,
            "user32",
            user32,
        ):
            sent = self.handwriting.send_unicode_text("知音", 123)

        self.assertTrue(sent)
        self.assertEqual(user32.SendInput.call_args.args[0], 4)


if __name__ == "__main__":
    unittest.main()
