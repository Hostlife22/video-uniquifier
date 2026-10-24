<a id="youtube-targets"></a>

# YouTube 输出要求

`video-uniq preflight` 在运行前检查源 + 配置文件是否符合 YouTube 推荐的上传编码设置，以及 HDR 的合理性。

<a id="what-the-matrix-checks"></a>

## 矩阵检查内容

|代码|严重性|触发条件|
|------|----------|----------------|
| `container.ok` / `container.unsupported` |正常 / 警告|源容器不在 `{mp4, mov, mkv}` 中|
| `video.codec.ok` / `video.codec.unusual` |正常 / 警告|源视频编解码器不在 `{h264, hevc, vp9, av1}` 中|
| `video.missing` |失败|源中没有视频流|
| `audio.missing` |警告|没有音频流 — 输出将仅为视频|
| `audio.codec.unusual` |警告|源音频编解码器不在 `{aac, opus, mp3}` 中（将重新编码为 AAC）|
| `audio.sr.bad` |警告|采样率 ≠ 44.1k / 48k（YouTube 将重新采样）|
| `fps.ok` / `fps.unusual` |正常 / 警告|帧率不在 `{23.976, 24, 25, 29.97, 30, 50, 59.94, 60}` ±0.1 的范围内|
| `subs.image_based` |警告|存在 PGS/DVB 字幕 — 无法复制到 mp4，将被丢弃|
| `hdr.color.transforms` |**失败**|HDR 源 + 配置文件有颜色/均衡/噪声变换，同时未启用 `keep_hdr=true` **也未**启用 `video.tonemap_sdr`（要么通过 zscale 包保持 HDR，要么通过色调映射转换为 SDR）|
| `hdr.unsupported.encoder` |**失败**|HDR 源 + 编码器是 libx264（不支持 10-bit 配置文件），并且配置文件保持 HDR（解决方法：启用 `video.tonemap_sdr` 以输出 SDR，或选择 `libx265`/HEVC 编码器）|
| `loudnorm.ok` / `loudnorm.missing` |正常 / 警告|配置文件缺少 `audio.loudnorm` — 输出无法达到 -14 LUFS|
| `bitrate.over` |警告|预计输出比特率 > YouTube 对该分辨率的上限|

<a id="h264-output-structure"></a>

## H.264 输出结构

合格的 `libx264` 路径明确发出 YouTube 官方文档中的上传结构：

- 现有视频管线的渐进式 4:2:0 输出；
- 高配置文件和 CABAC 熵编码；
- 最多两个连续 B 帧；
- 闭合 GOP，最大大小为本机帧率的一半（23.976/24 FPS 时为 `12` 帧，25 FPS 时为 `13` 帧，29.97/30 FPS 时为 `15` 帧，59.94/60 FPS 时为 `30` 帧）。

实际的比特流回归检查包括配置文件、B 帧运行、IDR 节奏和 CABAC。更改此内部编码器策略会增加计划哈希策略修订，因此恢复不能组合在不同 GOP 规则下编码的段。

H.264 VideoToolbox 请求相同的通用结构，并且已验证用于 High、CABAC、闭合半帧率 IDR 节奏和有限的 B 帧重排序。FFmpeg 通过任何正的 `-bf` 值来暴露 Apple 的帧重排序开关，而不是可靠的精确计数：合格的 Intel 硬件生成一次 B 帧运行，而 GitHub 的 Apple Silicon 运行器生成三次。因此，它不被声称为与 libx264 在字节或 B 模式上的等效。NVENC、QSV 和 AMF 仍然存在。
**未经验证**。接受 `-g`/`-bf` 参数是不够的：每个后端必须在匹配的物理硬件上证明其输出。

<a id="hevc-and-av1-random-access"></a>

## HEVC 和 AV1 随机访问

YouTube记录的半帧率上传GOP特指H.264。该项目并未将该规则作为HEVC/AV1上传要求。相反，HEVC和AV1使用内部两秒最大GOP，以使寻帧、段恢复和下游检查可预测：

- libx265和HEVC VideoToolbox生成封闭的IDR GOP；
- SDR HEVC VideoToolbox明确使用Main/8位，HDR使用Main10/10位；
- SVT-AV1和libaom-AV1生成Main-配置文件 4:2:0输出，使用相同的GOP限制；
- libaom恒定质量模式使用`-b:v 0`，不使用不兼容的VBV选项。

这些路径已在合格的Intel Mac上进行了比特流测试；三种软件路径也通过了Debian 12生产容器测试。NVENC/QSV/AMF和AV1 VideoToolbox仍然是硬件资格项目。

<a id="bitrate-ceilings-h264"></a>

## 比特率上限（h264）

|最大高度|天花板|
|------------|---------|
|≤ 1080p|12 Mbps|
|≤ 1440p|24 Mbps|
|> 1440p（例如 2160p）|68 Mbps|

检查将与 `source.video[0].bit_rate × 1.25` 比较，因为编码器在源上方分配了约 25% 的冗余。

<a id="loudness-target"></a>

## 响度目标

默认目标是 **-14.0 LUFS 综合**（YouTube 内容响度）。在 `Profile.target_loudness_lufs` 中设置；`audio.loudnorm` 会遵循它。

<a id="when-fail-is-returned"></a>

## 当返回失败时

当预检返回含有以下内容的发现时，`video-uniq run` 会在任何编码之前中止
`severity=fail`。如果你知道自己在做什么，可用 `--no-preflight` 覆盖（仅警告）。

`video-uniq preflight` 在失败时以代码 1 退出（因此对 CI 友好）。

<a id="references"></a>

## 参考

- [YouTube — 推荐的上传编码设置](https://support.google.com/youtube/answer/4603579)
- [YouTube — 推荐的比特率](https://support.google.com/youtube/answer/1722171)
- [YouTube — 内容响度目标](https://support.google.com/youtube/answer/13197387) （-14 LUFS 综合，-1 dB 真峰值）
