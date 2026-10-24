<a id="filter-graph"></a>

# 滤镜图

该管道将变换线性组合为每次 ffmpeg 调用的单个 `-filter_complex` 图。每个输入在 Python 端有且只有一个阶段（不会通过 `bgr24` 进行 `subprocess.stdin` 循环）。

<a id="building-blocks"></a>

## 构建模块

```
TransformSpec(id, kind="video"|"audio", schema, build)
  ↓ build(params, alloc, in_label, rng=...) ↓
FilterChain(in_label, out_label, filter_str, extra_inputs)
```

`LabelAllocator` 分配唯一标签（`v1`, `v2`, …, `a1`, `a2`, …），这样管道就可以在不需要变换之间协调的情况下拼接片段。

选择每次运行可变性的构建器可以接受一个可选的 `rng=random.Random` 参数，该参数从 `Plan.run_seed` 种子生成。相同的随机种子 → 相同的滤镜图。

<a id="registered-transforms-21"></a>

## 已注册的变换（21）

| ID |类型|备注|
|---|---|---|
| `video.crop_resize` |视频|微裁剪 + Lanczos 重缩放|
| `video.rotate` |视频|0.05–0.5° 旋转并填充边缘|
| `video.color_eq` |视频|亮度/对比度/伽玛/饱和度抖动|
| `video.noise` |视频|通过 `noise=alls=N:allf=t+u` 模拟胶片颗粒|
| `video.mirror` |视频|水平翻转（仅限自选）|
| `video.blend_b` |视频|使用第二个 `-i B.mp4` 进行帧混合|
| `video.speed` |视频| `setpts=PTS/rate` |
| `video.temporal_jitter` |视频|每周期遮挡 + 在随机相位上下降 (Fojcik 2025)|
| `video.tonemap_sdr` |视频|zscale 线性化 → 色调映射 (hable/reinhard/mobius/aces) → SDR|
| `video.fit_aspect` |视频|裁剪/信箱至目标纵横比和尺寸|
| `video.subpixel_sharpen` |视频|轻度仅亮度反锐化处理|
| `video.subtitles` |视频|可选的 SRT 嵌入，带路径/能力验证|
| `audio.pitch_tempo` |音频|`rubberband` (保持共振峰) 或 `asetrate`+`atempo` 级联|
| `audio.eq` |音频|参数化 `equalizer` 频段|
| `audio.resample` |音频|`aresample` 到并从不寻常的中间采样率|
| `audio.compand` |音频|动态范围抖动|
| `audio.reverb` |音频|`aecho` 预设 (小房间 / 中房间 / 大厅 / 混响板)|
| `audio.spectral_smear` |音频|轻度 `chorus` 用于 chromaprint 位移|
| `audio.haas_stereo` |音频|`adelay=0|N` 单声道兼容立体声扩展器 (Smitelli 2010)|
| `audio.noise_overlay` |音频|通过 `anull` + `anoisesrc` + `amix` 生成参数化粉/白/棕噪声|
| `audio.loudnorm` |音频|两遍处理 EBU R128；第一次传递缓存于 `state.json`|

<a id="composition-for-a-typical-profile-cid_aware"></a>

## 典型配置文件的组成（cid_aware）

```
[0:v:0]
   crop=iw*0.96:ih*0.96:iw*0.02:ih*0.02,
   scale=round(iw/0.96/2)*2:round(ih/0.96/2)*2:flags=lanczos            [v1]
[v1]
   eq=brightness=0.015:contrast=1.022:gamma=0.99:saturation=1.04        [v2]
[v2]
   noise=alls=5:allf=t+u                                                 [v3]
[v3]
   geq=lum='if(eq(mod(N\,30)\,8)\,128\,p(X\,Y))':
       cb='if(eq(mod(N\,30)\,8)\,128\,p(X\,Y))':
       cr='if(eq(mod(N\,30)\,8)\,128\,p(X\,Y))',
   select='not(eq(mod(n\,50)\,17))'                                     [v4]
[v4]
   scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p                    [vout]

[0:a:0]
   rubberband=pitch=1.058:tempo=1.000                                   [a1]
[a1]
   equalizer=f=120:t=q:w=1.0:g=-0.6,
   equalizer=f=4500:t=q:w=1.0:g=0.4                                     [a2]
[a2]
   adelay=0|17                                                          [a3]
[a3]
   aresample=47999,aresample=48000                                      [a4]
[a4]
   compand=attacks=0.05:decays=0.5:points=-80/-80|-20.7/-8.3|0/-3       [a5]
[a5]
   loudnorm=I=-14.0:TP=-1.5:LRA=11.0:
   measured_I=-21.8:measured_TP=-17.69:measured_LRA=0.1:
   measured_thresh=-31.8:offset=-0.0:linear=true:print_format=summary  [aout]
```

然后：

```bash
ffmpeg -hide_banner -y \
  -i input.mp4 \
  -filter_complex "<above>" \
  -map "[vout]" -map "[aout]" \
  -map "0:a:1?" -c:a:1 copy \
  -map "0:s?" -c:s copy \
  -map_chapters -1 \
  -c:v libx264 -preset slow -crf 18 \
  -c:a:0 aac -b:a:0 256k \
  -movflags +faststart \
  -map_metadata -1 \
  output.mp4
```

<a id="even-dimensions-guard"></a>

## 偶数尺寸保护

尾部总是在前面插入 `scale=trunc(iw/2)*2:trunc(ih/2)*2`
`format=yuv420p`。`libx264` 拒绝奇数宽度/高度；微裁剪可能留下一帧 319×180，我们在此将其向下取整为 318×180。

<a id="hdr-linear-light-wrap"></a>

## HDR 线性光包裹

当源为 HDR（PQ / HLG）且 `Profile.keep_hdr=true` 时，管道将每个 *色彩域* 转换（当前为 `video.color_eq` +
`video.noise`）包装在通过 `core/transforms/hdr_wrap.py` 的 zscale 往返中：

```
zscale=transfer=linear:matrix=gbr:npl=100,
format=gbrpf32le,
  eq=brightness=0.012:contrast=1.018:gamma=0.995:saturation=1.03,
  noise=alls=4:allf=t+u,
zscale=transfer=smpte2084:matrix=bt2020nc:npl=100,
format=yuv420p10le
```

需要线性光，因此“+1% 亮度”在 PQ 曲线的顶部和底部意味着相同的事情。还需要显式的浮点 RGB 工作格式：在下采样的 YUV 中仅进行传输处理可能会产生严重的色度偏差，而 HDR 元数据表面上看起来是正确的。几何变换（裁剪/重缩放/旋转/速度）和时间变换（temporal_jitter）可在任何域中操作，并且不受限制。

如果配置文件选择 `video.tonemap_sdr`（HDR → SDR），则跳过封装：色调映射会在链的开头折叠 HDR 传输，其余图形在普通 BT.709 SDR 中操作。输出 `pix_fmt` 总是
在这种情况下为 `yuv420p`。

<a id="the-videoblend_b-special-case"></a>

## `video.blend_b` 的特殊情况

`video.blend_b` 是唯一需要额外输入的变换。它的
`FilterChain.extra_inputs` 列出次要文件。管道：

1. 将 `-i B.mp4` 添加到 ffmpeg argv（输入索引 1）。
2. 将占位符令牌 `__B__` 在 `filter_str` 中重写为 `[1:v]`。

```
[0:v:0][1:v]scale2ref=w=iw:h=ih[b_scaled][a_ref];
[a_ref][b_scaled]blend=all_expr='A*0.97+B*0.03'                       [v_out]
```

<a id="the-audionoise_overlay-side-chain"></a>

## `audio.noise_overlay` 的侧链

`anoisesrc` 是一个*源*过滤器（0 输入，1 输出），因此它不能位于线性链中。该转换在其内部生成三个子链。
`filter_str`:

```
anull[main];
anoisesrc=c=pink:r=48000:amplitude=1[noise];
[main][noise]amix=inputs=2:weights=0.75 0.25:duration=first
```

前置 `anull` 消耗管道提供的输入标签并生成一个可标记的 `[main]` 节点，最终的 `amix` 可以与 `[noise]` 配对。

<a id="segment-mode-vs-full-mode"></a>

## 段模式与全模式

对于较长输入，`core/segmenter.py` 每段调用一次 `build_video_segment_command`（仅用于视频转换，音频 = 流复制），并且
`build_main_audio_command` 在整个源上调用一次（仅用于音频转换，两遍处理的 loudnorm 已缓存）。最终复用使用 concat 解复用器和流复制，因此接缝不会引入重新编码噪声。

在 `seed_strategy: divergent` 下，`segmenter._plan_for_segment` 在调用 `build_video_segment_command` 前用每段派生的随机种子替换，因此每段的随机转换（裁剪阶段、抖动偏移、噪声随机种子等）都是不同的。

<a id="quality-args-per-encoder"></a>

## 每个编码器的质量参数

|供应商|质量参数|
|--------|--------------|
| `nvenc` | `-preset p6 -rc vbr -cq 19 -b:v 0 -maxrate ~1.25× -bufsize 2×maxrate` |
| `qsv` | `-global_quality 19 -look_ahead 1` |
| `amf` | `-rc cqp -qp_i 19 -qp_p 19` |
| `videotoolbox` | `-q:v 50` |
| `x264` / `x265` | `-preset slow -crf 18` |

HDR 保留：当源为 HDR 时，管道选择 `yuv420p10le` 而不是 `yuv420p`，`keep_hdr=true`，且编码器宣称支持 10 位 (`hevc_nvenc`, `hevc_qsv`, `hevc_videotoolbox`, `libx265`)。`libx264` 不支持 10 位配置文件；运行开始前预检失败。
