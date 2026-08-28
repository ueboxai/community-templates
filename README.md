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

1. 把你的 UE 工程打包成 zip（任意层级下有一个 `.uproject` 就行），
   排除 `Binaries` / `Intermediate` / `Saved` / `.git`
2. 放进 `packages/`
3. 算出 sha256：`sha256sum packages/你的模板.zip`
4. 在 `manifest.json` 的 `templates` 里加一条
5. 提 PR

必填字段是 `id`、`name`、`packageUrl`、`sha256`。**没有合法 sha256 的条目会被客户端整条丢弃** ——
模板包解压出来是一个完整的 UE 工程，打开时里面的 C++、插件、脚本都会跑，
「下到的字节确实是你写的那份」是客户端唯一能提供的保证。

完整的字段说明和校验规则见客户端仓库的 `docs/community-templates.md`。

## 关于安全

这里的模板由第三方投稿，**未经逐行审核**。sha256 保证的是「没被中途篡改」，
不是「这个包是安全的」。客户端界面上有对应提示。

## 许可证

各模板的许可证见 `manifest.json` 里各自的 `license` 字段。
