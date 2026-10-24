<a id="architecture"></a>

# 架构

三层结构，其中 `Plan`（pydantic）作为它们之间的契约。

```
+---------------------------------------------------------+
| GUI (optional [gui]): PyQt6 — gui/app_pyqt.py           |
| CLI (typer): cli/{app, cmd_run, cmd_probe,              |
|              cmd_preflight, cmd_qa, cmd_batch,          |
|              cmd_calibrate, cmd_corpus,                 |
|              cmd_queue, cmd_worker}.py                  |
+----------------------------+----------------------------+
                             |  Plan + RunOptions
                             v
+---------------------------------------------------------+
| core/  (pure Python, no Qt, no UI)                      |
|                                                         |
|  probe  → planner → preflight → segmenter → pipeline    |
|     │        │                       │          │       |
|     v        v                       v          v       |
| encoder              checkpoint           runner        |
|                                                         |
|  seed_resolver  → divergent per-segment seeds           |
|  audio_windows  → per-window audio seeds (divergent)    |
|  calibration    → bisect intensity vs cid_predict       |
|  qa             → phash + audio_fp + vmaf + ssim        |
|                 + cid_predict + corpus + chunked QA     |
|  queue / worker → shared-FS distributed batch           |
|  sanitizer      → optional libx264 bitstream rewrap     |
|  errors         → typed exception hierarchy             |
|                                                         |
|                concat → (sanitize?) → metadata → qa     |
+---------------------------------------------------------+
                             |
                             v
                 ffmpeg / ffprobe / fpcalc
```

<a id="modules"></a>

## 模块

|路径|角色|
|------|------|
| `core/models.py` |所有 pydantic 数据类：SourceMeta, Plan, 配置文件, Segment, QAReport|
| `core/probe.py` |通过单次 ffprobe 调用获取 `probe(path) -> SourceMeta`|
| `core/encoder.py` | `detect_encoders()` 执行真实试编码并缓存；`pick_encoder()` 根据候选及其 `max_parallel` 限制选择编码器。 |
| `core/transforms/` |**21 个内置转换**在导入时注册（12 个视频，9 个音频 — `video_geom.py` 注册 `crop_resize`, `rotate`, `mirror`）；通过 `video_uniquifier.transforms` 入口点发现第三方插件（v0.8.0 R1，见 [plugins.md](plugins.md)）；见 [filter_graph.md](filter_graph.md)|
| `core/transforms/hdr_wrap.py` | 通过 zscale 在线性光空间中包装 HDR 色彩变换。 |
| `core/pipeline.py` |`FilterGraph.build()` + `build_video_segment_command` (+ `_fused`) + `build_main_audio_command` + `compute_plan_hash`；v0.8.0 R5 增加 `crf_override` 以支持每段目标 VMAF 重试|
| `core/runner.py` |带 `-progress pipe:1` 的子进程封装，RunEvent 流，CancelToken；v0.8.0 R5 增加 `target_vmaf` / `target_vmaf_failed` 事件类型|
| `core/resource_budget.py` |用于编码器插槽和估计工作区/最终输出字节预留的共享本地进程注册表；`VIDEO_UNIQ_RESOURCE_LOCK_DIR` 选择公共注册表|
| `core/segmenter.py` |关键帧感知拆分（或 PySceneDetect 驱动的场景模式，v0.8.0 R3）+ 每段处理（安全时并行）+ 合并解复用器；v0.8.0 R5 添加目标-VMAF 反馈循环|
| `core/scene_detect.py` |v0.8.0 R3 — `detect_scene_boundaries`（PySceneDetect 内容检测器，自愿选择）+ `snap_to_keyframes`（保持流拷贝不变性）|
| `core/checkpoint.py` | 使用线程安全的 `RLock`、fsync 与 `os.replace` 原子保存恢复状态 `state.json`。 |
| `core/seed_resolver.py` |`resolve_run_seed(profile, source)` + `derive_segment_seed(plan_hash, idx, run_seed)` 用于 `divergent` 策略|
| `core/audio_windows.py` |`~60 s` 音频窗口用于 `divergent` 策略 — 每窗口随机种子通过 `derive_segment_seed(plan_hash, window_idx + 1_000_000, run_seed)` 与 `0.1 s` 交叉淡化；loudnorm 保持全局|
| `core/metadata.py` |`-metadata` 参数 + 标题模板|
| `core/preflight.py` |YouTube 目标矩阵 + HDR 验证 + 干运行滤镜探测（`_ffmpeg_filter_works`）用于 `rubberband`、`zscale` 及色调映射依赖|
| `core/sanitizer.py` |自愿选择 libx264 互操作性规范化（`--sanitize-bitstream`）；生成损失警告，对 libx264 无操作，拒绝 HDR/HEVC/AV1 合同|
| `core/orchestrator.py` | `run_full(plan, options, on_event, cancel_token) -> RunSummary` |
| `core/profile_loader.py` |YAML → `Profile` 并进行 pydantic 验证（`extra=forbid`）|
| `core/errors.py` |已键入的异常层次结构: `VideoUniquifierError`, `ProbeError`, `EncoderError`, `FfmpegNotFoundError`, `PipelineError`, `CheckpointError`, `PreflightFailure`|
| `core/utils/ffmpeg_paths.py` | `ffmpeg_bin()` / `ffprobe_bin()` 统一解析可执行文件路径。 |
| `core/qa/` |哈希值, phash, audio_fp（相似度 + Hamming距离）, vmaf, ssim, cid_predict, 语料库（自 v0.8.0 R2 起通过 `corpus_db.py` 支持 SQLite，参见 [corpus.md](corpus.md)）, 质量（回退链）, 报告 + HTML|
| `core/qa/sscd.py` |v0.8.0 R4 — 可选择的 ML 级相似度，通过 Meta 的 SSCD 嵌入（`[ml]` 额外），参见 [sscd.md](sscd.md)|
| `core/qa/corpus_db.py` |v0.8.0 R2 — SQLite（WAL + `BEGIN IMMEDIATE`）语料库存储；从旧版 `index.json` 一次性自动迁移|
| `core/calibration/` |`intensity.scale_profile`（围绕恒等映射的乘法缩放）+ `loop.calibrate`（根据选定的度量进行二分查找：默认使用 chromaprint `cid_predict`，或通过 v0.8.0 R6 使用 SSCD `metric="sscd"`）|
| `core/queue/leasing.py` |原子 POSIX 重命名文件队列 (`pending/`, `in_progress/`, `done/`, `failed/`)，带有心跳、清理程序和持久化围栏输出提交恢复|
| `cli/cmd_worker.py` | 长期运行的队列工作进程，对每个获得租约的文件调用 `orchestrator.run_full`。 |

<a id="data-flow-for-one-input"></a>

## 单输入的数据流

```
input.mp4
  ├─ probe()              → SourceMeta (streams, HDR, chapters)
  ├─ load_profile()       → Profile (transforms, audio_tracks, keep_hdr, seed_strategy…)
  ├─ pick_encoder()       → EncoderCandidate (quality/balanced/speed + strict override)
  ├─ compute_plan_hash()  → Plan (frozen)
  ├─ resolve_run_seed()   → run_seed (per_run / per_file / fixed / divergent base)
  ├─ preflight()          → list[PreflightFinding] (fail → stop)
  ├─ plan_segments()      → list[Segment] (keyframe-aligned)
  ├─ checkpoint init/resume
  ├─ process_video_segments_parallel(workers=N, cap=encoder.max_parallel):
  │     acquire shared process CPU/vendor capacity per FFmpeg child
  │     for each pending segment:
  │       seg_plan = plan_for_segment(plan, idx)   # divergent: per-seg seed
  │       stream_copy_extract → seg_NNNN_src.mkv
  │       filter_complex      → seg_NNNN.mkv
  │       state.json mark done
  ├─ process_main_audio() ← runs on full source; two-pass loudnorm cached in state.json
  │   (divergent strategy: audio_windows.plan_windows → per-window seed + 0.1 s crossfade)
  ├─ concat_segments()    → concat demuxer + stream-copy mux of main audio
  ├─ sanitize_bitstream() → optional libx264 rewrap (opt-in via --sanitize-bitstream)
  └─ build_report()       → output.qa.json + output.qa.html
output.mp4
```

<a id="distributed-flow"></a>

## 分布式流程

```
Worker A (machine 1) ──┐
                       │
Worker B (machine 2) ──┼── pending/   ◄── queue add
                       │   ▲
Worker C (machine 3) ──┘   │ atomic rename
                           │
                       in_progress/<host>.<file>  + <host>.alive (heartbeat)
                           │ (success)
                           v
                       done/                          ◄── prune by mtime
                           │ (failure)
                           v
                       failed/<file>.err
```

每个工作进程对每个租赁文件调用 `orchestrator.run_full`。除了队列目录本身之外没有共享状态；参考 [distributed.md](distributed.md)。

<a id="why-a-separate-orchestrator"></a>

## 为什么需要单独的协调器

`core/orchestrator.run_full()` 是 CLI 命令 (`cmd_run`, `cmd_batch`, `cmd_worker`) 和 GUI 工作进程的**唯一入口点**。它接收一个 `on_event` 回调，因此任何 UI 都可以流式传输 `RunEvent`，而无需将展示逻辑嵌入核心。这解决了传统 AB 原型的架构债务，该原型将整个管道嵌入到 PyQt 内。
`QThread`.

<a id="why-split-process-concat-not-keyframe-seek"></a>

## 为什么选择拆分处理再合并（而不是关键帧跳转）

- 单个 ffmpeg `-ss <T>` 在崩溃时会丢失所有进度。
- 每段处理使得恢复操作为 O(1)，并为相同的 `(plan_hash, run_seed)` 提供干净且 MD5 稳定的输出。
- 主音频在完整源文件上**在分段之外**处理——loudnorm 和 pitch shift 在接缝处有瞬态行为，所以我们从不分割音频。

<a id="seed-strategy"></a>

## 随机种子策略

`Profile.seed_strategy` 控制每次运行的可变性：

- `fixed`     — `profile.seed` 原样；每次运行相同。
- `per_run`   — 每次调用都生成新的随机随机种子（传统默认）。
- `per_file`  — 源路径的确定性哈希；相同输入 → 相同随机种子。
- `divergent` — 每次运行使用新的基础随机种子并通过以下方式衍生每段随机种子
                `sha256(plan_hash, segment_idx, run_seed)`。相邻分段
                获得不同的变换参数相位。v0.3.3 默认值
                CID 感知配置文件。

查看 [seed_strategy.md](seed_strategy.md) 了解使用案例和可重复性影响。

<a id="runevent-contract"></a>

## RunEvent 合约

`core/runner.RunEvent` 是一个冻结的数据类，带有 `kind: EventKind` 判别器和一个自由形式的 `payload: dict[str, object]`。
`on_event` 回调是信息离开核心层的唯一路径，因此它的表面区域是公共契约的一部分——添加新的
`kind` 是向后兼容的扩展；**重命名**其中一个是重大变更。

| `kind`               |生产者|负载键（承重）|
|---|---|---|
| `progress`           |`runner._run_once`（ffmpeg `-progress`）|`out_time_us` *或* `out_time_ms`, `frame`, `phase`, `segment`|
| `log`                |编排器 / 分段器 / 运行观察者|`phase`（例如 `preflight`, `plan`, `segment`, `main_audio`, `paused`, `resumed`, `concat`, `sanitize`, `cleanup`），`message`|
| `error`              |任何层| `phase`, `message`, `returncode`, `tail`, `findings` |
| `done`               |`runner.run`（成功退出）| `duration_sec`, `output` |
| `divergence_sample`  |`orchestrator._maybe_emit_divergence`（v0.7 R4 / F2）|`segment`, `phash_similarity`（每段），`running_phash`（EMA，α=0.25），`frames_sampled`|

GUI 消费者使用的阶段不变量：

- `phase=segment` 携带 `segment: int`，以便进度聚合器可以将 ffmpeg 的流本地 `out_time_us` 映射回正确的整体桶。协调器在 `segmenter.py` 中的 `_wrap` 闭包注入了它；下游消费者不能假设 `segment` 在每个事件上都已设置。
- `phase=main_audio` 专用于 loudnorm + 音频重新编码过程，并驱动 GUI 中的辅助“音频”进度条；主进度条保持固定在基于视频段的值上。
- `phase=paused` / `phase=resumed` 在每个状态转换时正好触发一次（v0.7 R6 / F5）— 运行器观察者跟踪应用的 SIGSTOP 状态并去重重复的标记翻转。

<a id="cancel-pause-plumbing-v07-r6-f5"></a>

## 取消 + 暂停管道（v0.7 R6 / F5）

核心层提供两个协作取消原语，两者均
由 `threading.Event` 支持，因此任何线程的写入（GUI 按钮 → QThread，信号处理器 → 主循环）都能在工作进程线程上被正确观察到：

```
                              ┌──────────────────────────┐
            GUI Run screen ──►│ RunWorker (QThread)      │
            (Esc / Space)     │                          │
                              │  cancel_token: CancelToken
                              │  pause_token:  PauseToken
                              └────────────┬─────────────┘
                                           │ run_full(plan, options,
                                           │   on_event=…,
                                           │   cancel_token=…,
                                           │   pause_token=…)
                                           v
                              ┌──────────────────────────┐
                              │ orchestrator             │
                              │  ├─ pause observer thread│
                              │  │   writes paused_at    │
                              │  │   to state.json on    │
                              │  │   pause/resume        │
                              │  │   enforces 24h        │
                              │  │   auto-cancel         │
                              │  │                       │
                              │  └─ process_video_segments_parallel
                              │     ↓ pause_token forwarded
                              └──────────────────────────┘
                                           │
                                           v
                              ┌──────────────────────────┐
                              │ runner.run / _run_once   │
                              │  watcher thread:         │
                              │    cancel → SIGTERM      │
                              │    pause  → SIGSTOP via  │
                              │      process_control     │
                              │    resume → SIGCONT      │
                              └────────────┬─────────────┘
                                           v
                                       ffmpeg
```

`PauseToken` 是**幂等的**（重复调用 `pause()` / `resume()` 不会产生额外效果），记录用于 state.json 持久化的暂停时间，并提供 `should_auto_cancel()`。编排器的后台 `_start_pause_observer` 每秒检查一次；若暂停超过以下时限，则触发 `cancel_token.cancel()`：
`PauseToken.AUTO_CANCEL_SEC`（默认 24 小时）。

`core/process_control.py` 是跨操作系统的抽象：POSIX 使用标准库 `os.kill(pid, SIGSTOP|SIGCONT)`；Windows 使用 `psutil`，通过特定平台的运行时依赖自动安装。两者都遍历进程树（Linux 上使用 psutil 的子进程，或 `/proc` 作为回退）以便子级 ffmpeg 辅助进程也被挂起。所有操作均尽力而为，且永不抛出异常——失败的 `os.kill` 会记录为 WARN 级日志，并且返回值会报告确认次数。
