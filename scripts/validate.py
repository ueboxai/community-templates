#!/usr/bin/env python3
"""校验 manifest.json 与 packages/ 下的模板包是否一致。

只用标准库，本地和 CI 跑的是同一份：

    python3 scripts/validate.py

有任何问题会逐条列出并以非零状态退出。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
README = ROOT / "README.md"
PACKAGES = ROOT / "packages"

FORMAT_VERSION = 1
REQUIRED = ("id", "name", "packageUrl", "sha256")
# 字段 -> 允许的类型；不在这里的字段一律视为拼写错误
FIELDS: dict[str, type] = {
    "id": str,
    "name": str,
    "description": str,
    "category": str,
    "engineVersion": str,
    "packageUrl": str,
    "size": int,
    "sha256": str,
    "version": str,
    "author": str,
    "license": str,
}

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CATEGORY_RE = ID_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENGINE_RE = re.compile(r"^\d+\.\d+$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")

# 打包时必须排除的目录（任意层级）
EXCLUDED_DIRS = {"Binaries", "Intermediate", "Saved", "DerivedDataCache", ".git", ".vs"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_package(path: Path, where: str, errors: list[str]) -> None:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        errors.append(f"{where}: {path.name} 不是合法的 zip")
        return
    with zf:
        names = zf.namelist()
        if not any(n.lower().endswith(".uproject") for n in names):
            errors.append(f"{where}: {path.name} 里找不到 .uproject")
        for name in names:
            p = PurePosixPath(name)
            if "\\" in name or p.is_absolute() or ".." in p.parts:
                errors.append(f"{where}: {path.name} 含非法路径 {name!r}")
            bad = EXCLUDED_DIRS.intersection(p.parts[:-1] if not name.endswith("/") else p.parts)
            if bad:
                errors.append(f"{where}: {path.name} 不应包含 {sorted(bad)[0]}/ ({name})")
        broken = zf.testzip()
        if broken:
            errors.append(f"{where}: {path.name} 中 {broken} CRC 校验失败")


def check_template(i: int, t: object, errors: list[str]) -> str | None:
    where = f"templates[{i}]"
    if not isinstance(t, dict):
        errors.append(f"{where}: 应为对象")
        return None
    if isinstance(t.get("id"), str):
        where = f"templates[{i}] ({t['id']})"

    for key in REQUIRED:
        if key not in t:
            errors.append(f"{where}: 缺少必填字段 {key}")
    for key, value in t.items():
        expected = FIELDS.get(key)
        if expected is None:
            errors.append(f"{where}: 未知字段 {key}")
        elif not isinstance(value, expected) or isinstance(value, bool):
            errors.append(f"{where}: {key} 类型应为 {expected.__name__}")
        elif expected is str and not value.strip():
            errors.append(f"{where}: {key} 不能为空")

    def match(key: str, regex: re.Pattern[str], hint: str) -> None:
        v = t.get(key)
        if isinstance(v, str) and not regex.match(v):
            errors.append(f"{where}: {key}={v!r} 格式不对，应为{hint}")

    match("id", ID_RE, "小写字母/数字/连字符")
    match("category", CATEGORY_RE, "小写字母/数字/连字符")
    match("sha256", SHA256_RE, " 64 位小写十六进制")
    match("engineVersion", ENGINE_RE, "「主版本.次版本」，如 5.7")
    match("version", SEMVER_RE, "语义化版本，如 1.0.0")

    url = t.get("packageUrl")
    if not isinstance(url, str):
        return None
    if url.startswith(("http://", "https://")):
        # 外链包没法在这里校验内容，只能信任投稿者给的 sha256
        return None
    rel = PurePosixPath(url)
    if rel.parent != PurePosixPath("packages") or rel.suffix != ".zip":
        errors.append(f"{where}: packageUrl 应形如 packages/<名字>.zip")
        return None
    path = ROOT / rel
    if not path.is_file():
        errors.append(f"{where}: 找不到 {url}")
        return None

    actual = sha256_of(path)
    if isinstance(t.get("sha256"), str) and t["sha256"] != actual:
        errors.append(f"{where}: sha256 不匹配，实际为 {actual}")
    size = path.stat().st_size
    if "size" in t and t["size"] != size:
        errors.append(f"{where}: size 不匹配，实际为 {size}")
    check_package(path, where, errors)
    return rel.name


def main() -> int:
    errors: list[str] = []

    raw = MANIFEST.read_bytes()
    if b"\r" in raw:
        errors.append("manifest.json: 应使用 LF 换行")
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"manifest.json: 无法解析: {e}", file=sys.stderr)
        return 1

    canonical = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if text.replace("\r\n", "\n") != canonical:
        errors.append(
            "manifest.json: 格式不规范（2 空格缩进、UTF-8 原文、末尾换行），"
            "可运行 python3 scripts/validate.py --fix 自动整理"
        )
        if "--fix" in sys.argv[1:]:
            MANIFEST.write_text(canonical, encoding="utf-8", newline="\n")
            errors.pop()

    if not isinstance(data, dict):
        errors.append("manifest.json: 顶层应为对象")
        data = {}
    if data.get("formatVersion") != FORMAT_VERSION:
        errors.append(f"manifest.json: formatVersion 应为 {FORMAT_VERSION}")
    templates = data.get("templates")
    if not isinstance(templates, list):
        errors.append("manifest.json: templates 应为数组")
        templates = []

    ids: set[str] = set()
    used: set[str] = set()
    for i, t in enumerate(templates):
        name = check_template(i, t, errors)
        if name:
            if name in used:
                errors.append(f"templates[{i}]: {name} 被多个条目引用")
            used.add(name)
        tid = t.get("id") if isinstance(t, dict) else None
        if isinstance(tid, str):
            if tid in ids:
                errors.append(f"templates[{i}]: id {tid!r} 重复")
            ids.add(tid)

    for zip_path in sorted(PACKAGES.glob("*")):
        if zip_path.name.startswith("."):
            continue
        if zip_path.suffix != ".zip":
            errors.append(f"packages/{zip_path.name}: packages/ 下只放 .zip 模板包")
        elif zip_path.name not in used:
            errors.append(f"packages/{zip_path.name}: 没有被 manifest.json 引用")

    readme = README.read_text(encoding="utf-8")
    for tid in sorted(ids):
        if f"`{tid}`" not in readme:
            errors.append(f"README.md: 「现有模板」表里缺少 `{tid}`")

    if errors:
        for e in errors:
            print(f"✗ {e}", file=sys.stderr)
        print(f"\n共 {len(errors)} 个问题", file=sys.stderr)
        return 1
    print(f"✓ manifest.json 校验通过，共 {len(templates)} 个模板")
    return 0


if __name__ == "__main__":
    sys.exit(main())
