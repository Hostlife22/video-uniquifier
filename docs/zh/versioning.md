<a id="versioning-and-compatibility"></a>

# 版本与兼容性

本项目对 [API 契约](api-contracts.md)中列出的接口遵循[语义化版本 2.0.0](https://semver.org/)。公共 API 标记为 **stable**：导入 `video_uniquifier.core` 或从 shell 脚本调用 `video-uniq` 的代码，可使用 `video-uniquifier~=2.2`，在 2.x 系列内获得保持兼容性的更新。2.0.0 更改了分发包、导入、命令和环境变量名称；从更早的主版本迁移时需要更新集成。

<a id="what-counts-as-a-breaking-change"></a>

## 什么算作“重大更改”

当对标有 `stable` 标签的合同时发生以下任一情况时，该更改属于**重大**（1.x → 2.0）:

|表面|破坏动作|
|---|---|
| `core.Plan`, `core.Profile`, `core.SourceMeta`, `core.EncoderCandidate` |移除字段；重命名字段；收紧类型（例如 `int | None` → `int`）；更改默认语义|
| `core.RunEvent.kind` |移除一个 `kind` 字面量；更改现有 `kind` 的有效负载模式|
| `core.RunOptions`, `core.RunSummary` |删除字段；重命名；收紧类型|
|插件入口点组 `video_uniquifier.transforms`|更改已注册转换必须满足的协议|
|CLI: `video-uniq <subcommand>`|删除子命令；删除或重命名标志；更改退出代码约定|
|YAML 配置文件模式|删除顶级键；重命名转换 id；收紧 `extra=forbid` 以拒绝以前接受的形状|
|Python API 入口点: `build_plan`, `run_full`, `compute_plan_hash`|非新增方式更改调用签名|
|`Plan` JSON 序列化|在 N.Y.Z 中能成功回传的字段在 (N+1).0.0 中不再回传|

当发生任何以下情况时，变更为**次要**(1.0 → 1.1)：

- 向稳定模型添加带有合理默认值的新可选字段
- 添加一个新的 `RunEvent.kind` 字面量
- 添加一个新的 CLI 子命令、标志或环境变量
- 添加一个新的发布配置文件 YAML
- 添加一个新的转换（在 `core/transforms/__init__.py` 中注册）
- 弃用（但不删除）上述任何内容；在删除前发出一个
  `DeprecationWarning` 至少一个完整的 MINOR 周期

当仅为修复 bug 时，变更为 **PATCH** (1.0.0 → 1.0.1)：不移动契约表面，在文档化的不变量下的行为恢复到文档化契约。

<a id="stability-labels"></a>

## 稳定性标签

每个模型字段和 CLI 标志在 [API 合约](api-contracts.md) 中都带有三种标签之一：

- **`stable`** — 受上述 SemVer 承诺覆盖。
- **`experimental`** — 受承诺覆盖，但 MINOR 可以通过 `DeprecationWarning` 删除。使用风险自负；如果依赖实验性表面，请固定到确切的补丁版本。
- **`internal`** — 不涵盖。任何 `_*` 模块中的内容，
  `video_uniquifier.core._internal`，或在 [API Contracts](api-contracts.md) 中标记为内部的内容。可能在任何版本中发生变化。

在 [API Contracts](api-contracts.md) 中没有标签的 API 表面部分默认为 **`internal`**。如果你想依赖它，请开启 RFC 请求其升迁。

<a id="rfc-process-for-breaking-changes"></a>

## 破坏性变更的 RFC 流程

我们对重大版本升级持保守态度。任何意图破坏 `stable` 合同的 PR 必须：

1. **先开启 RFC。** 使用 [RFC issue 模板](https://github.com/hostlife22/video-uniquifier/issues/new?template=rfc.yml) 在 GitHub Discussion 的 "RFCs" 类别下创建。标题格式：`RFC: <short summary>`。
2. **在模板中陈述四个必填部分：**
   - **问题。** 当前行为哪里有错误、缺失或痛点。包括具体的用户可见症状或使用案例。

   - **提案。** 精确的新合同 — 字段签名,
     filter-string 更改，CLI 形状。PR 可以稍后进行原型设计，
     但RFC必须承诺遵守该形状。
   - **替代方案。** 有哪些附加（非破坏性）方法被
     被考虑过，以及它们为什么被拒绝。
   - **迁移计划。** 用户升级需要做的事情。包括
     如果可能，提供一个弃用路径（对一个次要版本发出警告，然后在删除）
     下一个主要的).
3. **至少开放7天。** RFC在讨论开启后7个日历日内不能被接受。这为不同时间时区的用户提供了发表意见的机会。
4. **维护者签署。** 一位维护者评论
   一旦共识明确，就使用 `accepted` 或 `rejected`。被接受的 RFC 会解除标记为 `breaking-change` 的 PR 的阻塞。
5. **更新日志条目。** 每个被接受的重大更改将在下一个主要版本块的 `### Removed` 或 `### Changed` 标题下获得一个专门的条目，包括返回 RFC 的链接。

微不足道的重大更改（例如在 Python 3.10 达到生命周期结束时停止支持）仍然需要 RFC，但由维护者撰写的 RFC 可以使用缩短的 3 天评论窗口。

<a id="supported-versions"></a>

## 支持的版本

|版本行|状态|错误修复|安全修复|直到|
|---|---|---|---|---|
|**2.2.x**|活跃|yes|yes|待定 — 见 GitHub Releases|
|2.1.x 及更早版本|生命周期结束|no|no|已被取代|

针对活动分支的安全修复将在确认的 CRITICAL 或 HIGH 漏洞披露后的 30 个日历日内以 PATCH 版本发布。有关披露政策，请参阅 [SECURITY.md](https://github.com/hostlife22/video-uniquifier/blob/main/SECURITY.md)。

<a id="python-version-policy"></a>

## Python 版本政策

版本 2.2.0 需要 Python 3.11 或更高版本。CI 在 Ubuntu、macOS 和 Windows 上测试 Python 3.11 和 3.12。除非明确添加，否则该矩阵不涵盖更新的解释器。更改最低支持的 Python 版本需要 RFC 以及面向下游打包者的文档化迁移/弃用政策。

<a id="profile-yaml-versioning"></a>

## 配置文件 YAML 版本管理

配置文件会根据原生 `Profile` 模型和每个转换的参数模式进行验证。没有单独的 `profile_schema_version` YAML 字段；未知键将被 `extra=forbid` 拒绝。应用程序版本 2.2.0 并不意味着 YAML 架构版本为 2.2.0。稳定的配置文件更改遵循 SemVer/RFC 政策和 [API contracts](api-contracts.md) 中描述的合同快照。

<a id="how-to-depend-on-video-uniquifier-safely"></a>

## 如何安全地依赖 video-uniquifier

|使用案例|推荐的固定版本|
|---|---|
|从 shell 脚本调用 `video-uniq` 的应用程序|`video-uniquifier~=2.2`（次要稳定版）|
|只导入 `video_uniquifier.core` 并使用 `stable` 接口的库| `video-uniquifier~=2.2` |
|使用任意 `experimental` 接口的库|`video-uniquifier==2.2.*`（补丁稳定版）|
|可重现的研究成果 / 论文|精确固定版本，例如 `video-uniquifier==2.2.0`|
|可编辑安装用于开发|从源码检出安装 `pip install -e ".[dev,gui]"`|
