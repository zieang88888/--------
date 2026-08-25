# -*- coding: utf-8 -*-
"""Brand the installed Weasel TSF profile as Zhiyin Input Method."""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from zhiyin_support import get_rime_user_dir  # noqa: E402

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only utility
    winreg = None


DISPLAY_NAME = "知音输入法"
BRAND_ICON_SOURCE = PROJECT_DIR / "assets" / "branding" / "zhiyin.ico"
WEASEL_TIP = "{A3F4CDED-B1E9-41EE-9CA6-7B4D0DE6CB0A}"
WEASEL_PROFILE = "{3D02CAB6-2B8E-4781-BA20-1C9267529467}"
LANGUAGE_IDS = ("00000404", "00000804", "00000c04", "00001004", "00001404")


def profile_key(language_id):
    return (
        rf"SOFTWARE\Microsoft\CTF\TIP\{WEASEL_TIP}"
        rf"\LanguageProfile\0x{language_id}\{WEASEL_PROFILE}"
    )


def brand_icon_path():
    program_data = Path(
        os.getenv(
            "PROGRAMDATA",
            os.getenv("LOCALAPPDATA", str(Path.home())),
        )
    )
    return program_data / "ZhiyinInput" / "zhiyin.ico"


def install_brand_icon():
    """Copy the profile icon to a stable shared application directory."""
    target = brand_icon_path()
    if (
        target.exists()
        and target.read_bytes() == BRAND_ICON_SOURCE.read_bytes()
    ):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRAND_ICON_SOURCE, target)
    return target


def update_profile_names(display_name=DISPLAY_NAME, icon_path=None):
    """Update all installed Weasel language profile names and icons."""
    if winreg is None:
        return {"updated": 0, "missing": [], "errors": ["仅支持 Windows"]}

    if icon_path is None:
        try:
            icon_path = install_brand_icon()
        except OSError as error:
            return {
                "updated": 0,
                "missing": [],
                "errors": [f"安装知音图标失败: {error}"],
            }
    icon_path = str(Path(icon_path).resolve())

    updated = 0
    missing = []
    errors = []
    read_access = winreg.KEY_READ
    write_access = winreg.KEY_SET_VALUE
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        read_access |= winreg.KEY_WOW64_64KEY
        write_access |= winreg.KEY_WOW64_64KEY

    for language_id in LANGUAGE_IDS:
        key_path = profile_key(language_id)
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                key_path,
                0,
                read_access,
            ) as key:
                current, _kind = winreg.QueryValueEx(key, "Description")
                try:
                    current_icon, _kind = winreg.QueryValueEx(
                        key,
                        "IconFile",
                    )
                except FileNotFoundError:
                    current_icon = ""
                try:
                    current_icon_index, _kind = winreg.QueryValueEx(
                        key,
                        "IconIndex",
                    )
                except FileNotFoundError:
                    current_icon_index = -1
            if (
                current != display_name
                or current_icon != icon_path
                or current_icon_index != 0
            ):
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    key_path,
                    0,
                    write_access,
                ) as key:
                    winreg.SetValueEx(
                        key,
                        "Description",
                        0,
                        winreg.REG_SZ,
                        display_name,
                    )
                    winreg.SetValueEx(
                        key,
                        "IconFile",
                        0,
                        winreg.REG_SZ,
                        icon_path,
                    )
                    winreg.SetValueEx(
                        key,
                        "IconIndex",
                        0,
                        winreg.REG_DWORD,
                        0,
                    )
                    updated += 1
        except FileNotFoundError:
            missing.append(language_id)
        except OSError as error:
            errors.append(f"{language_id}: {error}")

    return {"updated": updated, "missing": missing, "errors": errors}


def update_installation_name(rime_dir, display_name=DISPLAY_NAME):
    """Keep Rime's installation metadata consistent with the Windows name."""
    path = Path(rime_dir) / "installation.yaml"
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")
    replacement = f'distribution_name: "{display_name}"'
    updated, count = re.subn(
        r"(?m)^distribution_name\s*:.*$",
        replacement,
        content,
        count=1,
    )
    if count == 0:
        updated = replacement + "\n" + content
    if updated == content:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def notify_input_settings_changed():
    """Ask Windows shells to refresh cached input-profile labels."""
    if sys.platform != "win32":
        return
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF,
        0x001A,
        0,
        "intl",
        0x0002,
        1000,
        ctypes.byref(result),
    )


def relaunch_as_admin():
    """Run this script with UAC elevation and wait for its result."""
    env = os.environ.copy()
    env["ZHIYIN_PYTHON"] = sys.executable
    env["ZHIYIN_BRAND_SCRIPT"] = str(Path(__file__).resolve())
    env["ZHIYIN_PROJECT_DIR"] = str(PROJECT_DIR)
    command = (
        "$process = Start-Process "
        "-FilePath $env:ZHIYIN_PYTHON "
        "-ArgumentList @($env:ZHIYIN_BRAND_SCRIPT, '--elevated') "
        "-WorkingDirectory $env:ZHIYIN_PROJECT_DIR "
        "-Verb RunAs -PassThru -Wait; "
        "exit $process.ExitCode"
    )
    try:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            check=False,
            env=env,
        ).returncode
    except OSError as error:
        print(f"[错误] 无法启动管理员授权: {error}")
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="将 Windows 输入法列表中的“小狼毫”改为“知音输入法”"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查注册名称，不修改",
    )
    parser.add_argument(
        "--elevated",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if winreg is None:
        print("[错误] 此操作仅支持 Windows")
        return 1

    if args.check:
        mismatched = []
        expected_icon = str(brand_icon_path().resolve())
        if not Path(expected_icon).exists():
            mismatched.append(("图标文件", "不存在"))
        access = winreg.KEY_READ
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            access |= winreg.KEY_WOW64_64KEY
        for language_id in LANGUAGE_IDS:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    profile_key(language_id),
                    0,
                    access,
                ) as key:
                    value, _kind = winreg.QueryValueEx(key, "Description")
                    icon, _kind = winreg.QueryValueEx(key, "IconFile")
                    icon_index, _kind = winreg.QueryValueEx(key, "IconIndex")
                    if (
                        value != DISPLAY_NAME
                        or icon != expected_icon
                        or icon_index != 0
                    ):
                        mismatched.append(
                            (
                                language_id,
                                f"{value}, {icon}, {icon_index}",
                            )
                        )
            except OSError as error:
                mismatched.append((language_id, str(error)))
        if mismatched:
            for language_id, value in mismatched:
                print(f"{language_id}: {value}")
            return 1
        print(f"Windows 输入法名称: {DISPLAY_NAME}")
        return 0

    result = update_profile_names()
    update_installation_name(get_rime_user_dir())
    if result["errors"]:
        if not args.elevated:
            print("[提示] 即将请求管理员权限，修改 Windows 输入法名称。")
            return relaunch_as_admin()
        print("[错误] 已取得管理员权限，但仍无法修改系统输入法名称。")
        for error in result["errors"]:
            print(error)
        return 1

    notify_input_settings_changed()
    print(f"Windows 输入法名称: {DISPLAY_NAME}")
    print(f"已更新 {result['updated']} 个语言配置。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
