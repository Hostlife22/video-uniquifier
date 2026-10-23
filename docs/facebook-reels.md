# Facebook Reels 短剧处理（实验性 Worker）

面向已经剪辑完成、拥有版权或传播授权的视频，输出可人工检查的 MP4、质量报告、
镜头时间线和预览。按 P0 → P1 实现；不需要 AI、模型或云服务，不包含发布功能。
基础引擎锁定于 Hostlife22/video-uniquifier 2.1.2 的提交
`e9138ddbc798cb23e28b44d9edf7959a712f0add`。MIT 许可证继续适用。
实际 API 调研及验证记录见 [开发日志](facebook-reels-development.md)。

## 安装与运行

要求 Python ≥3.11、FFmpeg/FFprobe、libx264、loudnorm、colorspace；显式 HDR 转换还需
zscale/tonemap。默认镜头检测需要 `[scene]`，HTTP 服务需要 `[web]`。

```sh
sh tools/install_reels.sh
.venv/bin/video-reels validate examples/facebook_reels/reels_business_rules.yaml
.venv/bin/video-reels preflight input.mp4 --rules examples/facebook_reels/reels_business_rules.yaml
.venv/bin/video-reels run input.mp4 \
  --rules examples/facebook_reels/reels_business_rules.yaml \
  --asset-root ./assets --root ./reels-jobs --json-events
```

`run` 接受 `--job-id`（字母、数字、下划线和连字符，最多 64 字符）；已有任务 ID 不覆盖。
Ctrl+C 或 SIGTERM 会通过原生 CancelToken 终止 FFmpeg/镜头检测子进程并清理工作目录。
取消退出码 130，配置/处理失败退出码 2；失败原因以 JSON 写到 stderr。

这是独立的 `video-reels` CLI/API，没有向原桌面界面或稳定的 `video-uniq` CLI 添加字段。
默认仅使用实测的软件 libx264；硬件编码器还未纳入这个交付预设。

## 两层配置

| 文件 | 用途 | 加载方式 |
|---|---|---|
| `custom_profiles/facebook_reels_base.yaml` | 原生 Profile，仅包含原项目认可的字段 | 原生 `video-uniq --profile`；Worker 的可选 `--profile` |
| `examples/facebook_reels/reels_business_rules.yaml` | 业务规则：编码、包装、场景、QA、资源限制 | **只传 `video-reels --rules`** |

Worker 先校验原生 Profile 及每个 Transform 参数 schema，再按业务规则派生 fit_aspect、
loudnorm 和显式 tonemap。原生 Profile/Plan/RunOptions 的稳定 schema 没有修改。
缺省业务字段采用严格默认值；未知字段、重复 YAML 键、别名、危险路径、超限数值、
NaN/Infinity、字符串形式的数字均拒绝。JSON Schema 可从代码生成：

```sh
.venv/bin/video-reels schema > /tmp/reels-business.schema.json
```

输入副本经 FFprobe 检查实际媒体信息；扩展名白名单不代替解码验证。
默认限制 2048 MiB、7200 秒、8,847,360 像素、最多 2 个 CPU 任务；这些是本地资源预算，
不是 Facebook 发布限制。`worker.wall_timeout_sec` 是扫描/编码/预览阶段的进程超时；
原生 probe、响度测量、QA 同时沿用各自的引擎超时。编码线程自动分配，上限每任务 8。

## 默认行为与明确限制

- MP4 + faststart、1080×1920（可选 720×1280）、H.264 yuv420p、SAR 1:1、SDR Rec.709、
  CRF 21 / veryfast。识别常见 CFR 23.976/24/25/29.97/30/50/59.94/60 并保留，VFR 转 30 CFR。
- 9:16 输入保持完整画面；其他比例默认原生 `pad_blur`。开启中心裁切需要同时设置
  `geometry.nonvertical_source: crop` 和 `allow_center_crop: true`。
- HDR/PQ/HLG 默认拒绝；人工设置 `video.hdr_policy: tonemap_sdr` 才调用原生转换。
  广色域缺少可靠传递函数、SDR BT.2020 constant-luminance 输入要求先核实/转换。
  缺少色彩标记的普通 SDR 按 Rec.709 解释，并在报告中警告；有可靠 SDR 标记时执行色彩转换。
- 仅选择默认音轨（没有默认时选择第一条），记录绝对流索引。保持对白音高和速度；
  两遍响度目标 -16 LUFS / -1.5 dBTP / LRA 11，AAC-LC 48 kHz 双声道 128 kbps。
  测量值按输入 SHA256、所选音轨、裁切、目标、引擎和 FFmpeg 版本缓存。
  无音轨输出纯视频；静音记录 `silent`；极短音频无法稳定测量时如实记录。
  `audio.enabled: false` 或 `audio.loudnorm.enabled: false` 关闭响度归一化，仍保留并规范编码音轨。
- 镜头检测使用原生 PySceneDetect 适配器，输出 `scenes.json`，不重排、删除或自动加转场。
  `trim_start_sec/trim_end_sec` 同步裁切音视频，时间线同时记录源与输出坐标。
  黑帧、静音只报告；VFR 的镜头位置需要人工复核。缺少 `[scene]` 时返回可操作错误，
  或人工设置 `scenes.detect_enabled: false`。裁切带独立软字幕轨的输入会明确拒绝；
  已烧录字幕随画面保留。独立字幕的复杂转换/裁切不在本版范围。
- 标题和 Logo 默认关闭；标题由人提供，字体必须是 asset-root 下已有的授权字体，
  Logo 必须为 PNG。Pillow 先渲染透明图层，再与原生滤镜合并为**一次视频编码**。
  文件 Hash 仅用于复现记录，不是画质或平台原创性指标。
- 包装参数示例见 `examples/facebook_reels/packaging.json`，需放置示例引用的字体和图片。
  CLI 将它作为业务 YAML 的 `packaging` 节点；API 将该对象作为 multipart 的 `packaging` JSON 字段。
  路径只能相对 asset-root，拒绝穿越及越界符号链接。文字不会进入 shell 或 FFmpeg 表达式。
  `title.start_sec/end_sec` 相对于**裁切后的输出**；超出最大行数不静默截字。
  Logo/标题越界或侵入保护字幕区会失败，标题与 Logo 重叠会给出警告。
  720 画布下需要按像素调整 Logo 边距和字号。
- 安全区为内部启发式边距，默认左右 6%、顶部 14%、底部 30%；没有 OCR，无法自动找出
  所有硬字幕。独立 `safe-area.png` 只供预览；不插入封面，不改变交付视频。
  `preview.mp4` 默认取前 10 秒流复制，边界受音视频包量化影响；可分别关闭安全区/短片预览。

## 输出与质量门禁

```text
reels-jobs/
├── uploads/<uuid>.<ext>           # HTTP 输入，保留供重试
├── cache/<measurement-hash>.json # 可复用的有限响度测量值
├── work/<job-id>/                # 未发布临时产物，不可下载
├── results/<job-id>/             # QA 后整个目录原子发布
│   ├── output.mp4
│   ├── report.json
│   ├── scenes.json               # 检测开启时
│   ├── preview.mp4               # 短片预览开启时
│   ├── safe-area.png             # 安全区预览开启时
│   └── *.log / *-layer.png       # 复现诊断，仅本地
├── failures/<job-id>.json         # 失败/取消报告，无正式下载链接
└── jobs.json                     # 本地任务状态快照
```

报告包含 `preset_id/engine_version/job_id/source/output/warnings/quality_check`，
以及有效业务参数、派生原生 Profile、plan hash、输入/输出 SHA256、FFmpeg 版本、
执行 argv、选中音轨、测量值、镜头/黑帧/静音、编码尝试次数和耗时。
处理中若输入内容变化，拒绝发布。报告路径/argv 用于内部诊断，不直接作为公开业务响应。

QA 核实 MP4/faststart、编码/尺寸/色彩/SAR/帧率、时长差 ≤0.5 秒、AAC-LC 参数、
全片解码和音视频起止时间差 ≤100ms；输出响度目标容差 1 LU，峰值容差 0.5 dB，
始终检查是否超过 0 dBTP。缺少可靠时间戳时不会声称同步验证通过。
`quality_gate.enabled: false` 仅用于诊断：仍记录失败，但允许导出，请检查 `gates_enforced`。

时间戳同步不等于对白口型或语义同步。听感、字幕可读性、HDR 转换观感和真实手机界面
必须人工验收。重构后的画面没有已注册的对应参考帧，因此不输出误导性的原始 SSIM/VMAF；
`compare_against_source` 当前比较时长/音轨/几何交付约束，视觉相似度明确记为未计算。
不提供 Facebook 原创性认定、推荐量或流量保证。

## HTTP 接口规范

```sh
export VIDEO_REELS_API_TOKEN='replace-with-local-secret'
.venv/bin/video-reels serve --rules examples/facebook_reels/reels_business_rules.yaml \
  --root ./reels-jobs --asset-root ./assets --port 8765
curl -H "Authorization: Bearer $VIDEO_REELS_API_TOKEN" \
  -F 'file=@input.mp4' -F 'preset_id=facebook_reels_drama_v1' \
  http://127.0.0.1:8765/api/video-jobs
```

默认仅绑定 loopback，一个 API 进程。设置 token 后所有路由（含 `/docs` OpenAPI）
都需 Bearer 认证。请求必须有 Content-Length；不接受不受限的分块上传。
公开上传鉴权、用户隔离及 Redis 持久队列由 NestJS 承担，本服务是内部本地 Worker。

| 方法/路径 | 请求/响应 |
|---|---|
| GET `/api/video-presets` | 预设 ID、版本和有效业务默认值 |
| POST `/api/video-jobs` | multipart `file`、`preset_id`、可选 `packaging` JSON；202 返回任务状态 |
| GET `/api/video-jobs/{id}` | `job_id,preset_id,status,progress,error,cancel_requested,output_url,report_url` |
| POST `/api/video-jobs/{id}/cancel` | 请求取消；实际退出后才进入 cancelled。已终结任务保持原状态 |
| POST `/api/video-jobs/{id}/retry` | 仅 failed/cancelled；202，新任务 ID；进程重启后需重新上传 |
| GET `/api/video-jobs/{id}/report` | 完成/失败后的 JSON；处理中 409 |
| GET `/api/video-jobs/{id}/files/{filename}` | 成功后可取 output.mp4、preview.mp4、safe-area.png、scenes.json |

状态为 `queued → probing → processing → qa → success`，可在中途进入 failed/cancelled。
`progress` 为 0..1，编码阶段复用 FFmpeg RunEvent，只有原子发布后为 1；
耗时未知的扫描/响度/QA 阶段采用阶段进度，不伪造剩余时间。

常见响应：401 未认证，404 未知任务/不可用产物，409 状态冲突，413 超限，
422 配置/文件名/空文件错误，429 本地待办队列满。媒体格式/预检错误通过异步
`status=failed,error={code,message,retryable}` 返回；代码包括 `missing_video`、
`hdr_requires_tonemap`、`trim_duration`、`subtitle_zone_conflict`、`quality_failed`、
`process_failed`、`cancelled` 等。默认队列最多 32 个未完成任务。

原生 RunAdmission 协调同用户独立 CLI/Worker 的 CPU 并发；每个部署应使用一致并发预算。
编码瞬时失败按 `max_retries` 重试，错误配置/QA 失败不自动重试。任务取消会结束子进程。
单进程重启后历史终态仍可查询，运行中任务标记 worker_restarted，不自动假称已恢复。
本地快照保留最近 1000 条；输入/结果/缓存不会自动清空，需要业务配置磁盘保留策略。
请勿用多个 API 进程共享同一 jobs 根目录；跨机器队列和恢复由 BullMQ 管理。

## NestJS / BullMQ 对接

提供可直接导入的 Node ≥22 HTTP 适配器
`examples/facebook_reels/bullmq-worker.mjs`（无需额外 npm 依赖）。在 NestJS 的 WorkerHost 中：

```ts
@Processor('reels', { concurrency: 2 })
export class ReelsProcessor extends WorkerHost {
  async process(job: Job) {
    return processReelsJob(job, {
      baseUrl: 'http://127.0.0.1:8765',
      // NestJS 收到取消请求时，在 Redis/数据库设置标志；不要只删除活动 BullMQ job。
      isCancelled: async (job) => this.cancellations.isRequested(job.id),
    });
  }
}
```

导入 `processReelsJob`，通过可信队列数据传 `sourcePath/presetId/packaging`。
使用 Node ESM 项目（或将适配器构建进现有 Nest 项目）；原生 openAsBlob 流式上传文件。
适配器将真实状态写入 `job.updateProgress`，返回成功产物地址，失败抛异常供 BullMQ
按 attempts/backoff 重试；取消、轮询网络错误和超时均尝试终止对应 Python 任务。
每次 BullMQ 重试创建新 Python attempt；旧失败报告保留。私有 Worker URL 需由 NestJS
代理鉴权下载。没有 Meta SDK、发布 token 或发布端点。
示例使用模拟 HTTP 的自动化测试；实际 Redis、业务鉴权和数据库集成需放入现有 NestJS 系统。

## 自动化验收

```sh
uv pip install --python .venv/bin/python 'pytest>=9.0.3,<10' 'pytest-cov~=5.0'
.venv/bin/python -m pytest tests/unit/test_reels*.py tests/integration/test_reels_processing.py \
  --cov=video_uniquifier.core.reels --cov-report=term-missing
node --test examples/facebook_reels/bullmq-worker.test.mjs
.venv/bin/python tools/reels_acceptance.py --root /tmp/reels-acceptance
```

验收脚本生成 10 秒竖屏、30 秒横屏 29.97fps、90 秒竖屏 23.976fps 素材，按默认
1080×1920 全链路处理，保存源视频/成片/报告/安全区及汇总 `acceptance.json`，不提交大型视频到 Git。
可用 `--rules` 指定另一份业务配置。复跑相同目录会复用已有成功产物；测试新配置请换目录。
合成画面/正弦波仅验证技术参数；还需用已授权的真实对白+BGM 视频完成
10/30/60/180 秒抽样试听、硬字幕和手机界面人工检查。
