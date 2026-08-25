# -*- coding: utf-8 -*-
"""Graphical settings center for Zhiyin Input Method."""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

TOOLS_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from zhiyin_support import (  # noqa: E402
    KNOWN_SCHEMA_IDS,
    backup_once,
    ensure_patch_entries,
    extract_schema_ids,
    get_rime_user_dir,
    redeploy_weasel,
    replace_color_scheme,
    replace_schema_list,
    schema_list_with_preferred,
)


RIME_DIR = get_rime_user_dir()
APPDATA = Path(os.getenv("APPDATA", str(Path.home())))
TOOLBAR_CONFIG = APPDATA / "Zhiyin" / "zhiyin_toolbar.json"
LOGO_PATH = PROJECT_DIR / "assets" / "branding" / "zhiyin-logo-64.png"
SETTINGS_WINDOW_TITLE = "知音输入法设置"

ACCENT = "#ff654f"
ACCENT_DARK = "#e95240"
ACCENT_SOFT = "#ffede8"
SIDEBAR = "#f6f7fb"
SIDEBAR_HOVER = "#eef0f5"
BG = "#ffffff"
PANEL = "#ffffff"
FG = "#22252a"
MUTED = "#7a8089"
BORDER = "#e5e7eb"

SCHEMAS = (
    ("知音九键", "zhiyin_t9"),
    ("知音九键·位置", "zhiyin_t9_pos"),
    ("知音全拼", "zhiyin_full"),
    ("知音双拼", "zhiyin_double"),
)
SCHEMA_LABELS = {schema_id: label for label, schema_id in SCHEMAS}
SCHEMA_IDS = {label: schema_id for label, schema_id in SCHEMAS}

THEMES = (
    ("知音红", "zhiyin_red", "#c94f45"),
    ("水墨灰", "ink_gray", "#575757"),
    ("清透青", "cyber_cyan", "#19b8cf"),
    ("樱粉", "cherry_pink", "#e88ca7"),
)
THEME_LABELS = {key: label for label, key, _color in THEMES}
THEME_KEYS = {label: key for label, key, _color in THEMES}

FONTS = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "SimSun",
    "SimHei",
    "DengXian",
)


def read_text(path, default="patch:\n"):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


def patch_scalar(content, key, default=None):
    pattern = re.compile(
        rf'(?m)^\s{{2}}(?:"{re.escape(key)}"|{re.escape(key)})'
        r"\s*:\s*(.*?)\s*(?:#.*)?$"
    )
    match = pattern.search(content)
    if not match:
        return default
    value = match.group(1).strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def yaml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def update_patch_values(content, values):
    template_lines = ["patch:"]
    for key, value in values.items():
        template_lines.append(f'  "{key}": {yaml_scalar(value)}')
    template = "\n".join(template_lines) + "\n"
    return ensure_patch_entries(content, template, tuple(values))


def load_toolbar_config():
    try:
        value = json.loads(TOOLBAR_CONFIG.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def save_toolbar_config(values):
    config = load_toolbar_config()
    config.update(values)
    TOOLBAR_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    TOOLBAR_CONFIG.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def current_values():
    default_content = read_text(RIME_DIR / "default.custom.yaml")
    schema_ids = extract_schema_ids(default_content)
    schema_id = next(
        (item for item in schema_ids if item in KNOWN_SCHEMA_IDS),
        "zhiyin_t9",
    )

    t9_content = read_text(RIME_DIR / "zhiyin_t9.custom.yaml")
    weasel_content = read_text(RIME_DIR / "weasel.custom.yaml")
    toolbar = load_toolbar_config()
    return {
        "schema": schema_id,
        "page_size": patch_scalar(t9_content, "menu/page_size", 7),
        "horizontal": patch_scalar(
            weasel_content,
            "style/horizontal",
            True,
        ),
        "theme": patch_scalar(
            weasel_content,
            "style/color_scheme",
            "zhiyin_red",
        ),
        "font_face": patch_scalar(
            weasel_content,
            "style/font_face",
            "Microsoft YaHei UI",
        ),
        "font_point": patch_scalar(
            weasel_content,
            "style/font_point",
            13,
        ),
        "opacity": float(toolbar.get("opacity", 0.96)),
    }


def launch_script(relative_path, *arguments):
    script = PROJECT_DIR / relative_path
    if not script.exists():
        return False
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        executable = pythonw
    try:
        subprocess.Popen(
            [str(executable), str(script), *map(str, arguments)],
            cwd=str(PROJECT_DIR),
        )
        return True
    except OSError:
        return False


def show_existing_settings():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, SETTINGS_WINDOW_TITLE)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return True
    except (AttributeError, OSError):
        return False


class ToggleSwitch(tk.Canvas):
    """Compact switch control backed by a BooleanVar."""

    def __init__(self, parent, variable):
        super().__init__(
            parent,
            width=40,
            height=22,
            bg=PANEL,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.variable = variable
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        self._draw()

    def _draw(self):
        self.delete("all")
        active = bool(self.variable.get())
        color = ACCENT if active else "#c8ccd2"
        self.create_oval(1, 2, 19, 20, fill=color, outline=color)
        self.create_oval(21, 2, 39, 20, fill=color, outline=color)
        self.create_rectangle(10, 2, 30, 20, fill=color, outline=color)
        knob_x = 29 if active else 11
        self.create_oval(
            knob_x - 7,
            4,
            knob_x + 7,
            18,
            fill="#ffffff",
            outline="#ffffff",
        )


class SegmentedControl(tk.Frame):
    """Text choices rendered as a compact segmented selector."""

    def __init__(self, parent, variable, choices, width=7):
        super().__init__(
            parent,
            bg=BORDER,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.variable = variable
        self.buttons = []
        for label, value in choices:
            button = tk.Button(
                self,
                text=label,
                width=width,
                bg=PANEL,
                fg=FG,
                activebackground=ACCENT_SOFT,
                activeforeground=ACCENT,
                bd=0,
                relief="flat",
                font=("Microsoft YaHei UI", 9),
                cursor="hand2",
                command=lambda selected=value: self._select(selected),
            )
            button.pack(side="left", padx=(0, 1))
            self.buttons.append((button, value))
        self._refresh()

    def _select(self, value):
        self.variable.set(value)
        self._refresh()

    def _refresh(self):
        selected = self.variable.get()
        for button, value in self.buttons:
            active = selected == value
            button.configure(
                bg=ACCENT_SOFT if active else PANEL,
                fg=ACCENT if active else FG,
                font=(
                    "Microsoft YaHei UI",
                    9,
                    "bold" if active else "normal",
                ),
            )


class SettingsWindow:
    def __init__(self, root):
        self.root = root
        values = current_values()

        self.schema = tk.StringVar(
            value=SCHEMA_LABELS.get(values["schema"], "知音九键")
        )
        self.page_size = tk.IntVar(value=values["page_size"])
        self.horizontal = tk.BooleanVar(value=values["horizontal"])
        self.theme = tk.StringVar(
            value=THEME_LABELS.get(values["theme"], "知音红")
        )
        self.font_face = tk.StringVar(value=values["font_face"])
        self.font_point = tk.IntVar(value=values["font_point"])
        self.opacity = tk.DoubleVar(value=values["opacity"])
        self.status = tk.StringVar(value="已加载当前配置")
        self.active_page = None
        self.nav_buttons = {}
        self.group_row_counts = {}
        self.theme_items = []

        root.title(SETTINGS_WINDOW_TITLE)
        root.geometry("1040x680")
        root.minsize(920, 620)
        root.configure(bg=BG)
        self._set_icon()
        self._center()
        self._configure_styles()
        self._build_shell()
        self.show_page("common")

    def _set_icon(self):
        self.icon = None
        self.brand_icon = None
        try:
            if LOGO_PATH.exists():
                self.icon = tk.PhotoImage(file=str(LOGO_PATH))
                self.root.iconphoto(True, self.icon)
                self.brand_icon = self.icon.subsample(2, 2)
        except tk.TclError:
            self.icon = None
            self.brand_icon = None

    def _center(self):
        self.root.update_idletasks()
        width, height = 1040, 680
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2 - 12)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure(
            "Zhiyin.TCombobox",
            font=("Microsoft YaHei UI", 10),
            padding=(8, 6),
        )

    def _build_shell(self):
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, bg=SIDEBAR, width=190)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR, height=86)
        brand.pack(fill="x")
        brand.pack_propagate(False)
        brand_inner = tk.Frame(brand, bg=SIDEBAR)
        brand_inner.pack(anchor="w", padx=26, pady=(22, 0))
        if self.brand_icon is not None:
            tk.Label(
                brand_inner,
                image=self.brand_icon,
                bg=SIDEBAR,
                bd=0,
            ).pack(side="left", padx=(0, 9))
        else:
            tk.Label(
                brand_inner,
                text="知",
                bg=ACCENT,
                fg="#ffffff",
                font=("Microsoft YaHei UI", 11, "bold"),
                width=2,
                pady=3,
            ).pack(side="left", padx=(0, 9))
        tk.Label(
            brand_inner,
            text="知音输入法",
            bg=SIDEBAR,
            fg=FG,
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(side="left")

        tk.Label(
            self.sidebar,
            text="属性设置",
            bg=SIDEBAR,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=32, pady=(8, 6))

        for page_id, label in (
            ("common", "常用"),
            ("appearance", "外观"),
            ("dictionary", "词库"),
            ("keys", "按键"),
            ("advanced", "高级"),
        ):
            self._add_nav_button(page_id, label)

        separator = tk.Frame(self.sidebar, bg="#e8eaf0", height=1)
        separator.pack(fill="x", padx=25, pady=(13, 10))
        self._add_nav_button("about", "关于知音")

        tk.Label(
            self.sidebar,
            text="v0.1",
            bg=SIDEBAR,
            fg="#a0a5ad",
            font=("Microsoft YaHei UI", 8),
        ).pack(side="bottom", anchor="w", padx=32, pady=18)

        content = tk.Frame(shell, bg=PANEL)
        content.pack(side="left", fill="both", expand=True)

        self.header = tk.Frame(content, bg=PANEL, height=92)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)
        self.page_title = tk.Label(
            self.header,
            text="",
            bg=PANEL,
            fg=FG,
            font=("Microsoft YaHei UI", 23, "bold"),
        )
        self.page_title.pack(anchor="w", padx=52, pady=(29, 0))

        footer = tk.Frame(content, bg=PANEL, height=62)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.status,
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", padx=52)
        self.apply_button = tk.Button(
            footer,
            text="应用",
            bg=ACCENT,
            fg="#ffffff",
            activebackground=ACCENT_DARK,
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            width=10,
            pady=8,
            font=("Microsoft YaHei UI", 10),
            cursor="hand2",
            command=self.apply,
        )
        self.apply_button.pack(side="right", padx=(8, 30), pady=12)
        tk.Button(
            footer,
            text="关闭",
            bg=PANEL,
            fg=FG,
            activebackground=SIDEBAR_HOVER,
            activeforeground=FG,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
            relief="flat",
            width=9,
            pady=7,
            font=("Microsoft YaHei UI", 10),
            cursor="hand2",
            command=self.root.destroy,
        ).pack(side="right", pady=12)

        page_host = tk.Frame(content, bg=PANEL)
        page_host.pack(fill="both", expand=True)
        self.body_canvas = tk.Canvas(
            page_host,
            bg=PANEL,
            bd=0,
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(
            page_host,
            orient="vertical",
            command=self.body_canvas.yview,
        )
        self.body_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.body_canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.body_canvas, bg=PANEL)
        self.body_window = self.body_canvas.create_window(
            (0, 0),
            window=self.body,
            anchor="nw",
        )
        self.body.bind("<Configure>", self._update_scroll_region)
        self.body_canvas.bind("<Configure>", self._resize_body)
        self.body_canvas.bind("<Enter>", self._bind_mousewheel)
        self.body_canvas.bind("<Leave>", self._unbind_mousewheel)

    def _add_nav_button(self, page_id, label):
        button = tk.Button(
            self.sidebar,
            text=label,
            anchor="w",
            bg=SIDEBAR,
            fg=FG,
            activebackground=SIDEBAR_HOVER,
            activeforeground=FG,
            bd=0,
            relief="flat",
            font=("Microsoft YaHei UI", 10),
            padx=24,
            pady=8,
            cursor="hand2",
            command=lambda selected=page_id: self.show_page(selected),
        )
        button.pack(fill="x", padx=18, pady=1)
        self.nav_buttons[page_id] = button

    def _update_scroll_region(self, _event=None):
        self.body_canvas.configure(
            scrollregion=self.body_canvas.bbox("all")
        )

    def _resize_body(self, event):
        self.body_canvas.itemconfigure(self.body_window, width=event.width)

    def _bind_mousewheel(self, _event=None):
        self.body_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self.body_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.body_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _clear_body(self):
        for widget in self.body.winfo_children():
            widget.destroy()
        self.group_row_counts.clear()
        self.theme_items = []
        self.body_canvas.yview_moveto(0)

    def _section(self, title):
        tk.Label(
            self.body,
            text=title,
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=52, pady=(5, 8))
        group = tk.Frame(
            self.body,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        group.pack(fill="x", padx=52, pady=(0, 20))
        self.group_row_counts[group] = 0
        return group

    def _row(self, group, label, help_text="", height=None):
        if self.group_row_counts.get(group, 0):
            tk.Frame(group, bg=BORDER, height=1).pack(
                fill="x",
                padx=16,
            )
        row_height = height or (66 if help_text else 52)
        row = tk.Frame(group, bg=PANEL, height=row_height)
        row.pack(fill="x")
        row.pack_propagate(False)
        text = tk.Frame(row, bg=PANEL)
        text.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(20, 12),
        )
        tk.Label(
            text,
            text=label,
            bg=PANEL,
            fg=FG,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(12 if help_text else 15, 0))
        if help_text:
            tk.Label(
                text,
                text=help_text,
                bg=PANEL,
                fg=MUTED,
                justify="left",
                wraplength=500,
                font=("Microsoft YaHei UI", 8),
            ).pack(anchor="w", pady=(3, 0))
        self.group_row_counts[group] = (
            self.group_row_counts.get(group, 0) + 1
        )
        return row

    def _value(self, row, text, accent=False):
        tk.Label(
            row,
            text=text,
            bg=PANEL,
            fg=ACCENT if accent else MUTED,
            font=(
                "Microsoft YaHei UI",
                9,
                "bold" if accent else "normal",
            ),
        ).pack(side="right", padx=20)

    def _action_button(self, row, label, command, primary=False):
        button = tk.Button(
            row,
            text=label,
            command=command,
            bg=ACCENT if primary else PANEL,
            fg="#ffffff" if primary else ACCENT,
            activebackground=ACCENT_DARK if primary else ACCENT_SOFT,
            activeforeground="#ffffff" if primary else ACCENT,
            highlightbackground=ACCENT,
            highlightthickness=1 if not primary else 0,
            bd=0,
            relief="flat",
            padx=13,
            pady=5,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
        )
        button.pack(side="right", padx=20)
        return button

    def show_page(self, page_id):
        self.active_page = page_id
        for key, button in self.nav_buttons.items():
            active = key == page_id
            button.configure(
                bg=ACCENT_SOFT if active else SIDEBAR,
                fg=ACCENT if active else FG,
                activebackground=(
                    ACCENT_SOFT if active else SIDEBAR_HOVER
                ),
                activeforeground=ACCENT if active else FG,
                font=(
                    "Microsoft YaHei UI",
                    10,
                    "bold" if active else "normal",
                ),
            )
        self._clear_body()
        {
            "common": self._render_common,
            "appearance": self._render_appearance,
            "dictionary": self._render_dictionary,
            "keys": self._render_keys,
            "advanced": self._render_advanced,
            "about": self._render_about,
        }[page_id]()
        self._update_scroll_region()

    def _render_common(self):
        self.page_title.configure(text="常用")

        group = self._section("默认状态")
        row = self._row(group, "默认输入方案")
        ttk.Combobox(
            row,
            textvariable=self.schema,
            values=[label for label, _schema_id in SCHEMAS],
            state="readonly",
            width=20,
            style="Zhiyin.TCombobox",
        ).pack(side="right", padx=20)

        row = self._row(group, "横向排列候选")
        ToggleSwitch(row, self.horizontal).pack(side="right", padx=20)

        group = self._section("候选设置")
        row = self._row(group, "每页候选数量")
        SegmentedControl(
            row,
            self.page_size,
            (("5 个", 5), ("7 个", 7), ("9 个", 9)),
            width=6,
        ).pack(side="right", padx=20)

        row = self._row(
            group,
            "九键输入",
            "数字小键盘与主键盘数字均可输入九键编码",
        )
        self._value(row, "已启用", accent=True)

        group = self._section("小键盘操作")
        for label, value in (
            ("候选与拼音切换", "/  和  *"),
            ("候选翻页", "-  和  +"),
            ("上屏首选", "Enter"),
            ("继续输入", "数字键 0-9"),
        ):
            row = self._row(group, label)
            self._value(row, value)

    def _theme_selector(self, parent):
        selector = tk.Frame(parent, bg=PANEL)
        selector.pack(side="right", padx=18)
        for label, _key, color in THEMES:
            item = tk.Frame(
                selector,
                bg=PANEL,
                width=88,
                height=48,
                highlightbackground=BORDER,
                highlightthickness=1,
                cursor="hand2",
            )
            item.pack(side="left", padx=3)
            item.pack_propagate(False)
            swatch = tk.Canvas(
                item,
                width=18,
                height=18,
                bg=PANEL,
                highlightthickness=0,
                cursor="hand2",
            )
            swatch.create_oval(2, 2, 16, 16, fill=color, outline="")
            swatch.pack(side="left", padx=(10, 4))
            text = tk.Label(
                item,
                text=label,
                bg=PANEL,
                fg=FG,
                font=("Microsoft YaHei UI", 8),
                cursor="hand2",
            )
            text.pack(side="left")
            for widget in (item, swatch, text):
                widget.bind(
                    "<Button-1>",
                    lambda _event, value=label: self._select_theme(value),
                )
            self.theme_items.append((item, swatch, text, label))
        self._refresh_themes()

    def _select_theme(self, value):
        self.theme.set(value)
        self._refresh_themes()

    def _refresh_themes(self):
        selected = self.theme.get()
        for item, swatch, text, label in self.theme_items:
            active = selected == label
            background = ACCENT_SOFT if active else PANEL
            item.configure(
                bg=background,
                highlightbackground=ACCENT if active else BORDER,
                highlightthickness=2 if active else 1,
            )
            swatch.configure(bg=background)
            text.configure(
                bg=background,
                fg=ACCENT if active else FG,
            )

    def _render_appearance(self):
        self.page_title.configure(text="外观")

        group = self._section("候选窗口")
        row = self._row(group, "配色方案", height=72)
        self._theme_selector(row)

        row = self._row(group, "候选字体")
        ttk.Combobox(
            row,
            textvariable=self.font_face,
            values=FONTS,
            width=22,
            style="Zhiyin.TCombobox",
        ).pack(side="right", padx=20)

        row = self._row(group, "候选字号")
        tk.Spinbox(
            row,
            from_=10,
            to=24,
            textvariable=self.font_point,
            width=8,
            justify="center",
            font=("Microsoft YaHei UI", 10),
        ).pack(side="right", padx=20)

        group = self._section("悬浮工具栏")
        row = self._row(group, "工具栏透明度")
        tk.Scale(
            row,
            from_=0.65,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            variable=self.opacity,
            showvalue=True,
            length=230,
            bg=PANEL,
            fg=FG,
            troughcolor="#eceef2",
            activebackground=ACCENT,
            highlightthickness=0,
        ).pack(side="right", padx=20)

    def _render_dictionary(self):
        self.page_title.configure(text="词库")

        group = self._section("输入方案")
        selected = self.schema.get()
        for label, _schema_id in SCHEMAS:
            row = self._row(group, label)
            self._value(
                row,
                "默认" if label == selected else "已安装",
                accent=label == selected,
            )

        group = self._section("用户词典")
        row = self._row(
            group,
            "词库目录",
            str(RIME_DIR),
        )
        self._action_button(row, "打开", self.open_rime_directory)

        row = self._row(
            group,
            "重新部署词库",
            "重新生成输入方案和用户词典缓存",
        )
        self._action_button(row, "部署", self.redeploy, primary=True)

    def _render_keys(self):
        self.page_title.configure(text="按键")

        group = self._section("输入法快捷键")
        for label, value in (
            ("切换输入方案", "Ctrl + Shift + 1"),
            ("中英文切换", "Ctrl + Shift + 2"),
            ("中英文标点", "Ctrl + ."),
            ("语音输入", "Ctrl + Alt + V"),
            ("手写输入", "Ctrl + Alt + H"),
            ("显示或隐藏工具栏", "Ctrl + Alt + L"),
        ):
            row = self._row(group, label)
            self._value(row, value)

        group = self._section("九键候选操作")
        for label, value in (
            ("前后切换候选及拼音", "/  和  *"),
            ("上一页或下一页", "-  和  +"),
            ("上屏当前首选", "Enter"),
        ):
            row = self._row(group, label)
            self._value(row, value)

    def _render_advanced(self):
        self.page_title.configure(text="高级")

        group = self._section("辅助输入")
        row = self._row(
            group,
            "手写输入",
            "打开知音简体中文手写面板",
        )
        self._action_button(row, "打开", self.open_handwriting)

        row = self._row(
            group,
            "新手引导",
            "重新选择使用场景并检查安装状态",
        )
        self._action_button(row, "运行", self.open_wizard)

        group = self._section("维护")
        row = self._row(
            group,
            "重新部署输入法",
            "保存配置后重新生成知音输入方案",
        )
        self._action_button(row, "部署", self.redeploy, primary=True)

        row = self._row(
            group,
            "Windows 名称和图标",
            "修复输入法列表中仍显示小狼毫的情况",
        )
        self._action_button(row, "修复", self.repair_brand)

        row = self._row(
            group,
            "Rime 用户目录",
            str(RIME_DIR),
        )
        self._action_button(row, "打开", self.open_rime_directory)

    def _render_about(self):
        self.page_title.configure(text="关于知音")

        hero = tk.Frame(
            self.body,
            bg="#fff8f5",
            height=126,
            highlightbackground="#ffe2da",
            highlightthickness=1,
        )
        hero.pack(fill="x", padx=52, pady=(5, 22))
        hero.pack_propagate(False)
        if self.icon is not None:
            tk.Label(
                hero,
                image=self.icon,
                bg="#fff8f5",
            ).pack(side="left", padx=(24, 18))
        text = tk.Frame(hero, bg="#fff8f5")
        text.pack(side="left", fill="y")
        tk.Label(
            text,
            text="知音输入法",
            bg="#fff8f5",
            fg=FG,
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w", pady=(28, 2))
        tk.Label(
            text,
            text="面向 Windows 数字小键盘优化的中文输入法",
            bg="#fff8f5",
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")

        group = self._section("产品信息")
        row = self._row(group, "版本")
        self._value(row, "v0.1 开发版")
        row = self._row(group, "技术基础")
        self._value(row, "Rime / 小狼毫 · xuanli199/t9")

        group = self._section("开发者")
        row = self._row(group, "姓名")
        self._value(row, "李子旺")
        row = self._row(group, "联系邮箱")
        self._value(row, "2601121787@qq.com", accent=True)

    def apply(self):
        try:
            RIME_DIR.mkdir(parents=True, exist_ok=True)
            self._save_default_schema()
            self._save_t9_options()
            self._save_appearance()
            save_toolbar_config({"opacity": round(self.opacity.get(), 2)})
        except (OSError, ValueError, tk.TclError) as error:
            messagebox.showerror("知音输入法", f"保存设置失败：\n{error}")
            self.status.set("设置保存失败")
            return

        if redeploy_weasel(PROJECT_DIR):
            self.status.set("设置已保存，正在重新部署知音输入法")
        else:
            self.status.set("设置已保存，请稍后手动重新部署")

    def _save_default_schema(self):
        target = RIME_DIR / "default.custom.yaml"
        content = read_text(target)
        selected = SCHEMA_IDS[self.schema.get()]
        schema_ids = schema_list_with_preferred(
            content,
            [selected],
            [item for item in KNOWN_SCHEMA_IDS if item != selected],
        )
        backup_once(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            replace_schema_list(content, schema_ids),
            encoding="utf-8",
        )

    def _save_t9_options(self):
        page_size = int(self.page_size.get())
        if page_size not in {5, 7, 9}:
            raise ValueError("候选数量只能是 5、7 或 9")
        for schema_id in ("zhiyin_t9", "zhiyin_t9_pos"):
            target = RIME_DIR / f"{schema_id}.custom.yaml"
            content = read_text(target)
            backup_once(target)
            target.write_text(
                update_patch_values(
                    content,
                    {"menu/page_size": page_size},
                ),
                encoding="utf-8",
            )

    def _save_appearance(self):
        target = RIME_DIR / "weasel.custom.yaml"
        content = read_text(target)
        content = replace_color_scheme(
            content,
            THEME_KEYS[self.theme.get()],
        )
        content = update_patch_values(
            content,
            {
                "style/horizontal": self.horizontal.get(),
                "style/font_face": self.font_face.get().strip()
                or "Microsoft YaHei UI",
                "style/font_point": int(self.font_point.get()),
            },
        )
        backup_once(target)
        target.write_text(content, encoding="utf-8")

    def redeploy(self):
        self.status.set(
            "正在重新部署知音输入法"
            if redeploy_weasel(PROJECT_DIR)
            else "没有找到小狼毫部署程序"
        )

    def open_handwriting(self):
        if launch_script(
            Path("tools") / "ZhiyinHandwriting" / "zhiyin_handwriting.py"
        ):
            self.status.set("手写输入已打开")
        else:
            self.status.set("手写输入启动失败")

    def open_wizard(self):
        if launch_script(
            Path("tools") / "ZhiyinWizard" / "zhiyin_wizard.py",
            "--force",
        ):
            self.status.set("新手引导已打开")

    def repair_brand(self):
        if launch_script(
            Path("scripts") / "start_zhiyin.py",
            "--brand",
            "--no-toolbar",
        ):
            self.status.set("请在 Windows 管理员授权窗口中确认")
        else:
            self.status.set("品牌修复启动失败")

    def open_rime_directory(self):
        try:
            RIME_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(RIME_DIR))
        except OSError as error:
            messagebox.showerror("知音输入法", f"无法打开目录：\n{error}")


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    if show_existing_settings():
        return
    root = tk.Tk()
    SettingsWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
