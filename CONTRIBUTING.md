# 投稿指南

## 流程

1. 把 UE 工程目录放到 `templates/<名字>/` 下，工程根目录里要有一个 `.uproject`。
   `<名字>` 就是模板包的文件名，如 `templates/GameStart/` 对应 `packages/GameStart.zip`。

   模板源码和模板包一起提交，审核的人在 PR 里看到的是逐行的改动，不是一个看不透的 zip。
   CI 会逐字节核对两者，对不上就报错。
2. 打包：

   ```sh
   python3 scripts/pack.py templates/MyTemplate
   ```

   脚本会排除 `Binaries` / `Intermediate` / `Saved` / `DerivedDataCache` / `.git` / `.vs`，
   生成 `packages/MyTemplate.zip`，并打印要填进清单的 `size` 和 `sha256`。
   同样的输入每次打出的字节都一样，重新打包不会无故改掉哈希。
3. 在 `manifest.json` 的 `templates` 末尾加一条（字段见下）
4. 本地校验和测试：

   ```sh
   python3 scripts/validate.py
   python3 -m unittest discover -s tests
   ```

5. 在 README 的「现有模板」表里加一行
6. 提 PR。CI 会跑同样的校验和测试。PR 上 `signature` 这一项失败是正常的，见[签名](#签名)。

更新已有模板时，改 `templates/<名字>/` 下的文件，重新打包，更新 `size` / `sha256`，并提升 `version`。

只需要 Python 3.9+，不用装任何依赖。

## 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | ✓ | 唯一标识，小写字母 / 数字 / 连字符，如 `gamestart`。发布后不要改 |
| `name` | ✓ | 显示名称 |
| `packageUrl` | ✓ | 模板包地址，一般是 `packages/<名字>.zip`（相对于清单地址）；大包见[大模板包](#大模板包) |
| `sha256` | ✓ | 模板包的 sha256，64 位小写十六进制 |
| `description` |  | 一两句话的简介 |
| `category` |  | 分类，小写，如 `game`、`render` |
| `tags` |  | 标签数组，每个都是小写字母 / 数字 / 连字符，最多 10 个，如 `["lumen", "starter"]` |
| `engineVersion` |  | 适用的引擎版本，`主版本.次版本`，如 `5.7`。必须和 `.uproject` 的 `EngineAssociation` 一致 |
| `size` |  | 模板包字节数 |
| `version` |  | 模板自身版本，语义化版本，如 `1.0.0` |
| `updated` |  | 最近一次更新的日期，`YYYY-MM-DD` |
| `minClientVersion` |  | 需要的最低虚幻盒子版本，语义化版本。模板依赖新版客户端的功能时才填 |
| `author` |  | 作者 |
| `license` |  | 许可证，建议用 [SPDX 标识](https://spdx.org/licenses/)，如 `Apache-2.0` |
| `homepage` |  | 模板主页或源码仓库，必须是 `https://` 地址 |
| `thumbnail` |  | 缩略图，形如 `thumbnails/<名字>.png`（png / jpg / webp，不超过 512 KB） |

**没有合法 `sha256` 的条目会被客户端整条丢弃。** 模板包解压出来是一个完整的 UE 工程，
打开时里面的 C++、插件、脚本都会跑，「下到的字节确实是你写的那份」是客户端唯一能提供的保证。

### 兼容性

- 客户端遇到不认识的字段应当忽略，而不是丢弃整条。所以新增**可选**字段不需要改 `formatVersion`
- 只有不兼容的改动（改必填字段、改已有字段的含义）才提升 `formatVersion`

## CI 检查什么

- 清单字段齐全、类型和格式正确，`id` 不重复
- `sha256`、`size` 与实际模板包一致
- 模板包是合法 zip，只有一个与包名同名的顶层目录，里面有且只有一个 `.uproject`
- 模板包里没有 `Binaries` / `Intermediate` / `Saved` / `DerivedDataCache` / `.git` / `.vs`，
  没有绝对路径、`..`、符号链接、重复条目、只差大小写的路径
- 模板包解压后不超过 2 GiB、不超过 20000 个条目
- `.uproject` 的 `EngineAssociation` 与 `engineVersion` 一致
- `Config/*.ini` 里没有写死 `ProjectID`
- `packages/` 下的模板包与 `templates/` 下的源码逐字节一致
- `packages/`、`templates/`、`thumbnails/` 下没有清单没引用的东西
- README 的「现有模板」表列出了清单里的每个模板
- `manifest.json` 是 UTF-8、LF、2 空格缩进
- 外链模板包会被下载下来做同样的检查

包里有 C++ 源码、工程内插件、Python 脚本、`.dll` / `.exe` 等会被执行的内容，
或者 `.uproject` 启用了 `PythonScriptPlugin`，CI 不会报错，但会在 PR 上给出警告，审核时会重点看。

## 约定

- `manifest.json`：UTF-8、LF、2 空格缩进、末尾换行，中文直接写不转义。
  格式不对时可以 `python3 scripts/validate.py --fix` 自动整理
- 模板配置里不要写 `ProjectID`，UE 会在工程首次打开时生成；写死的话所有新建工程会共用同一个标识
- 不要提交编辑器自动写出的无用配置（比如只有引擎默认值的 `DefaultEditor.ini`）
- `packages/` 下只放被清单引用的 `.zip`
- 提交信息使用 `feat:` / `fix:` / `chore:` / `docs:` 前缀

## 大模板包

`packages/` 适合几 MB 以内的模板。带大量资源的模板请放到 GitHub Releases 之类的地方，
`packageUrl` 填完整的 `https://` 地址，同样要填 `sha256` 和 `size`。

- **不要用 Git LFS。** 客户端从 `raw.githubusercontent.com` 读文件，LFS 文件在那里只是一个指针文本，
  下下来 sha256 必然对不上
- 外链包不在仓库里放源码，CI 会下载下来做结构检查，并提示审核的人需要解包人工检查

## 维护者

### 签名

客户端通过 sha256 确认模板包没被换掉，但清单本身是否可信，要看这个 GitHub 仓库和账号有没有被攻破。
清单签名用来补上这一环：维护者在自己的电脑上用私钥给 `manifest.json` 签名，
客户端内置公钥，只接受签名有效的清单。

用的是 [minisign](https://jedisct1.github.io/minisign/)，各语言都有能校验它的库。

一次性准备（私钥**只放在维护者自己的电脑上**，不要提交，也不要放进 CI secrets）：

```sh
minisign -G -p keys/manifest.pub -s ~/.minisign/community-templates.key
git add keys/manifest.pub
```

公钥提交之后，CI 的 `signature` 检查就会生效。之后每次合并改动了 `manifest.json` 的 PR 之前：

```sh
minisign -Sm manifest.json -s ~/.minisign/community-templates.key
git add manifest.json.minisig
```

把签名推到 PR 分支上，`signature` 变绿再合并。投稿者没有私钥，他们的 PR 在签名前这一项一定是红的，
等于「维护者签名 = 审核通过」。可以在分支保护里把 `signature` 设为必须通过。

注意：CI 的检查只是防止忘了签名。真正的保护来自**客户端内置的公钥**。
有人在 PR 里换掉 `keys/manifest.pub` 也骗不过客户端，但审核时要特别留意这个文件的改动。

### 下架模板

发现有问题的模板，把条目从 `manifest.json` 里删掉，同时删掉 `packages/` 和 `templates/` 下对应的文件，
重新签名后合并。客户端下次读取清单时就不会再列出它。流程见 [SECURITY.md](SECURITY.md)。
