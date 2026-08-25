# -*- coding: utf-8 -*-
"""Graphical settings center for Zhiyin Input Method."""

from __future__ import annotations

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

ACCENT = "#d84a3a"
SIDEBAR = "#242424"
SIDEBAR_HOVER = "#353535"
BG = "#f5f6f8"
PANEL = "#ffffff"
FG = "#202124"
MUTED = "#6f7378"
BORDER = "#dfe2e6"

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
        self.status = tk.StringVar(value="设置已从当前知音配置中读取")
        self.active_page = None
        self.nav_buttons = {}

        root.title("知音输入法设置")
        root.geometry("920x640")
        root.minsize(920, 640)
        root.configure(bg=BG)
        self._set_icon()
        self._center()
        self._configure_styles()
        self._build_shell()
        self.show_page("input")

    def _set_icon(self):
        try:
            if LOGO_PATH.exists():
                self.icon = tk.PhotoImage(file=str(LOGO_PATH))
                self.root.iconphoto(True, self.icon)
        except tk.TclError:
            self.icon = None

    def _center(self):
        self.root.update_idletasks()
        width, height = 920, 640
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 3)
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
            padding=5,
        )
        style.configure(
            "Zhiyin.TCheckbutton",
            background=PANEL,
            font=("Microsoft YaHei UI", 10),
        )

    def _build_shell(self):
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=SIDEBAR, width=188)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg=SIDEBAR, height=102)
        brand.pack(fill="x")
        brand.pack_propagate(False)
        tk.Label(
            brand,
            text="知音",
            bg=ACCENT,
            fg="#ffffff",
            font=("Microsoft YaHei UI", 12, "bold"),
            padx=8,
            pady=5,
        ).pack(anchor="w", padx=22, pady=(24, 7))
        tk.Label(
            brand,
            text="输入法设置",
            bg=SIDEBAR,
            fg="#ffffff",
            font=("Microsoft YaHei UI", 11),
        ).pack(anchor="w", padx=22)

        for page_id, label in (
            ("input", "输入与候选"),
            ("appearance", "外观"),
            ("tools", "工具"),
            ("about", "关于"),
        ):
            button = tk.Button(
                sidebar,
                text=label,
                anchor="w",
                bg=SIDEBAR,
                fg="#e8e8e8",
                activebackground=SIDEBAR_HOVER,
                activeforeground="#ffffff",
                bd=0,
                relief="flat",
                font=("Microsoft YaHei UI", 10),
                padx=22,
                pady=12,
                cursor="hand2",
                command=lambda selected=page_id: self.show_page(selected),
            )
            button.pack(fill="x")
            self.nav_buttons[page_id] = button

        tk.Label(
            sidebar,
            text="v0.1 开发版",
            bg=SIDEBAR,
            fg="#8e8e8e",
            font=("Microsoft YaHei UI", 9),
        ).pack(side="bottom", anchor="w", padx=22, pady=18)

        content = tk.Frame(shell, bg=BG)
        content.pack(side="left", fill="both", expand=True)

        self.header = tk.Frame(content, bg=PANEL, height=88)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.page_title = tk.Label(
            self.header,
            text="",
            bg=PANEL,
            fg=FG,
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        self.page_title.pack(anchor="w", padx=34, pady=(20, 2))
        self.page_subtitle = tk.Label(
            self.header,
            text="",
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        )
        self.page_subtitle.pack(anchor="w", padx=34)

        self.body = tk.Frame(content, bg=BG)
        self.body.pack(fill="both", expand=True, padx=34, pady=24)

        footer = tk.Frame(content, bg=PANEL, height=62)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            textvariable=self.status,
            bg=PANEL,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left", padx=28)
        self.apply_button = tk.Button(
            footer,
            text="应用设置",
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#bc3d30",
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            padx=24,
            pady=8,
            font=("Microsoft YaHei UI", 10, "bold"),
            cursor="hand2",
            command=self.apply,
        )
        self.apply_button.pack(side="right", padx=24, pady=13)

    def _clear_body(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _section(self, title, description=None):
        tk.Label(
            self.body,
            text=title,
            bg=BG,
            fg=FG,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 3))
        if description:
            tk.Label(
                self.body,
                text=description,
                bg=BG,
                fg=MUTED,
                font=("Microsoft YaHei UI", 9),
            ).pack(anchor="w", pady=(0, 12))

    def _row(self, label, help_text=""):
        row = tk.Frame(self.body, bg=PANEL, highlightbackground=BORDER)
        row.pack(fill="x", pady=1, ipady=11)
        text = tk.Frame(row, bg=PANEL)
        text.pack(side="left", fill="x", expand=True, padx=16)
        tk.Label(
            text,
            text=label,
            bg=PANEL,
            fg=FG,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w")
        if help_text:
            tk.Label(
                text,
                text=help_text,
                bg=PANEL,
                fg=MUTED,
                font=("Microsoft YaHei UI", 8),
            ).pack(anchor="w", pady=(2, 0))
        return row

    def show_page(self, page_id):
        self.active_page = page_id
        for key, button in self.nav_buttons.items():
            button.configure(
                bg=ACCENT if key == page_id else SIDEBAR,
                activebackground=ACCENT if key == page_id else SIDEBAR_HOVER,
            )
        self._clear_body()
        {
            "input": self._render_input,
            "appearance": self._render_appearance,
            "tools": self._render_tools,
            "about": self._render_about,
        }[page_id]()

    def _render_input(self):
        self.page_title.configure(text="输入与候选")
        self.page_subtitle.configure(text="设置默认方案和候选窗行为")
        self._section("输入方案")

        row = self._row("默认输入方案", "重新部署后作为知音方案列表首项")
        ttk.Combobox(
            row,
            textvariable=self.schema,
            values=[label for label, _schema_id in SCHEMAS],
            state="readonly",
            width=20,
            style="Zhiyin.TCombobox",
        ).pack(side="right", padx=16)

        row = self._row("每页候选数量", "横向候选窗推荐 5 到 7 个")
        ttk.Combobox(
            row,
            textvariable=self.page_size,
            values=(5, 7, 9),
            state="readonly",
            width=8,
            style="Zhiyin.TCombobox",
        ).pack(side="right", padx=16)

        row = self._row("横向候选", "候选词与拼音注释按电脑输入法形式横排")
        ttk.Checkbutton(
            row,
            variable=self.horizontal,
            style="Zhiyin.TCheckbutton",
        ).pack(side="right", padx=20)

        self._section(
            "小键盘操作",
            "这些按键在知音九键和知音九键·位置方案中通用",
        )
        for key_text, action in (
            ("/  和  *", "前后切换候选及拼音"),
            ("-  和  +", "上一页 / 下一页候选"),
            ("Enter", "上屏当前首选"),
            ("小键盘数字", "继续输入九键编码"),
        ):
            row = self._row(key_text)
            tk.Label(
                row,
                text=action,
                bg=PANEL,
                fg=MUTED,
                font=("Microsoft YaHei UI", 9),
            ).pack(side="right", padx=16)

    def _render_appearance(self):
        self.page_title.configure(text="外观")
        self.page_subtitle.configure(text="调整候选窗主题、字体和状态栏")
        self._section("候选窗主题")

        theme_row = tk.Frame(self.body, bg=BG)
        theme_row.pack(fill="x", pady=(0, 18))
        for label, _key, color in THEMES:
            item = tk.Frame(theme_row, bg=PANEL)
            item.pack(side="left", fill="x", expand=True, padx=(0, 6))
            swatch = tk.Canvas(
                item,
                width=22,
                height=22,
                bg=PANEL,
                highlightthickness=0,
            )
            swatch.create_rectangle(3, 3, 19, 19, fill=color, outline="")
            swatch.pack(pady=(10, 2))
            tk.Radiobutton(
                item,
                text=label,
                variable=self.theme,
                value=label,
                bg=PANEL,
                fg=FG,
                activebackground=PANEL,
                font=("Microsoft YaHei UI", 9),
            ).pack(pady=(0, 10))

        self._section("文字")
        row = self._row("候选字体")
        ttk.Combobox(
            row,
            textvariable=self.font_face,
            values=FONTS,
            width=22,
            style="Zhiyin.TCombobox",
        ).pack(side="right", padx=16)

        row = self._row("候选字号")
        tk.Spinbox(
            row,
            from_=10,
            to=24,
            textvariable=self.font_point,
            width=8,
            font=("Microsoft YaHei UI", 10),
        ).pack(side="right", padx=16)

        self._section("悬浮状态栏")
        row = self._row("透明度")
        tk.Scale(
            row,
            from_=0.65,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            variable=self.opacity,
            showvalue=True,
            length=220,
            bg=PANEL,
            fg=FG,
            highlightthickness=0,
        ).pack(side="right", padx=16)

    def _tool_button(self, label, command, secondary=False):
        return tk.Button(
            self.body,
            text=label,
            command=command,
            bg="#ffffff" if secondary else ACCENT,
            fg=FG if secondary else "#ffffff",
            activebackground="#eeeeee" if secondary else "#bc3d30",
            activeforeground=FG if secondary else "#ffffff",
            highlightbackground=BORDER,
            bd=1 if secondary else 0,
            relief="solid" if secondary else "flat",
            padx=16,
            pady=9,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
        )

    def _render_tools(self):
        self.page_title.configure(text="工具")
        self.page_subtitle.configure(text="部署、修复和辅助输入")
        self._section("常用工具")
        actions = tk.Frame(self.body, bg=BG)
        actions.pack(fill="x", pady=(0, 20))
        self._tool_button("打开手写输入", self.open_handwriting).pack(
            side="left", padx=(0, 8)
        )
        self._tool_button(
            "重新部署输入法",
            self.redeploy,
            secondary=True,
        ).pack(side="left", padx=(0, 8))
        self._tool_button(
            "重新运行新手引导",
            self.open_wizard,
            secondary=True,
        ).pack(side="left")

        self._section("系统修复")
        row = self._row(
            "Windows 输入法名称和图标",
            "需要管理员授权，修复 Win+Space 中仍显示“小狼毫”的情况",
        )
        tk.Button(
            row,
            text="修复品牌",
            command=self.repair_brand,
            bg=PANEL,
            fg=ACCENT,
            activebackground="#f7e8e5",
            bd=0,
            font=("Microsoft YaHei UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=16)

        self._section("高级")
        row = self._row(
            "Rime 用户目录",
            str(RIME_DIR),
        )
        tk.Button(
            row,
            text="打开目录",
            command=self.open_rime_directory,
            bg=PANEL,
            fg=FG,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
        ).pack(side="right", padx=16)

    def _render_about(self):
        self.page_title.configure(text="关于")
        self.page_subtitle.configure(text="知音输入法 v0.1")
        self._section("知音输入法")
        tk.Label(
            self.body,
            text=(
                "面向 Windows 数字小键盘优化的中文输入法。\n"
                "基于 Rime / 小狼毫和 xuanli199/t9 九键方案开发。"
            ),
            bg=BG,
            fg=FG,
            justify="left",
            font=("Microsoft YaHei UI", 11),
        ).pack(anchor="w", pady=(0, 20))
        self._section("开发者")
        tk.Label(
            self.body,
            text="李子旺\n2601121787@qq.com",
            bg=BG,
            fg=MUTED,
            justify="left",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w")

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
    root = tk.Tk()
    SettingsWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
