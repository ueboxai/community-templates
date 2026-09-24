"""pack.py 和 validate.py 共用的约定：哪些文件不进模板包、怎么收集工程文件。"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 打包时排除的目录（任意层级）：构建产物、缓存、版本控制和 IDE 目录
EXCLUDED_DIRS = {"Binaries", "Intermediate", "Saved", "DerivedDataCache", ".git", ".vs"}
# 系统自动生成的文件
EXCLUDED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
# UE 给每个开发者建的私人目录，子目录名就是本机用户名，打包者的真名会跟着模板分发出去
DEVELOPERS_DIR = ("Content", "Developers")


def is_excluded(parts: tuple[str, ...]) -> bool:
    """parts 是相对工程根目录的路径各段。"""
    return bool(EXCLUDED_DIRS.intersection(parts)) or parts[:2] == DEVELOPERS_DIR


def collect(src: Path) -> list[Path]:
    """返回 src 下要进模板包的文件，按包内路径排序。"""
    files = []
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if is_excluded(rel.parts) or p.name in EXCLUDED_FILES:
            continue
        if p.is_file():
            files.append(p)
    return sorted(files, key=lambda p: p.relative_to(src).as_posix())


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
