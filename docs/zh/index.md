# video-uniquifier

处理并重新编码您自有或已获授权的视频。先预览变换，再对比原片与成片，
通过桌面应用、命令行或本地网页界面处理单个视频或批量任务。

<a id="start-here"></a>

## 从这里开始

- [安装](install.md)：Python、桌面安装包、FFmpeg 与首次启动。
- [快速入门](getting-started.md)：探测源文件、校验配置并开始编码。
- [桌面界面指南](gui-walkthrough.md)：源文件、样片、处理设置与结果。
- [视频交付 / Reels](facebook-reels.md)：四步竖屏交付、CLI 与 HTTP Worker、镜头时间线和技术质量报告。
- [网页界面与 Docker](web.md)：启动本地网页服务或容器。

```sh
pip install "video-uniquifier[gui] @ git+https://github.com/Hostlife22/video-uniquifier.git@v2.2.0"
python -c "from importlib.resources import files; from pathlib import Path; Path('review-soft.yaml').write_bytes(files('video_uniquifier').joinpath('profiles/soft.yaml').read_bytes())"
video-uniq-gui
video-uniq probe input.mp4
video-uniq preflight input.mp4 --profile review-soft.yaml
video-uniq run input.mp4 --profile review-soft.yaml --out output.mp4
```

从源代码安装需要 Python 3.11+，并确保 FFmpeg/FFprobe 位于 PATH 中。
可选功能需要各自文档中列出的依赖，例如镜头检测需要 `[scene]`。

<a id="processing-and-review"></a>

## 处理与验收

- [配置文件](profiles.md)和[变换参考](transform_reference.md)介绍画面几何、视听变换、
  HDR 兼容性与经过校验的参数。
- [架构](architecture.md)说明按片段恢复、资源限制，以及桌面、CLI 和网页共用的处理核心。
- [质量报告](qa_report.md)区分技术正确性、感知质量与诊断性相似度。成片仍需人工观看和试听。
- [分布式批处理](distributed.md)介绍经过验证的共享文件系统；
  [硬件验证](hardware_qualification.md)说明具体设备的限制。

应用和文档均提供英语、俄语与简体中文。通过页眉语言菜单切换文档语言。
源码结构与翻译维护检查见[文档语言](documentation.md)。

!!! warning "自有或已获授权的内容"
    仅使用自有或已获授权的视频。局部相似度指标不能预测外部版权管理系统的决定。
    项目不保证绕过 Content ID、被平台认定为原创或获得推荐流量。
