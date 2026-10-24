<a id="seed-strategy"></a>

# 随机种子策略

随机变换使用 `Plan.run_seed` 选择参数。`Profile.seed_strategy` 决定新任务是重复这些选择，还是生成新变体。变体仅应用于您拥有或获准修改、分发的视频。

<a id="the-four-strategies"></a>

## 四种策略

| 策略 | 种子来源 | 行为 |
|---|---|---|
| `fixed` | `Profile.seed`，未设置时为 0，并转换到 uint32 范围 | 重复相同的随机参数选择 |
| `per_run` | 新任务使用新的随机 uint32 | 独立任务之间采用不同参数 |
| `per_file` | `source.path.as_posix()` 的 SHA-256 前四个字节 | 相同路径字符串得到相同参数选择 |
| `divergent` | 新的任务种子，加上每段视频的派生种子 | 不同视频片段使用不同参数 |

`per_file` 对路径而非文件内容计算哈希。移动文件或使用不同路径可能改变种子；在同一路径修改文件内容不会改变此种子计算。处理计划另由计划哈希标识。

<a id="configure-a-profile"></a>

## 配置文件设置

复制一个原生配置文件并设置策略：

```yaml
seed_strategy: fixed
seed: 42
```

独立变体可使用 `per_run`。需要在各视频片段间改变参数的实验可使用 `divergent`；该名称并不承诺外部检测系统会作出特定判断。

```yaml
seed_strategy: divergent
```

片段种子取 UTF-8 字符串 `"{plan_hash}:{segment_idx}:{run_seed}"` 的 SHA-256 前四个字节，并按无符号大端整数解释。派生输入相同，片段种子就相同。完整源音频的处理仍使用任务级种子。

<a id="resume-and-new-variants"></a>

## 恢复任务与新变体

`state.json` 中的检查点保存任务种子。恢复同一个兼容计划时，会复用参数选择和已完成片段。`--new-variant` 为 `per_run`、`divergent` 请求新变体；`fixed`、`per_file` 仍是确定性的。

```bash
video-uniq run master.mp4 --profile p.yaml --out result.mp4
video-uniq run master.mp4 --profile p.yaml --out result.mp4 --new-variant
```

此处 `p.yaml` 是您保存的原生配置文件。每个并行任务应使用独立的输出和工作目录。

<a id="reproducibility-limits"></a>

## 可复现性的边界

种子保证随机参数选择可复现，但不能保证跨编码器版本、线程调度、硬件、平台构建或容器元数据得到完全相同的文件字节。复现时请保留源文件校验和、配置文件、计划哈希、实际种子及工具版本。应验证解码媒体的正确性，并使用已配准参考画面比较质量。

本地相似度分数不能预测 Content ID 决策、平台原创认定、触达量或发布许可。使用获准制作的衍生视频前，请人工检查画面、对白和字幕。

<a id="implementation-and-tests"></a>

## 实现与测试

- `core/seed_resolver.py`：任务种子选择及片段种子派生。
- `core/segmenter.py::_plan_for_segment`：各视频片段的计划副本。
- `core/orchestrator.py::build_plan`：初始种子选择。
- `tests/unit/test_seed_resolver.py`、`tests/unit/test_divergent_seed.py`：确定性派生、策略行为及 uint32 边界。
