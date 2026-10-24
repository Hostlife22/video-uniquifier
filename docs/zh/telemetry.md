<a id="telemetry-v090-r3"></a>

# 本地遥测

`video-uniquifier` 在您明确选择加入之前不会记录任何遥测数据。当启用时，每次完成或失败的编码结束时，恰好会在本地 JSONL 文件中追加一个摘要事件。v0.9 版本中没有网络输出——将汇总统计数据上传到共享收集器是 v1.0 版本的另一个议题，并且将需要其自身的同意步骤。

<a id="what-gets-recorded"></a>

## 记录内容

每次编码，无论成功或失败，以下字段会写入 `events.jsonl`：

|字段|示例|备注|
|------------------|----------------------------------|------------------------------------|
| `kind`           | `run_summary`                    |固定|
| `status`         | `completed` / `failed`           |固定集|
| `profile_name`   | `cid_aware`                      |来自用户的 YAML|
| `profile_codec`  | `h264`                           |来自配置文件.target_codec|
| `encoder_name`   | `libx264`                        |来自 EncoderCandidate.name|
| `encoder_vendor` | `x264` / `nvenc` / `videotoolbox`|来自 EncoderCandidate.vendor|
| `wall_clock_sec` | `423.17`                         |端到端时间|
| `workers`        | `4`                              |来自 RunOptions.工作进程|
| `os`             | `darwin` / `linux` / `win32`     |sys.platform|
| `os_release`     | `25.5.0`                         |platform.release()|
| `python`         | `3.12`                           |仅主版本.次版本|
| `segments_done`  | `27`                             |仅成功|
| `output_basename`| `clip__cid_aware.mp4`            |仅成功；仅 **basename**|
| `error_summary`  |`PipelineError: …`（前200个字符）|仅失败|
| `schema_version` | `1`                              |在任何破坏性形状更改时更新|
| `event_id`       | UUID4                            |每个事件的唯一键|
| `ts`             |Unix纪元|服务器端时间戳|

**从不**记录的内容：源文件路径、源文件内容、文件哈希、音频指纹、配置文件 YAML主体、时长、分辨率、超过前200字符的错误追踪，或任何能识别源文件的内容。

相同的有限递归编辑器安装在结构化日志接收器、审核 JSONL 写入器和遥测序列化之前。敏感的键名（`authorization`、cookies、密码、机密、API/访问/私密密钥和令牌）、内联的 bearer/basic 凭证、常见的 GitHub/OpenAI 令牌形式以及带有令牌的查询参数都将被替换为 `<REDACTED>`。公共审计字段将每个绝对路径都编辑为 `<PATH>/<basename>`；结构化日志仅保留安全的基本名称。Prometheus 使用固定的状态和编码器标签词汇，从不将路径、令牌、运行 ID、计划 ID、作业 ID 或分段 ID 作为标签存储。

<a id="what-does-not-go-into-the-event"></a>

## 什么内容 *不* 会进入事件

* 完整路径。默认配置具有 `redact_paths=True`，它会在任何存留在模式中字符串字段中将 `$HOME` → `<HOME>` 重写。仅保留基本名称的 `output_basename` 已经不含 HOME；此规则作为纵深防御而存在。
* 错误回溯。我们捕获 `type(exc).__name__: str(exc)`，截断为 200 个字符。内部帧和局部变量不会保留在事件中。

<a id="where-the-events-live"></a>

## 事件发生的地方

| OS      |路径|
|---------|--------------------------------------------------------------------------------|
|macOS| `~/Library/Application Support/video_uniquifier/telemetry/events.jsonl`           |
|Linux|`$XDG_DATA_HOME/video_uniquifier/telemetry/events.jsonl`（或 `~/.local/share/…`）|
|窗口| `%APPDATA%\video_uniquifier\telemetry\events.jsonl`                               |

当文件达到 1 MiB 时会旋转（可按每个配置）
`TelemetryConfig.rotate_at_bytes`); 仅保留一个备份 (`events.jsonl.1`)。

同意标记——证明你已经以某种方式回答了首次运行对话——位于
`~/.config/video_uniquifier/telemetry-consent`。它的主体是字面字符串 `enabled` 或 `disabled`，因此支持技术人员无需解析 JSON 就能判断状态。

## CLI

```bash
video-uniq telemetry status                      # path, event count, consent state
video-uniq telemetry status --json
video-uniq telemetry export ~/share.jsonl        # copy out for sharing
video-uniq telemetry purge --yes                 # wipe events dir
```

有意没有 `video-uniq telemetry enable` 子命令。开启它必须是明确的 GUI 点击或程序操作
`RunOptions(telemetry=TelemetryConfig(enabled=True))` 所以脚本无法意外地翻转全局标志。

## GUI

**设置 → 本地遥测（可选择加入）** 有：

* 一个 **启用** 切换开关
* 一个 **遮盖路径** 切换开关（默认开启）
* 状态（事件计数 + 磁盘上的路径）
* **应用遥测** — 保存配置并写入同意标记
* **打开事件文件夹** — 在操作系统文件浏览器中显示目录
* **清除事件** — 通过确认对话框不可逆地删除

首次启动会显示一次性对话框，带有两个按钮（**启用**/**保持禁用**）；默认状态为 *禁用*。如果不选择直接关闭对话框，则记录为“禁用”，以后将不再提示。

<a id="programmatic-use"></a>

## 编程使用

```python
from video_uniquifier.core.telemetry import TelemetryConfig
from video_uniquifier.core.orchestrator import RunOptions, run_full

opts = RunOptions(
    work_dir=Path("work"),
    output=Path("out.mp4"),
    telemetry=TelemetryConfig(enabled=True),  # off by default
)
run_full(plan, opts)
```

`record(event, config)` 也是公开的，如果你希望通过自己的管道处理将自定义事件推送到同一文件。失败会被吞掉并通过 `logging` 记录 — 遥测从不改变运行结果。
