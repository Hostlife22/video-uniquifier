<a id="experimental-calibration-workflow"></a>

# 自动调参

`video-uniq calibrate`搜索现有配置文件的强度，以处理自有或许可媒体。它使用本地工程诊断将源与授权衍生进行比较。它不预测YouTube Content ID或任何其他外部版权管理系统。

此命令仍为实验性：相似性阈值依赖于语料库，短的代表性样本不能证明完整文件的质量。在发布前，始终在完整源文件上运行调优后的配置文件并检查最终QA报告。

<a id="quick-start"></a>

## 快速入门

```bash
video-uniq calibrate /path/to/master.mp4 \
  --base src/video_uniquifier/profiles/medium.yaml \
  --out /path/to/tuned.yaml \
  --target 0.2 \
  --min-quality 88.0 \
  --iterations 7 \
  --clip-sec 60.0 \
  --metric chromaprint

video-uniq run /path/to/master.mp4 \
  --profile /path/to/tuned.yaml \
  --out /path/to/derivative.mp4
```

`chromaprint` 命名了一个混合的最大 pHash/音频诊断，并且需要 `fpcalc` 用于带音频的来源。缺少必需的指纹会中止处理，而不是让仅视觉候选看起来可行。`sscd` 需要可选的 `[ml]` 依赖，并且体积明显更大。

<a id="calibration-v2-behavior"></a>

## 校准 v2 行为

1. 总的 `--clip-sec` 预算分配在长来源的开头、中间和末尾。比预算更短的来源作为一个完整的剪辑使用。
2. 三个窗口被流复制并合并为一个内容键探针。这避免了花费三倍于请求的编码预算。
3. 每个候选都使用 `seed_strategy: fixed` 和相同的随机种子，因此随机变换模式不会在试验之间移动目标。
4. 搜索首先测量因子 `1.0`、下界 `0.25` 和上界
   `4.0`（取决于迭代预算）。然后它在对数刻度上划分信息间隔。它不假设变换堆栈是单调的。
5. 每个候选项都通过现有的 `build_plan` 和 `run_full` 管道。编码/评估失败会在相同的因子下重试一次，然后中止；它从不被转换为低分。
6. 相似性和感知质量是独立的约束。只有当两者都通过时，候选项才是可行的。
7. 首次成功试验使用的质量后端在搜索中被固定。如果后端在 VMAF 和 SSIM 之间发生变化，校准将中止，而不是比较不兼容的数值。
8. 完整评分的试验通过计划哈希、算法版本和相似性度量进行原子缓存。重新运行中断的搜索可以重用先前的测量数据。源文件、配置文件、编码器、随机种子、工具版本或度量发生变化时，会生成不同的键。不完整的运行器/输出工件是会话隔离的，因此同时进行的 GUI 或 CLI 搜索不会相互破坏。自定义程序化评估回调有意绕过此缓存。
9. 在可行的候选者中，结果优先考虑测量质量较高的，然后是因子较温和的。如果没有可行的候选者，它会返回规范化约束违规最小的候选者并以状态 2 退出。

这三个锚点试验是故意设计的。因此，校准不会仅因为因子 `1.0` 通过而停止；额外的证据用于检测质量陡降和非单调行为。耐用的试验重复使用抵消了反复运行的成本。

<a id="quality-threshold-semantics"></a>

## 质量阈值语义

`--min-quality` 不是通用感知单位：

|后端|报告值|典型可用性|
|---|---:|---|
| VMAF |本地 0..100 分数|FFmpeg 由 `libvmaf` 构建|
| SSIM |平均 SSIM × 100|当 VMAF 不可用时的备用|

pHash 不是感知质量的备用。CLI 和 GUI 始终在值旁显示后端。即使两个实验都使用数值阈值 `88`，也将 VMAF 实验和 SSIM 实验视为不同的校准。

<a id="options"></a>

## 选项

|标志|默认值|工程意义|
|---|---:|---|
| `--target` | 0.2 |最大本地源/导数相似性诊断；非外部概率|
| `--min-quality` | 88.0 |明确报告的 VMAF 或 SSIM 后端的最低分数|
| `--iterations` | 5 |总界限搜索试验预算；对异构长格式来源使用7–9|
| `--clip-sec` | 60.0 |总时间分布在开始/中间/结束窗口|
| `--metric` |chromaprint|`chromaprint` 或 `sscd` 本地诊断|
| `--encoder` |自动|当生产编码将使用特定编码器时固定|
| `--work-dir` | `.video_uniq_calib` |探测、候选、工作和得分试验缓存目录|

<a id="reading-the-result"></a>

## 读取结果

`converged` 意味着至少有一个测量的候选在请求的因子范围内通过了两个约束。这不意味着整部电影已经被认证。

`not converged` 意味着没有采样的候选通过两个门槛。常见原因是相似性诊断平坦/噪声、质量脆弱的来源、不适合的基础配置文件，或迭代预算过小。检查每一步的后端和备注；不要通过盲目提高转换强度来补偿。

工作目录是可重复使用的。标记为 `scored-trial cache hit` 的步骤未重新编码。如果您有意进行全新测量而其他输入保持不变，仅删除该校准工作目录。

<a id="programmatic-api"></a>

## 程序化 API

```python
from pathlib import Path

from video_uniquifier.core.calibration.loop import CalibrationTarget, calibrate
from video_uniquifier.core.profile_loader import dump_profile, load_profile

base = load_profile(Path("profiles/medium.yaml"))
result = calibrate(
    input_path=Path("/movies/master.mp4"),
    base_profile=base,
    target=CalibrationTarget(
        max_self_match=0.15,
        min_quality=86.0,
        max_iterations=8,
        test_clip_sec=90.0,
        seed=0,
        min_factor=0.25,
        max_factor=4.0,
    ),
    work_dir=Path("/tmp/calib"),
)

print(result.converged, result.factor, result.final_quality_metric)
dump_profile(result.profile, Path("tuned.yaml"))
```

`CalibratedResult.steps` 记录每个采样的因素、配置文件、相似度分数、质量值/后端、已耗评分时间以及缓存/回退注释。在进行任何媒体工作前会验证边界，并且必须满足
`0 < min_factor <= 1 <= max_factor`.

校准仅按现有强度规则调整参数。它不会切换变换、重新排序滤镜图、选择第二管道或替换全输出正确性和质量验证。

<a id="intensity-rules-and-scoring-domain"></a>

## 强度规则和评分域

请参阅 [audit implementation decisions](https://github.com/Hostlife22/video-uniquifier/blob/d6af67ac05eb0689f958f18cca08cfdb6cb7c4db/docs/audit-implementation-decisions.md) 了解当前的参数规则、固定效应、边界和缓存迁移。原始校准质量比较源和候选；它与注册的编码质量是分开的。不支持 HDR 原始参考。仅视频输入可以使用视觉诊断；在带音频的源上音频提取失败是一个错误。缓存模式 3 记录实际可执行版本和官方 SSCD 模型身份。
