# 虚幻盒子 · 社区模板库

[![validate](https://github.com/ueboxai/community-templates/actions/workflows/validate.yml/badge.svg)](https://github.com/ueboxai/community-templates/actions/workflows/validate.yml)

[虚幻盒子](https://ue5box.com/)「新建工程 → 社区模板」的默认模板源。

这里没有服务端，只有静态文件：一份 [`manifest.json`](manifest.json) 清单，加上
[`packages/`](packages/) 下的模板包。每个模板包是一个打成 zip 的 Unreal Engine 工程，
客户端下载、校验、解压之后就是一个可以直接打开的新工程。

## 现有模板

| 模板 | id | 分类 | 引擎 | 版本 | 说明 |
| --- | --- | --- | --- | --- | --- |
| **GameStart 游戏启动工程** | `gamestart` | game | 5.7 | 1.1.0 | 空白游戏工程骨架，已配好默认输入映射和 Lumen / Substrate 渲染设置，开箱可跑 |
| **RenderStart 渲染起步工程** | `renderstart` | render | 5.7 | 2.0.0 | 面向离线出片和可视化：Lumen、硬件光追、路径追踪已开，带 Datasmith 导入、Movie Render Queue、日照和 HDRI 环境光 |

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
客户端                                   本仓库（raw.githubusercontent.com）
  │  1. GET manifest.json  ──────────────▶  manifest.json
  │  2. 丢弃没有合法 sha256 的条目
  │  3. 用户选中模板后下载 packageUrl ────▶  packages/<模板>.zip
  │  4. 比对 sha256，不一致就拒绝
  ▼  5. 解压成新的 UE 工程
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
      "sha256": "52ca96cb…",                // 必填，64 位小写十六进制
      "description": "…",
      "category": "game",
      "engineVersion": "5.7",
      "size": 8703,
      "version": "1.1.0",
      "author": "Unreal Box Team",
      "license": "Apache-2.0"
    }
  ]
}
```

每个字段的含义和格式要求见 [CONTRIBUTING.md](CONTRIBUTING.md#字段)。

## 投稿模板

欢迎投稿。大致流程：

```sh
# 1. 打包：排除 Binaries/Intermediate/Saved 等目录，输出 size 和 sha256
python3 scripts/pack.py path/to/MyTemplate

# 2. 把输出的 size / sha256 填进 manifest.json 的新条目

# 3. 本地校验，和 CI 跑的是同一个脚本
python3 scripts/validate.py
```

然后提 PR。只需要 Python 3.9+，不用装任何依赖。详细步骤、字段说明和约定见
[CONTRIBUTING.md](CONTRIBUTING.md)。

CI 会检查：

- 清单字段齐全、类型和格式正确，`id` 不重复
- `sha256`、`size` 与实际模板包一致
- 模板包是合法 zip，里面有 `.uproject`，没有 `Binaries` / `Intermediate` / `Saved` /
  `DerivedDataCache` / `.git` / `.vs`，没有绝对路径或 `..`
- `packages/` 下没有清单没引用的文件
- README 的「现有模板」表列出了清单里的每个模板
- `manifest.json` 是 UTF-8、LF、2 空格缩进

## 关于安全

模板包解压出来是一个完整的 UE 工程，**打开时里面的 C++、插件、Python 脚本都会运行**。

- 这里的模板由第三方投稿，**没有逐行审核**
- sha256 能保证的是「下到的字节就是清单里写的那份，没被中途篡改」，
  不能保证「这个包是安全的」
- 客户端界面上有对应的提示；只打开你信任的作者的模板

发现有问题的模板，请[提 issue](https://github.com/ueboxai/community-templates/issues)。

## 仓库结构

```
.
├── manifest.json                 模板清单，客户端读的就是它
├── packages/                     模板包（zip，按二进制提交）
├── scripts/
│   ├── pack.py                   可复现打包，输出 size / sha256
│   └── validate.py               清单与模板包校验
├── .github/
│   ├── workflows/validate.yml    PR / main 上跑校验
│   └── pull_request_template.md  投稿自查清单
└── CONTRIBUTING.md               投稿指南与字段说明
```

## 许可证

每个模板的许可证见 `manifest.json` 里对应条目的 `license` 字段。
