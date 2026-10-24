<a id="distributed-batch"></a>

# 分布式批处理

`video-uniq queue` + `video-uniq worker` 允许多台机器共享一个工作队列而无需任何外部协调。协调只是
在共享文件系统上的两个目录之间的 `os.rename(2)`。

<a id="filesystem-requirements"></a>

## 文件系统要求

协议：跨目录重命名必须是 **原子操作** — 每个租约只有一个工作进程获胜。兼容的设置：

|文件系统 / 挂载|状态|
|---|---|
|**NFSv4** 与 `noac` 挂载选项|目标配置；在生产前在真实主机上验证|
|**ZFS** 通过 NFSv4 共享 (`sharenfs=on`)|支持|
|**ext4** 在单台主机上（单机多进程）|支持|
|**APFS** 在 macOS 上（单主机测试）|支持|
|NFSv3 无 `noac`|不支持 — 属性缓存会导致重命名看起来非原子性|
|`s3fs-fuse`, `goofys`（通过 FUSE 的 S3）|不支持 — 重命名是通过复制+删除实现的|
| SMB1 |不支持|
| SMB2/3 |部分支持；请使用 `init` 步骤验证|

`video-uniq queue init` 会针对所选目录执行真正的原子重命名测试，如果文件系统无法满足要求，会快速失败并显示明确错误。

<a id="nfs-mount-options-linux"></a>

## NFS 挂载选项（Linux）

在客户端：

```
your.nfs.server:/exports/queue  /shared/queue  nfs4  noac,vers=4.2,hard,timeo=600  0  0
```

`noac` 禁用使 `rename` 对并发读取者看起来非原子的属性缓存。是的，这会减慢元数据操作速度 — 这是正确租赁的权衡。

<a id="workflow"></a>

## 工作流程

```bash
# On one machine (or any one machine that mounts the share):
video-uniq queue init /shared/queue
video-uniq queue add  /shared/queue /shared/sources/movie1.mp4 \
                                  /shared/sources/movie2.mp4 \
                                  /shared/sources/movie3.mp4

# On worker hosts A and B (both mount /shared):
video-uniq worker /shared/queue \
  --profile /shared/profiles/cid_aware.yaml \
  --out-dir /shared/uniq/ \
  --encoder libx264 \
  --workers 4 \
  --heartbeat-sec 30 &

# Monitor from anywhere:
video-uniq queue status /shared/queue --json
# {"pending": 0, "in_progress": 2, "done": 1, "failed": 0}
```

<a id="heartbeat-and-recovery"></a>

## 心跳与恢复

每个工作进程进程都有主机名、PID 和 nonce 标识，并定期更新 `.alive` 文件，间隔为
`--heartbeat-sec`（默认 30 秒）。如果文件的 mtime 比此时间还旧
`stale_sec`（默认 300 秒，可通过 `video-uniq queue reset --stale-sec` 配置），任何其他工作进程的下一个 `lease()` 将把该主机的租赁文件移回 `pending/`。

CLI 和 GUI 工作进程在 FFmpeg 活动期间保持该心跳运行。已完成的编码首先写入最终输出旁的隐藏工作进程-特定文件。共享编排器检查其流/时间戳/颜色合同，并在工作进程提交该文件之前解码完整的主视频以及所有音频流。此正确性门是强制性的；丰富的 pHash/VMAF/SSIM HTML/JSON 报告仍然是单独的诊断，而不是发布标准。工作进程只有在将其租约原子地移至 `done/` 中的日志特定隐藏栅栏后，才可以发布它；如果清理程序已回收租约，则将丢弃过时的结果。发布后，该栅栏将成为普通的 `done/<input>` 标记。

在那个栅栏之前，工作进程会坚持在下面维护一个小型权限控制的日志
`<queue>/.commits/`。如果进程在租约到栅栏重命名和最终输出重命名之间终止，另一个 CLI 或 GUI 工作进程会等待原始心跳过期，并发布已经验证的暂存文件。随机栅栏令牌只属于唯一一个日志，因此较旧的同名 `done` 标记或重新排队的硬链接无法授权新的输出。如果租约在到达其栅栏之前被收割，恢复会删除未加栅栏的暂存工件，而不是发布它。

这会关闭本地硬崩溃发布窗口，并保持带围栏的至少一次处理。它不是跨网络分区的事务性严格一次性保证。跨主机 NFS 部署仍必须在生产前在实际挂载点上运行租约/收割/日志/崩溃资格检查；该矩阵**未经过验证**。所有工作进程需要相同的服务 UID，或者显式可继承的 ACL 授予队列、输出目录、暂存文件和
`.commits/` 所需的读/写/删除访问权限。仅共享 GID 对于提交日志恢复是不够的。日志负载仅包含基础名称和一个随机围栏令牌，而不包含绝对的源/输出路径。日志文件在发布后是不可变的，仅限所有者访问（`0600`，并进一步受 `umask` 限制）；恢复会删除它们的目录条目，而不是修改其内容。

<a id="local-nfs-fault-injection-lab"></a>

## 本地 NFS 故障注入实验室

在 Linux 主机上，Docker 可以创建一个临时的 NFSv4 服务器和两个独立的客户端，然后执行并发租约、网络分区后的陈旧回收、陈旧所有者发布围栏以及在四个发布边界（阶段后、日志、围栏和发布）进行 SIGKILL 恢复。它还验证了幂等的重复恢复、损坏检查点拒绝以及在有界 ENOSPC tmpfs 上的原子检查点存活情况：

```bash
tools/docker_nfs_fault_smoke.sh
```

证据写入 `.nfs-qualification/`，包括每个场景的 JSON、Docker 检查结果和客户端挂载表。实验使用较短的 `soft` 超时时间，因此强制分区不会阻塞 Docker 清理。这与上文推荐的生产环境 `hard` 挂载有意不同：通过实验是一个确定性的应用/围栏门控，而实际生产主机仍必须使用其实际的 `hard` 挂载、服务器、网络和故障恢复策略进行验证。

原始已修正的实验在 GitHub 托管的 Ubuntu 上的 Actions 运行中通过了
`33881832592`。扩展矩阵也在本地 Docker Desktop/Intel macOS 上通过，包括并发租赁唯一性、过期回收/围栏以及在恢复客户端 TCP/2049 后继续操作。这些是保留的临时实验结果，并不代表部署的实际 NFS 服务器或挂载选项的认证。

<a id="per-machine-encoder-variation"></a>

## 每台机器的编码器差异

按设计，两台工作进程可能使用**不同**的编码器（Linux 上使用 libx264，Mac 上使用 hevc_videotoolbox）。因此，同一来源的生成变体在 H.264 / HEVC 比特流参数上会略有差异。对于 CID 分歧的使用情况来说，这通常是没问题的（变体本来就应该有所不同）。如果需要一致性，请通过 `--encoder libx264` 将所有工作进程锁定到同一编码器。

<a id="output-collisions"></a>

## 输出冲突

工作进程发布到 `out_dir/<input.stem>.uniq.<profile-container>`。队列插入会拒绝重复的基本名，但独立的队列根仍然可以指向相同的输出目录，并在相同的文件名干上竞争。通过以下方式避免这种部署：

1. 确保 `pending/` 中的基本名唯一，或
2. 为每个工作进程设置 `--out-dir`，然后稍后合并。

<a id="docker-compose-example"></a>

## Docker Compose 示例

```yaml
services:
  worker:
    image: video-uniquifier:2.2.0
    volumes:
      - /mnt/shared:/shared:rw            # NFSv4 noac mount on host
    environment:
      VIDEO_UNIQ_PROFILE: /shared/profiles/cid_aware.yaml
    command:
      - video-uniq
      - worker
      - /shared/queue
      - --profile=/shared/profiles/cid_aware.yaml
      - --out-dir=/shared/uniq
      - --encoder=libx264
      - --workers=4
    deploy:
      mode: replicated
      replicas: 4                          # 4 workers in this stack
```

<a id="cleanup"></a>

## 清理

`done/` 只是一个标记——文件会不断累积。定期执行：

```bash
find /shared/queue/done -mtime +30 -delete
```

当 `<queue>/.commits/` 中仍有匹配文件时，不要修剪 `done/` 标记：该标记是发布的边界。健康的工作进程会在拥有者心跳超时后对日志进行对账，远早于 30 天示例保留期。

（`video-uniq queue prune --done-older-than 30d` 子命令已推迟到 v0.4——在真正的 CID 验证框架到位之前，不会有工作进入这个子命令。在此之前在 cron 中使用上面的 `find` 片段。）
