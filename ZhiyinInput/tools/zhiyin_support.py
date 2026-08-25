# -*- coding: utf-8 -*-
"""Shared Windows and Rime configuration helpers for Zhiyin tools."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - only used by non-Windows test hosts
    winreg = None


KNOWN_SCHEMA_IDS = (
    "zhiyin_t9",
    "zhiyin_full",
    "zhiyin_t9_pos",
    "zhiyin_double",
)

COLOR_SCHEME_KEYS = (
    "zhiyin_red",
    "ink_gray",
    "cyber_cyan",
    "cherry_pink",
)


def _registry_value(root, subkey, name, access=0):
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | access) as key:
            value, _value_type = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return None


def get_rime_user_dir():
    """Return Weasel's configured user directory, including custom locations."""
    override = os.getenv("ZHIYIN_RIME_DIR")
    if override:
        return Path(override).expanduser()

    if winreg is not None:
        value = _registry_value(
            winreg.HKEY_CURRENT_USER,
            r"Software\Rime\Weasel",
            "RimeUserDir",
        )
        if value:
            return Path(os.path.expandvars(value)).expanduser()

    appdata = os.getenv("APPDATA", str(Path.home()))
    return Path(appdata) / "Rime"


def get_weasel_root():
    """Return the installed Weasel directory from registry or common paths."""
    override = os.getenv("ZHIYIN_WEASEL_ROOT")
    if override:
        path = Path(override).expanduser()
        if path.exists():
            return path

    if winreg is not None:
        access_modes = [0]
        if hasattr(winreg, "KEY_WOW64_32KEY"):
            access_modes.extend(
                [winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY]
            )
        for access in access_modes:
            value = _registry_value(
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\Rime\Weasel",
                "WeaselRoot",
                access,
            )
            if value:
                path = Path(os.path.expandvars(value)).expanduser()
                if path.exists():
                    return path

    program_files = Path(
        os.getenv("ProgramFiles", r"C:\Program Files")
    )
    candidates = (
        program_files / "Rime" / "weasel",
        program_files / "Rime" / "weasel-0.17.4",
    )
    return next((path for path in candidates if path.exists()), None)


def find_weasel_deployer(project_root=None):
    root = get_weasel_root()
    if root:
        executable = root / "WeaselDeployer.exe"
        if executable.exists():
            return executable

    if project_root:
        base = Path(project_root).resolve().parent
        matches = base.glob("**/weasel-*/WeaselDeployer.exe")
        return next((path for path in matches if path.exists()), None)
    return None


def redeploy_weasel(project_root=None):
    executable = find_weasel_deployer(project_root)
    if not executable:
        return False
    try:
        subprocess.Popen(
            [str(executable), "/deploy"],
            cwd=str(executable.parent),
        )
        return True
    except OSError:
        return False


def backup_once(path):
    path = Path(path)
    backup = path.with_suffix(path.suffix + ".zhiyin.bak")
    if path.exists() and not backup.exists():
        import shutil

        shutil.copy2(path, backup)
    return backup


def extract_schema_ids(content):
    """Read schema IDs from the patch/schema_list block without parsing YAML."""
    lines = content.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r'^\s{2}(?:"?schema_list"?):\s*$', line)
        ),
        None,
    )
    if start is None:
        return []

    schema_ids = []
    for line in lines[start + 1 :]:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if indent <= 2:
                break
        match = re.search(
            r"\bschema\s*:\s*[\"']?([^\"'\s,}]+)",
            line,
        )
        if match and match.group(1) not in schema_ids:
            schema_ids.append(match.group(1))
    return schema_ids


def replace_schema_list(content, schema_ids):
    lines = content.splitlines()
    replacement = ["  schema_list:"]
    replacement.extend(
        f"    - schema: {schema_id}" for schema_id in schema_ids
    )

    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r'^\s{2}(?:"?schema_list"?):\s*$', line)
        ),
        None,
    )
    if start is not None:
        end = start + 1
        while end < len(lines):
            line = lines[end]
            if line.strip():
                indent = len(line) - len(line.lstrip())
                if indent <= 2:
                    break
            end += 1
        lines[start:end] = replacement
        return "\n".join(lines).rstrip() + "\n"

    patch_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^patch\s*:\s*$", line)
        ),
        None,
    )
    if patch_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("patch:")
        patch_index = len(lines) - 1
    lines[patch_index + 1 : patch_index + 1] = replacement
    return "\n".join(lines).rstrip() + "\n"


def schema_list_with_preferred(content, preferred_ids, ensured_ids=()):
    """Move preferred IDs first while retaining existing third-party schemas."""
    result = []
    for schema_id in (
        *preferred_ids,
        *ensured_ids,
        *extract_schema_ids(content),
    ):
        if schema_id and schema_id not in result:
            result.append(schema_id)
    return result


def replace_color_scheme(content, scheme):
    pattern = re.compile(
        r'(?m)^(\s*(?:"style/color_scheme"|style/color_scheme|'
        r'color_scheme)\s*:\s*)(?:"[^"]*"|\'[^\']*\'|[^\s#]+)'
    )
    if pattern.search(content):
        return pattern.sub(rf"\g<1>{scheme}", content, count=1)

    lines = content.splitlines()
    patch_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^patch\s*:\s*$", line)
        ),
        None,
    )
    if patch_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("patch:")
        patch_index = len(lines) - 1
    lines.insert(patch_index + 1, f'  "style/color_scheme": {scheme}')
    return "\n".join(lines).rstrip() + "\n"


def _extract_patch_entry(content, key):
    lines = content.splitlines()
    pattern = re.compile(
        rf'^\s{{2}}(?:"{re.escape(key)}"|{re.escape(key)})\s*:'
    )
    start = next(
        (index for index, line in enumerate(lines) if pattern.match(line)),
        None,
    )
    if start is None:
        return []

    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip())
            if indent <= 2:
                break
        end += 1
    return lines[start:end]


def _patch_block_end(lines, patch_index):
    end = patch_index + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                break
        end += 1
    return end


def ensure_color_schemes(content, template):
    """Merge Zhiyin theme definitions into an existing weasel.custom.yaml."""
    lines = content.splitlines()
    patch_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^patch\s*:\s*$", line)
        ),
        None,
    )
    if patch_index is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("patch:")
        patch_index = len(lines) - 1

    insert_at = _patch_block_end(lines, patch_index)
    additions = []
    for scheme in COLOR_SCHEME_KEYS:
        key = f"preset_color_schemes/{scheme}"
        if re.search(
            rf'(?m)^\s{{2}}(?:"{re.escape(key)}"|{re.escape(key)})\s*:',
            "\n".join(lines),
        ):
            continue
        entry = _extract_patch_entry(template, key)
        if entry:
            if additions or (
                insert_at > 0 and lines[insert_at - 1].strip()
            ):
                additions.append("")
            additions.extend(entry)

    if additions:
        lines[insert_at:insert_at] = additions
    return "\n".join(lines).rstrip() + "\n"
