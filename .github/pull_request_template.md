## 模板信息

- 模板 id：
- 引擎版本：
- 新增 / 更新：

## 自查

- [ ] 模板源码放在 `templates/<名字>/`，包里有 `.uproject`，没有 `Binaries` / `Intermediate` / `Saved` / `.git`
- [ ] 用 `python3 scripts/pack.py templates/<名字>` 打包
- [ ] `manifest.json` 里的 `size` / `sha256` 与包一致，`engineVersion` 与 `.uproject` 的 `EngineAssociation` 一致
- [ ] 配置里没有写死 `ProjectID`
- [ ] 更新已有模板时提升了 `version`
- [ ] README「现有模板」表已更新
- [ ] 本地 `python3 scripts/validate.py` 通过
- [ ] 如果包含 C++、插件或 Python 脚本，已在下面说明它们做什么
- [ ] 我有权以 `license` 字段声明的许可证发布这个模板

## 包含的代码 / 插件 / 脚本

<!-- 没有就写「无」。CI 会把这些内容标出来，审核时会重点看 -->
