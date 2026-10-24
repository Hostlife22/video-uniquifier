<a id="api-contracts"></a>

# API 契约

本页面是 `video-uniquifier` 的权威参考
**公开、稳定的 API 接口**，根据 [版本控制](versioning.md) 的 SemVer 承诺。下面的每一条目都在 `tests/contracts/` 下通过快照测试进行强制执行；如果契约偏离，将导致 CI 失败，并提供指向 `tools/regen_contract_goldens.py` 的指针。

<a id="stability-labels"></a>

## 稳定性标签

- **`stable`** — 受 SemVer 承诺覆盖。移除或破坏需要 MAJOR 升级；添加字段可以用 MINOR 升级。
- **`experimental`** — 覆盖范围内，但 MAY 在 MINOR 升级中移除并伴随 `DeprecationWarning`。如果依赖它，请固定 `==2.2.*`。
- **`internal`** — 不在覆盖范围内。默认适用于未列出的任何内容。

<a id="how-to-import"></a>

## 如何导入

版本 2.0.0 将分发包重命名为 `video-uniquifier`，Python 导入改为
`video_uniquifier`，可执行文件改为 `video-uniq`、`video-uniq-gui` 和
`video-uniq-web`。将插件入口点更新为 `video_uniquifier.transforms`，环境前缀更新为 `VIDEO_UNIQ_*`、`VIDEO_UNIQUIFIER_*` 和 `VU_*`。旧的导入/命令别名已被移除。当不存在新状态时，GUI 设置/历史记录通过复制先前的数据目录进行迁移；以前的缓存保持独立并重新生成。历史基准测试/发布保留其原始工件名称。所有者授权的命名决定记录在
[specs/29-project-rename-rfc.md](https://github.com/Hostlife22/video-uniquifier/blob/d6af67ac05eb0689f958f18cca08cfdb6cb7c4db/specs/29-project-rename-rfc.md) 的历史版本中。

支持的入口点是 `video_uniquifier.core` 桶：

```python
from video_uniquifier.core import (
    Plan, Profile, RunOptions, RunSummary, RunEvent,
    build_plan, run_full, compute_plan_hash,
)
```

从子模块 (`from video_uniquifier.core.orchestrator import ...`) 导入仍然有效，但不遵循 SemVer——这些路径可能在次要版本之间进行内部重组。

<a id="locked-surfaces"></a>

## 锁定的界面

<a id="pydantic-models-stable"></a>

### Pydantic 模型 (`stable`)

以下每个模型的完整 JSON 结构都由以下测试锁定：
`tests/contracts/test_pydantic_schemas_stable.py`。快照文件位于
`tests/fixtures/contracts/schemas/`.

|模型|来源|备注|
|---|---|---|
| `HDRInfo` | `core/models.py` |`frozen=True`。颜色特性加可选的静态/动态 HDR 元数据。|
| `VideoStream` | `core/models.py` |`frozen=True`。来自 `ffprobe` 的一个视频流。|
| `AudioStream` | `core/models.py` |`frozen=True`。v1.4 添加了可选的 `title` 和 `dispositions`。|
| `SubtitleStream` | `core/models.py` |`frozen=True`。v1.4 添加了可选的 `title`、`is_default` 和 `dispositions`。|
| `Chapter` | `core/models.py` | `frozen=True`. |
| `SourceMeta` | `core/models.py` |`frozen=True`。稳定的序列化音/视频/字幕/章节探测结果。辅助附件/数据/封面艺术拓扑有意保持私有/内部，因此此更正变更不会改变 v1 模式。|
| `EncoderCandidate` | `core/models.py` |`frozen=True`。`max_parallel ∈ [1, 64]`；包括 AV1 软件供应商 `svtav1` 和 `libaom`。|
| `TransformConfig` | `core/models.py` |`extra="forbid"`。`params: dict[str, object]` — 参数字典在转换自身的 `*Params` 模型处进行形状检查，而不是在这里。`video.fit_aspect.allow_upscale` 是一个加性布尔值，默认为 `false`；明确选择发货固定画布配置文件 ([RFC #11](https://github.com/Hostlife22/video-uniquifier/issues/11))。|
| `SegmentationConfig` | `core/models.py` |`extra="forbid"`。v0.8.0 添加了 `mode="scene"` 可选项。|
| `Profile` | `core/models.py` |`extra="forbid"`。面向用户的 YAML 模式；v1.3 添加了 `skip_watermark_check`。|
| `Plan` | `core/models.py` |`frozen=True`。包含 `plan_hash`（简历键）+ `run_seed`（不属于哈希的一部分）。|
| `QAReport` | `core/models.py` |`frozen=True`。所有 ML/指纹指标均为 `Optional`；v1.5 添加了可为空的计划注册指标字段和嵌套的有限注册溯源，同时保留所有原始字段。|

<a id="dataclasses-stable"></a>

### 数据类（`stable`）

RFC #21（v1.6.0）添加了可为空的 `QAReport.correctness`、`loudness`，以及
`quality_policy`，带嵌套冻结的证据/策略模型。字段含义、旧版 JSON 行为和可选 CLI 退出契约，请参见 [QA 证据与门控](qa_report.md#explicit-evidence-and-optional-gates-v160)。QA 命令选项也被 `tests/contracts/test_qa_cli_contract.py` 锁定。

十月审计修复保留了这些模式和 CLI 标志。不可用的评分保持为空（或 `phash_samples=0`）；不可用的间隔音频值将从现有开放的 `chunk_similarities` 字典中省略，其原因在 `notes` 中。客户端必须使用 `.get("audio")`，而不是将缺失值视为零。请参见 [审计兼容性决策](https://github.com/Hostlife22/video-uniquifier/blob/d6af67ac05eb0689f958f18cca08cfdb6cb7c4db/docs/audit-implementation-decisions.md)。

字段形状（名称 + 类型表示 + 有默认值）由
`tests/contracts/test_runoptions_dataclass_stable.py` 和
`tests/contracts/test_runevent_kinds_stable.py` 锁定。默认*值*明确未锁定——仅在 PATCH 内允许行为上的默认调整（`target_segment_sec=600` → `900`）。

|数据类|来源|已锁定字段|
|---|---|---|
| `RunEvent` | `core/runner.py` | `kind`, `payload` |
| `RunResult` | `core/runner.py` | `returncode`, `duration_sec`, `output_path` |
| `RunOptions` | `core/orchestrator.py` | `work_dir`, `output`, `encoder_override`, `title_template`, `target_segment_sec`, `keep_segments`, `enforce_preflight`, `force_new_variant`, `workers`, `sanitize_bitstream`, `sample_phash`, `notifications`, `telemetry`, `run_id`, `accept_watermark_risk`, `audit_log_path`, `audit_principal` |
| `RunSummary` | `core/orchestrator.py` |`output`, `plan`, `segments_done`, `preflight_findings`, 可选 `decode_evidence`（v1.6.0；不透明的进程本地令牌，而不是序列化/持久化的认证）|

<a id="runevent-kinds-stable"></a>

### RunEvent 类型 (`stable`)

`tests/contracts/test_runevent_kinds_stable.py` 枚举确切元组。从 v1.0.0 起：

| `kind` |由|承载的|
|---|---|---|
| `progress` |`runner.run_ffmpeg` 每 `-progress pipe:1` 块|字典镜像 ffmpeg 进度字段 (`out_time_ms`, `fps`, `speed`, ...)|
| `log` |调度器 / 分段器 / 运行器|`phase: str` 和自由格式上下文。将负载键视为**实验性**——新增属于次要更改。|
| `done` | `runner.run_ffmpeg`, `orchestrator.run_full` |`duration_sec` 或 `output`|
| `error` |任意阶段|`reason`, `phase`, 可选 `returncode`, `tail`|
| `divergence_sample` |`orchestrator._maybe_emit_divergence` (v0.7 R4)| `segment_idx`, `phash_similarity`, `ema` |
| `target_vmaf` |每次尝试 `segmenter._encode_once` (v0.8 R5)| `segment`, `vmaf`, `crf`, `attempt`, `target` |
| `target_vmaf_failed` |耗尽后 `segmenter._encode_once`|如上，加上 `best_attempt`|

添加新类型是**次要**；消费者必须容忍未知类型（例如通过默认的 `if-elif-else` 分支记录并丢弃）。删除或重命名类型是**主要**，需要 RFC。

<a id="profile-yaml-schema-stable"></a>

### 配置文件 YAML 模式 (`stable`)

每个发货的配置文件的加载形式被锁定于
`tests/contracts/test_shipped_profiles_stable.py`（黄金数据在
`tests/fixtures/contracts/profiles/`）。该集合本身被锁定于
`shipped_profiles.json`。截至 v2.2.0：

| 配置文件 |容器|编解码器| LUFS |备注|
|---|---|---|---|---|
| `soft` |mp4|h264| -14 |保守授权衍生；自然语料带待定。|
| `medium` |mp4|h264| -14 |中等处理；自然语料带待定。|
| `medium_hdr` |mp4|hevc| -14 |通过 `zscale` 线性包裹保持 HDR 路径。|
| `aggressive` |mp4|h264| -14 |实验性高变堆栈；需要操作员审查。|
| `cid_aware` |mp4|h264| -14 |遗留实验兼容性配置文件；无外部系统预测。|
| `cid_aware_hdr_to_sdr` |mp4|h264| -14 |实验性 HDR → SDR 导出路径。|
| `cid_aggressive` |mp4|h264| -14 |遗留最大变化堆栈；非质量优先。|
| `youtube_4k` |mp4|h264| -14 |YouTube 4K 目标几何 + 比特率。|
| `youtube_1080p` |mp4|h264| -14 |YouTube 1080p 目标。|
| `youtube_av1` |mp4|av1| -14 |YouTube 1080p AV1 目标。|
| `youtube_4k_av1` |mp4|av1| -14 |YouTube 4K AV1 目标。|
| `youtube_shorts` |mp4|h264| -14 |9:16 竖屏，预计 ≤60 秒。|
| `tiktok_vertical` |mp4|h264| -16 |9:16 竖屏，TikTok 响度。|
| `instagram_reels` |mp4|h264| -16 |9:16 竖屏。|
| `instagram_square` |mp4|h264| -16 |1:1 正方形。|
| `linkedin_square` |mp4|h264| -16 |1:1 正方形，LinkedIn 响度。|
| `facebook_reels_base` | mp4 | h264 | -16 | Reels 交付基础配置；v2.2.0 新增。 |

添加配置文件是次要的；移除一个是主要的（RFC）。

<a id="public-python-surface-stable"></a>

### 公共 Python 接口 (`stable`)

`video_uniquifier.__all__` 和 `video_uniquifier.core.__all__` 被 `tests/contracts/test_public_surface_stable.py` 锁定。添加一个名称为次要更改；删除一个为重大更改。

<a id="cli-subcommands-stable"></a>

### CLI 子命令 (`stable`)

每个 `video-uniq` 子命令都是合同的一部分。添加子命令或标志为次要更改；删除或重命名为重大更改。

|子命令|来源|
|---|---|
| `version` | `cli/app.py` |
| `probe` | `cli/cmd_probe.py` |
| `preflight` | `cli/cmd_preflight.py` |
| `run` | `cli/cmd_run.py` |
| `batch` | `cli/cmd_batch.py` |
| `qa` | `cli/cmd_qa.py` |
| `calibrate` | `cli/cmd_calibrate.py` |
| `worker` | `cli/cmd_worker.py` |
| `corpus` | `cli/cmd_corpus.py` |
| `queue` | `cli/cmd_queue.py` |
| `profile` |`cli/cmd_profile.py` (v0.9 R1)|
| `subtitles` |`cli/cmd_subtitles.py` (v0.9 R2)|
| `telemetry` |`cli/cmd_telemetry.py` (v0.9 R3)|
| `update` |`cli/cmd_update.py` (v1.3 Task 33)|

<a id="plugin-entry-point-group-stable"></a>

### 插件入口点组 (`stable`)

`video_uniquifier.transforms` (v0.8.0 R1) 是第三方转换的发现点。注册对象必须满足的协议是 `core.transforms.base.TransformSpec` — 由上面的 pydantic 模式测试锁定的字段。

<a id="surfaces-marked-experimental"></a>

## 标记为 `experimental` 的界面

如果您依赖其中任何一个，请固定 `video-uniquifier==2.2.*`。

|表面|原因|
|---|---|
|`[web]` HTTP API (`src/video_uniquifier/web/routes/*`)|v0.9 R4 以 v1 版本发布；在提升之前路由可能会增加。|
|`RunEvent` 有效负载键已设置（字典本身是稳定的；单个键不是）|预期在次要版本(MINOR release)之间会有累积增长。|
| `core.telemetry.TelemetryConfig` |v0.9 R3 提供同意用户体验(UX)；未来的次要版本可能会添加字段。|
| `core.notifications.NotificationConfig` |提供者自动检测可能会演进。|
|GUI `gui/screens/*` 和 `gui/workers/*` Python API|屏幕 / 工作进程是内部的；它们的*行为*（键盘快捷键、可访问名称、屏幕布局）是用户可见的约定。|

<a id="out-of-scope-internal"></a>

## 不在范围内的(`internal`)

上述未列出的任何内容。具体包括：

- 以下划线开头的模块(`core/_internal/`, `_*`)。
- `cli/_*` 和 `gui/_*` 辅助模块。
- `core/utils/` 下的任何实用程序。
- 测试夹具和开发工具(`tools/*`)。

如果你依赖于内部内容，请提交 [RFC](versioning.md#rfc-process-for-breaking-changes) 请求将其升级到 `stable` 或 `experimental`。

<a id="snapshot-tests-reference"></a>

## 快照测试参考

|测试文件|它锁定的内容|黄金目录|
|---|---|---|
| `test_pydantic_schemas_stable.py` |每个模型的 `model_json_schema()`| `tests/fixtures/contracts/schemas/` |
| `test_shipped_profiles_stable.py` |每个 YAML 的 `model_dump(mode="json")` + 已发布配置文件名称的集合| `tests/fixtures/contracts/profiles/` + `shipped_profiles.json` |
| `test_runevent_kinds_stable.py` |`EventKind` 字面成员 + `RunEvent` 数据类结构| `tests/fixtures/contracts/runevent_*.json` |
| `test_runoptions_dataclass_stable.py` |`RunOptions`, `RunSummary`, `RunResult` 字段结构| `tests/fixtures/contracts/dataclasses/` |
| `test_public_surface_stable.py` |`video_uniquifier.__all__` 和 `video_uniquifier.core.__all__`| `tests/fixtures/contracts/public_surface/` |

<a id="see-also"></a>

## 另见

- [版本控制与兼容性](versioning.md) — SemVer 承诺和 RFC 流程。
- [`SECURITY.md`](https://github.com/hostlife22/video-uniquifier/blob/main/SECURITY.md) — 信息披露政策。
- [`CHANGELOG.md`](https://github.com/hostlife22/video-uniquifier/blob/main/CHANGELOG.md) — 每一次被接受的合同变更都会记录在这里。
