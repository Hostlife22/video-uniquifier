<a id="profiles"></a>

# 配置文件

配置文件是一个 YAML 文件，声明应用哪些转换及其强度。配置文件位于 `src/video_uniquifier/profiles/` 下，并可以通过路径加载。

<a id="yaml-schema"></a>

## YAML 架构

```yaml
name: string                                                  # required
description: string                                           # optional
transforms:                                                   # list
  - id: <transform.id>                                        # see Transform reference
    enabled: bool                                             # default true
    params: { ... }                                           # validated by the transform's schema
audio_tracks: "first" | "all" | [int, ...]                  # list = absolute ffprobe stream indices
keep_hdr: bool                                                # default false
output_container: "mp4" | "mov" | "mkv"                       # default mp4
target_codec: "h264" | "hevc" | "av1"          # v1.2.0 Task 22 added av1
target_loudness_lufs: float                                   # default -14.0
seed: int | null                                              # used when seed_strategy=fixed
seed_strategy: "fixed" | "per_run" | "per_file" | "divergent" # default per_run; v0.3.3 CID profiles ship divergent

# --- v0.8.0 R3 — segmentation strategy ---
segmentation:
  mode: "keyframe" | "scene"                                  # default keyframe
  scene_threshold: float                                       # default 27.0 (PySceneDetect ContentDetector)
  scene_min_length_sec: float                                  # default 2.0
# --- v0.8.0 R5 — per-segment VMAF target-quality ---
target_vmaf: float | null                                      # default null (loop disabled)
target_vmaf_step: int                                          # default 2 (CRF decrement per retry)
target_vmaf_max_retries: int                                   # default 2 (cap on re-encode attempts)
```

未知的顶级字段会被拒绝 (`extra=forbid`)。

`audio_tracks: first` 选择探测到的第一条音轨，`all` 按源顺序保留全部音轨。显式列表填写 `ffprobe`/`SourceMeta.audio[].index` 的绝对流索引；输出遵循列表顺序，无效索引在编码前拒绝。音频效果作用于第一条选中音轨，其余音轨在容器支持其编码时直接复制，否则按封装规则转码。

`video.crop_resize.max_strength` 是每个轴上移除的最大**总**比例。例如，`0.06` 最多移除左右总共 6% 的宽度，而不是每边独立移除 6%。重新缩放后输出 SAR 被重置为 1:1。

<a id="segmentation-modes-v080-r3"></a>

### 分段模式 (v0.8.0 R3)

* **`keyframe`**（默认）：在源视频关键帧上对齐片段边界，从而直接复制流进行提取。内置配置使用此模式。
* **`scene`**：通过 [PySceneDetect 的 ContentDetector](https://github.com/Breakthrough/PySceneDetect) 检测镜头边界，再向前对齐到最近的关键帧，保留流复制约束。若没有可用边界，则退回单个片段。需要 `[scene]`：`pip install 'video-uniquifier[scene]'`。

<a id="per-segment-vmaf-target-quality-v080-r5"></a>

### 每段 VMAF 目标质量 (v0.8.0 R5)

设置 `target_vmaf` 后，每个片段逐次降低 CRF，每次减少 `target_vmaf_step`，直到 VMAF 达到目标或用完 `target_vmaf_max_retries`。x264/x265 的初始 CRF 提示为 18；硬件编码器将相同变化映射到 NVENC `cq`、QSV `global_quality` 或 AMF `qp`。重试耗尽时保留评分最高的已编码候选文件。

分布式工作进程保留 `target_vmaf` 并执行相同的有界每段循环。编码前仍会应用未注册参考保护。

请参阅 [seed_strategy.md](seed_strategy.md) 了解每种策略的含义以及何时选择使用。

<a id="shipped-profiles"></a>

## 已发货配置文件

<a id="quality-high-change-family"></a>

### 质量 / 高变动系列

|名称|目标|验证状态|
|------|-----|-------------------|
| `soft.yaml`                 |保守授权衍生|合成正确性通过；自然质量等级待定|
| `medium.yaml`               |中度处理|自然质量等级待定|
| `aggressive.yaml`           |实验性可见/可听处理|强制操作员审核|
| `medium_hdr.yaml`           |通过浮点 RGB 线性光变换包装器保留 PQ/HLG|合成和衍生自然场景 HDR 通过；原生相机 HDR 待定|
| `cid_aware.yaml`            |传统实验性高变动保存任务兼容性|无外部系统预测|
| `cid_aggressive.yaml`       |传统最大变化兼容性|非质量优先；强制审查|
| `cid_aware_hdr_to_sdr.yaml` |实验性 HDR→SDR 派生|合成色调映射通过；自然 HDR 待处理|

<a id="platform-destination-family-v070"></a>

### 平台目标系列 (v0.7.0)

锁定纵横比的预设，用于直接上传到特定社交平台。每个预设将 `video.fit_aspect`（目标几何 + 适配模式）与轻度质量保护变换和平台适配
`audio.loudnorm` 集成目标。适用于跨平台发布工作流，其中源为横向但目标期望纵向/方形画面 — 无需手动 ffmpeg 操作。

内置平台交付配置显式设置 `allow_upscale: true`，以保证表中承诺的输出分辨率。自定义 `video.fit_aspect` 默认使用 `allow_upscale: false`：crop 在源画面及配置上限内选择最大的偶数尺寸目标比例矩形；padding 可以扩大画布，但不会放大源画面。只有固定交付画布是明确要求时才设为 `true`；放大分辨率无法恢复源文件中不存在的细节。

|名称|目标|模式|分辨率| LUFS |备注|
|------|--------|------|------------|------|-------|
| `youtube_4k.yaml`        | 16:9 | `crop`     | 3840×2160 | -14 |YouTube 4K 横向母带|
| `youtube_1080p.yaml`     | 16:9 | `crop`     | 1920×1080 | -14 |YouTube 标准上传|
| `youtube_shorts.yaml`    | 9:16 | `crop`     | 1080×1920 | -14 |YouTube Shorts（中心裁剪）|
| `tiktok_vertical.yaml`   | 9:16 | `crop`     | 1080×1920 | -16 |TikTok 响度目标比 YT 更严格|
| `instagram_reels.yaml`   | 9:16 | `pad_blur` | 1080×1920 | -16 |信箱模糊背景保留完整横向画面|
| `instagram_square.yaml`  | 1:1  | `pad_blur` | 1080×1080 | -16 |方形动态贴文带模糊侧边栏|
| `linkedin_square.yaml`   | 1:1  | `crop`     | 1080×1080 | -16 |LinkedIn 时间线（无模糊——专业外观）|

<a id="facebook-reels-delivery-v220"></a>

### Facebook Reels 交付（v2.2.0）

`facebook_reels_base.yaml` 是 Reels 工作进程使用的原生配置文件。它生成 1080×1920、9:16 的模糊背景画布，显式允许放大，选择第一条音轨，并执行目标为 −16 LUFS / −1.5 dBTP 的两遍响度归一化。输出使用 H.264/MP4，固定随机种子为 42。该文件与其他配置一同位于 `src/video_uniquifier/profiles/`，运行时从已安装软件包的资源中加载。

业务规则、标题和标志选项使用独立结构；参见 [Reels 交付指南](facebook-reels.md)及 `examples/facebook_reels/` 中的示例。

<a id="av1-family-v120-task-22"></a>

### AV1 家族（v1.2.0 任务 22）

AV1 可作为可选交付编码器提供。实际大小、质量和编码时间取决于编码器和源文件，必须进行基准测试；不假定固定百分比或平台偏好。配置文件目标 `av1` —
`pick_encoder()` 默认采用 `quality` 策略：`libaom-av1`，然后
`libsvtav1`，然后是经过验证的硬件编码器。`balanced` 优先使用 SVT-AV1 并且
`speed` 优先使用经过验证的 NVENC/QSV/VideoToolbox/AMF；通过以下环境变量配置：
`VIDEO_UNIQ_ENCODER_POLICY`。不提供 `av1_vulkan`，因为现有 CPU 帧滤镜图没有经过验证的 Vulkan `hwupload` 路径。CRF 范围为 0..63，默认值为 30；其质量和速度不能与 x264 CRF 直接按数值比较，必须使用具体素材进行对照测试。

|名称|目标|模式|分辨率| LUFS |备注|
|------|--------|------|------------|------|-------|
| `youtube_av1.yaml`       | 16:9 | `crop`     | 1920×1080 | -14 |AV1 1080p；对选定编码器进行基准测试并与控制对照|
| `youtube_4k_av1.yaml`    | 16:9 | `crop`     | 3840×2160 | -14 |AV1 4K；明确画布可能会将较小的来源放大|

该项目在使用经过时间和空间注册的参考的已授权自然内容语料库运行之前，不会发布配置文件 VMAF 频段。

⚠️ **HDR 与 `pad_blur`：** `gblur` 不具备 HDR 感知能力。PQ/HLG 源必须先经 `video.tonemap_sdr` 转为 SDR，再使用模糊背景，或者改用 `crop`/`pad_black`。不兼容组合在预检阶段返回 `FAIL`，不会先开始耗时编码。

<a id="transform-reference-19"></a>

## 参考文献（19）

| ID |类型|显著参数|
|----|------|----------------|
| `video.fit_aspect`      |视频|`target_aspect`（`16:9` / `9:16` / `1:1` / `4:5` / `4:3`），`mode`（`crop` / `pad_blur` / `pad_black`），`target_width`，`target_height`，`allow_upscale`（默认 `false`），`blur_sigma`（0..80，仅 `pad_blur`），`pad_color`（仅 `pad_black`）— 由所有平台目标配置文件使用|
| `video.crop_resize`     |视频| `max_strength` (0..0.10), `rng_seed` |
| `video.rotate`          |视频|`degrees` (-2..2), `fillcolor_sdr`, `fillcolor_pq`（HDR 变体）|
| `video.color_eq`        |视频| `brightness`, `contrast`, `gamma`, `saturation` |
| `video.noise`           |视频| `strength` (0..100) |
| `video.mirror`          |视频|(无参数) — 水平翻转；仅限自愿选择|
| `video.blend_b`         |视频| `b_video_path`, `opacity` (0.01..0.15) |
| `video.speed`           |视频| `rate` (0.5..2.0) |
| `video.temporal_jitter` |视频|实验性/破坏性，仅限自愿参与：`blackout_prob` (0..0.2)，`drop_prob` (0..0.2)，`blackout_blur` (布尔值)；确定性 60 秒模式使用 24 Hz PTS 网格，与源 FPS 无关|
| `video.tonemap_sdr`     |视频|`tone` (hable / reinhard / mobius / aces)，`peak_nits`，`desat`|
| `audio.pitch_tempo`     |音频|`pitch`，`tempo`，`sample_rate`，`method` (rubberband / asetrate)，`randomize_within`|
| `audio.eq`              |音频|`bands` (列表 `(freq_hz, gain_db)`)，`width_q`，`randomize_bands`|
| `audio.resample`        |音频|`intermediate_sr` (例如 47999)|
| `audio.compand`         |音频| `threshold_db`, `ratio`, `randomize_within` |
| `audio.reverb`          |音频|`intensity` (0..0.5)，`style` (small_room / medium_room / hall / plate)|
| `audio.spectral_smear`  |音频| `intensity` (0..0.10), `delay_ms`, `speed` |
| `audio.haas_stereo`     |音频| `delay_ms` (1..40), `randomize_within_ms` |
| `audio.noise_overlay`   |音频|`noise_db` (-40..-3)，`color` (white / pink / brown)，`randomize_within_db`|
| `audio.loudnorm`        |音频|`integrated` (LUFS)，`true_peak`，`lra`，`target_jitter_lufs`|

<a id="writing-your-own-profile"></a>

## 编写你自己的配置文件

1. 将 `soft.yaml` 或 `medium.yaml` 复制到 `my_profile.yaml`。从满足授权衍生作品编辑需求的最小转换集合开始。
2. 切换 `enabled` 并调整 `params`。
3. 使用 `video-uniq run --profile my_profile.yaml …` 运行。
4. 检查 `<output>.qa.html`。在解释质量或内部相似性诊断之前，必须确保其正确性通过。在源/输出对具有有效的时间和空间注册之前，不要应用 VMAF 阈值。
5. 对于自动强度调节，请使用 `video-uniq calibrate` — 参见 [calibrate.md](calibrate.md)。

<a id="notes"></a>

## 注意事项

- 当设置时，`seed` 字段由 `video.crop_resize.rng_seed` 使用；相同的随机种子 → 相同的滤镜图，这对于重现性很有用。
- `audio.loudnorm` 是一个 **两遍处理** 滤镜 — 第一次运行会测量完整的源，并将结果缓存到 `state.json`，因此恢复运行将跳过该步骤。
- `video.blend_b` 需要一个 B 视频路径。在 CLI 上通过 `--b-video <path>` 传递；该值将在运行时注入到转换的参数中。

<a id="performance-notes"></a>

## 性能注意事项

- **`audio.pitch_tempo` 与 `method: rubberband`**（用于传统的 `cid_aware` 和 `cid_aggressive`）大约比默认设置慢 5–10 倍
  `asetrate+atempo` 路径。Rubberband 会保留共振峰——这对于语音内容很重要——但在长时间片段上，音频处理链可能比实时慢 10–20 倍，而不是 <1 倍实时。2026-05-31 的测试测量了一个 90 秒的片段 × `cid_aware` × `libx264`，在一台 8 核 Mac 上的实际时间约为 18 分钟。对于非语音内容的批量吞吐，建议使用
  `medium` / `aggressive`（不使用 `method: rubberband` 标志，而是回退到 atempo 路径）。
- 当配置文件使用它们时，**预检查需要 `rubberband` 和 `zscale` 滤镜**。如果 ffmpeg 缺少 `librubberband`（用于 Rubberband 音高路径）或
  `libzimg`（被 `video.tonemap_sdr` 和 `keep_hdr: true` 使用），则运行开始时的干运行探测会快速失败（<1 秒）。Homebrew 默认的 ffmpeg 都不自带——安装可以使用
  `brew install ffmpeg --HEAD` 或从源码构建，命令如下
  `--enable-librubberband --enable-libzimg`.

<a id="rubberband-performance-characteristic"></a>

### Rubberband 性能特性

2026-05-31 的真实视频矩阵（`docs/bug-triage-2026-05-31.md` §9）在随附的配置文件 × 输入组合上测量了实际用时，
`evermeet.cx` ffmpeg 8.1.1 + `librubberband` + `libzimg` + `libvmaf`，单线程-工作进程，`libx264`。数字表示实际秒数：

| 配置文件         |clip_a 30 秒|clip_long 90 秒|synth_sdr_4k 12 秒|synth_long_5min 300 秒|
|---              |---:         |---:            |---:               |---:                   |
| `soft`          | 17          | 37             | —                 |136（运行） + 326（恢复）|
| `medium`        | 17          | 39             | —                 | 145                   |
| `aggressive`    | 20          | 46             | —                 | 242                   |
| `cid_aware`     | 224         | 623            |超时（>1800）|超时（>1800）|
| `cid_aggressive`| 316         | 871            |超时（>1800）|超时（>1800）|

`cid_aware` / `cid_aggressive` 的实际运行时间约为以下编码器的 10–15 倍：
`soft` / `medium` / `aggressive` 在相同内容上。Rubberband 音频链在 ffmpeg 内是单线程的，并且与（并行的）视频链串行运行，因此在 `>60 s` 或 `>1080p` 源上音频处理占主导时间。选择是有意的：

- **当音色保持比吞吐量更重要时，请保留 `rubberband`** —— 对于语音内容、播客、人物访谈视频，任何情况下 `asetrate` 的“花栗鼠效应”都是不可接受的。
- **不要从外部匹配阈值中选择音高数量。** 仅使用编辑上合理的音高数量，并通过聆听验证语音/音乐质量。
- **当吞吐量更重要时切换到`asetrate`**——B卷、纯音乐内容、大文件批量作业。原地编辑配置文件YAML或保存衍生副本：

```yaml
# my_fast_derivative.yaml — legacy profile with the asetrate fallback
transforms:
  - id: audio.pitch_tempo
    enabled: true
    params: {pitch: 1.06, randomize_within: 0.005, method: asetrate}
```

当带橡皮筋的配置文件运行在源`>60 s` 或`warn``audio.pitch.rubberband.slow``preflight()`
`>1080p`墙成本在编码开始前就已显示。WARN是信息性质的——编码仍会继续进行。实现于
`src/video_uniquifier/core/preflight.py::_check_rubberband_perf`.

_（2026-05-31 `evermeet.cx`在 ffmpeg 8.1.1 + librubberband 8核 Mac 上测量。每年或在 ffmpeg 大幅提升后重新测量。）_

<a id="legacy-high-change-profiles"></a>

## 遗产高变革的配置文件

`cid_aware` 和 `cid_aggressive` 保留它们的标识符，因此现有的已保存作业和自动化流程仍然可以加载。它们是实验性效果堆栈，而不是生产质量的默认值。它们的音高、时间、相位、动态和噪声操作可能是可见或可听的，需要在拥有或许可的内容上进行审核。

pHash、音频相似度与 SSCD 只用于内部回归诊断和自有变体比较，不能预测或保证 YouTube Content ID 或其他外部版权系统的判断。

设置 `target_vmaf` 后，每个片段逐次降低 CRF，每次减少 `target_vmaf_step`，直到 VMAF 达到目标或用完 `target_vmaf_max_retries`。x264/x265 的初始 CRF 提示为 18；硬件编码器将相同变化映射到 NVENC `cq`、QSV `global_quality` 或 AMF `qp`。重试耗尽时保留评分最高的已编码候选文件。
`quality.target_vmaf.unregistered_reference`。当前的反馈回路只能调整编码器 CRF；它无法将未注册的源/输出比较解释为压缩质量。请改为运行已注册的后处理质控。
