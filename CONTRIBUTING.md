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

   脚本会排除 `Binaries` / `Intermediate` / `Saved` / `DerivedDataCache` / `.git` / `.vs`
   和 `Content/Developers`（目录名是你电脑的用户名），生成 `packages/MyTemplate.zip`，并打印要填进清单的 `size` 和 `sha256`。
   同样的输入每次打出的字节都一样，重新打包不会无故改掉哈希。
3. 在 `manifest.json` 的 `templates` 末尾加一条（字段见下）
4. 本地校验和测试：

   ```sh
   python3 scripts/validate.py
   python3 -m unittest discover -s tests
   ```

5. 在 README 的「现有模板」表里加一行
6. 提 PR。CI 会跑同样的校验和测试。

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
| `category` |  | 分类，只能是 `game` / `render` / `film` / `architecture` / `automotive` / `other`，与客户端界面上的分类对应 |
| `engineVersion` |  | 适用的引擎版本，`主版本.次版本`，如 `5.7`。必须和 `.uproject` 的 `EngineAssociation` 一致 |
| `size` |  | 模板包字节数 |
| `version` |  | 模板自身版本，语义化版本，如 `1.0.0` |
| `author` |  | 作者 |
| `license` |  | 许可证，建议用 [SPDX 标识](https://spdx.org/licenses/)，如 `Apache-2.0` |
| `homepage` |  | 模板主页或源码仓库，必须是 `https://` 地址 |
| `previewUrl` |  | 预览图，形如 `previews/<名字>.png`（png / jpg / webp，不超过 512 KB），也可以是 `https://` 外链 |

**没有合法 `sha256` 的条目会被客户端整条丢弃。** 模板包解压出来是一个完整的 UE 工程，
打开时里面的 C++、插件、脚本都会跑，「下到的字节确实是你写的那份」是客户端唯一能提供的保证。

### 兼容性

- 上面的字段就是客户端会读的全部字段。客户端遇到不认识的字段会忽略，但 CI 会把它当拼写错误拦下
- 客户端只认 `formatVersion: 1`，改成别的值整份清单都会被拒绝

## CI 检查什么

- 清单字段齐全、类型和格式正确，`id` 不重复
- `sha256`、`size` 与实际模板包一致
- 模板包是合法 zip，只有一个与包名同名的顶层目录，里面有且只有一个 `.uproject`
- 模板包里没有 `Binaries` / `Intermediate` / `Saved` / `DerivedDataCache` / `.git` / `.vs`，
  没有绝对路径、`..`、符号链接、重复条目、只差大小写的路径
- 模板包解压后不超过 2 GiB、不超过 20000 个条目
- `.uproject` 的 `EngineAssociation` 与 `engineVersion` 一致
- 模板包里没有 `Content/Developers/`
- `Config/*.ini` 里没有写死 `ProjectID`，也没有本机生成的 `SecurityToken`
- `packages/` 下的模板包与 `templates/` 下的源码逐字节一致
- `packages/`、`templates/`、`previews/` 下没有清单没引用的东西
- README 的「现有模板」表列出了清单里的每个模板
- `manifest.json` 是 UTF-8、LF、2 空格缩进
- 外链模板包会被下载下来做同样的检查

包里有 C++ 源码、工程内插件、Python 脚本、`.dll` / `.exe` 等会被执行的内容，
或者 `.uproject` 启用了 `PythonScriptPlugin`，CI 不会报错，但会在 PR 上给出警告，审核时会重点看。

## 约定

- `manifest.json`：UTF-8、LF、2 空格缩进、末尾换行，中文直接写不转义。
  格式不对时可以 `python3 scripts/validate.py --fix` 自动整理
- 模板配置里不要写 `ProjectID`，UE 会在工程首次打开时生成；写死的话所有新建工程会共用同一个标识
- 打包前把工程用引擎开一次再关掉，然后删掉 `Saved/`；如果 `Config/DefaultEngine.ini` 里多出了带 `SecurityToken` 的
  `[/Script/AndroidFileServerEditor...]` 一段，删掉它（每台机器生成的都不一样）
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

### 国内镜像

客户端内置了两个官方源，「启用官方社区库」会同时打开：

| 源 | 清单地址 |
| --- | --- |
| GitHub | `https://raw.githubusercontent.com/ueboxai/community-templates/main/manifest.json` |
| 国内镜像 | `https://gitee.com/ueboxai/community-templates/raw/main/manifest.json` |

国内镜像必须是这个仓库的**原样同步**，模板包字节一致。自己重新打包会让 sha256 不同，用户会看到重复的模板。

### 下架模板

发现有问题的模板，把条目从 `manifest.json` 里删掉，同时删掉 `packages/` 和 `templates/` 下对应的文件，
合并到 `main`。客户端下次读取清单时就不会再列出它。流程见 [SECURITY.md](SECURITY.md)。
