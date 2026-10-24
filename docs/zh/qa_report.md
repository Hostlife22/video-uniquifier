<a id="qa-report"></a>

# 质量报告

每个 `video-uniq run`（除非 `--no-qa`）在输出文件旁会生成两个 artefacts：

```
output.mp4
output.mp4.qa.json    # machine-readable
output.mp4.qa.html    # human-readable, with heatmaps + verdict banner
```

`video-uniq qa <input> <output>` 对于已有的输入/输出对生成相同的一对 artefacts，而无需重新编码。

<a id="whats-measured"></a>

## 测量内容

对于一个（输入，输出）对，报告评估三个独立的维度：媒体正确性、感知质量和诊断相似性。可选的指标后端会优雅降级，但缺失或损坏的媒体流会被视为正确性失败，并生成 `INVALID`，绝不会产生正常的指标判定。

> **自 v0.8.0 起新增**：可选 SSCD 语义相似度评分
> (`video-uniq qa --sscd`,
> 需要 `[ml]` 额外）以及针对的 VMAF 有界重试事件用于
> 配置文件选择使用 `target_vmaf`。请参阅下面的 SSCD + 目标 VMAF 小节。
> 如下小节。

<a id="file-level"></a>

### 文件级别

|字段|来源|含义|
|---|---|---|
| `input_md5`, `output_md5` |流式 md5（4 MB 块）|精确字节身份（每次成功运行不同——仅与相同计划的 `--new-variant=false` 恢复匹配）|
| `input_size_bytes`, `output_size_bytes` |文件系统|比特率预算的完整性检查|
| `input_duration_sec`, `output_duration_sec` |ffprobe|应在 ±0.5 秒内匹配；`duration_match` 是布尔值|

在生成哈希或采样指标之前，QA 会探测两个文件。自动运行/批处理/GUI 报告也会接收现有的 `Plan` 并重用最终媒体合同以进行流拓扑、时间戳和 HDR/SDR 检查。独立 QA 则应用保守的对检查。候选文件的主要视频和所有音频流随后使用 FFmpeg `-xerror -err_detect explode` 解码至文件末尾，因此损坏的未采样尾部会变成
`correctness: full output decode failed` 位于 `notes[]` 且状态为 `INVALID`。

独立于报告生成，`run_full` 执行完整解码，作为 CLI、GUI、Web 和分布式工作进程的强制最终发布门。这同样适用于 `--no-qa`。自动后运行报告会重复使用成功的门，而不是对相同输出进行两次解码；独立的 `video-uniq qa` 执行自己的解码。

<a id="visual-similarity"></a>

### 视觉相似性

|字段|来源|范围|含义|
|---|---|---|---|
| `phash_samples` | — |通常 120|抽样了多少帧|
| `phash_distance_min`, `_mean`, `_max` |在 `samples` 帧上使用 imagehash.phash|0..64 位|配对帧之间的汉明距离|
| `phash_similarity` | `1 - mean_distance / 64` | 0..1 |聚合值；越高 = 越接近源|
| `vmaf_mean` |ffmpeg `libvmaf`| 0..100 |感知质量与源相比；如果缺少 libvmaf 或不支持原始 HDR 域，则为空|
| `ssim_mean` |ffmpeg `ssim`| 0..1 |结构相似性指数；如果禁用则为空|

<a id="audio-similarity"></a>

### 音频相似性

|字段|来源|范围|含义|
|---|---|---|---|
| `audio_fp_similarity` |chromaprint 通过 uint32 子指纹的 Jaccard 指数| 0..1 |解码代码的集合重叠；非字节相同|
| **`audio_fp_hamming_per_frame`** |chromaprint 异或 + 位计数，成对帧，平均值|0..32 位|内部位级距离诊断|
| **`audio_fp_match_confidence`** | `1 - hamming_per_frame / 32` | 0..1 |传统归一化相似度启发式；非校准信心值|

所有三个指纹字段均源自每个文件的一次指纹提取，而非每份报告六个 `fpcalc` 进程。对于超过 600 秒的音源，五个 120 秒窗口覆盖起点、中段和尾部，并在指纹提取前进行连接；`notes[]` 记录了采用了分层覆盖。

`audio_fp_similarity` 是基于解码的 32 位子指纹集合的 Jaccard 指数 (`|A ∩ B| / |A ∪ B|`)。完全的代码匹配并不等同于字节一致；重新编码可能保留原有代码。顺序被忽略，低分数并不证明可听见的损坏。汉明距离是另一种指纹诊断方法，而不是人类感知的模型。这两个指标都不是校准的置信度或专有系统预测。

汉明字段是在 v0.3.3 版本中引入的。为了模式兼容性，保留了原有名称，但它们不是权利系统的 KPI 或概率。只能相对于固定的来源/语料库和工具版本来解释它们：

|`hamming_per_frame`（位）|解释|
|---|---|
|较低值|配对的 Chromaprint 代码在此实验中更接近|
|中间值|结果需要聆听和时间线/对齐检查|
|较高值|配对码差异更大；这并不能说明可听性或外部系统情况|

<a id="plan-registered-metrics-v15-rfc-12"></a>

### 计划注册的指标（v1.5，RFC #12）

对于长文件，原始和注册的 VMAF 采用现有的自动采样策略（大约每秒四帧评分）。注册采样使用输出时长和节奏，其间隔记录在报告注释中。可取消的 VMAF/SSIM 也会为非活动监控器发出 FFmpeg 进度；空多路复用器写入可移植空设备。整个时间线被解码；这是 VMAF 分数的采样，而不是更短的参考或每帧连续的质量证据。短文件保留每帧评分。该策略不对 FFmpeg 或整体 QA 内存设置硬性限制。

上述原始源/输出指标故意保留其历史含义。当自动运行/批处理质量保证具有完全完成的 `Plan` 时，它还会将现有的视频滤镜图与恢复的运行随机种子和每段随机种子回放到临时无损 FFV1 参考中。注册的 VMAF/SSIM 比较会在评分前局部重置两个时间轴，因此有意裁剪、镜像、重新定时或确定性帧丢失是参考的一部分，而不会被错误归类为编码损伤。

|字段|范围|工程意义|
|---|---:|---|
| `vmaf_registered_mean` |0..100 或 null|针对变换后的参考的编码/世代质量|
| `ssim_registered_mean` |-1..1 或 null|针对变换后的参考的结构质量|
| `sscd_registered_mean` |-1..1 或 null|有界单调表示相似性；输出帧无法重复使用|
| `audio_fp_registered_hamming_per_frame` |0..32 或 null|在有界全局偏移和线性漂移校准后，订购Chromaprint距离|
| `registration.reference_mode` | `plan_transformed` |声明参考来自精确的Plan重放|
| `registration.plan_hash`, `run_seed` |来源|将报告绑定到完成的计划和随机实现|
| `registration.video`, `.audio` |对象或空|偏移/漂移、比较样本、覆盖率、置信度和可用性说明|

这些字段仍然是诊断信息：裁决继续使用正确性和未更改的原始质量策略，直到经过许可的自然内容语料库建立注册阈值。低重叠音频/SSCD 对齐会被拒绝，而不是返回一个欺骗性好的值。注册 VMAF 在保留 HDR 时会失败关闭，而不是使用 SDR 模型解释 PQ/HLG 代码值；HDR→SDR 输出可以在显式色调映射后进行评分，因为此时两个注册输入都是 SDR。

例如，扩展的 4K 自然内容实验在同一个单元中产生了原始 VMAF 3.73 和计划注册 VMAF 93.81。第一个包含与原始场景/时间线的差异；第二个将编码与已转换的参考进行比较。单独的任何一个数字都不能授权生产发布。语料库运行器会分别记录测量完整性与 QA 判定和人工验收；其 `measured` 状态不是质量通过。

公共可空正确性/响度对象和可选质量策略是在已接受的 RFC #21 下实现的；请参阅下面的明确证据部分。

参考生成是可取消的，并由空闲空间和
`VIDEO_UNIQ_REGISTERED_REFERENCE_MAX_BYTES`（默认 40 GiB）。如果保守的 FFV1 估计超过该预算，则注册的视频指标将不可用，并显示明确的 `notes[]` 条目；原始 QA 会继续。为长篇运行提供更多临时空间，并有意设置该变量。SSCD 参考嵌入被缓存于 `VIDEO_UNIQ_QA_CACHE_DIR` 或使用源内容、规范配置文件、plan/随机种子、FFmpeg/工具/模型版本、采样网格及编码参考摘要的每用户 QA 缓存中；损坏的条目会以原子方式重建。

<a id="sscd-semantic-similarity-v080-r4-opt-in"></a>

### SSCD 语义相似度（v0.8.0 R4，自愿参与）

仅在传入 `video-uniq qa --sscd` 时填充。需要额外的 `[ml]`（torch + torchvision）。第一次运行将下载约 94 MB 的模型权重至
`~/.cache/video_uniquifier/models/`；随后运行使用缓存。完整背景见 [`docs/en/sscd.md`](sscd.md)。

|字段|来源|范围|含义|
|---|---|---|---|
| `sscd_mean` |配对嵌入的余弦平均值| -1..1 |图像复制诊断|
| `sscd_min` |采样余弦的最低值| -1..1 |最不相似的配对样本|
| `sscd_per_frame[]` |归一化中点网格上的排序余弦| -1..1 |抽样证据，而非片段定位|

`notes[]` 记录了最高抽样余弦及其请求的源/输出时间戳、配对计数、官方模型哈希和预处理。在样本之间的短匹配插入可能会被遗漏。SSCD 不是人工质量，也不是 Content ID。

<a id="target-vmaf-retry-events-v080-r5"></a>

### 目标 VMAF 重试事件 (v0.8.0 R5)

配置文件设置 `target_vmaf` 在片段低于目标时触发飞行重试。这些是由 CLI/GUI 调用者使用的实时 `RunEvent` 记录；它们当前未嵌入 `QAReport` JSON 中：

|字段|含义|
|---|---|
| `target_vmaf.payload.segment` |哪个片段被打分|
| `target_vmaf.payload.attempt` |零基编码尝试 (`0` 是初始编码)|
| `target_vmaf.payload.vmaf` |实际测量的 VMAF，或者如果评分失败则为 null|
| `target_vmaf.payload.crf` |对尝试的软等效质量提示|
| `target_vmaf.payload.target` |配置的目标|
| `target_vmaf_failed.payload.best_attempt` |保留在磁盘上的基于零的尝试|

`target_vmaf_max_retries` 限制循环。耗尽后，分段器保留得分最高的编码候选并输出 `target_vmaf_failed`。

反馈评分器当前使用普通源切片。预检拒绝
`target_vmaf` 带有几何、重时序、镜像、叠加、字幕或色调映射，因为该组合未注册，CRF 重试无法使分数收敛。仅在支持的未修改参考域中使用此源切片重试；它与运行后计划注册的 QA 分开。

<a id="legacy-self-similarity-heuristic-v02"></a>

### 传统自相似启发式（v0.2+）

|字段|来源|含义|
|---|---|---|
| `cid_predict_self` |采样 pHash 与可用聚合前缀音频 Jaccard 的最大值|0..1；内部自相似启发式（传统字段名）|
| `weakest_chunk_sec` |在 `chunk_similarities[].combined` 上取最大值|与源最相似的块的 (start_sec, end_sec)|
| `chunk_similarities[]` |在公共前缀上采样的窗口：`{start_sec, end_sec, visual, combined}`，可选 `audio`|驱动 HTML 热力图|
| `corpus_matches[]` |与 `video-uniq corpus` 条目比较|阈值以上文件的 `{id, path, visual, audio, combined}`|

`cid_predict_self` 既不是概率，也不是 YouTube Content ID 的预测指标。它是一个项目特定的最大相似度诊断工具，可用于回归比较以及自有或许可衍生产品的自碰撞诊断。在未经过语料库特定验证的情况下，不要将其用作生产环境的通过/失败门。

<a id="notes-assessment"></a>

### 注释 + 评估

|字段|含义|
|---|---|
| `notes[]` |不可用后端的警告（例如 "fpcalc 未在 PATH 中"）|
| `duration_match` |布尔值 — 输入/输出持续时间在 ±0.5 秒内|

CLI 和 HTML 显示独立轴：

- **正确性** — `VALID`, `INVALID` 或 `NOT_VERIFIED`。拓扑结构、时长、首个视频PTS、声明的颜色/HDR 合约及完整解码优先。
- **质量** — `PASS`, `WARNING`, `FAIL` 或 `UNAVAILABLE`，基于 VMAF/SSIM。
- **视觉相似度** — `LOW`, `MODERATE`, `HIGH` 或 `UNAVAILABLE`，基于抽样 pHash 并进行明确诊断。

整体输出状态为 `INVALID` 表示正确性失败，否则绿色/黄色/红色仅根据质量证据决定。相似度从不弥补质量差，也不会将正确、高质量输出判定为失败。现有的
`QAReport` JSON 架构保持与可叠加兼容；旧版 `notes[]` 仍然存在，而 v1.6.0 在 [RFC #21](https://github.com/Hostlife22/video-uniquifier/issues/21) 下添加了结构化证据。

<a id="explicit-evidence-and-optional-gates-v160"></a>

## 明确证据与可选门控（v1.6.0）

- `correctness`：`status`（`passed`, `failed`, `not_verified`），`scope`（`plan_contract` 或 `pair_contract`），`failure_codes`，`full_decode_status`，`note`。通过意味着只检查了声明的合同和完整解码。它确实
  **不** 认证内部唇同步、可听瞬态或视觉质量。没有计划时，仅提供保守的配对合同。旧版 `duration_match` 仍然比较源/输出时长；接受的速度变化使用计划的预期时长来进行结构正确性和判定。
- `loudness`：测量 `status`、`streams` 和 `note`。每个输出音频流报告其绝对 `stream_index`、`integrated_lufs`、`true_peak_dbtp`、`method`、测量 `status` 和 `note`。对测量信号不进行降混或归一化。负无穷静音/次门控测量会变为 null；无效的 NaN/+无穷结果不会标记为已验证。`passed` 表示扫描已完成，**并不**意味着响度目标、削波/相位或聆听测试已通过。默认：`not_verified`（未请求扫描）；使用 `--loudness` 对每个输出轨道进行完整扫描。对于长片，这可能需要相当长的时间。
- `quality_policy`：可选 `domain`（`raw` 或 `registered`），`min_vmaf`（0–100）和 `min_ssim`（-1–1）。为空表示旧的启发式分级仍然有效。当明确请求最小值时，所选域中的这些最小值将驱动质量轴；**所有**请求的指标必须可用、有限且合格。注册门控还需要可用的视频注册证据，而不仅仅是数字值。它们不建立普遍校准的质量目标。

仅示例 — 这些是操作员选择的阈值，而不是生产默认值：

```bash
video-uniq qa source.mkv output.mp4 --plan-json plan.json --quality-domain registered \
  --min-vmaf 90 --min-ssim 0.98 --loudness
```

明确的门失败或未经验证的正确性会写入 JSON/HTML 并退出 **2**。无效组合（例如 `--fast-qa --min-vmaf 90`、`--no-ssim --min-ssim .9` 或没有计划的注册门）会在执行昂贵指标之前失败。原始 VMAF 门拒绝 HDR 配对：`phone_model=0` 并不能使 SDR VMAF 模型 HDR 有效。注册的 VMAF 对于保留的 HDR 仍然不可用。对于授权的 HDR→SDR，请在计划转换的 SDR 域内进行比较，然后进行人工视觉审查。

默认情况下不会启用新的阈值或响度扫描；旧的 CLI 调用保持其退出行为。有效的 VMAF 0/0.5 现在会被保留，因此旧的启发式判定可能正确地变差，而不是默默地回退到 SSIM。旧的 JSON 加载中可为空的证据字段未设置。使用自己严格模式的消费者必须为新的可选字段更新它们。

`RunSummary.decode_evidence` 是进程本地的，并根据文件身份（设备/ inode/ 大小/ 修改时间）进行检查。运行/批处理/ GUI 仅在匹配输出时重用它；过时的令牌会导致重新进行完整解码。它不是加密证明，绝不能从不可信的 JSON 中加载或作为恢复缓存存储。在 QA 过程中输出的变化会产生 `output.changed_during_qa`，而不是成功的结果。

<a id="acceptance-targets"></a>

## 验收目标

该项目不发布 pHash、Chromaprint、SSCD 或传统 `cid_predict_self` 字段的通用阈值。它们随采样、对齐和内容而变化，也不衡量感知质量。生产验收以媒体正确性为起点，然后使用已注册的 VMAF/SSIM/PSNR 和音频 LUFS/真峰值 与许可的自然内容语料库进行比较。相似性字段仍作为单独的诊断指标。

<a id="reading-the-heatmap"></a>

## 读取热图

HTML 会呈现采样窗口，并按视觉相似性着色。只有当单个窗口覆盖整个测量前缀时，音频才会出现在窗口中。总体得分也包括可用的聚合音频。缺失的音频会从窗口字典中省略，并显示为不可用，而不是零。

公共前缀在最短文件或 600 秒处结束。较长的尾部未测量。窗口划分该前缀（最多 150 个窗口，最多 600 个视觉样本），包括剩余时长；它们不是连续分析。原始重定时不会自动对齐。请求的采样时间具有节奏分辨率，每个比较的文件使用相同的绝对视觉跨度：

```
[█][█][░][▒][█][▒][░][░][█][▒]  ← time →
 green = lower heuristic similarity     red = higher heuristic similarity
```

传统的 **最弱块** 字段指向相似性最高的样本。常见的诊断模式：

- 在开头附近的单个高相似度片段通常对应于标志/标题卡，应检查其时序配对是否正确。
- 连续带可能表示静态内容或采样/对齐问题。
- 低相似度并不意味着高质量；应单独检查注册的质量指标和呈现的媒体。

<a id="standalone-qa-no-encode"></a>

## 独立QA（无编码）

```bash
video-uniq qa /path/to/master.mp4 /path/to/candidate.mp4 --vs-corpus
# writes candidate.mp4.qa.json + candidate.mp4.qa.html
```

`--vs-corpus` 添加了 `corpus_matches` 部分，以便您可以验证候选内容是否与之前上传的变体过于相似。

独立QA从不猜测变换、随机种子或分割。要请求注册的指标，请序列化已完成的 `RunSummary.plan` 的精确内容，并提供产生输出的相同片段目标：

```python
Path("completed-plan.json").write_text(summary.plan.model_dump_json(indent=2))
```

```bash
video-uniq qa master.mp4 candidate.mp4 \
  --plan-json completed-plan.json \
  --registration-segment-sec 600
```

没有 `--plan-json`，所有注册字段保持为空，原始指标不变。

<a id="fast-qa"></a>

## 快速QA

对于不需要 VMAF（慢速）的批处理工作流：

```bash
video-uniq run … --fast-qa
# - skips VMAF (the slowest stage)
# - halves the phash sample count
```

JSON 结构完全相同，使用 `vmaf_mean = null` 和 `phash_samples ≈ 60`。

<a id="programmatic-access"></a>

## 编程访问

```python
import json
from pathlib import Path

qa = json.loads(Path("out.mp4.qa.json").read_text())

# Internal audio fingerprint diagnostic:
hp = qa.get("audio_fp_hamming_per_frame")
if hp is not None:
    print(f"Audio FP distance: {hp:.1f} bits/frame")

# Worst chunk:
worst = max((c["combined"] for c in qa["chunk_similarities"]), default=None)
print("worst sampled similarity:", worst)
```

如果你更愿意使用类型化对象，Pydantic 模型是 `video_uniquifier.core.models.QAReport`。

对于超过 600 秒的源进行分层拼接时，音频距离的汇总仍然可用，但物理时间线偏移/漂移注册不可用。拼接指纹上的偏移无法转换为整个影片的时钟。
