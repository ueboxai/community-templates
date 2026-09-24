#!/usr/bin/env python3
"""校验 manifest.json、packages/ 下的模板包和 templates/ 下的模板源码是否一致。

只用标准库，本地和 CI 跑的是同一份：

    python3 scripts/validate.py            # 校验
    python3 scripts/validate.py --fix      # 顺便把 manifest.json 整理成规范格式
    python3 scripts/validate.py --remote   # 同时下载并校验外链模板包（CI 会加）

有任何问题会逐条列出并以非零状态退出。需要审核的人留意、但不算错误的情况以警告列出。
"""

from __future__ import annotations

import datetime
import json
import os
import re
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from _common import EXCLUDED_DIRS, ROOT, collect, sha256_of

FORMAT_VERSION = 1
REQUIRED = ("id", "name", "packageUrl", "sha256")
# 字段 -> 允许的类型；不在这里的字段一律视为拼写错误
FIELDS: dict[str, type] = {
    "id": str,
    "name": str,
    "description": str,
    "category": str,
    "tags": list,
    "engineVersion": str,
    "packageUrl": str,
    "size": int,
    "sha256": str,
    "version": str,
    "updated": str,
    "minClientVersion": str,
    "author": str,
    "license": str,
    "homepage": str,
    "thumbnail": str,
}
TYPE_NAMES = {str: "字符串", int: "整数", list: "数组"}

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CATEGORY_RE = ID_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENGINE_RE = re.compile(r"^\d+\.\d+$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_TAGS = 10
THUMBNAIL_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_THUMBNAIL_SIZE = 512 * 1024

# 模板包的上限，防止 zip 炸弹：条目数和解压后的总字节数
MAX_ENTRIES = 20_000
MAX_UNCOMPRESSED = 2 << 30

# 打开工程时可能被执行的文件类型。不禁止，但 CI 会提示审核的人重点看
EXECUTABLE_SUFFIXES = {".py", ".dll", ".exe", ".so", ".dylib", ".bat", ".cmd", ".ps1", ".sh"}
# 模板里钉死 ProjectID 会让所有新建工程共用同一个工程标识
PROJECT_ID_RE = re.compile(r"^\s*ProjectID\s*=", re.MULTILINE)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def decode_text(data: bytes) -> str:
    """UE 的文本文件可能是 UTF-8（带或不带 BOM）或 UTF-16。"""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def same_bytes(zf: zipfile.ZipFile, info: zipfile.ZipInfo, path: Path) -> bool:
    # 逐字节比较，不用 CRC：CRC 可以被刻意撞出来
    if info.file_size != path.stat().st_size:
        return False
    with zf.open(info) as a, path.open("rb") as b:
        while True:
            x, y = a.read(1 << 20), b.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def check_uproject(data: bytes, where: str, r: Report, engine_version: str | None, flagged: list[str]) -> None:
    try:
        project = json.loads(decode_text(data))
    except ValueError:
        r.error(f"{where}: .uproject 不是合法的 JSON")
        return
    if not isinstance(project, dict):
        r.error(f"{where}: .uproject 顶层应为对象")
        return
    association = project.get("EngineAssociation")
    if engine_version is not None and association != engine_version:
        r.error(
            f"{where}: .uproject 的 EngineAssociation={association!r} "
            f"与清单的 engineVersion={engine_version!r} 不一致"
        )
    if project.get("Modules"):
        flagged.append("C++ 模块（.uproject 的 Modules）")
    for plugin in project.get("Plugins") or []:
        if isinstance(plugin, dict) and plugin.get("Name") == "PythonScriptPlugin" and plugin.get("Enabled"):
            flagged.append("启用了 PythonScriptPlugin")


def compare_source(
    zf: zipfile.ZipFile, files: dict[str, zipfile.ZipInfo], source: Path, where: str, name: str, r: Report
) -> None:
    top = source.name
    if not source.is_dir():
        r.error(f"{where}: 找不到模板源码 templates/{top}/，放在 packages/ 下的模板包必须附带源码")
        return
    expected = {p.relative_to(source).as_posix(): p for p in collect(source)}
    diffs = [f"包里缺少 {n}" for n in sorted(expected.keys() - files.keys())]
    diffs += [f"包里多出 {n}" for n in sorted(files.keys() - expected.keys())]
    diffs += [
        f"{n} 内容不同"
        for n in sorted(expected.keys() & files.keys())
        if not same_bytes(zf, files[n], expected[n])
    ]
    if diffs:
        more = f" 等 {len(diffs)} 处" if len(diffs) > 3 else ""
        r.error(
            f"{where}: {name} 与 templates/{top}/ 不一致（{'；'.join(diffs[:3])}{more}），"
            f"请运行 python3 scripts/pack.py templates/{top} 重新打包"
        )


def check_package(
    path: Path,
    where: str,
    r: Report,
    *,
    top: str,
    engine_version: str | None = None,
    source: Path | None = None,
) -> None:
    """检查模板包本身：结构、大小、工程文件、可执行内容；给了 source 还要与源码逐字节一致。"""
    name = f"{top}.zip"
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        r.error(f"{where}: {name} 不是合法的 zip")
        return
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            r.error(f"{where}: {name} 有 {len(infos)} 个条目，超过上限 {MAX_ENTRIES}")
            return
        total = sum(i.file_size for i in infos)
        if total > MAX_UNCOMPRESSED:
            r.error(f"{where}: {name} 解压后 {total} 字节，超过上限 {MAX_UNCOMPRESSED}")
            return
        broken = zf.testzip()
        if broken:
            r.error(f"{where}: {name} 中 {broken} CRC 校验失败")
            return

        seen: dict[str, str] = {}
        stray: list[str] = []
        files: dict[str, zipfile.ZipInfo] = {}  # 相对顶层目录的路径 -> 条目
        for info in infos:
            entry = info.filename
            p = PurePosixPath(entry)
            if "\\" in entry or ":" in entry or p.is_absolute() or ".." in p.parts:
                r.error(f"{where}: {name} 含非法路径 {entry!r}")
                continue
            key = entry.rstrip("/").casefold()
            if key in seen:
                if seen[key] == entry:
                    r.error(f"{where}: {name} 含重复条目 {entry!r}")
                else:
                    r.error(f"{where}: {name} 中 {entry!r} 与 {seen[key]!r} 只差大小写，在 Windows 上会互相覆盖")
                continue
            seen[key] = entry
            if info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16):
                r.error(f"{where}: {name} 含符号链接 {entry!r}")
                continue
            if p.parts[0] != top:
                stray.append(entry)
                continue
            bad = EXCLUDED_DIRS.intersection(p.parts if info.is_dir() else p.parts[:-1])
            if bad:
                r.error(f"{where}: {name} 不应包含 {sorted(bad)[0]}/ ({entry})")
                continue
            if not info.is_dir() and len(p.parts) > 1:
                files["/".join(p.parts[1:])] = info
        if stray:
            r.error(
                f"{where}: {name} 里应只有一个顶层目录 {top}/（与包名一致），"
                f"{stray[0]!r} 等 {len(stray)} 个条目不在其中"
            )

        flagged: list[str] = []
        uprojects = [n for n in files if n.lower().endswith(".uproject")]
        if not uprojects:
            r.error(f"{where}: {name} 里找不到 .uproject")
        elif len(uprojects) > 1 or "/" in uprojects[0]:
            r.error(f"{where}: {name} 的 {top}/ 下应有且只有一个 .uproject，实际为 {uprojects}")
        else:
            check_uproject(zf.read(files[uprojects[0]]), where, r, engine_version, flagged)

        for rel, info in files.items():
            if rel.startswith("Config/") and rel.lower().endswith(".ini"):
                if PROJECT_ID_RE.search(decode_text(zf.read(info))):
                    r.error(f"{where}: {name} 的 {rel} 写死了 ProjectID，请删掉，UE 会在工程首次打开时生成")

        roots = {rel.split("/")[0] for rel in files}
        if "Source" in roots:
            flagged.append("C++ 源码（Source/）")
        if "Plugins" in roots:
            flagged.append("工程内插件（Plugins/）")
        suffixes = sorted({PurePosixPath(rel).suffix.lower() for rel in files} & EXECUTABLE_SUFFIXES)
        if suffixes:
            flagged.append(f"{' / '.join(suffixes)} 文件")
        if flagged:
            r.warn(f"{where}: 含打开工程时可能执行的内容：{'、'.join(flagged)}，审核时请重点检查")

        if source is not None:
            compare_source(zf, files, source, where, name, r)


def download(url: str, limit: int, where: str, r: Report) -> Path | None:
    tmp = tempfile.NamedTemporaryFile(prefix="template-", suffix=".zip", delete=False)
    try:
        with tmp, urllib.request.urlopen(url, timeout=60) as resp:
            received = 0
            while chunk := resp.read(1 << 20):
                received += len(chunk)
                if received > limit:
                    raise ValueError(f"超过 {limit} 字节")
                tmp.write(chunk)
    except (OSError, ValueError) as e:
        r.error(f"{where}: 下载 {url} 失败：{e}")
        Path(tmp.name).unlink(missing_ok=True)
        return None
    return Path(tmp.name)


def check_template(
    i: int,
    t: object,
    r: Report,
    root: Path,
    remote: bool,
    used_packages: set[str],
    used_thumbnails: set[str],
) -> None:
    where = f"templates[{i}]"
    if not isinstance(t, dict):
        r.error(f"{where}: 应为对象")
        return
    if isinstance(t.get("id"), str):
        where = f"templates[{i}] ({t['id']})"

    for key in REQUIRED:
        if key not in t:
            r.error(f"{where}: 缺少必填字段 {key}")
    for key, value in t.items():
        expected = FIELDS.get(key)
        if expected is None:
            r.error(f"{where}: 未知字段 {key}")
        elif not isinstance(value, expected) or isinstance(value, bool):
            r.error(f"{where}: {key} 类型应为{TYPE_NAMES[expected]}")
        elif expected is str and not value.strip():
            r.error(f"{where}: {key} 不能为空")

    def match(key: str, regex: re.Pattern[str], hint: str) -> bool:
        v = t.get(key)
        if isinstance(v, str) and not regex.match(v):
            r.error(f"{where}: {key}={v!r} 格式不对，应为{hint}")
            return False
        return isinstance(v, str)

    match("id", ID_RE, "小写字母/数字/连字符")
    match("category", CATEGORY_RE, "小写字母/数字/连字符")
    match("sha256", SHA256_RE, " 64 位小写十六进制")
    engine_ok = match("engineVersion", ENGINE_RE, "「主版本.次版本」，如 5.7")
    match("version", SEMVER_RE, "语义化版本，如 1.0.0")
    match("minClientVersion", SEMVER_RE, "语义化版本，如 1.0.0")
    if match("updated", DATE_RE, " YYYY-MM-DD 格式的日期"):
        try:
            datetime.date.fromisoformat(t["updated"])
        except ValueError:
            r.error(f"{where}: updated={t['updated']!r} 不是有效日期")
    if isinstance(t.get("homepage"), str) and not t["homepage"].startswith("https://"):
        r.error(f"{where}: homepage 应为 https:// 开头的地址")

    tags = t.get("tags")
    if isinstance(tags, list):
        if len(tags) > MAX_TAGS:
            r.error(f"{where}: tags 最多 {MAX_TAGS} 个")
        for tag in tags:
            if not isinstance(tag, str) or not ID_RE.match(tag):
                r.error(f"{where}: tags 里的 {tag!r} 格式不对，应为小写字母/数字/连字符")
        if len(set(map(str, tags))) != len(tags):
            r.error(f"{where}: tags 有重复")

    thumb = t.get("thumbnail")
    if isinstance(thumb, str):
        rel = PurePosixPath(thumb)
        if rel.parent != PurePosixPath("thumbnails") or rel.suffix.lower() not in THUMBNAIL_SUFFIXES:
            r.error(f"{where}: thumbnail 应形如 thumbnails/<名字>.png（png / jpg / webp）")
        elif not (root / rel).is_file():
            r.error(f"{where}: 找不到 {thumb}")
        else:
            used_thumbnails.add(rel.name)
            if (root / rel).stat().st_size > MAX_THUMBNAIL_SIZE:
                r.error(f"{where}: {thumb} 超过 {MAX_THUMBNAIL_SIZE // 1024} KB")

    engine_version = t["engineVersion"] if engine_ok else None
    url = t.get("packageUrl")
    if not isinstance(url, str):
        return
    if url.startswith("http://"):
        r.error(f"{where}: packageUrl 外链必须用 https")
        return
    if url.startswith("https://"):
        top = PurePosixPath(urllib.parse.urlparse(url).path).stem
        if not remote:
            r.warn(f"{where}: 外链模板包未下载校验，加 --remote 参数可校验")
            return
        size = t.get("size")
        path = download(url, size + 1 if isinstance(size, int) else MAX_UNCOMPRESSED, where, r)
        if path is None:
            return
        try:
            check_hash_and_size(path, t, where, r)
            check_package(path, where, r, top=top, engine_version=engine_version)
        finally:
            path.unlink(missing_ok=True)
        r.warn(f"{where}: 外链模板包没有随仓库附带源码，审核时需要解包人工检查")
        return

    rel = PurePosixPath(url)
    if rel.parent != PurePosixPath("packages") or rel.suffix != ".zip":
        r.error(f"{where}: packageUrl 应形如 packages/<名字>.zip")
        return
    if rel.name in used_packages:
        r.error(f"{where}: {rel.name} 被多个条目引用")
    used_packages.add(rel.name)
    path = root / rel
    if not path.is_file():
        r.error(f"{where}: 找不到 {url}")
        return
    check_hash_and_size(path, t, where, r)
    check_package(
        path, where, r, top=rel.stem, engine_version=engine_version, source=root / "templates" / rel.stem
    )


def check_hash_and_size(path: Path, t: dict, where: str, r: Report) -> None:
    actual = sha256_of(path)
    if isinstance(t.get("sha256"), str) and t["sha256"] != actual:
        r.error(f"{where}: sha256 不匹配，实际为 {actual}")
    size = path.stat().st_size
    if isinstance(t.get("size"), int) and t["size"] != size:
        r.error(f"{where}: size 不匹配，实际为 {size}")


def validate(root: Path = ROOT, *, fix: bool = False, remote: bool = False) -> tuple[Report, int]:
    """校验 root 下的仓库，返回问题报告和模板数。"""
    r = Report()
    manifest = root / "manifest.json"

    raw = manifest.read_bytes()
    if b"\r" in raw:
        r.error("manifest.json: 应使用 LF 换行")
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        r.error(f"manifest.json: 无法解析: {e}")
        return r, 0

    canonical = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if text.replace("\r\n", "\n") != canonical:
        if fix:
            manifest.write_bytes(canonical.encode("utf-8"))
        else:
            r.error(
                "manifest.json: 格式不规范（2 空格缩进、UTF-8 原文、末尾换行），"
                "可运行 python3 scripts/validate.py --fix 自动整理"
            )

    if not isinstance(data, dict):
        r.error("manifest.json: 顶层应为对象")
        data = {}
    if data.get("formatVersion") != FORMAT_VERSION:
        r.error(f"manifest.json: formatVersion 应为 {FORMAT_VERSION}")
    templates = data.get("templates")
    if not isinstance(templates, list):
        r.error("manifest.json: templates 应为数组")
        templates = []

    ids: set[str] = set()
    used_packages: set[str] = set()
    used_thumbnails: set[str] = set()
    for i, t in enumerate(templates):
        tid = t.get("id") if isinstance(t, dict) else None
        check_template(i, t, r, root, remote, used_packages, used_thumbnails)
        if isinstance(tid, str):
            if tid in ids:
                r.error(f"templates[{i}]: id {tid!r} 重复")
            ids.add(tid)

    packages = root / "packages"
    for p in sorted(packages.glob("*")) if packages.is_dir() else []:
        if p.name.startswith("."):
            continue
        if p.suffix != ".zip":
            r.error(f"packages/{p.name}: packages/ 下只放 .zip 模板包")
        elif p.name not in used_packages:
            r.error(f"packages/{p.name}: 没有被 manifest.json 引用")

    sources = root / "templates"
    packaged = {PurePosixPath(n).stem for n in used_packages}
    for p in sorted(sources.glob("*")) if sources.is_dir() else []:
        if p.name.startswith("."):
            continue
        if not p.is_dir():
            r.error(f"templates/{p.name}: templates/ 下只放模板工程目录")
        elif p.name not in packaged:
            r.error(f"templates/{p.name}/: 没有对应的 packages/{p.name}.zip 被清单引用")

    thumbnails = root / "thumbnails"
    for p in sorted(thumbnails.glob("*")) if thumbnails.is_dir() else []:
        if not p.name.startswith(".") and p.name not in used_thumbnails:
            r.error(f"thumbnails/{p.name}: 没有被 manifest.json 引用")

    readme = (root / "README.md").read_text(encoding="utf-8")
    for tid in sorted(ids):
        if f"`{tid}`" not in readme:
            r.error(f"README.md: 「现有模板」表里缺少 `{tid}`")

    return r, len(templates)


def main() -> int:
    args = sys.argv[1:]
    unknown = set(args) - {"--fix", "--remote"}
    if unknown:
        print(__doc__, file=sys.stderr)
        return 2
    r, count = validate(fix="--fix" in args, remote="--remote" in args)

    # 在 GitHub Actions 里输出成注解，绿色的运行里也能在 PR 上看到警告
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for w in r.warnings:
        print(f"::warning::{w}" if in_actions else f"⚠ {w}")
    if r.errors:
        for e in r.errors:
            print(f"✗ {e}", file=sys.stderr)
        print(f"\n共 {len(r.errors)} 个问题", file=sys.stderr)
        return 1
    print(f"✓ manifest.json 校验通过，共 {count} 个模板")
    return 0


if __name__ == "__main__":
    sys.exit(main())
