<a id="authorized-platform-validation-harness"></a>

# 验证工具

该工作流程在本地处理和平台转码后验证授权衍生物。适用于您拥有或有许可处理的视频。它不会针对 YouTube Content ID 或任何其他版权管理系统进行优化。

<a id="what-the-validation-can-answer"></a>

## 验证可以回答的问题

- 本地输出是否保留了声明的流、时长、节奏、颜色和 HDR 策略？
- 平台是否接受并完成了上传处理？
- 其转码是否引入了可见的条纹、振铃、运动问题、裁剪、响度变化或音视频漂移？
- 对于固定源、配置文件、随机种子和工具链，内部 pHash、音频指纹和 SSCD 诊断是否可重复？

它无法证明平台私人系统的所有权、许可、合理使用、感知质量或未来行为。索赔或限制是一个权利/合规信号需要解决，而不是参数优化目标。

<a id="preconditions"></a>

## 前提条件

- 保留你拥有该源或拥有允许此处理和上传的许可的证据。
- 在验证时使用非公开可见性设置。
- 记录源校验和，配置文件，随机种子，编码器，FFmpeg 版本，应用提交和输出校验和。
- 在上传前通过本地正确性检查。切勿使用平台回放来掩盖本地解码、时间线、流拓扑或 HDR 失败。

<a id="step-1-produce-one-controlled-candidate"></a>

## 步骤 1 — 生成一个受控候选项

从编辑/交付目标所需的最小转换集开始：

```bash
video-uniq preflight master.mp4 --profile src/video_uniquifier/profiles/soft.yaml
video-uniq run master.mp4 --profile src/video_uniquifier/profiles/soft.yaml --out candidate.mp4 --encoder libx264
video-uniq qa master.mp4 candidate.mp4 --vs-corpus
```

使用 `ffprobe` 检查最终媒体，解码每个音频/视频流，并查看生成的 QA JSON/HTML。原始源/输出 VMAF 不是在变换更改几何或时间时的编码质量评分；请使用注册参考或将结果记录为 `NOT VERIFIED`。

<a id="step-2-record-the-local-baseline"></a>

## 步骤 2 — 记录本地基线

至少存储：

|字段|目的|
|---|---|
|源/输出 SHA-256|将证据绑定到确切文件|
|应用提交和配置文件 JSON|可重复性|
|编码器、FFmpeg 和操作系统/硬件|能力来源|
|流拓扑和每个流的开始/结束|捕获丢失和音视频漂移|
|解码帧/音频样本计数|捕获截断和重复|
|颜色/HDR 元数据|捕获传输/基色/范围丢失|
|LUFS 和 真峰值|音频接收|
|注册的 VMAF/SSIM/PSNR（有效时）|视觉回归决策|
|墙时、峰值 RAM、临时磁盘和输出大小|操作预算|

pHash、Chromaprint、SSCD 以及传统的 `cid_predict_self` 字段可以保留为独立的内部诊断工具。它们不得覆盖已失败的正确性或质量门控。

<a id="step-3-manual-platform-check"></a>

## 步骤 3 — 手动平台检查

仅通过正常的平台 UI 上传经授权的候选内容，并在验证期间保持未列出/私密状态。处理完成后，检查代表性的暗部、亮部、渐变、文本、肤色和高速移动部分，以及长格式媒体的开头、中间和结尾。在启用音效时，通过耳机和扬声器进行监听。

记录：

- 上传和处理完成时间；
- 播放所提供的分辨率/编解码器；
- 可见的瑕疵及主观严重性；
- 在内部闪光/冲击或对话提示处的音视频同步；
- 响度/剪辑观察；
- 任何平台处理错误；
- 任何权利主张/限制，通过平台支持的解决流程以及您的所有权/许可证明来处理。

在回应权利主张时不要生成更强的变体。这会将质量验证转化为规避检测优化，并超出项目范围。

<a id="step-4-compare-results"></a>

## 第4步 — 比较结果

按内容类别比较 `source → local candidate → platform playback`。仅在正确性通过且其注册的质量/资源分布满足 `BENCHMARKS.md` 中批准的阈值时，才接受配置文件。将主观评审笔记保留在机器指标旁边；较低的相似度分数并不表示质量提高。

历史 `tools/generate_variants.py` 和 `tools/validation_correlate.py` 实用程序仍然保留以保持向后兼容。它们的旧版无匹配关联不作为生产接受标准，也不应用于调优外部系统行为。

<a id="release-evidence"></a>

## 发布证据

保留精确的命令、JSON 报告、环境清单和汇总结果。如果无法下载或重复测量平台转码，请将这些指标标记为 `NOT VERIFIED`，而不是从浏览器播放中推断。
