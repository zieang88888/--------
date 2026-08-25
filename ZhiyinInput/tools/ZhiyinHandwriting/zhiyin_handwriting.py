# -*- coding: utf-8 -*-
"""Native handwriting panel for Zhiyin Input Method."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
LOGO_PATH = PROJECT_DIR / "assets" / "branding" / "zhiyin-logo-64.png"
PROGRAM_FILES = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
COMMON_PROGRAM_FILES = Path(
    os.getenv("CommonProgramFiles", r"C:\Program Files\Common Files")
)

BG = "#f3f4f6"
PANEL = "#ffffff"
FG = "#202124"
MUTED = "#70757a"
BORDER = "#d9dde3"
ACCENT = "#d84a3a"

GA_ROOT = 2
SW_RESTORE = 9
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


ULONG_PTR = wt.WPARAM


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wt.DWORD),
        ("wParamL", wt.WORD),
        ("wParamH", wt.WORD),
    )


class INPUTUNION(ctypes.Union):
    _fields_ = (
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    )


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = (
        ("type", wt.DWORD),
        ("union", INPUTUNION),
    )


user32.GetForegroundWindow.restype = wt.HWND
user32.IsWindow.argtypes = [wt.HWND]
user32.IsWindow.restype = wt.BOOL
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [
    wt.HWND,
    ctypes.POINTER(wt.DWORD),
]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.AttachThreadInput.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.InvalidateRect.argtypes = [wt.HWND, ctypes.c_void_p, wt.BOOL]
user32.InvalidateRect.restype = wt.BOOL
user32.SendInput.argtypes = [
    wt.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
]
user32.SendInput.restype = wt.UINT


def set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def python_ink_modules():
    try:
        import pythoncom
        import win32com.client

        return pythoncom, win32com.client
    except ImportError:
        return None, None


def chinese_recognizer(dispatch):
    recognizers = dispatch("Msinkaut.InkRecognizers")
    for index in range(recognizers.Count):
        recognizer = recognizers.Item(index)
        if 2052 in tuple(recognizer.Languages):
            return recognizer
    return None


def recognizer_status():
    _pythoncom, client = python_ink_modules()
    if client is None:
        return False, "缺少 pywin32"
    try:
        recognizer = chinese_recognizer(client.Dispatch)
    except Exception as error:
        return False, str(error)
    if recognizer is None:
        return False, "未安装简体中文手写识别器"
    return True, recognizer.Name


def deduplicate_candidates(values, limit=8):
    result = []
    for value in values:
        value = str(value).strip()
        if value and value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result


def unwrap_recognition_result(value):
    if isinstance(value, tuple):
        return next(
            (
                item
                for item in value
                if hasattr(item, "TopString")
            ),
            None,
        )
    return value


def launch_system_handwriting():
    candidates = (
        COMMON_PROGRAM_FILES / "microsoft shared" / "ink" / "TabTip.exe",
        PROGRAM_FILES / "Common Files" / "microsoft shared" / "ink" / "TabTip.exe",
    )
    for executable in candidates:
        if not executable.exists():
            continue
        try:
            subprocess.Popen([str(executable)])
            return True
        except OSError:
            continue
    try:
        subprocess.Popen(["tabtip.exe"])
        return True
    except OSError:
        return False


def _keyboard_input(code_unit, key_up=False):
    flags = KEYEVENTF_UNICODE
    if key_up:
        flags |= KEYEVENTF_KEYUP
    return INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(
            wVk=0,
            wScan=code_unit,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        ),
    )


def focus_window(hwnd):
    if not hwnd or not user32.IsWindow(hwnd):
        return False

    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    foreground = user32.GetForegroundWindow()
    foreground_thread = (
        user32.GetWindowThreadProcessId(foreground, None)
        if foreground
        else 0
    )
    current_thread = kernel32.GetCurrentThreadId()
    attached = []
    try:
        for thread_id in (foreground_thread, target_thread):
            if (
                thread_id
                and thread_id != current_thread
                and user32.AttachThreadInput(
                    current_thread,
                    thread_id,
                    True,
                )
            ):
                attached.append(thread_id)
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return user32.GetForegroundWindow() == hwnd
    finally:
        for thread_id in reversed(attached):
            user32.AttachThreadInput(current_thread, thread_id, False)


def send_unicode_text(text, target_hwnd):
    if not text or not focus_window(target_hwnd):
        return False

    encoded = text.encode("utf-16-le")
    code_units = [
        int.from_bytes(encoded[index : index + 2], "little")
        for index in range(0, len(encoded), 2)
    ]
    events = []
    for code_unit in code_units:
        events.append(_keyboard_input(code_unit))
        events.append(_keyboard_input(code_unit, key_up=True))
    inputs = (INPUT * len(events))(*events)
    return (
        user32.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
        == len(inputs)
    )


class InkRecognizer:
    def __init__(self, hwnd):
        _pythoncom, client = python_ink_modules()
        if client is None:
            raise RuntimeError("请安装 pywin32 后使用知音手写")

        recognizer = chinese_recognizer(client.Dispatch)
        if recognizer is None:
            raise RuntimeError("系统未安装简体中文手写识别器")

        self.hwnd = int(hwnd)
        self.collector = client.Dispatch("Msinkaut.InkCollector")
        self.collector.hWnd = self.hwnd
        attributes = self.collector.DefaultDrawingAttributes
        attributes.Color = 0x262626
        attributes.Width = 90
        attributes.Height = 90
        attributes.AntiAliased = True
        self.collector.Enabled = True
        self.context = recognizer.CreateRecognizerContext()
        self.recognizer_name = recognizer.Name

    @property
    def stroke_count(self):
        return int(self.collector.Ink.Strokes.Count)

    def recognize(self, limit=8):
        if self.stroke_count == 0:
            return []
        self.context.Strokes = self.collector.Ink.Strokes
        result = unwrap_recognition_result(self.context.Recognize(0))
        if result is None:
            return []
        values = [result.TopString]
        alternates = result.AlternatesFromSelection(0, -1, limit)
        values.extend(
            alternates.Item(index).String
            for index in range(alternates.Count)
        )
        return deduplicate_candidates(values, limit)

    def clear(self):
        self.collector.Ink.DeleteStrokes()
        user32.InvalidateRect(self.hwnd, None, True)

    def undo(self):
        strokes = self.collector.Ink.Strokes
        if strokes.Count:
            self.collector.Ink.DeleteStroke(strokes.Item(strokes.Count - 1))
            user32.InvalidateRect(self.hwnd, None, True)

    def close(self):
        try:
            self.collector.Enabled = False
        except Exception:
            pass


class HandwritingWindow:
    def __init__(self, root, target_hwnd=None):
        self.root = root
        self.target_hwnd = int(target_hwnd or 0)
        self.ink = None
        self.last_stroke_count = 0
        self.recognition_job = None
        self.poll_job = None
        self.target_job = None
        self.status = tk.StringVar(value="正在启动简体中文手写识别")
        self.candidate_buttons = []

        root.title("知音手写输入")
        root.geometry("760x430")
        root.minsize(680, 390)
        root.configure(bg=BG)
        root.attributes("-topmost", True)
        self._set_icon()
        self._center()
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after_idle(self._initialize_ink)

    def _set_icon(self):
        try:
            if LOGO_PATH.exists():
                self.icon = tk.PhotoImage(file=str(LOGO_PATH))
                self.root.iconphoto(True, self.icon)
        except tk.TclError:
            self.icon = None

    def _center(self):
        self.root.update_idletasks()
        width, height = 760, 430
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, self.root.winfo_screenheight() - height - 90)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build(self):
        header = tk.Frame(self.root, bg="#242424", height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="知音手写",
            bg="#242424",
            fg="#ffffff",
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(side="left", padx=20)
        tk.Label(
            header,
            textvariable=self.status,
            bg="#242424",
            fg="#c7c7c7",
            font=("Microsoft YaHei UI", 9),
        ).pack(side="right", padx=20)

        candidates = tk.Frame(
            self.root,
            bg=PANEL,
            height=74,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        candidates.pack(fill="x", padx=18, pady=(16, 10))
        candidates.pack_propagate(False)
        self.candidate_frame = tk.Frame(candidates, bg=PANEL)
        self.candidate_frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._show_candidates([])

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.canvas = tk.Canvas(
            content,
            bg="#ffffff",
            highlightbackground=BORDER,
            highlightthickness=1,
            cursor="pencil",
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._draw_guides)

        controls = tk.Frame(content, bg=BG, width=132)
        controls.pack(side="right", fill="y", padx=(12, 0))
        controls.pack_propagate(False)
        self._button(controls, "退一笔", self.undo).pack(fill="x", pady=(0, 8))
        self._button(controls, "清空", self.clear).pack(fill="x", pady=(0, 8))
        self._button(
            controls,
            "系统手写",
            self.open_system_panel,
            secondary=True,
        ).pack(fill="x", pady=(12, 0))

    def _button(self, parent, text, command, secondary=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=PANEL if secondary else ACCENT,
            fg=FG if secondary else "#ffffff",
            activebackground="#eceff2" if secondary else "#bd3d31",
            activeforeground=FG if secondary else "#ffffff",
            relief="solid" if secondary else "flat",
            bd=1 if secondary else 0,
            highlightbackground=BORDER,
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=9,
            cursor="hand2",
        )

    def _draw_guides(self, _event=None):
        self.canvas.delete("guide")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        self.canvas.create_line(
            width // 2,
            12,
            width // 2,
            height - 12,
            fill="#e6e8eb",
            dash=(4, 6),
            tags="guide",
        )
        self.canvas.create_line(
            12,
            height // 2,
            width - 12,
            height // 2,
            fill="#e6e8eb",
            dash=(4, 6),
            tags="guide",
        )

    def _initialize_ink(self):
        self.root.update_idletasks()
        try:
            self.ink = InkRecognizer(self.canvas.winfo_id())
        except Exception as error:
            self.status.set(str(error))
            self._show_candidates([], "可点击“系统手写”使用 Windows 面板")
            return
        self.status.set(self.ink.recognizer_name)
        self.poll_job = self.root.after(100, self._poll_strokes)
        self.target_job = self.root.after(250, self._track_input_target)

    @staticmethod
    def _is_own_window(hwnd):
        process_id = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return process_id.value == os.getpid()

    def _track_input_target(self):
        foreground = user32.GetForegroundWindow()
        if (
            foreground
            and user32.IsWindow(foreground)
            and not self._is_own_window(foreground)
        ):
            self.target_hwnd = int(foreground)
        self.target_job = self.root.after(250, self._track_input_target)

    def _poll_strokes(self):
        if self.ink is None:
            return
        try:
            count = self.ink.stroke_count
        except Exception:
            self.status.set("手写识别组件已停止")
            return

        if count != self.last_stroke_count:
            self.last_stroke_count = count
            if self.recognition_job is not None:
                self.root.after_cancel(self.recognition_job)
            self.recognition_job = (
                self.root.after(450, self.recognize)
                if count
                else None
            )
        self.poll_job = self.root.after(100, self._poll_strokes)

    def recognize(self):
        self.recognition_job = None
        if self.ink is None or not self.ink.stroke_count:
            self._show_candidates([])
            return
        try:
            values = self.ink.recognize()
        except Exception as error:
            self.status.set(f"识别失败：{error}")
            return
        self._show_candidates(values)
        self.status.set("点击候选文字即可输入")

    def _show_candidates(self, values, empty_text="请在下方书写"):
        for widget in self.candidate_frame.winfo_children():
            widget.destroy()
        self.candidate_buttons = []
        if not values:
            tk.Label(
                self.candidate_frame,
                text=empty_text,
                bg=PANEL,
                fg=MUTED,
                font=("Microsoft YaHei UI", 10),
            ).pack(side="left", padx=8)
            return
        for value in values:
            button = tk.Button(
                self.candidate_frame,
                text=value,
                command=lambda text=value: self.commit(text),
                bg=PANEL,
                fg=FG,
                activebackground="#f7e8e5",
                activeforeground=ACCENT,
                bd=0,
                font=("Microsoft YaHei UI", 18),
                padx=13,
                pady=4,
                cursor="hand2",
            )
            button.pack(side="left")
            self.candidate_buttons.append(button)

    def commit(self, text):
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            self.status.set("请先在目标程序中点一下输入框")
            return
        if not send_unicode_text(text, self.target_hwnd):
            self.status.set("未能写入目标输入框，请重新点击输入位置")
            return
        self.clear()
        self.status.set(f"已输入：{text}")

    def undo(self):
        if self.ink is None:
            return
        try:
            self.ink.undo()
            self.last_stroke_count = self.ink.stroke_count
            self.recognize()
        except Exception as error:
            self.status.set(f"撤销失败：{error}")

    def clear(self):
        if self.recognition_job is not None:
            self.root.after_cancel(self.recognition_job)
            self.recognition_job = None
        if self.ink is not None:
            try:
                self.ink.clear()
            except Exception as error:
                self.status.set(f"清空失败：{error}")
                return
        self.last_stroke_count = 0
        self._draw_guides()
        self._show_candidates([])

    def open_system_panel(self):
        self.status.set(
            "已打开 Windows 手写面板"
            if launch_system_handwriting()
            else "Windows 手写面板启动失败"
        )

    def close(self):
        if self.recognition_job is not None:
            self.root.after_cancel(self.recognition_job)
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
        if self.target_job is not None:
            self.root.after_cancel(self.target_job)
        if self.ink is not None:
            self.ink.close()
        self.root.destroy()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="知音输入法手写面板")
    parser.add_argument("--target", type=int, default=0)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    available, description = recognizer_status()
    if args.check:
        print(
            f"简体中文手写识别：{'可用' if available else '不可用'}"
            f"（{description}）"
        )
        return 0 if available else 1

    set_dpi_awareness()
    target = args.target or user32.GetForegroundWindow()
    root = tk.Tk()
    HandwritingWindow(root, target)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
