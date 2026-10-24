<a id="web-ui-docker"></a>

# 网页界面与 Docker

一个无头 FastAPI 服务器，驱动 CLI 和桌面 GUI 使用的同一协调器。Web 层是一个薄壳 — 每个端点构建一个 `Plan` + `RunOptions` 并将它们交给
`core.orchestrator.run_full`。`web/` 中不包含任何业务逻辑。

预期的部署是家庭实验室 NAS：部署容器，挂载你的媒体目录，从局域网内的手机或笔记本驱动编码。在前端使用反向代理（nginx、Caddy、Traefik）可以提供 TLS 和比内置基本认证更合理的身份验证。

<a id="run-it-locally"></a>

## 在本地运行

```bash
pip install video-uniquifier[web]
video-uniq-web                           # binds 127.0.0.1:8080 by default
```

然后打开 <http://127.0.0.1:8080>. 页面是一个原生 JS SPA（无框架）。选择输入路径，从下拉菜单中选择一个配置文件，可选输出文件名 —— 点击 **开始**。通过服务器发送事件进行实时进度流显示。

CLI 参数（等效环境变量在括号内）：

|标志|环境变量|默认值|
|------------------|--------------------------|-------------------------------|
| `--host`         | `VIDEO_UNIQ_WEB_HOST`       | `127.0.0.1`                   |
| `--port`         | `VIDEO_UNIQ_WEB_PORT`       | `8080`                        |
| `--work-dir`     | `VIDEO_UNIQ_WEB_WORK_DIR`   | `~/.cache/video_uniquifier/web`  |
| `--output-dir`   | `VIDEO_UNIQ_WEB_OUTPUT_DIR` | `./output`                    |
| `--profile-dir`  | `VIDEO_UNIQ_WEB_PROFILE_DIR`|每用户 XDG 配置|
| `--input-root`   | `VIDEO_UNIQ_WEB_INPUT_ROOT` |当前工作目录|
| —                | `VIDEO_UNIQ_WEB_MAX_CONCURRENT_RUNS` | `2`                    |
| —                | `VIDEO_UNIQ_WEB_RUN_RETENTION_SEC` |`604800`（7 天）|
| —                | `VIDEO_UNIQ_WEB_MAX_RUN_RECORDS` | `1000`                    |

基本认证受 `VIDEO_UNIQ_WEB_USER` 和
正在设置 `VIDEO_UNIQ_WEB_PASS`。如果两者都未设置，服务器处于 LAN 信任模式，并将每个请求视为已认证——仅适用于回环绑定或孤立的容器网络。HTTP Basic 凭据只是编码而非加密：绝不可直接在不信任的网络上公开此服务。在反向代理处终止 TLS 并强制执行访问策略；当代理在同一主机运行时，将主机端口绑定到 `127.0.0.1`。

## Docker

随附的 `Dockerfile` 是一个两阶段构建：一个 Python wheel 构建器和一个 `python:3.12-slim-bookworm` 运行时，它会安装 Debian 匹配架构的 `ffmpeg` 和 `ffprobe`。运行时用户是非 root 用户 (`uid 1000 videouniq`)；可写数据卷挂载点已预创建，如果容器在编码中途被杀死，`tini` 会清理僵死的 ffmpeg 子进程。

镜像故意**不**安装 `[ml]` 扩展 (`torch` 单独约 800 MB)。如果你想在容器内使用 SSCD，请自制容器：

```dockerfile
FROM video-uniquifier:2.2.0
USER root
RUN pip install --no-cache-dir "video-uniquifier[ml]"
USER videouniq
```

<a id="build"></a>

### 构建

```bash
docker build -t video-uniquifier:2.2.0 .
```

发布工作流会为 `linux/amd64` 和 `linux/arm64` 发布一个清单。在发布之前，每种架构必须构建、生成 H.264/AAC 试件，通过 `video-uniq` 处理它，验证输出比特流，启动 Web 服务并通过 `/healthz`：

```bash
tools/docker_multiarch_smoke.sh linux/amd64 video-uniquifier:smoke-amd64
tools/docker_multiarch_smoke.sh linux/arm64 video-uniquifier:smoke-arm64
```

运行非本地架构使用 QEMU，可能比本地构建慢好几倍。GitHub Actions 存储每种架构的单独 BuildKit 缓存，并在最终签名的多架构构建中复用这两者。

<a id="run-lan-trust"></a>

### 运行（LAN 信任）

```bash
docker run --rm -p 127.0.0.1:8080:8080 \
    -v $PWD/input:/data/input:ro \
    -v $PWD/output:/data/output \
    -v $PWD/work:/data/work \
    video-uniquifier:2.2.0
```

<a id="run-behind-a-same-host-tls-reverse-proxy"></a>

### 在同一主机 TLS 反向代理后运行

```bash
docker run --rm -p 127.0.0.1:8080:8080 \
    -e VIDEO_UNIQ_WEB_USER=alice \
    -e VIDEO_UNIQ_WEB_PASS=hunter2 \
    -v $PWD/input:/data/input:ro \
    -v $PWD/output:/data/output \
    video-uniquifier:2.2.0
```

配置 nginx、Caddy 或 Traefik 以公开 `https://` 端点并代理到 `http://127.0.0.1:8080`。不要将发布地址更改为 `0.0.0.0`，除非外部防火墙提供了等效的可信边界。

### docker-compose

一个参考 `docker-compose.yml` 在仓库根目录下运行，绑定回环接口，挂载输入/输出/work/配置文件的卷，并且基本认证环境变量被注释掉。它还应用了默认的硬上限：4 个 CPU、12 GiB 内存、512 个 PIDs，以及两个并发的 web 运行。内存默认值包括高于 1080p60 HDR/VMAF 处理过程中观察到的约 8.8 GiB 峰值的余量；内存较低的主机应禁用重量级 QA 或为更小值设置明确限制。将其复制到您的 NAS，编辑卷路径，调整 `VIDEO_UNIQ_CPU_LIMIT`，`VIDEO_UNIQ_MEMORY_LIMIT`，
`VIDEO_UNIQ_PIDS_LIMIT`，和 `VIDEO_UNIQ_MAX_CONCURRENT_RUNS` 对于主机，然后运行
`docker compose up -d`。本地安装必须通过操作系统服务管理器强制相应的 CPU/内存硬上限；单独使用 `--workers` 只是一个编码器调度器，而不是内存上限。

<a id="api-surface"></a>

## API 接口

除 SSE 事件流和 QA HTML/JSON 转发外，每个端点都是 JSON 输入 / JSON 输出。

|方法|路径|备注|
|--------|-----------------------------------------------------|-----------------------------------|
| GET    | `/`                                                 |SPA 外壳（HTML）|
| GET    | `/healthz`                                          |活跃性检查；返回 `ok`|
| GET    | `/api/profiles/local`                               |捆绑 + 每用户 YAML 文件|
| GET    | `/api/profiles/community?refresh=true`              |市场目录|
| POST   | `/api/profiles/community/{id}/install`              |验证 SHA + 安装|
| POST   | `/api/run`                                          |开始编码；返回 `run_id`|
| GET    | `/api/run/{id}/events`                              |RunEvents 的 SSE 流|
| GET    | `/api/run/{id}/status`                              |终端状态轮询|
| POST   | `/api/run/{id}/cancel`                              |翻转 CancelToken（遵守 ≤ 7 秒）|
| GET    | `/api/qa/{name}/html`                               |提供 `<name>.qa.html`|
| GET    | `/api/qa/{name}/json`                               |提供 `<name>.qa.json`|

`POST /api/run` 主体：

```json
{
  "input_path": "/data/input/source.mp4",
  "profile_path": "/data/profiles/cid_aware.yaml",
  "output_name": "optional.mp4",
  "encoder_override": null,
  "workers": 1
}
```

`WebConfig.input_root` 之外的输入路径将被拒绝并返回 **403**；当未设置时，服务器使用其当前工作目录作为根。对于 NAS/容器挂载，请显式设置 `--input-root /data/input`。针对的路径遍历尝试
`/api/qa/...` 会以 **400 / 404** 被拒绝。带 body 的请求需要恰好一个有效的非负 `Content-Length`；缺失、格式错误、为负、重复或超出限制的长度在路由处理前会被拒绝。将 `Transfer-Encoding` 与 `Content-Length` 组合也会被拒绝。不支持分块请求体，因此无法绕过配置的硬性上限。

终端运行状态以原子方式存储在 `<work-dir>/web_runs.json` 中，并且在进程重启后仍然保留。当服务器停止时运行状态为 `pending` 或 `running` 的运行会被报告为 `failed`，并附有中断/重启诊断；FFmpeg 检查点数据会保存在其每次运行的工作目录中，供操作员检查。只有运行 ID、状态、经脱敏的错误类别、时间戳和输出基名被持久化——源/配置文件路径和完整异常信息不会写入此 Web 注册表。

默认输出文件名使用所选配置文件的容器 (`.mp4`, `.mkv` 或 `.mov`)。在后台任务启动之前，如果显式文件名的后缀不兼容，将被拒绝。活动的最终输出在
`<output-dir>/.video_uniquifier-reservations/` 中以原子方式保留，因此共享本地文件系统的独立服务器进程会返回 **409** 而不是写入相同文件。确切的拥有者在终端状态释放其保留；在同一主机上的失效拥有者可以恢复。外部主机的过期记录因为无法证明远程进程存活而关闭失败。共享/NFS 部署必须为其文件系统确定原子创建和恢复语义；该矩阵目前**未验证**。

`max_concurrent_runs` 在共享相同
`output_dir` 的服务器进程中强制执行。原子拥有者槽及其不可变容量记录存在于
`<output-dir>/.video_uniquifier-admission/`；满池返回 **429**，而不可用或配置不一致的池返回 **503**。每个共享该目录的实例必须使用相同的值。要更改它，请停止所有此类服务器，确认没有编码进程仍在运行，仅删除该许可目录，然后使用新的通用值重启服务器。死掉的同主机所有者将被恢复；格式错误和异主机所有者将失败关闭。

每个 `run_full` 调用者还通过 `VIDEO_UNIQ_RESOURCE_LOCK_DIR` 协调编码器插槽和估算的临时磁盘字节（默认：
`~/.cache/video_uniquifier/resource-admission`）。Docker 镜像将其指向挂载的 `/data/work/.resource-admission`，因此兄弟容器必须共享该工作卷以共享预算。对所有本地实例使用相同的绝对注册表路径和服务账户。在清理它或更改检测到的编码器容量之前，请停止所有参与的进程。

这仍然是基于估算的本地安全边界，而不是集群调度器。混合 GPU 可见性/设备路由、不同的服务账户、NFS 原子性、网络分区以及自然 4K/长视频码率估算的准确性仍然存在
**未经验证**；在这些部署中需要外部强制执行硬文件系统配额。

<a id="whats-not-on-the-web-yet"></a>

## 什么还没有在网页上发布

* 校准、批处理、队列、验证、语料屏幕 — 仅在 v0.9 的桌面 GUI 中可用。网页端 shell 有意针对单输入“驱动编码”用于 NAS 部署的用例；完全的屏幕功能一致性在 v1.0 的计划中。
* 在 `/` 上没有文件系统浏览器 — 路径必须手动输入（或从 NAS 网页 UI 粘贴）。选择器在 v1.0 的愿望清单中。
* 瞬时掉线时不会重新连接 SSE。请刷新页面；
  `run_id` 会在服务器端保留直到下一次启动。
