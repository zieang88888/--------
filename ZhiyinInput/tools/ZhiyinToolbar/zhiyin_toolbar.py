# -*- coding: utf-8 -*-
"""
知音输入法悬浮工具栏。

依赖 Python 3.10+ 标准库，提供中英、标点、语音、手写、输入方案、
皮肤、设置和工具箱入口。Ctrl+Alt+L 可在任意程序中显示或隐藏。
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from zhiyin_support import (  # noqa: E402
    get_rime_user_dir,
    redeploy_weasel,
    replace_color_scheme,
)


# Win32 constants
HWND_TOPMOST = -1
SW_SHOWNOACTIVATE = 4
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_OEM_PERIOD = 0xBE
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
GA_ROOT = 2

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\ZhiyinToolbar"
TOOLBAR_WINDOW_TITLE = "知音输入法工具栏"

HOTKEY_TOGGLE = 1
HOTKEY_VOICE = 2
HOTKEY_HANDWRITE = 3
HOTKEYS = (
    (HOTKEY_TOGGLE, 0x4C),    # Ctrl+Alt+L
    (HOTKEY_VOICE, 0x56),     # Ctrl+Alt+V
    (HOTKEY_HANDWRITE, 0x48), # Ctrl+Alt+H
)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [
    wt.HWND,
    ctypes.POINTER(wt.DWORD),
]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.IsWindow.argtypes = [wt.HWND]
user32.IsWindow.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [
    wt.HWND,
    wt.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wt.UINT,
]
user32.SetWindowPos.restype = wt.BOOL
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL


# Paths and configuration
APPDATA = Path(os.getenv("APPDATA", str(Path.home())))
PROGRAM_FILES = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
COMMON_PROGRAM_FILES = Path(
    os.getenv("CommonProgramFiles", r"C:\Program Files\Common Files")
)
PROJECT_DIR = Path(__file__).resolve().parents[2]
ZHIYIN_DIR = APPDATA / "Zhiyin"
RIME_DIR = get_rime_user_dir()
CONFIG_FILE = ZHIYIN_DIR / "zhiyin_toolbar.json"
SETTINGS_SCRIPT = (
    PROJECT_DIR / "tools" / "ZhiyinConfig" / "zhiyin_settings.py"
)
HANDWRITING_SCRIPT = (
    PROJECT_DIR
    / "tools"
    / "ZhiyinHandwriting"
    / "zhiyin_handwriting.py"
)
LOGO_32_PATH = PROJECT_DIR / "assets" / "branding" / "zhiyin-logo-32.png"
LOGO_64_PATH = PROJECT_DIR / "assets" / "branding" / "zhiyin-logo-64.png"
ZHIYIN_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "x": None,
    "y": None,
    "opacity": 0.96,
    "theme": "dark",
    "ascii_mode": False,
    "ascii_punct": False,
}

COLOR_SCHEMES = {
    "知音红": "zhiyin_red",
    "水墨灰": "ink_gray",
    "清透青": "cyber_cyan",
    "樱粉": "cherry_pink",
}


def set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def acquire_single_instance():
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle or kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def show_existing_instance():
    hwnd = user32.FindWindowW(None, TOOLBAR_WINDOW_TITLE)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )
    return True


def load_config():
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("toolbar config must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}

    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, value)
    return data


def save_config(config):
    try:
        CONFIG_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def weasel_running():
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq WeaselServer.exe"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return b"WeaselServer.exe" in (result.stdout or b"")
    except (OSError, subprocess.SubprocessError):
        return False


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
    # INPUT is sized to its largest union member. Omitting MOUSEINPUT makes
    # SendInput reject every event with an invalid cbSize on 64-bit Windows.
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


user32.SendInput.argtypes = [
    wt.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
]
user32.SendInput.restype = wt.UINT


def _keyboard_input(key, key_up=False):
    return INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(
            wVk=key,
            wScan=0,
            dwFlags=KEYEVENTF_KEYUP if key_up else 0,
            time=0,
            dwExtraInfo=0,
        ),
    )


def build_hotkey_inputs(modifiers, key):
    events = [_keyboard_input(modifier) for modifier in modifiers]
    events.append(_keyboard_input(key))
    events.append(_keyboard_input(key, key_up=True))
    events.extend(
        _keyboard_input(modifier, key_up=True)
        for modifier in reversed(modifiers)
    )
    return (INPUT * len(events))(*events)


def focus_input_window(target_hwnd):
    if not target_hwnd:
        return True
    if not user32.IsWindow(target_hwnd):
        return False
    if user32.GetForegroundWindow() == target_hwnd:
        return True
    if not user32.SetForegroundWindow(target_hwnd):
        return False
    return user32.GetForegroundWindow() == target_hwnd


def send_hotkey(modifiers, key, target_hwnd=None):
    """Send one exact key chord to the intended input window."""
    if not focus_input_window(target_hwnd):
        return False

    inputs = build_hotkey_inputs(modifiers, key)
    sent = user32.SendInput(
        len(inputs),
        inputs,
        ctypes.sizeof(INPUT),
    )
    return sent == len(inputs)


def launch_voice(target_hwnd=None):
    """Win+H is the supported Windows 10/11 voice typing entry point."""
    return send_hotkey([VK_LWIN], ord("H"), target_hwnd)


def pythonw_executable():
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    return candidate if candidate.exists() else executable


def launch_python_tool(script, *arguments):
    script = Path(script)
    if not script.exists():
        return False
    try:
        subprocess.Popen(
            [
                str(pythonw_executable()),
                str(script),
                *map(str, arguments),
            ],
            cwd=str(PROJECT_DIR),
        )
        return True
    except OSError:
        return False


def launch_handwrite(target_hwnd=None):
    arguments = ()
    if target_hwnd:
        arguments = ("--target", int(target_hwnd))
    if launch_python_tool(HANDWRITING_SCRIPT, *arguments):
        return True

    candidates = (
        COMMON_PROGRAM_FILES / "microsoft shared" / "ink" / "TabTip.exe",
        PROGRAM_FILES / "Common Files" / "microsoft shared" / "ink" / "TabTip.exe",
    )
    for executable in candidates:
        if executable.exists():
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


def launch_settings():
    return launch_python_tool(SETTINGS_SCRIPT)


def open_directory(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))
        return True
    except OSError:
        return False


def launch_wizard():
    script = PROJECT_DIR / "tools" / "ZhiyinWizard" / "zhiyin_wizard.py"
    try:
        subprocess.Popen([sys.executable, str(script), "--force"])
        return True
    except OSError:
        return False


def apply_color_scheme(scheme):
    """Update the effective color scheme without duplicating patch keys."""
    RIME_DIR.mkdir(parents=True, exist_ok=True)
    target = RIME_DIR / "weasel.custom.yaml"
    try:
        if target.exists():
            content = target.read_text(encoding="utf-8")
        else:
            content = "patch:\n"
        target.write_text(
            replace_color_scheme(content, scheme),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def start_hotkey_thread(event_queue, stop_event):
    """Register process-wide shortcuts without creating a custom Win32 class."""
    registered = []
    try:
        for hotkey_id, virtual_key in HOTKEYS:
            if user32.RegisterHotKey(
                None,
                hotkey_id,
                MOD_CONTROL | MOD_ALT | MOD_NOREPEAT,
                virtual_key,
            ):
                registered.append(hotkey_id)
            else:
                event_queue.put(("registration_error", hotkey_id))

        message = wt.MSG()
        while not stop_event.wait(0.05):
            while user32.PeekMessageW(
                ctypes.byref(message), None, 0, 0, PM_REMOVE
            ):
                if message.message == WM_HOTKEY:
                    event_queue.put(("hotkey", int(message.wParam)))
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
    finally:
        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)


class ZhiyinToolbar:
    """Always-on-top toolbar that does not take focus from the editor."""

    def __init__(self, root, config, initial_target=None):
        self.root = root
        self.config = config
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.visible = True
        self.is_dragging = False
        self.input_target_hwnd = initial_target

        root.title(TOOLBAR_WINDOW_TITLE)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", config["opacity"])
        try:
            root.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        root.update_idletasks()

        self.theme = config["theme"]
        self.bg = "#242424" if self.theme == "dark" else "#f4f4f4"
        self.fg = "#ffffff" if self.theme == "dark" else "#202020"
        self.hover = "#3b3b3b" if self.theme == "dark" else "#dedede"
        self.divider = "#505050" if self.theme == "dark" else "#cacaca"
        self.accent = "#c94f45"

        self.frame = tk.Frame(
            root,
            bg=self.bg,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.divider,
        )
        self.frame.pack()

        self.logo_image = None
        self.window_icon = None
        try:
            if LOGO_32_PATH.exists():
                self.logo_image = tk.PhotoImage(file=str(LOGO_32_PATH))
            if LOGO_64_PATH.exists():
                self.window_icon = tk.PhotoImage(file=str(LOGO_64_PATH))
                root.iconphoto(True, self.window_icon)
        except tk.TclError:
            self.logo_image = None
            self.window_icon = None

        brand_options = {
            "font": ("Microsoft YaHei UI", 10, "bold"),
            "cursor": "fleur",
        }
        if self.logo_image:
            brand_options.update(
                text="",
                image=self.logo_image,
                width=36,
                height=32,
                bg=self.bg,
            )
        else:
            brand_options.update(
                text="知音",
                width=5,
                height=1,
                bg=self.accent,
                fg="#ffffff",
            )
        self.brand = tk.Label(self.frame, **brand_options)
        self.brand.pack(
            side="left",
            padx=(0, 3),
            pady=0,
            ipady=0 if self.logo_image else 5,
        )
        self.brand.bind("<ButtonPress-1>", self._drag_start)
        self.brand.bind("<B1-Motion>", self._drag_move)
        self.brand.bind("<ButtonRelease-1>", self._drag_end)
        self._tooltip(self.brand, "按住拖动工具栏")

        self.buttons = {}
        items = (
            ("ascii", "中", "中英切换 (Ctrl+Shift+2)", self.cmd_ascii, 3),
            ("punct", "，", "中英标点 (Ctrl+.)", self.cmd_punct, 3),
            (None, None, None, None, 0),
            ("voice", "语", "系统语音 (Ctrl+Alt+V)", self.cmd_voice, 3),
            ("ink", "手", "系统手写 (Ctrl+Alt+H)", self.cmd_handwrite, 3),
            ("schema", "方案", "切换输入方案 (Ctrl+Shift+1)", self.cmd_schema, 4),
            ("skin", "色", "候选窗皮肤", self.cmd_skin, 3),
            (None, None, None, None, 0),
            ("settings", "设", "知音设置", self.cmd_settings, 3),
            ("toolbox", "箱", "工具箱", self.cmd_toolbox, 3),
            ("hide", "−", "隐藏 (Ctrl+Alt+L 唤出)", self.hide, 3),
        )
        for key, text, tooltip, command, width in items:
            if key is None:
                tk.Frame(self.frame, width=1, bg=self.divider).pack(
                    side="left", fill="y", padx=3, pady=7
                )
                continue
            self._add_button(key, text, tooltip, command, width)

        self._update_state_labels()
        self._apply_position()
        self._apply_window_style()
        self._restore_input_target()
        root.after(250, self._track_foreground_window)

        if not weasel_running():
            root.after(300, lambda: self.flash("小狼毫未运行，请先启动小狼毫"))

    def _add_button(self, key, text, tooltip, command, width):
        button = tk.Label(
            self.frame,
            text=text,
            width=width,
            height=1,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.bg,
            fg=self.fg,
            cursor="hand2",
        )
        button.pack(side="left", padx=1, pady=2, ipady=3)
        button.bind("<ButtonRelease-1>", lambda _event, action=command: action())
        button.bind(
            "<Enter>",
            lambda _event, widget=button: widget.configure(bg=self.hover),
            add="+",
        )
        button.bind(
            "<Leave>",
            lambda _event, widget=button: widget.configure(bg=self.bg),
            add="+",
        )
        self._tooltip(button, tooltip)
        self.buttons[key] = button

    def _hwnd(self):
        widget_hwnd = self.root.winfo_id()
        top_level = user32.GetAncestor(widget_hwnd, GA_ROOT)
        return int(top_level or widget_hwnd)

    @staticmethod
    def _is_own_window(hwnd):
        if not hwnd:
            return False
        process_id = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return process_id.value == os.getpid()

    def _track_foreground_window(self):
        foreground = user32.GetForegroundWindow()
        if (
            foreground
            and user32.IsWindow(foreground)
            and not self._is_own_window(foreground)
        ):
            self.input_target_hwnd = foreground
        try:
            self.root.after(250, self._track_foreground_window)
        except tk.TclError:
            pass

    def _input_target(self):
        foreground = user32.GetForegroundWindow()
        if (
            foreground
            and user32.IsWindow(foreground)
            and not self._is_own_window(foreground)
        ):
            self.input_target_hwnd = foreground
        if self.input_target_hwnd and user32.IsWindow(
            self.input_target_hwnd
        ):
            return self.input_target_hwnd
        return None

    def _restore_input_target(self):
        target = self._input_target()
        if target and user32.GetForegroundWindow() != target:
            user32.SetForegroundWindow(target)

    def after_hotkey_release(self, action, trigger_key, attempts=30):
        keys = (VK_CONTROL, VK_MENU, trigger_key)
        if any(user32.GetAsyncKeyState(key) & 0x8000 for key in keys):
            if attempts > 0:
                self.root.after(
                    25,
                    lambda: self.after_hotkey_release(
                        action,
                        trigger_key,
                        attempts - 1,
                    ),
                )
                return
        action()

    def _apply_window_style(self):
        try:
            hwnd = self._hwnd()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                style
                | WS_EX_LAYERED
                | WS_EX_TOOLWINDOW
                | WS_EX_TOPMOST
                | WS_EX_NOACTIVATE,
            )
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

            # Windows 11 rounded corners. Older systems ignore this attribute.
            corner_preference = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                33,
                ctypes.byref(corner_preference),
                ctypes.sizeof(corner_preference),
            )
        except OSError:
            pass

    def _apply_position(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = self.config["x"]
        y = self.config["y"]
        if x is None or y is None:
            x, y = (screen_width - width) // 2, 10

        x = max(0, min(int(x), max(0, screen_width - width)))
        y = max(0, min(int(y), max(0, screen_height - 40)))
        self.config["x"], self.config["y"] = x, y
        self.root.geometry(f"+{x}+{y}")

    def _tooltip(self, widget, text):
        popup = tk.Toplevel(self.root)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        tk.Label(
            popup,
            text=text,
            bg="#fff6df",
            fg="#252525",
            font=("Microsoft YaHei UI", 9),
            padx=7,
            pady=3,
            relief="solid",
            bd=1,
        ).pack()

        def show(event):
            popup.geometry(f"+{event.x_root + 12}+{event.y_root + 16}")
            popup.deiconify()

        def hide(_event):
            popup.withdraw()

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")

    def _drag_start(self, event):
        self.is_dragging = True
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        if not self.is_dragging:
            return
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")
        self.config["x"], self.config["y"] = x, y

    def _drag_end(self, _event):
        self.is_dragging = False
        save_config(self.config)

    def _update_state_labels(self):
        self.buttons["ascii"].configure(
            text="英" if self.config["ascii_mode"] else "中"
        )
        self.buttons["punct"].configure(
            text="," if self.config["ascii_punct"] else "，"
        )

    def flash(self, message):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        tk.Label(
            popup,
            text=message,
            bg=self.accent,
            fg="#ffffff",
            font=("Microsoft YaHei UI", 10),
            padx=14,
            pady=7,
        ).pack()
        popup.update_idletasks()
        x = popup.winfo_screenwidth() - popup.winfo_width() - 24
        y = 72
        popup.geometry(f"+{x}+{y}")
        popup.after(2800, popup.destroy)

    def toggle_visibility(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        self.root.deiconify()
        self.visible = True
        self.root.after_idle(self._apply_window_style)

    def hide(self):
        self.config["x"] = self.root.winfo_x()
        self.config["y"] = self.root.winfo_y()
        save_config(self.config)
        self.root.withdraw()
        self.visible = False

    def cmd_ascii(self):
        if send_hotkey(
            [VK_CONTROL, VK_SHIFT],
            ord("2"),
            self._input_target(),
        ):
            self.config["ascii_mode"] = not self.config["ascii_mode"]
            self._update_state_labels()
            save_config(self.config)
        else:
            self.flash("中英切换失败，请先点回输入框")

    def cmd_punct(self):
        if send_hotkey(
            [VK_CONTROL],
            VK_OEM_PERIOD,
            self._input_target(),
        ):
            self.config["ascii_punct"] = not self.config["ascii_punct"]
            self._update_state_labels()
            save_config(self.config)
        else:
            self.flash("标点切换失败，请先点回输入框")

    def cmd_voice(self):
        if not launch_voice(self._input_target()):
            self.flash("无法启动系统语音输入")

    def cmd_handwrite(self):
        if not launch_handwrite(self._input_target()):
            self.flash("系统手写面板不可用")

    def cmd_schema(self):
        if send_hotkey(
            [VK_CONTROL, VK_SHIFT],
            ord("1"),
            self._input_target(),
        ):
            self.flash("已切换到下一个输入方案")
        else:
            self.flash("方案切换失败，请先点回输入框")

    def cmd_skin(self):
        menu = tk.Menu(self.root, tearoff=0)
        for label, key in COLOR_SCHEMES.items():
            menu.add_command(
                label=label,
                command=lambda scheme=key, name=label: self._apply_skin(
                    scheme, name
                ),
            )
        try:
            menu.tk_popup(
                self.root.winfo_pointerx(),
                self.root.winfo_pointery(),
            )
        finally:
            menu.grab_release()

    def _apply_skin(self, scheme, label):
        if not apply_color_scheme(scheme):
            self.flash("写入配色失败")
            return
        if redeploy_weasel(PROJECT_DIR):
            self.flash(f"已应用“{label}”")
        else:
            self.flash(f"已选择“{label}”，请重新部署小狼毫")

    def cmd_settings(self):
        if not launch_settings():
            self.flash("知音设置启动失败")

    def cmd_toolbox(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="重新部署小狼毫", command=self._redeploy)
        menu.add_separator()
        menu.add_command(
            label="打开小狼毫用户目录",
            command=lambda: open_directory(RIME_DIR),
        )
        menu.add_command(
            label="打开知音配置目录",
            command=lambda: open_directory(ZHIYIN_DIR),
        )
        menu.add_command(label="重新运行新手引导", command=launch_wizard)
        menu.add_separator()
        menu.add_command(
            label="检查小狼毫状态",
            command=lambda: self.flash(
                "小狼毫正在运行" if weasel_running() else "小狼毫未运行"
            ),
        )
        menu.add_command(
            label="关于知音输入法",
            command=lambda: self.flash("知音输入法 v0.1"),
        )
        menu.add_command(label="退出工具栏", command=self.root.destroy)
        try:
            menu.tk_popup(
                self.root.winfo_pointerx(),
                self.root.winfo_pointery(),
            )
        finally:
            menu.grab_release()

    def _redeploy(self):
        self.flash(
            "正在重新部署小狼毫"
            if redeploy_weasel(PROJECT_DIR)
            else "未找到 WeaselDeployer.exe"
        )


def main():
    set_dpi_awareness()
    mutex = acquire_single_instance()
    if mutex is None:
        show_existing_instance()
        return

    initial_target = user32.GetForegroundWindow()
    config = load_config()
    event_queue = queue.Queue()
    stop_event = threading.Event()
    root = tk.Tk()
    app = ZhiyinToolbar(root, config, initial_target)
    app.show()

    threading.Thread(
        target=start_hotkey_thread,
        args=(event_queue, stop_event),
        daemon=True,
    ).start()

    def poll_events():
        try:
            while True:
                event_type, value = event_queue.get_nowait()
                if event_type == "hotkey":
                    if value == HOTKEY_TOGGLE:
                        app.toggle_visibility()
                    elif value == HOTKEY_VOICE:
                        app.after_hotkey_release(
                            app.cmd_voice,
                            ord("V"),
                        )
                    elif value == HOTKEY_HANDWRITE:
                        app.after_hotkey_release(
                            app.cmd_handwrite,
                            ord("H"),
                        )
                elif event_type == "registration_error":
                    app.flash(f"快捷键注册失败：{value}")
        except queue.Empty:
            pass
        root.after(100, poll_events)

    def on_close():
        app.config["x"] = root.winfo_x()
        app.config["y"] = root.winfo_y()
        save_config(app.config)
        stop_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    poll_events()
    try:
        root.mainloop()
    finally:
        stop_event.set()
        kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
