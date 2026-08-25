# -*- coding: utf-8 -*-
"""
知音输入法 · 新手引导 (MVP)
====================================================
首次启动 5 步卡片教学，零第三方依赖 (tkinter)。

步骤：
  1. 欢迎    2. 选模式    3. 演示    4. 个性化    5. 完成

完成时：
  - 写入 %APPDATA%\\Zhiyin\\zhiyin_first_run.yaml
  - 写入注册表 HKCU\\Software\\ZhiyinIME\\FirstRunCompleted = 1
  - 将所选默认方案写入 %APPDATA%\\Rime\\default.custom.yaml

用法：
  python zhiyin_wizard.py [--force]
====================================================
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from zhiyin_support import (  # noqa: E402
    backup_once,
    get_rime_user_dir,
    redeploy_weasel,
    replace_color_scheme,
    replace_schema_list,
    schema_list_with_preferred,
)

APPDATA = os.getenv("APPDATA", str(Path.home()))
ZHIYIN_DIR = Path(APPDATA) / "Zhiyin"
RIME_DIR = get_rime_user_dir()
FIRST_RUN_FILE = ZHIYIN_DIR / "zhiyin_first_run.yaml"
REG_KEY = r"Software\ZhiyinIME"
REG_NAME = "FirstRunCompleted"

ACCENT = "#e8543b"
BG = "#ffffff"
FG = "#222222"
SUB = "#777777"

STEPS = [
    ("欢迎", "欢迎使用知音输入法", "九键打字，越打越懂你。\n本引导仅需 3 分钟。", None),
    ("选模式", "选择你的输入方式", None, "mode"),
    ("演示", "怎么输入？", "数字小键盘 = 手机九键\n\n"
     "  按 2-4-3   （abc-ghi-def）→ 候选「吃」\n"
     "  按 0        （空格）→ 上屏首选\n"
     "  看候选注释   → 确认当前候选的完整拼音\n"
     "  按 \\ 键     → 切换下一候选并查看其拼音\n"
     "  按 [ / ]    → 查看上一页 / 下一页候选\n"
     "  按 Ctrl+Shift+1 → 切换 九键/26键", None),
    ("个性化", "把输入法调成你喜欢的样子", None, "skin"),
    ("完成", "一切就绪", "现在就试试吧！\n在任意输入框按九键，开始你的知音之旅。", None),
]

SCHEMAS = [
    ("知音九键（推荐）", "zhiyin_t9",
     "与手机九键完全一致，小键盘打字"),
    ("知音九键·位置", "zhiyin_t9_pos",
     "小键盘 789/456/123 对应 1/2/3 行"),
    ("知音全键（26键）", "zhiyin_full",
     "标准全拼键盘，打习惯全键的人"),
    ("知音双拼", "zhiyin_double",
     "自然码双拼，两键一音"),
]

SKINS = [
    ("知音红（默认）", "zhiyin_red"),
    ("水墨灰", "ink_gray"),
    ("极客青", "cyber_cyan"),
    ("樱粉", "cherry_pink"),
]


class Wizard:
    def __init__(self, root: tk.Tk, force: bool):
        self.root = root
        self.force = force
        self.step = 0
        self.schema_choice = tk.StringVar(value="zhiyin_t9")
        self.skin_choice = tk.StringVar(value="zhiyin_red")

        root.title("知音输入法 · 新手引导")
        root.geometry("680x460")
        root.resizable(False, False)
        root.configure(bg=BG)
        self._center()

        # 顶部进度条
        self.progress = tk.Canvas(root, height=6, bg="#eeeeee",
                                  highlightthickness=0)
        self.progress.pack(fill="x")
        self.bar = self.progress.create_rectangle(0, 0, 0, 6,
                                                  fill=ACCENT, width=0)

        # 内容区
        self.card = tk.Frame(root, bg=BG)
        self.card.pack(fill="both", expand=True, padx=40, pady=20)

        # 标题
        self.title_lbl = tk.Label(self.card, text="", font=("Microsoft YaHei UI", 20, "bold"),
                                  bg=BG, fg=FG)
        self.title_lbl.pack(pady=(10, 6))

        # 正文
        self.body = tk.Frame(self.card, bg=BG)
        self.body.pack(fill="both", expand=True)

        # 按钮区
        self.btn_bar = tk.Frame(root, bg="#f7f7f7", height=60)
        self.btn_bar.pack(fill="x", side="bottom")
        self.btn_bar.pack_propagate(False)

        self.back_btn = tk.Button(self.btn_bar, text="上一步", width=10,
                                  font=("Microsoft YaHei UI", 10),
                                  bg="#eeeeee", fg=FG, bd=0, padx=8, pady=6,
                                  activebackground="#dddddd", command=self.go_back)
        self.back_btn.pack(side="left", padx=12, pady=12)

        self.next_btn = tk.Button(self.btn_bar, text="下一步", width=10,
                                  font=("Microsoft YaHei UI", 10, "bold"),
                                  bg=ACCENT, fg="white", bd=0, padx=8, pady=6,
                                  activebackground="#c0402a",
                                  command=self.go_next)
        self.next_btn.pack(side="right", padx=12, pady=12)

        self.skip_btn = tk.Button(self.btn_bar, text="跳过引导", width=8,
                                  font=("Microsoft YaHei UI", 9),
                                  bg="#f7f7f7", fg=SUB, bd=0,
                                  activebackground="#eeeeee",
                                  command=self.skip)
        self.skip_btn.pack(side="right", padx=4, pady=12)

        self.render(0)

    # ---------- 布局 ----------
    def _center(self):
        self.root.update_idletasks()
        w, h = 680, 460
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 3
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _clear(self):
        for child in self.body.winfo_children():
            child.destroy()

    # ---------- 渲染各步骤 ----------
    def render(self, idx):
        self.step = idx
        title, subtitle, text, kind = STEPS[idx]
        self.title_lbl.config(text=subtitle)
        self._clear()

        # 进度条
        pct = (idx + 1) / len(STEPS)
        w = int(self.progress.winfo_width() * pct)
        self.progress.coords(self.bar, 0, 0, max(w, 4), 6)

        # 按钮状态
        self.back_btn.config(state="disabled" if idx == 0 else "normal")
        self.next_btn.config(
            text="开始使用" if idx == len(STEPS) - 1 else "下一步",
            command=self.finish if idx == len(STEPS) - 1 else self.go_next)

        if kind == "mode":
            self._render_mode()
        elif kind == "skin":
            self._render_skin()
        else:
            tk.Label(self.body, text=text or "",
                     font=("Microsoft YaHei UI", 12), bg=BG, fg=FG,
                     justify="left").pack(anchor="w", pady=8)

    def _render_mode(self):
        tk.Label(self.body, text="想用哪种方式打字？以后随时可切换。",
                 font=("Microsoft YaHei UI", 11), bg=BG, fg=SUB,
                 justify="left").pack(anchor="w", pady=(0, 12))
        for label, sid, desc in SCHEMAS:
            row = tk.Frame(self.body, bg=BG)
            row.pack(fill="x", pady=3)
            rb = tk.Radiobutton(row, text=label,
                                variable=self.schema_choice, value=sid,
                                font=("Microsoft YaHei UI", 12),
                                bg=BG, fg=FG, activebackground=BG)
            rb.pack(side="left", anchor="w")
            tk.Label(row, text=f"— {desc}",
                     font=("Microsoft YaHei UI", 9), bg=BG, fg=SUB).pack(
                side="left", padx=8)

    def _render_skin(self):
        tk.Label(self.body, text="选一套喜欢的配色：",
                 font=("Microsoft YaHei UI", 11), bg=BG, fg=SUB,
                 justify="left").pack(anchor="w", pady=(0, 12))
        colors = {"zhiyin_red": "#c94f45", "ink_gray": "#575757",
                  "cyber_cyan": "#00d4ff", "cherry_pink": "#f8a4b8"}
        for label, key in SKINS:
            row = tk.Frame(self.body, bg=BG)
            row.pack(fill="x", pady=3)
            sw = tk.Canvas(row, width=18, height=18, bg=BG,
                           highlightthickness=0)
            sw.create_oval(2, 2, 16, 16, fill=colors.get(key, "#ccc"),
                           outline="")
            sw.pack(side="left", padx=(4, 8))
            rb = tk.Radiobutton(row, text=label,
                                variable=self.skin_choice, value=key,
                                font=("Microsoft YaHei UI", 12),
                                bg=BG, fg=FG, activebackground=BG)
            rb.pack(side="left", anchor="w")

    # ---------- 流程 ----------
    def go_next(self):
        if self.step < len(STEPS) - 1:
            self.render(self.step + 1)

    def go_back(self):
        if self.step > 0:
            self.render(self.step - 1)

    def skip(self):
        self._mark_done()
        self._exit()

    def finish(self):
        try:
            self._write_defaults()
        except OSError as error:
            messagebox.showerror("知音输入法", f"写入配置失败：\n{error}")
            return
        self._mark_done()
        redeploy_weasel(PROJECT_DIR)
        self._exit()

    # ---------- 写配置 ----------
    def _write_defaults(self):
        """把所选默认方案写入 default.custom.yaml"""
        RIME_DIR.mkdir(parents=True, exist_ok=True)
        selected = self.schema_choice.get()

        target = RIME_DIR / "default.custom.yaml"
        backup_once(target)
        content = (
            target.read_text(encoding="utf-8")
            if target.exists()
            else "# 由知音新手引导生成\npatch:\n"
        )
        known_ids = [
            schema_id
            for _label, schema_id, _desc in SCHEMAS
            if schema_id != selected
        ]
        schema_ids = schema_list_with_preferred(
            content,
            [selected],
            known_ids,
        )
        target.write_text(
            replace_schema_list(content, schema_ids),
            encoding="utf-8",
        )

        style_target = RIME_DIR / "weasel.custom.yaml"
        backup_once(style_target)
        style_content = (
            style_target.read_text(encoding="utf-8")
            if style_target.exists()
            else "# 由知音新手引导生成\npatch:\n"
        )
        style_target.write_text(
            replace_color_scheme(style_content, self.skin_choice.get()),
            encoding="utf-8",
        )

    def _mark_done(self):
        try:
            ZHIYIN_DIR.mkdir(parents=True, exist_ok=True)
            FIRST_RUN_FILE.write_text(
                "first_run_completed: true\n"
                f"default_schema: {self.schema_choice.get()}\n"
                f"skin: {self.skin_choice.get()}\n"
                "completed_at: " + _now() + "\n", encoding="utf-8")
            # 注册表
            _reg_write(REG_KEY, REG_NAME, 1)
        except Exception:
            pass

    def _exit(self):
        self.root.destroy()


def _now():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")


def _reg_write(subkey, name, value):
    import winreg
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey)
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
    except Exception:
        pass


def _reg_read(subkey, name):
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except Exception:
        return None


def main():
    force = "--force" in sys.argv
    # 已引导过且非强制 → 直接退出
    if not force and _reg_read(REG_KEY, REG_NAME) == 1:
        return
    root = tk.Tk()
    Wizard(root, force)
    root.mainloop()


if __name__ == "__main__":
    main()
