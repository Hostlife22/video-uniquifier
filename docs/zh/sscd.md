<a id="sscd-copy-detection-qa"></a>

# SSCD 副本检测

> 在 v0.8.0 中新增（R4 — 指标；R6 — 通过 SSCD 校准）。

SSCD（自监督复制检测）是 Meta 的图像复制嵌入模型，[在 DISC/Copydays 上评估](https://github.com/facebookresearch/sscd-copy-detection)。该项目将其应用于抽样的视频帧，作为拥有/授权内容的内部诊断。时间抽样/对齐是一个独立的过程，并不能重现 YouTube Content ID 或人眼视觉质量。

在 `video-uniquifier` 中，SSCD 是**可选择的**：该模型不是捆绑的，Torch 不是硬性依赖，而且只有在你请求时才运行该指标。

<a id="install"></a>

## 安装

```bash
pip install 'video-uniquifier[ml]'
```

这会拉取一对当前的 Torch/torchvision。在首次使用时
~94 MB `sscd_disc_mixup` 的 TorchScript 检查点会从官方 Meta CDN 下载到 `~/.cache/video_uniquifier/models/` 并通过 SHA-256 验证。若缓存文件不匹配，将被删除并重新下载 — 哈希值固定在 `core/qa/sscd.py::_MODEL_SHA256` 中，因此 CDN 换源会明显失败，而不会默默使用未知权重。

仅支持官方的 TorchScript 工件。Meta 的上游项目未发布 ONNX 检查点；必须通过 `model_loader` 明确提供自定义后端。上游 SSCD 项目在 MIT 许可证下发布；在重新分发检查点之前，请查看该许可证。

Intel macOS 是一个受限的例外情况：PyPI 仅为该架构提供 Torch 2.2.2，并且当前漏洞数据库对该版本发布了安全通告。因此，该项目仅将此组合限定于内置的 SSCD 检查点，其确切的 SHA-256 如上所示。在 Intel macOS 上不要加载不受信任的 Torch 模型；在需要完全修补的 ML 运行时的情况下，请使用 Apple Silicon、Linux、Windows 或注入的非 Torch 后端。

如果未安装 `[ml]`，每个公共 SSCD 入口点都会引发异常
`PipelineError` 根据上述安装提示。工具的其余部分——ffmpeg 管道、chromaprint QA、校准——仍然可用。

<a id="in-the-qa-report"></a>

## 在 QA 报告中

```bash
video-uniq qa source.mp4 output.mp4 --sscd
# or, for finer per-frame resolution:
video-uniq qa source.mp4 output.mp4 --sscd --sscd-frames 64
```

控制台会显示分段标题（`high` / `caution` / `clean`），HTML 报告（`<out>.qa.html`）会在现有的 VMAF + chromaprint 模块旁边渲染按颜色编码的逐帧热图。JSON 旁车文件增加了三个平坦字段：

* `sscd_mean` —— 匹配帧对之间的平均余弦值
* `sscd_min` —— 最不相似的帧对（用于发现单个异常值）
* `sscd_per_frame` —— 与源帧网格 1:1 对齐的余弦数组

<a id="threshold-bands"></a>

### 阈值分段

这些是保留的项目显示桶，而不是校准的检测器阈值或 DISC21 精度曲线的直接转换：

|平均相似度|分段|读取|
|----------------:|:----------|:-------------------------------------------|
| ≥ 0.85          | `high`    |高内部源/输出相似性|
| 0.65 – 0.85     | `caution` |混合结果；检查质量和对齐情况|
| < 0.65          | `clean`   |低相似性；检查可能的质量损失|

这些传统波段名称是诊断标签，而不是通过/不通过的目标。较低的分数可能意味着破坏性变换、时间错位或测量失败；必须结合VMAF/SSIM、音频和媒体合同结果一起解读。

<a id="in-calibration"></a>

## 正在校准中

```bash
video-uniq calibrate input.mp4 \
  --base profiles/cid_aware.yaml \
  --out tuned.yaml \
  --metric sscd \
  --target 0.8
```

`--metric sscd` 用基于SSCD的评估器替换了v0.5 chromaprint预测器。SSCD的约束平均余弦值直接传递给校准：值越高表示相似性越高，而收敛需要`mean_similarity <= target`，同时独立质量下限也通过。SSCD和Chromaprint的目标不可互换，必须在授权语料库上单独校准。

Chromaprint 的默认设置未更改：省略 `--metric` 会运行 v0.7 混合最大 pHash/音频诊断，包括当源有音频时的 `fpcalc` 要求。缺失的指纹无法满足其接受门槛。

GUI：校准屏幕在测试剪辑持续时间微调器旁有一个 **Metric** 下拉菜单。

<a id="determinism"></a>

## 确定性

相同的输入字节 + 相同的模型文件 + `torch.set_grad_enabled(False)` + 固定帧网格 → 位完全相同的嵌入，位完全相同的余弦。两次连续的 `compute_sscd` 调用返回相等的 `SSCDResult` 元组。这对于恢复很重要：一个经过 SSCD 校准的配置文件会在相同的源上重新运行得到相同分数，因此今天调好的配置文件明天在 CI 中仍能在相同剪辑上收敛。

<a id="public-api"></a>

## 公共 API

```python
from video_uniquifier.core.qa.sscd import compute_sscd, sscd_band, SSCDResult

result: SSCDResult = compute_sscd(
    source=Path("in.mp4"),
    output=Path("out.mp4"),
    frame_count=32,            # default — 32 uniform samples
    cancel_token=token,        # optional, including during FFmpeg extraction
    model_loader=None,         # test-only injection seam
)
print(result.mean_similarity, sscd_band(result.mean_similarity))
```

`model_loader` 的存在是为了让单元测试可以传递一个存根网络，而无需安装数百 MB 的 torch wheel（参见
`tests/unit/test_sscd_offline.py`).

<a id="cancellation"></a>

## 取消

`compute_sscd` 是一个在默认 frame_count 下耗时 5–10 秒的 CPU 密集型调用。`cancel_token` 参数在每个阶段 (`model_load`, `extract_source`, `extract_output`, `embed`, `cosine`) 之间都会被检查。中点提取也使用共享运行器，因此取消操作会终止其完整的 FFmpeg 进程树，而不是等待所有搜索完成。

`calibrate(metric="sscd")` 在每次迭代中转发相同的令牌，与 v0.5.5 版本 A6 在 chromaprint 路径上的行为一致。

<a id="architecture-notes"></a>

## 架构说明

* **懒加载导入**：`import torch` 位于 `compute_sscd` 内部，而不是模块顶部。导入 `video_uniquifier.core.qa.sscd` 是免费的。
* **统一时间线抽样**：中点搜索覆盖完整的源时间线，而无需解码多小时文件的每一帧。一个文件的所有搜索请求都通过单个 FFmpeg 进程发出，并使用单线程解码器输入。样本大小调整为 288×288，并在推理前使用上游 ImageNet 均值/标准差进行归一化。
* **成对余弦**：模型已经输出了 L2 归一化向量；显式的 `clamp([-1, 1])` 是为了防止浮点漂移的安全措施。
* **插件层未修改**：SSCD 完全存在于 `core/qa/` 中，因此第三方转换插件不需要知道它的存在。

另请参阅：

* [`docs/en/qa_report.md`](qa_report.md) — QA 工件的 JSON/HTML 架构
* [`docs/en/calibrate.md`](calibrate.md) — 二分循环语义
* [`docs/en/profiles.md`](profiles.md) — 配置文件架构（无 SSCD 字段；指标为每次运行）

请求的时间戳、最高采样余弦、成对计数、模型哈希和预处理都会记录在 QA 笔记中。样本之间的插入可能会被遗漏。静态矩阵无法建立时间偏移；在原始成对余弦仍然作为有效采样诊断的情况下，该模糊性无法进行注册。
