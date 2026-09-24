"""scripts/ 下打包和校验脚本的测试，只用标准库：

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pack  # noqa: E402
import validate  # noqa: E402

UPROJECT = {"FileVersion": 3, "EngineAssociation": "5.7", "Plugins": []}


class RepoTestCase(unittest.TestCase):
    """在临时目录里搭一个只有一个模板 Demo 的最小仓库。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.src = self.root / "templates" / "Demo"
        self.write("Demo.uproject", json.dumps(UPROJECT))
        self.write("Config/DefaultGame.ini", "[/Script/EngineSettings.GeneralProjectSettings]\nProjectName=Demo\n")
        self.entry = {
            "id": "demo",
            "name": "Demo",
            "packageUrl": "packages/Demo.zip",
            "sha256": "",
            "engineVersion": "5.7",
            "version": "1.0.0",
        }
        (self.root / "README.md").write_text("| Demo | `demo` |\n", encoding="utf-8")
        self.repack()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, rel: str, text: str) -> None:
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    @property
    def zip_path(self) -> Path:
        return self.root / "packages" / "Demo.zip"

    def repack(self) -> None:
        pack.pack(self.src, self.zip_path)
        self.sync_manifest()

    def sync_manifest(self, **extra: object) -> None:
        data = self.zip_path.read_bytes()
        self.entry.update(sha256=hashlib.sha256(data).hexdigest(), size=len(data), **extra)
        manifest = {"formatVersion": 1, "templates": [self.entry]}
        (self.root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def write_zip(self, entries: list[tuple[zipfile.ZipInfo | str, bytes]]) -> None:
        """手工写一个模板包（用来构造 pack.py 不会产生的坏包），并同步清单。"""
        with zipfile.ZipFile(self.zip_path, "w") as zf:
            for info, data in entries:
                zf.writestr(info, data)
        self.sync_manifest()

    def run_validate(self, **kwargs: bool) -> validate.Report:
        report, _ = validate.validate(self.root, **kwargs)
        return report

    def assertError(self, report: validate.Report, needle: str) -> None:
        self.assertTrue(
            any(needle in e for e in report.errors),
            f"期望有包含 {needle!r} 的错误，实际为 {report.errors}",
        )


class PackTest(RepoTestCase):
    def test_reproducible(self) -> None:
        first = self.zip_path.read_bytes()
        (self.src / "Config" / "DefaultGame.ini").touch()  # 只改时间戳
        self.repack()
        self.assertEqual(first, self.zip_path.read_bytes())

    def test_excludes_build_dirs(self) -> None:
        self.write("Saved/Logs/Demo.log", "log")
        self.write("Intermediate/x.bin", "x")
        self.write(".DS_Store", "x")
        self.write("Content/Developers/zhangsan/a.uasset", "x")
        self.write("Content/Maps/Main.umap", "x")
        self.repack()
        with zipfile.ZipFile(self.zip_path) as zf:
            self.assertEqual(
                zf.namelist(),
                ["Demo/Config/DefaultGame.ini", "Demo/Content/Maps/Main.umap", "Demo/Demo.uproject"],
            )

    def test_requires_uproject(self) -> None:
        (self.src / "Demo.uproject").unlink()
        with self.assertRaises(ValueError):
            pack.pack(self.src, self.zip_path)


class ValidateTest(RepoTestCase):
    def test_valid_repo_passes(self) -> None:
        report = self.run_validate()
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_sha256_and_size_mismatch(self) -> None:
        self.write("Config/DefaultEngine.ini", "[x]\n")
        pack.pack(self.src, self.zip_path)  # 不同步清单
        report = self.run_validate()
        self.assertError(report, "sha256 不匹配")
        self.assertError(report, "size 不匹配")

    def test_project_id_rejected(self) -> None:
        self.write("Config/DefaultGame.ini", "[/Script/EngineSettings.GeneralProjectSettings]\nProjectID=ABC\n")
        self.repack()
        self.assertError(self.run_validate(), "写死了 ProjectID")

    def test_engine_association_must_match(self) -> None:
        self.write("Demo.uproject", json.dumps({**UPROJECT, "EngineAssociation": "5.6"}))
        self.repack()
        self.assertError(self.run_validate(), "EngineAssociation='5.6'")

    def test_source_must_match_package(self) -> None:
        self.write("Config/DefaultGame.ini", "changed\n")
        self.assertError(self.run_validate(), "Config/DefaultGame.ini 内容不同")

    def test_package_requires_source(self) -> None:
        (self.src / "Demo.uproject").unlink()
        (self.src / "Config" / "DefaultGame.ini").unlink()
        (self.src / "Config").rmdir()
        self.src.rmdir()
        self.assertError(self.run_validate(), "找不到模板源码 templates/Demo/")

    def test_orphan_source_dir(self) -> None:
        (self.root / "templates" / "Other").mkdir()
        self.assertError(self.run_validate(), "templates/Other/")

    def test_single_top_level_dir(self) -> None:
        self.write_zip([("Demo/Demo.uproject", json.dumps(UPROJECT).encode()), ("Extra/readme.txt", b"x")])
        self.assertError(self.run_validate(), "只有一个顶层目录 Demo/")

    def test_rejects_symlink(self) -> None:
        link = zipfile.ZipInfo("Demo/link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        self.write_zip([("Demo/Demo.uproject", json.dumps(UPROJECT).encode()), (link, b"/etc/passwd")])
        self.assertError(self.run_validate(), "符号链接")

    def test_rejects_case_collision(self) -> None:
        self.write_zip(
            [
                ("Demo/Demo.uproject", json.dumps(UPROJECT).encode()),
                ("Demo/Config/a.ini", b"x"),
                ("Demo/config/A.ini", b"y"),
            ]
        )
        self.assertError(self.run_validate(), "只差大小写")

    def test_rejects_path_traversal(self) -> None:
        self.write_zip([("Demo/Demo.uproject", json.dumps(UPROJECT).encode()), ("Demo/../evil.txt", b"x")])
        self.assertError(self.run_validate(), "非法路径")

    def test_rejects_excluded_dirs(self) -> None:
        self.write_zip([("Demo/Demo.uproject", json.dumps(UPROJECT).encode()), ("Demo/Binaries/Win64/a.dll", b"x")])
        self.assertError(self.run_validate(), "不应包含 Binaries/")

    def test_uncompressed_size_limit(self) -> None:
        with mock.patch.object(validate, "MAX_UNCOMPRESSED", 10):
            self.assertError(self.run_validate(), "超过上限")

    def test_warns_on_executable_content(self) -> None:
        self.write(
            "Demo.uproject",
            json.dumps({**UPROJECT, "Plugins": [{"Name": "PythonScriptPlugin", "Enabled": True}]}),
        )
        self.write("Content/Python/init_unreal.py", "print('hi')\n")
        self.repack()
        report = self.run_validate()
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("PythonScriptPlugin", report.warnings[0])
        self.assertIn(".py", report.warnings[0])

    def test_optional_fields(self) -> None:
        self.sync_manifest(category="render", homepage="https://example.com", previewUrl="https://example.com/a.png")
        self.assertEqual(self.run_validate().errors, [])

    def test_optional_field_formats(self) -> None:
        self.sync_manifest(category="rpg", homepage="http://example.com", tags=["x"])
        report = self.run_validate()
        self.assertError(report, "category='rpg' 客户端不认识")
        self.assertError(report, "homepage 应为 https://")
        self.assertError(report, "未知字段 tags")

    def test_previews(self) -> None:
        previews = self.root / "previews"
        previews.mkdir()
        (previews / "demo.png").write_bytes(b"\x89PNG")
        self.assertError(self.run_validate(), "previews/demo.png: 没有被 manifest.json 引用")
        self.sync_manifest(previewUrl="previews/demo.png")
        self.assertEqual(self.run_validate().errors, [])
        self.sync_manifest(previewUrl="images/demo.png")
        self.assertError(self.run_validate(), "previewUrl 应形如 previews/")

    def test_security_token_rejected(self) -> None:
        self.write(
            "Config/DefaultEngine.ini",
            "[/Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings]\nSecurityToken=ABCDEF\n",
        )
        self.repack()
        self.assertError(self.run_validate(), "SecurityToken")

    def test_developers_dir_rejected(self) -> None:
        self.write_zip(
            [
                ("Demo/Demo.uproject", json.dumps(UPROJECT).encode()),
                ("Demo/Content/Developers/zhangsan/a.uasset", b"x"),
            ]
        )
        self.assertError(self.run_validate(), "Content/Developers/")

    def test_external_package_requires_https(self) -> None:
        self.zip_path.unlink()
        self.entry["packageUrl"] = "http://example.com/Demo.zip"
        manifest = {"formatVersion": 1, "templates": [self.entry]}
        (self.root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.assertError(self.run_validate(), "必须用 https")

    def test_external_package_remote(self) -> None:
        # 外链包：把本地包搬到别处当作「下载结果」，源码目录也去掉
        remote_copy = self.root / "remote.zip"
        self.zip_path.rename(remote_copy)
        for p in sorted(self.src.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() else p.unlink()
        self.src.rmdir()
        self.entry["packageUrl"] = "https://example.com/releases/Demo.zip"
        manifest = {"formatVersion": 1, "templates": [self.entry]}
        (self.root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        report = self.run_validate()
        self.assertEqual(report.errors, [])
        self.assertIn("未下载校验", report.warnings[0])

        def fake_download(url: str, limit: int, where: str, r: validate.Report) -> Path:
            tmp = self.root / "downloaded.zip"
            tmp.write_bytes(remote_copy.read_bytes())
            return tmp

        with mock.patch.object(validate, "download", fake_download):
            report = self.run_validate(remote=True)
        self.assertEqual(report.errors, [])
        self.assertIn("没有随仓库附带源码", report.warnings[0])

    def test_download_size_limit(self) -> None:
        report = validate.Report()
        path = validate.download(self.zip_path.as_uri(), 10, "t", report)
        self.assertIsNone(path)
        self.assertError(report, "超过 10 字节")
        path = validate.download(self.zip_path.as_uri(), 1 << 20, "t", report)
        self.assertIsNotNone(path)
        self.assertEqual(path.read_bytes(), self.zip_path.read_bytes())
        path.unlink()

    def test_readme_must_list_template(self) -> None:
        (self.root / "README.md").write_text("nothing here\n", encoding="utf-8")
        self.assertError(self.run_validate(), "缺少 `demo`")

    def test_fix_formats_manifest(self) -> None:
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(json.loads(manifest.read_text()), indent=4), encoding="utf-8")
        self.assertError(self.run_validate(), "格式不规范")
        self.assertEqual(self.run_validate(fix=True).errors, [])
        self.assertEqual(self.run_validate().errors, [])


if __name__ == "__main__":
    unittest.main()
