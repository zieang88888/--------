# -*- coding: utf-8 -*-
"""One-click development launcher for Zhiyin IME."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from install_dev import install  # noqa: E402
from zhiyin_support import KNOWN_SCHEMA_IDS, get_rime_user_dir  # noqa: E402


TOOLBAR_SCRIPT = (
    PROJECT_DIR / "tools" / "ZhiyinToolbar" / "zhiyin_toolbar.py"
)
WIZARD_SCRIPT = (
    PROJECT_DIR / "tools" / "ZhiyinWizard" / "zhiyin_wizard.py"
)
FIRST_RUN_FILE = (
    Path(os.getenv("APPDATA", str(Path.home())))
    / "Zhiyin"
    / "zhiyin_first_run.yaml"
)
REG_KEY = r"Software\ZhiyinIME"
REG_NAME = "FirstRunCompleted"


def installation_complete(rime_dir):
    rime_dir = Path(rime_dir)
    required = [
        rime_dir / f"{schema_id}.schema.yaml"
        for schema_id in KNOWN_SCHEMA_IDS
    ]
    required.append(rime_dir / "weasel.custom.yaml")
    return all(path.exists() for path in required)


def first_run_completed():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, REG_NAME)
            if value == 1:
                return True
    except (ImportError, FileNotFoundError, OSError):
        pass

    try:
        content = FIRST_RUN_FILE.read_text(encoding="utf-8")
    except OSError:
        return False
    return "first_run_completed: true" in content


def pythonw_executable():
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    return candidate if candidate.exists() else executable


def run_wizard(force=False):
    command = [sys.executable, str(WIZARD_SCRIPT)]
    if force:
        command.append("--force")
    return subprocess.run(
        command,
        cwd=str(PROJECT_DIR),
        check=False,
    ).returncode


def start_toolbar():
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        )

    with open(os.devnull, "rb") as stdin, open(
        os.devnull, "wb"
    ) as output:
        process = subprocess.Popen(
            [str(pythonw_executable()), str(TOOLBAR_SCRIPT)],
            cwd=str(PROJECT_DIR),
            stdin=stdin,
            stdout=output,
            stderr=output,
            close_fds=True,
            creationflags=creationflags,
        )
    time.sleep(0.4)
    return process.poll() in (None, 0)


def describe_actions(rime_dir, force_install=False, force_setup=False):
    actions = []
    if force_install or not installation_complete(rime_dir):
        actions.append("部署知音输入方案并重新部署小狼毫")
    if force_setup or not first_run_completed():
        actions.append("打开首次使用引导")
    actions.append("后台启动知音悬浮工具栏")
    return actions


def main(argv=None):
    parser = argparse.ArgumentParser(description="启动知音输入法")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="强制重新打开新手引导",
    )
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="强制重新部署输入方案",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将执行的步骤",
    )
    parser.add_argument(
        "--no-toolbar",
        action="store_true",
        help="完成部署或引导后不启动工具栏",
    )
    args = parser.parse_args(argv)

    rime_dir = get_rime_user_dir()
    actions = describe_actions(
        rime_dir,
        force_install=args.reinstall,
        force_setup=args.setup,
    )
    if args.no_toolbar:
        actions = [
            action for action in actions
            if action != "后台启动知音悬浮工具栏"
        ]

    if args.dry_run:
        print(f"小狼毫用户目录: {rime_dir}")
        for index, action in enumerate(actions, start=1):
            print(f"{index}. {action}")
        return 0

    if args.reinstall or not installation_complete(rime_dir):
        result = install(rime_dir, deploy=True)
        print(
            f"已部署 {result['schema_count']} 个知音方案到 "
            f"{result['rime_dir']}"
        )

    if args.setup or not first_run_completed():
        if run_wizard(force=args.setup) != 0:
            print("[错误] 新手引导启动失败")
            return 1

    if not args.no_toolbar:
        if not start_toolbar():
            print("[错误] 悬浮工具栏启动失败")
            return 1
        print("知音悬浮工具栏已启动，Ctrl+Alt+L 可显示或隐藏。")

    print("使用 Win+Space 选择小狼毫，然后选择知音输入方案。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
