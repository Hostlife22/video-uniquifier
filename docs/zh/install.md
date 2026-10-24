<a id="installation-and-launch"></a>

# 安装与启动

本指南介绍 2.2.0 桌面版本及源码安装。只处理您拥有或获准修改、分发的视频。正式发布前请从源码安装；以下下载链接对应 v2.2.0。

<a id="desktop-downloads"></a>

## 桌面安装包

请从 [GitHub Releases](https://github.com/Hostlife22/video-uniquifier/releases) 下载。每个版本提供校验和、CycloneDX 软件物料清单（SBOM）及 cosign 签名验证文件。

| 平台 | 文件 | FFmpeg |
|---|---|---|
| Linux x86_64 | `video-uniq-gui-2.2.0-x86_64.AppImage` | 内含静态 FFmpeg/FFprobe |
| macOS Apple Silicon | `video-uniq-gui-macOS.zip` | 需另行安装 |
| Windows 10/11 | `video-uniq-gui-Windows.zip` | 需另行安装 |

macOS 安装包面向 Apple Silicon。Intel Mac 及其他架构请从源码安装或在本机编译。Linux 另有 tar 压缩包；它与 AppImage 不同，需要系统 FFmpeg。

### Linux

```bash
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-2.2.0-x86_64.AppImage
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
chmod +x video-uniq-gui-2.2.0-x86_64.AppImage
./video-uniq-gui-2.2.0-x86_64.AppImage
```

### macOS

```bash
brew install ffmpeg
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-macOS.zip
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS
shasum -a 256 video-uniq-gui-macOS.zip
unzip video-uniq-gui-macOS.zip
mv video-uniq-gui.app /Applications/
open /Applications/video-uniq-gui.app
```

解压前，请将输出的哈希值与 `SHA256SUMS` 中对应文件的记录比较。应用仅有 ad-hoc 签名，没有 Apple Developer ID 公证。若 Gatekeeper 拦截已验证的下载，请在 macOS“隐私与安全性”设置中批准该应用。本构建流程不提供 Intel 或通用架构版本的承诺。

### Windows

```powershell
choco install ffmpeg
Invoke-WebRequest https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-Windows.zip -OutFile video-uniq-gui-Windows.zip
Invoke-WebRequest https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS -OutFile SHA256SUMS
Get-FileHash video-uniq-gui-Windows.zip -Algorithm SHA256
Expand-Archive video-uniq-gui-Windows.zip -DestinationPath .
.\video-uniq-gui\video-uniq-gui.exe
```

解压前请与 `SHA256SUMS` 比较。Windows 安装包未签名。若 SmartScreen 拦截已验证的下载，请核对来源后再批准；组织的 AppLocker 或 WDAC 策略可能需要管理员批准。

<a id="verify-the-release"></a>

### 验证发布文件

若文件哈希与 `SHA256SUMS` 不一致，请勿运行。若还需要验证 GitHub Actions 的签名身份，请另行安装 cosign：

```bash
cosign verify-blob \
  --bundle video-uniq-gui-2.2.0-x86_64.AppImage.cosign.bundle \
  --certificate-identity-regexp 'https://github\.com/Hostlife22/video-uniquifier/' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  video-uniq-gui-2.2.0-x86_64.AppImage
```

其他文件请使用对应的 `.cosign.bundle`。发布流程会在创建草稿前验证这些签名。`sbom.cdx.json` 和各安装包的 SBOM 描述所含组件，但不保证没有漏洞。

<a id="system-requirements"></a>

## 系统要求

源码安装需要 Python 3.11 或更高版本，以及位于 `PATH` 中的 FFmpeg 和 FFprobe。CI 在 Linux、macOS 和 Windows 上测试 Python 3.11、3.12。编码时间、内存和工作磁盘空间取决于时长、分辨率、编码器和启用的变换。

macOS 可运行 `brew install ffmpeg`，Debian/Ubuntu 可运行 `sudo apt install ffmpeg`，Windows 可运行 `choco install ffmpeg`。请检查实际安装版本的能力：

```bash
ffmpeg -version
ffprobe -version
ffmpeg -filters
```

可选能力包括：用于已配准参考画面质量评估的 `libvmaf`、用于 HDR 的 `zscale`、用于相应音频变换的 `rubberband`，以及 Chromaprint 音频指纹工具 `fpcalc`。缺少必需滤镜时，应安装合适的 FFmpeg 构建或禁用对应变换。

<a id="install-from-source"></a>

## 从源码安装

```bash
git clone https://github.com/Hostlife22/video-uniquifier.git
cd video-uniquifier
```

macOS/Linux：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,gui]"
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,gui]"
```

仅使用 CLI 时安装 `-e .` 即可。`[gui]` 添加 PyQt6 和 WebEngine，`[dev,gui]` 还包含开发工具。可选的 `[web]`、`[ml]`、`[scene]` 分别启用 HTTP 接口、SSCD 和场景检测。

```bash
video-uniq --version
video-uniq probe --encoders
video-uniq-gui --version
```

此版本源码的两个版本命令都应输出 `2.2.0`。编码器发现会实际执行能力探测，首次调用可能需要数秒。

<a id="first-cli-run"></a>

## 首次使用 CLI

先使用一段有权处理的短视频及较温和的配置文件：

```bash
video-uniq probe /path/to/master.mp4
video-uniq preflight /path/to/master.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml
video-uniq run /path/to/master.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml \
  --out /tmp/derivative.mp4 --encoder libx264
```

检查输出视频和 QA 报告。原生配置位于 `src/video_uniquifier/profiles/`，Reels 业务规则示例位于 `examples/facebook_reels/`。另见 [CLI 入门](getting-started.md) 和 [Reels 指南](facebook-reels.md)。

<a id="first-desktop-run"></a>

## 首次启动桌面应用

```bash
video-uniq-gui
```

选择源视频、输出路径和配置文件，先运行预检，再执行处理。使用结果前请检查播放效果和 QA 报告。**视频交付**工作区提供 Reels 的“源视频 → 设置 → 结果”流程。[桌面操作指南](gui-walkthrough.md)介绍全部十一个页面。

<a id="tests-and-local-builds"></a>

## 测试和本地构建

Makefile 是开发者的主要入口。集成测试会运行真实 FFmpeg；完整测试可能持续数十分钟，具体取决于硬件和已安装的可选依赖。

```bash
make lint
make typecheck
make test-unit
make test-integration
make check
```

构建 Python wheel 或桌面应用：

```bash
make build-wheel
make build
```

Wheel 位于 `dist/`。桌面输出分别为 macOS 的 `dist/video-uniq-gui.app`、Windows 的 `dist/video-uniq-gui/video-uniq-gui.exe`、Linux 的 `dist/video-uniq-gui/video-uniq-gui`。请在目标操作系统上构建。

预览三种语言的文档：

```bash
python -m pip install -e ".[docs,docs-test]"
make docs-build
make docs-serve
```

<a id="update-and-uninstall"></a>

## 更新与卸载

更新没有本地改动的源码副本：

```bash
git pull --ff-only
python -m pip install -e ".[dev,gui]" --upgrade
```

从当前环境卸载 Python 包：

```bash
python -m pip uninstall video-uniquifier
```

如不再需要，可随后删除本项目的 `.venv`。请保留仍需使用的导出文件、配置文件和素材库数据。

<a id="shared-resource-admission"></a>

## 共享资源准入

CLI、GUI、Web 和队列工作进程通过可写的共享目录协调预计编码器占用和磁盘需求。需要协作的进程应使用同一个绝对路径，并以同一服务账户运行：

```bash
export VIDEO_UNIQ_RESOURCE_LOCK_DIR=/shared/video-work/resource-admission
```

Docker 默认使用 `/data/work/.resource-admission`；协作容器应共享 `/data/work` 挂载。编码期间不要删除资源登记目录。硬件或容量改变后，先停止所有工作进程，再重置目录。该机制基于估算；需要硬性磁盘上限时应使用文件系统配额。网络文件系统、不同 UID 及混用 `CUDA_VISIBLE_DEVICES` 的配置尚未验证。

FFmpeg 默认在持续 600 秒没有输出时触发看门狗。`VIDEO_UNIQ_STALL_TIMEOUT_SEC=0` 可禁用此机制；`VIDEO_UNIQ_WALL_TIMEOUT_SEC` 可设置每个进程的硬性时间限制，默认禁用。

<a id="troubleshooting"></a>

## 常见问题

- **找不到 FFmpeg：**检查 `PATH`，或通过 `VIDEO_UNIQ_FFMPEG` 和 `VIDEO_UNIQ_FFPROBE` 设置绝对路径。
- **缺少 PyQt6：**在启动应用所用的环境中安装 `[gui]`。
- **内嵌 QA 查看器不可用：**使用**在浏览器中打开**；无界面运行时 WebEngine 为可选组件。
- **Linux 缺少 xcb 平台插件：**安装系统库：

```bash
sudo apt install libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
  libxkbcommon-x11-0 libgl1
```

- **Homebrew 缺少 HDR/rubberband 滤镜：**检查实际滤镜列表，也可显式选择完整构建：

```bash
brew install ffmpeg-full
export VIDEO_UNIQ_FFMPEG="$(brew --prefix ffmpeg-full)/bin/ffmpeg"
export VIDEO_UNIQ_FFPROBE="$(brew --prefix ffmpeg-full)/bin/ffprobe"
```

- **Wayland 无法拖放：**使用**浏览…**按钮；若有 XWayland，也可设置 `QT_QPA_PLATFORM=xcb` 后启动。
- **需要重新探测编码器：**更换 FFmpeg 或 GPU 环境后，使用**设置 → 重置编码器缓存**。

更多设置参见[配置文件](profiles.md)、[安全](security.md)和[文档目录](documentation.md)。
