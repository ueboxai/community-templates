# 投稿指南

## 流程

1. 准备好 UE 工程目录（任意层级下有一个 `.uproject` 就行）
2. 打包：

   ```sh
   python3 scripts/pack.py path/to/MyTemplate
   ```

   脚本会排除 `Binaries` / `Intermediate` / `Saved` / `DerivedDataCache` / `.git` / `.vs`，
   生成 `packages/MyTemplate.zip`，并打印要填进清单的 `size` 和 `sha256`。
   同样的输入每次打出的字节都一样，重新打包不会无故改掉哈希。

   也可以自己打 zip，但请同样排除上面这些目录，然后用 `sha256sum` 算哈希。
3. 在 `manifest.json` 的 `templates` 末尾加一条（字段见下）
4. 本地校验：

   ```sh
   python3 scripts/validate.py
   ```

5. 提 PR。CI 会跑同一个校验脚本。

更新已有模板时，替换 zip、更新 `size` / `sha256`，并提升 `version`。

## 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | ✓ | 唯一标识，小写字母 / 数字 / 连字符，如 `gamestart`。发布后不要改 |
| `name` | ✓ | 显示名称 |
| `packageUrl` | ✓ | 模板包路径，形如 `packages/<名字>.zip`（相对于清单地址） |
| `sha256` | ✓ | 模板包的 sha256，64 位小写十六进制 |
| `description` |  | 一两句话的简介 |
| `category` |  | 分类，小写，如 `game`、`render` |
| `engineVersion` |  | 适用的引擎版本，`主版本.次版本`，如 `5.7` |
| `size` |  | 模板包字节数 |
| `version` |  | 模板自身版本，语义化版本，如 `1.0.0` |
| `author` |  | 作者 |
| `license` |  | 许可证，建议用 [SPDX 标识](https://spdx.org/licenses/)，如 `Apache-2.0` |

**没有合法 `sha256` 的条目会被客户端整条丢弃。** 模板包解压出来是一个完整的 UE 工程，
打开时里面的 C++、插件、脚本都会跑，「下到的字节确实是你写的那份」是客户端唯一能提供的保证。

## 约定

- `manifest.json`：UTF-8、LF、2 空格缩进、末尾换行，中文直接写不转义。
  格式不对时可以 `python3 scripts/validate.py --fix` 自动整理
- `packages/` 下只放被清单引用的 `.zip`
- 提交信息使用 `feat:` / `fix:` / `chore:` / `docs:` 前缀
