# 虚幻盒子 · 社区模板库

[![validate](https://github.com/ueboxai/community-templates/actions/workflows/validate.yml/badge.svg)](https://github.com/ueboxai/community-templates/actions/workflows/validate.yml)

[虚幻盒子](https://ue5box.com/)「新建工程 → 社区模板」的默认模板源。

这里没有服务端，只有静态文件：一份 [`manifest.json`](manifest.json) 清单，加上
[`packages/`](packages/) 下的模板包。每个模板包是一个打成 zip 的 Unreal Engine 工程，
客户端下载、校验、解压之后就是一个可以直接打开的新工程。模板包的源码放在 [`templates/`](templates/) 下，
CI 保证两者逐字节一致。

## 现有模板

| 模板 | id | 分类 | 引擎 | 版本 | 说明 |
| --- | --- | --- | --- | --- | --- |
| **GameStart 游戏启动工程** | `gamestart` | game | 5.7 | 1.1.1 | 空白游戏工程骨架，已配好默认输入映射和 Lumen / Substrate 渲染设置，开箱可跑 |
| **RenderStart 渲染起步工程** | `renderstart` | render | 5.7 | 2.0.1 | 面向离线出片和可视化：Lumen、硬件光追、路径追踪已开，带 Datasmith 导入、Movie Render Queue、日照和 HDRI 环境光 |

以上模板均由 Unreal Box Team 提供，许可证为 Apache-2.0。每个模板的完整信息（包大小、sha256、作者、许可证）以
[`manifest.json`](manifest.json) 为准。

## 在虚幻盒子里使用

虚幻盒子社区版**完全离线运行**，装好之后不会主动联网，这个模板源**默认是关着的**。

1. 打开「新建工程 → 社区模板」
2. 点「启用官方社区库」
3. 从列表里选一个模板，创建工程

不点第 2 步，应用不会向这里发任何请求。启用之后，客户端读取的清单地址是：

```
https://raw.githubusercontent.com/ueboxai/community-templates/main/manifest.json
```

`main` 分支上的内容就是用户看到的内容，合并即发布。

## 工作方式

```
客户端                                   本仓库（raw.githubusercontent.com 或镜像）
  │  1. GET manifest.json  ──────────────▶  manifest.json
  │     GET manifest.json.minisig ───────▶  manifest.json.minisig
  │  2. 用内置公钥校验清单签名（配置公钥后）
  │  3. 丢弃没有合法 sha256 的条目
  │  4. 用户选中模板后下载 packageUrl ────▶  packages/<模板>.zip
  │  5. 比对 sha256，不一致就拒绝
  ▼  6. 解压成新的 UE 工程
```

`packageUrl` 是相对清单的路径，所以整个仓库可以原样镜像到任何静态托管上，
只要把清单地址换成镜像地址就行。

清单格式（`formatVersion: 1`）：

```jsonc
{
  "formatVersion": 1,
  "templates": [
    {
      "id": "gamestart",                    // 必填，唯一，小写字母/数字/连字符
      "name": "GameStart 游戏启动工程",      // 必填
      "packageUrl": "packages/GameStart.zip", // 必填
      "sha256": "db5cdea7…",                // 必填，64 位小写十六进制
      "description": "…",
      "category": "game",
      "engineVersion": "5.7",
      "size": 2968,
      "version": "1.1.1",
      "author": "Unreal Box Team",
      "license": "Apache-2.0"
    }
  ]
}
```

另外还有 `tags`、`updated`、`minClientVersion`、`homepage`、`thumbnail` 几个可选字段。
客户端遇到不认识的字段应当忽略，新增可选字段不改 `formatVersion`。
每个字段的含义和格式要求见 [CONTRIBUTING.md](CONTRIBUTING.md#字段)。

## 镜像

`raw.githubusercontent.com` 在国内经常很慢或者连不上。仓库不需要任何改动就能通过 jsDelivr 访问：

```
https://cdn.jsdelivr.net/gh/ueboxai/community-templates@main/manifest.json
```

- `main` 上的清单或模板包变了之后，[`mirror`](.github/workflows/mirror.yml) 工作流会自动刷新 jsDelivr 的缓存，
  避免镜像上新清单配旧包
- jsDelivr 不提供超过 20 MB 的单个文件，在国内也时好时坏。建议客户端内置多个清单地址，依次尝试
- 也可以把整个仓库原样同步到国内的对象存储或 CDN，清单地址换成那里的地址即可

镜像是否可信不影响安全性：模板包有 sha256 把关，配置签名公钥后清单也有签名把关，
镜像只能让下载失败，改不了内容。

## 投稿模板

欢迎投稿。大致流程：

```sh
# 1. 把工程放到 templates/MyTemplate/，然后打包：输出 size 和 sha256
python3 scripts/pack.py templates/MyTemplate

# 2. 把输出的 size / sha256 填进 manifest.json 的新条目

# 3. 本地校验和测试，和 CI 跑的是同一套
python3 scripts/validate.py
python3 -m unittest discover -s tests
```

然后提 PR。只需要 Python 3.9+，不用装任何依赖。详细步骤、字段说明、CI 检查项和约定见
[CONTRIBUTING.md](CONTRIBUTING.md)。

## 关于安全

模板包解压出来是一个完整的 UE 工程，**打开时里面的 C++、插件、Python 脚本都会运行**。

- 这里的模板由第三方投稿，经过审核，但**不等于逐行审计**
- 模板源码随仓库提交，审核看的是逐行的改动；包里有代码、插件、脚本时，CI 会在 PR 上标出来
- sha256 能保证的是「下到的字节就是清单里写的那份，没被中途篡改」，
  清单签名能保证「清单是维护者签过的那份」，都不能保证「这个包是安全的」
- 客户端界面上有对应的提示；只打开你信任的作者的模板

发现可疑的模板，请按 [SECURITY.md](SECURITY.md) 私下报告；普通问题请[提 issue](https://github.com/ueboxai/community-templates/issues/new/choose)。

## 仓库结构

```
.
├── manifest.json                 模板清单，客户端读的就是它
├── manifest.json.minisig         清单签名（配置公钥后由维护者生成）
├── keys/manifest.pub             清单签名公钥（配置后）
├── packages/                     模板包（zip，按二进制提交）
├── templates/                    模板源码，与 packages/ 下的包逐字节一致
├── thumbnails/                   模板缩略图（可选）
├── scripts/
│   ├── pack.py                   可复现打包，输出 size / sha256
│   └── validate.py               清单、模板包与源码校验
├── tests/                        脚本的单元测试
├── .github/
│   ├── workflows/validate.yml    PR / main 上跑校验、测试和签名检查
│   ├── workflows/mirror.yml      main 更新后刷新 jsDelivr 镜像缓存
│   ├── ISSUE_TEMPLATE/           issue 模板
│   ├── CODEOWNERS
│   └── pull_request_template.md  投稿自查清单
├── CONTRIBUTING.md               投稿指南、字段说明、维护者流程
└── SECURITY.md                   安全问题报告
```

## 许可证

每个模板的许可证见 `manifest.json` 里对应条目的 `license` 字段。
