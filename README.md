# 虚幻盒子 · 社区模板库

[虚幻盒子](https://ue5box.com/)「新建工程 → 社区模板」的默认模板源。

内容全是静态文件：一份 [`manifest.json`](manifest.json) + `packages/` 下的模板包。
应用启用这个源之后会读取清单地址：

```
https://raw.githubusercontent.com/ueboxai/community-templates/main/manifest.json
```

## 这个源默认是关着的

虚幻盒子社区版**完全离线运行**，装好之后不会主动联网。用户要在「社区模板」里
显式点一下「启用官方社区库」，应用才会来读这份清单 —— 不点就一个请求都不发。

## 投稿一个模板

打包、填清单、本地校验、提 PR。详细步骤和字段说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。

```sh
python3 scripts/pack.py path/to/MyTemplate   # 打包并输出 size / sha256
python3 scripts/validate.py                  # 校验清单与模板包
```

## 目录结构

```
manifest.json        模板清单（客户端读取的就是它）
packages/            模板包 zip
scripts/pack.py      可复现打包
scripts/validate.py  清单校验（CI 同款）
```

## 关于安全

这里的模板由第三方投稿，**未经逐行审核**。sha256 保证的是「没被中途篡改」，
不是「这个包是安全的」。客户端界面上有对应提示。

## 许可证

各模板的许可证见 `manifest.json` 里各自的 `license` 字段。
