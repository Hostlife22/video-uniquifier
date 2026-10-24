<a id="getting-started"></a>

# 快速入门

对 `video-uniquifier` 的 5 分钟导览。涵盖 CLI、GUI 和网页——选择其中一个，之后其他的也会显得很熟悉。

<a id="1-install"></a>

## 1. 安装

```bash
pip install "video-uniquifier[gui,web] @ git+https://github.com/Hostlife22/video-uniquifier.git@v2.2.0"
python -c "from importlib.resources import files; from pathlib import Path; Path('review-soft.yaml').write_bytes(files('video_uniquifier').joinpath('profiles/soft.yaml').read_bytes())"
```

拉取核心 CLI、PyQt6 桌面 GUI 和 FastAPI 网络终端。如果不需要该界面，可以去掉括号。有关二进制要求，请参见 [安装](install.md)（`ffmpeg`，可选 `fpcalc`，可选 Whisper）。

<a id="2-pick-or-install-a-profile"></a>

## 2. 选择（或安装）一个配置文件

随附的配置文件覆盖了大多数使用场景：

|配置文件号|使用案例|
|----------------------|---------------------------------------|
| `soft`               |最低影响基线|
| `medium`             |平衡默认|
| `aggressive`         |实验性更强的处理|
| `cid_aware`          |传统实验兼容性|
| `cid_aggressive`     |传统最大变更兼容性|
| `youtube_shorts`     |9:16 重构为 Shorts（≤ 60 秒）|
| `youtube_1080p`      |16:9 1080p|
| `youtube_4k`         | 16:9 4K                               |
| `tiktok_vertical`    |9:16 适用于抖音|
| `instagram_reels`    |9:16 适用于 Reels|
| `instagram_square`   |适用于 Instagram 的 1:1|
| `linkedin_square`    |适用于 LinkedIn 的 1:1|

也浏览社区贡献的配置文件：

```bash
video-uniq profile list-community
video-uniq profile install cid_aware       # installs into ~/.config/video_uniquifier/profiles/
```

该目录按条目进行了 SHA 固定；如果哈希不匹配，安装程序将拒绝写入文件。详细信息请参见 [社区市场](marketplace.md)。

<a id="3-sanity-check-the-input"></a>

## 3. 对输入进行合理性检查

```bash
video-uniq probe ~/Videos/in.mp4
video-uniq preflight ~/Videos/in.mp4 --profile review-soft.yaml
```

`probe` 打印解析后的 `SourceMeta`（容器、流、HDR 状态）。`preflight` 执行与 `run` 中强制的一样的警告矩阵，并告诉你在编码开始前哪些会失败。

<a id="4-run-an-encode"></a>

## 4. 运行编码

=== "CLI"

    ```bash
    video-uniq run ~/Videos/in.mp4 \
        --profile review-soft.yaml \
        --out ~/Videos/out.mp4
    ```

=== "桌面 GUI"

    ```bash
    video-uniq-gui
    ```

    Then on the **Run** screen: pick input, pick profile, click
    **▶ Run**. The live divergence indicator on the right shows
    a sparkline of pHash divergence per segment.

=== "Web UI（Docker）"

    ```bash
    docker run --rm -p 127.0.0.1:8080:8080 \
        -v $PWD/input:/data/input:ro \
        -v $PWD/output:/data/output \
        -v $PWD/work:/data/work \
        ghcr.io/hostlife22/video-uniquifier:v2.2.0
    ```

    Open http://127.0.0.1:8080 and fill in the form. Full guide
    at [Web UI & Docker](web.md).

<a id="5-inspect-the-qa-report"></a>

## 5. 检查 QA 报告

每次运行后都会在输出旁生成 `<out>.qa.json` 和 `<out>.qa.html`。在浏览器中打开 HTML 以获取完整报告，包括 pHash / chromaprint / VMAF /（可选）SSCD 分数。架构已在 [QA 报告](qa_report.md) 中记录。

<a id="6-next-steps"></a>

## 6. 后续步骤

* **对该源自动调谐配置文件** — `video-uniq calibrate`（或 GUI 运行界面的 **Auto-tune** 按钮）根据质量目标二分参数。参见 [校准](calibrate.md)。
* **对文件夹进行批处理** — `video-uniq batch ~/Videos/in/` 或批处理界面。
* **在 NAS / 实验室中分发** — `video-uniq worker` + 共享文件系统。参见 [分布式批处理](distributed.md)。
* **预生成字幕** — `video-uniq subtitles generate
  ~/Videos/in.mp4`. The `video.subtitles` 在编码时将其嵌入。
* **选择加入遥测** — 设置 → 本地遥测，或在
  您自己的脚本中传入 `--telemetry`。仅限本地 JSONL；不联网。

卡住了？打开 `video-uniq <subcommand> --help` 查看任何子命令，或提交问题。
