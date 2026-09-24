#!/usr/bin/env python3
"""把一个 UE 工程目录打成可复现的模板包，并打印 manifest 里要填的 size / sha256。

    python3 scripts/pack.py templates/<名字> [输出.zip]

- 自动排除 Binaries / Intermediate / Saved / DerivedDataCache / .git / .vs
- 条目按路径排序、时间戳固定为 2020-01-01，同样的输入永远得到同样的字节，
  重新打包不会无故改掉 sha256
- 输出默认是 packages/<目录名>.zip
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

from _common import ROOT, collect

FIXED_TIME = (2020, 1, 1, 8, 0, 0)


def pack(src: Path, out: Path) -> int:
    """把 src 打包到 out，返回打进去的文件数。src 里必须有 .uproject。"""
    files = collect(src)
    if not any(p.suffix.lower() == ".uproject" for p in files):
        raise ValueError(f"{src} 里找不到 .uproject")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in files:
            # 包内保留顶层目录名，解压后是 <目录名>/<工程文件>
            info = zipfile.ZipInfo(f"{src.name}/{p.relative_to(src).as_posix()}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, p.read_bytes(), compresslevel=9)
    return len(files)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(sys.argv[1]).resolve()
    if not src.is_dir():
        print(f"不是目录: {src}", file=sys.stderr)
        return 2
    out = Path(sys.argv[2]) if len(sys.argv) == 3 else ROOT / "packages" / f"{src.name}.zip"
    try:
        count = pack(src, out)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    data = out.read_bytes()
    print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}  ({count} 个文件)")
    print(f'"size": {len(data)},')
    print(f'"sha256": "{hashlib.sha256(data).hexdigest()}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
