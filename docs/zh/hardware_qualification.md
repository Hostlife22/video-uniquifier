<a id="hardware-encoder-qualification"></a>

# 硬件验证

编码器发现证明 FFmpeg 可以为一个精确任务打开设备。这并不能证明生成的流拥有所需的配置文件、色彩信号、帧节奏或随机访问结构。仅当生成的文件在目标设备和驱动程序上通过真实的比特流合约时，后端才被认为具备生产资格。

手动 `Hardware qualification` GitHub Actions 工作流在受信任的自托管运行器上运行该合约。它故意没有参与推送和拉取请求触发，因此正常的 CI 矩阵既不会等待稀缺的 GPU，也不会在持久机器上执行不受信任的更改。

<a id="what-is-checked"></a>

## 检查内容

工作流程通过真实的 `build_plan` 和 `run_full` 路径生成一个六秒的 640×360、24 FPS BT.709 限幅源。需要存在并完成一个明确请求的编码器；它不能变成跳过。输出检查涵盖：

- 精确的编解码器、级别信号和 MP4 样本条目标签；
- Main/High 配置文件和 8-bit 4:2:0 像素格式；
- 保持的帧数、节奏和 BT.709/范围信号；
- 保持的 30/20/60 FPS VFR 时间戳模式和精确解码帧数；
- 当编码器标识 HEVC 时，HEVC Main10 HLG/BT.2020/限幅信号；
- 在未明确验证保留 ST2086/MaxCLL/MaxFALL 的硬件路径上，对静态 HDR10 元数据进行关闭失败拒绝；
- 当编码器声明至少两个会话时，两个并行作业；
- 严格的 1080p 和 3840×2160 SDR 作业用于 H.264/HEVC VideoToolbox；
- 在硬件处理发出进度后取消，不生成部分最终输出；
- 当对应的 VideoToolbox 候选不可用时，自动按速度策略回退到实际探测的软件编码器；
- H.264 高级/CABAC 和封闭半帧率 IDR GOP，对于精确计数的后端使用一到两个连续 B 帧，或对于合格的 VideoToolbox 范围使用一到三个 B 帧；
- HEVC 封闭 IDR 和最长两秒的 GOP；
- AV1 的关键帧间隔最多为两秒。

`qualification-artifacts` 包含 JUnit XML、每个生成的媒体文件以及带哈希的 JSON 报告，FFprobe 帧/流数据，FFmpeg 构建信息和可用的 GPU 清单。工件会保留 30 天。失败的断言是有用的合格证据：请修复并使供应商策略符合要求，而不是仅通过编码器发现就削弱合同或标记后台为支持状态。

<a id="runner-preparation"></a>

## 运行器准备

使用带有生产驱动程序的专用机器或临时虚拟机、预期的 FFmpeg 构建、`ffprobe`、Git 以及受支持的 Python。将其注册为自托管运行器，使用默认操作系统标签加上一个特定设备标签，例如：

|设备|建议标签|典型编码器选择|
|---|---|---|
|NVIDIA 图灵（例如 T4）| `gpu-nvenc-turing` | `h264_nvenc,hevc_nvenc` |
|NVIDIA Ada| `gpu-nvenc-ada` | `h264_nvenc,hevc_nvenc,av1_nvenc` |
|Intel Arc / 最近的集成 GPU| `gpu-qsv` |支持的 `h264_qsv,hevc_qsv,av1_qsv` 子集|
| AMD GPU | `gpu-amf` |支持的 `h264_amf,hevc_amf,av1_amf` 子集|
|Apple Silicon| `gpu-videotoolbox` |支持的 VideoToolbox 编码器子集|

不要请求物理设备无法编码的编解码器。例如，NVIDIA T4 有 NVENC H.264/HEVC，但没有 AV1 编码器。如果指定的编码器缺失或其实际能力探测失败，工作流程会故意失败。

!!! warning
    永远不要将此工作流程附加到 `pull_request`，也不要将长期运行的
    自托管运行器暴露给不受信任的分支。使用非管理员运行器账户，隔离
    主机/网络，避免使用仓库密钥，并在作业结束后在可行的情况下重建临时运行器。


<a id="run-and-evaluate"></a>

## 运行并评估

在 Actions 用户界面中，选择 **硬件认证**，选择提交的分支、操作系统标签、设备标签以及精确的逗号分隔编码器列表。等效的 CLI 分发命令为：

```bash
gh workflow run hardware-qualification.yml \
  -f runner_os=Linux \
  -f runner_label=gpu-nvenc-turing \
  -f encoders=h264_nvenc,hevc_nvenc \
  -f python_version=3.12
```

当没有在线运行器具有所有三个标签（`self-hosted`、所选操作系统和设备标签）时，作业可能会无限排队。绿色结果仅认证记录的操作系统、FFmpeg 构建、设备代和驱动程序—而不是整个供应商。在进行驱动程序、FFmpeg 或编码器策略更改后，保留发布证据的工件并重新运行。

在本地，可以在没有 Actions 的情况下使用相同的严格选择：

```bash
export VIDEO_UNIQ_HARDWARE_ENCODERS=h264_videotoolbox,hevc_videotoolbox

pytest tests/integration/test_encoder_bitstream_matrix.py -vv \
  --basetemp=.qualification/pytest-temp \
  --junitxml=.qualification/junit.xml

python tools/hardware_qualification_report.py \
  --media-root .qualification \
  --output .qualification/report.json
```

`.qualification` 目录是证据，而不是受源控的固定文件。在归档报告和存储发布记录的媒介后将其删除。

在认证的 Intel Mac（Intel UHD 630 + Radeon Pro 5300M，FFmpeg 9.0.1）上，扩展矩阵完成，结果为 **22 通过 / 36 未请求跳过**。
`h264_videotoolbox,hevc_videotoolbox`。保留的报告包含39个已探测和哈希的媒体工件，以及UHD/取消证据。SDR和HLG编码路径已被确认合格；HDR10静态元数据被故意设置为失败关闭，因为此VideoToolbox路径无法证明ST2086/MaxCLL的保留。这只适用于特定的Mac/FFmpeg组合；NVENC、QSV、AMF和Apple Silicon仍属于独立的运行资格。
