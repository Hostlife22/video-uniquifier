<a id="runbook-scale-validation-and-long-form-recovery"></a>

# 负载测试手册

此程序验证现有的段/检查点/音频/合并流水线；它不引入第二条流水线。

<a id="scope-and-evidence-levels"></a>

## 范围和证据级别

仅使用您拥有或被许可处理的媒体。分别运行每个声明的生产组合：容器、SDR/HDR 模式、编码器、声道布局和主机。

- `VERIFIED`：针对该确切组合，保留的命令、清单、日志和 QA/基准 JSON 文件存在。
- `LIMITED`：合成夹具通过，但自然许可语料库未通过。
- `NOT VERIFIED`：不存在保留运行。不要从编码器发现中推断支持。

2026-09-03 的 Intel Mac 基准保存在 `BENCHMARKS.md` 中：合成 1/2/3 小时 SDR libx264 运行保留了所有 `7,200/14,400/21,600` 帧。一次 1 小时中断运行重用了前两个片段，未更改它们的 SHA-256 或 mtime。自然长片段、NFS、NVENC/QSV/AMF 和硬件 HDR 恢复保持 `NOT VERIFIED`。

<a id="prerequisites"></a>

## 先决条件

- 来自 `make dev` 和 `.venv/bin/video-uniq` 的 Python 环境。
- `ffmpeg` 和 `ffprobe` 在 `PATH` 上；libvmaf 仅在混乱等效性断言时需要。
- 固定的源校验和和足够的可用空间。从 `--dry-run` 开始；不要依赖固定的 `3× source` 估算高比特率中间文件。
- 每个案例都有专用的工作目录和输出路径。切勿在实时作业间共享工作目录。

每次运行前记录：

```bash
shasum -a 256 "$SOURCE"
ffmpeg -version | head -n 1
.venv/bin/video-uniq run "$SOURCE" \
  --profile src/video_uniquifier/profiles/medium.yaml \
  --out "$OUTPUT" --encoder libx264 --work-dir "$WORK" --dry-run
```

<a id="baseline-and-parallel-qualification"></a>

## 基准和并行资格

```bash
# Sequential baseline. Keep artifacts so resume identity can be inspected.
.venv/bin/video-uniq run "$SOURCE" \
  --profile src/video_uniquifier/profiles/medium.yaml \
  --out "$CASE_DIR/sequential.mp4" \
  --encoder libx264 --workers 1 --segment-sec 600 \
  --keep-segments --work-dir "$CASE_DIR/sequential.work"

# Parallel run of the same declared combination.
.venv/bin/video-uniq run "$SOURCE" \
  --profile src/video_uniquifier/profiles/medium.yaml \
  --out "$CASE_DIR/parallel.mp4" \
  --encoder libx264 --workers 4 --segment-sec 600 \
  --keep-segments --work-dir "$CASE_DIR/parallel.work"
```

如果水印保护在授权内容上触发，先检查发现，然后将 `--accept-watermark-risk` 添加为明确的操作员认证。

<a id="crash-and-resume"></a>

## 崩溃并恢复

仓库混乱测试在单独的进程组中启动整个 CLI，在确定的伪随机偏移处向该组发送 SIGKILL，恢复相同的工作目录，并将结果与干净的基线进行比较：

```bash
VIDEO_UNIQ_CHAOS_ROUNDS=3 \
  .venv/bin/pytest tests/chaos/test_random_sigkill.py -q
```

对于较长的手动案例，在中断前立即捕获 `state.json` 以及已完成片段的 SHA-256/mtime 清单。终止整个 CLI/FFmpeg 进程组，而不仅仅是父 Python 进程。使用完全相同的原始命令、输出路径和工作目录恢复。恢复期间不要传递 `--new-variant`。

在恢复后，每个持久化为 `done` 并且仍然匹配其记录的 SHA-256 的段必须保留其 SHA-256 和 mtime。任何 `in_progress`、缺失、零字节或摘要不匹配的段都必须重新处理。

<a id="deterministic-fault-injection-gates"></a>

## 确定性故障注入门

在发布候选版本之前运行：

```bash
.venv/bin/pytest \
  tests/unit/test_orchestrator_checkpoint_lifecycle.py \
  tests/unit/test_checkpoint.py \
  tests/unit/test_main_audio_atomic.py \
  tests/unit/test_concat_segments_workdir.py \
  tests/integration/test_resume_truncated.py \
  tests/integration/test_resume_partial_cleanup.py -q
```

这些测试涵盖被拒绝的并发所有权、检查点初始化失败、检查点 `fsync`/磁盘已满行为、部分音频清理、concat 失败、最终替换失败、损坏的段以及部分清理。它们断言现有的已发布输出/状态/音频工件不会被失败的尝试覆盖。

<a id="validation-and-acceptance"></a>

## 验证与接受

在保留的检查点边界上运行注册的接缝诊断：

```bash
.venv/bin/python tools/seam_test.py "$OUTPUT" \
  --source "$SOURCE" \
  --work-dir "$WORK" \
  --frames 8 --search-frames 2 --threshold 0.005
```

该工具比较解码后的源窗口/输出窗口，重置本地PTS，并仅搜索配置的有界帧偏移。缺少指标即为失败，而非静默跳过。几何/重定时变换仍可能需要RFC #12中提出的计划感知转换参考；保留原始输出，不要放宽阈值以隐藏未注册的对。

对于每个输出保留 `state.json`、FFmpeg 日志、源/输出 SHA-256、QA JSON 和基准测试结果。接受性以正确性为第一原则：

|门|通过标准|
|---|---|
|解码|主视频和每个选定的音频流解码到文件结尾（EOF）。|
|时间线|第一个视频PTS、持续时间、流计数/元数据以及音视频差异满足最终媒体协议。|
|接缝|帧数和单调时间戳与预期节奏相符；检查每个计划边界附近的源/输出。|
|简历|有效的已完成段哈希和修改时间保持不变；损坏/不完整的工件将被重新处理。|
|出版物|音频/concat/最终替换失败会保留之前有效的工件，并且没有 `.part` 文件。|
|质量|只有当源/输出在空间和时间上对齐时，才解释 VMAF/SSIM/PSNR；否则标记为不适用。|
|资源|峰值进程树 RSS、临时磁盘高水位、实际时间和编码时间已保留。|

位完全相同的最终文件并不是普遍接受的规则：编码线程调度和容器元数据可能会改变字节。对于固定确定性情况，需要精确重用已完成的片段工件，并验证最终媒体契约以及注册的质量指标。

<a id="remaining-mandatory-matrix"></a>

## 剩余的必需矩阵

- 拥有/授权的自然内容在1小时、2小时和3小时以上。
- 立体声、5.1声道和多音频轨道；MP4、MKV和MOV。
- 每个宣传的编码器都支持SDR、HDR10和HLG。
- APFS/本地磁盘以及任何实际部署的网络文件系统。
- 在可丢弃卷上进行断电/重启和低空间测试。

切勿在开发者的主卷上模拟满盘情况。使用可丢弃的映像、容器或专用CI 工作进程并保留恢复证据。
