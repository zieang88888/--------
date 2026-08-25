# -*- coding: utf-8 -*-
"""Install the Zhiyin development files into the active Weasel user folder."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from zhiyin_support import (  # noqa: E402
    KNOWN_SCHEMA_IDS,
    backup_once,
    ensure_color_schemes,
    extract_schema_ids,
    get_rime_user_dir,
    get_weasel_root,
    redeploy_weasel,
    replace_schema_list,
    schema_list_with_preferred,
)


def _copy_matching(source_dir, pattern, target_dir):
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sorted(source_dir.glob(pattern)):
        target = target_dir / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _install_default_config(source, target):
    template = source.read_text(encoding="utf-8")
    if not target.exists():
        target.write_text(template, encoding="utf-8")
        return

    content = target.read_text(encoding="utf-8")
    existing_ids = extract_schema_ids(content)
    schema_ids = schema_list_with_preferred(
        content,
        existing_ids,
        KNOWN_SCHEMA_IDS,
    )
    updated = replace_schema_list(content, schema_ids)
    if updated != content:
        backup_once(target)
        target.write_text(updated, encoding="utf-8")


def _install_weasel_config(source, target):
    template = source.read_text(encoding="utf-8")
    if not target.exists():
        target.write_text(template, encoding="utf-8")
        return

    content = target.read_text(encoding="utf-8")
    updated = ensure_color_schemes(content, template)
    if updated != content:
        backup_once(target)
        target.write_text(updated, encoding="utf-8")


def install(rime_dir, deploy=True):
    source = PROJECT_DIR / "weasel" / "data"
    schema_source = source / "schemas"
    lua_source = source / "lua"
    rime_dir = Path(rime_dir).resolve()
    rime_dir.mkdir(parents=True, exist_ok=True)

    schemas = _copy_matching(schema_source, "*.schema.yaml", rime_dir)
    lua_files = _copy_matching(lua_source, "*.lua", rime_dir / "lua")
    _install_default_config(
        source / "zhiyin.default.yaml",
        rime_dir / "default.custom.yaml",
    )
    _install_weasel_config(
        source / "zhiyin.weasel.yaml",
        rime_dir / "weasel.custom.yaml",
    )

    missing_dictionaries = []
    weasel_root = get_weasel_root()
    if weasel_root:
        shared_data = weasel_root / "data"
        for filename in (
            "t9.dict.yaml",
            "luna_pinyin.dict.yaml",
            "terra_pinyin.dict.yaml",
        ):
            if not (shared_data / filename).exists():
                missing_dictionaries.append(filename)

    deploy_started = deploy and redeploy_weasel(PROJECT_DIR)
    return {
        "rime_dir": rime_dir,
        "schema_count": len(schemas),
        "lua_count": len(lua_files),
        "missing_dictionaries": missing_dictionaries,
        "deploy_started": deploy_started,
    }


def main():
    parser = argparse.ArgumentParser(description="部署知音输入法开发版")
    parser.add_argument(
        "--rime-dir",
        type=Path,
        default=None,
        help="覆盖自动检测到的小狼毫用户目录",
    )
    parser.add_argument(
        "--no-deploy",
        action="store_true",
        help="只复制配置，不启动小狼毫重新部署",
    )
    args = parser.parse_args()

    result = install(
        args.rime_dir or get_rime_user_dir(),
        deploy=not args.no_deploy,
    )
    print(f"目标目录: {result['rime_dir']}")
    print(f"已复制 {result['schema_count']} 个方案文件")
    print(f"已复制 {result['lua_count']} 个实验 Lua 文件（默认未启用）")
    if result["missing_dictionaries"]:
        print(
            "警告: 共享目录缺少词典: "
            + ", ".join(result["missing_dictionaries"])
        )
    if args.no_deploy:
        print("已跳过重新部署")
    elif result["deploy_started"]:
        print("已启动小狼毫重新部署")
    else:
        print("未找到 WeaselDeployer.exe，请手动重新部署")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
