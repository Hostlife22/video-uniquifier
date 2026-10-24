<a id="accessibility"></a>

# 无障碍

`video-uniquifier`针对桌面GUI（`video-uniq-gui`）和可选web界面（`video-uniq-web`）实现**WCAG 2.1 Level AA**符合性。本页面是符合性声明、手动测试清单，以及针对少数AA标准我们采用记录的桌面适配而非完全遵循Web文字说明的理由。

CLI（`video-uniq …`）继承了用户终端模拟器和屏幕阅读器的辅助功能；它不在WCAG范围内，也未在此进行审核。

<a id="conformance-summary-v100"></a>

## 符合性概述 (v1.0.0)

|原理|等级|状态|我们如何验证|
|----------------|-------|--------|----------------------------------------------------------------------------------|
|可感知| AA    | ✅      |`tests/gui/test_theme_contrast.py` — 每个绘制的 (前景, 背景) 对 ≥ 4.5:1。|
|可操作| AA    | ✅      |`tests/gui/test_wcag_aa_compliance.py` — 焦点可见，可通过键盘访问。|
|可理解| AA    | ✅      |`tests/unit/test_gui_accessibility.py` — 每个交互式小部件都有名称。|
|稳健| AA    | ✅      |Qt 平台集成: PyQt6 开箱即用地提供 IA2 / AT-SPI / AX 桥接。|

<a id="programmatic-checks-ci-gate"></a>

## 程序化检查 (CI 门)

这些检查在每次推送时作为 `pytest` 的一部分运行:

|测试文件|断言| WCAG SC          |
|-------------------------------------------------|----------------------------------------------------|------------------|
| `tests/gui/test_theme_contrast.py`              |每个主题令牌 (前景, 背景) 对 ≥ 4.5:1| 1.4.3            |
| `tests/gui/test_wcag_aa_compliance.py`          |主题 QSS 定义可见的焦点轮廓| 2.4.7            |
| `tests/gui/test_wcag_aa_compliance.py`          |每个交互式小部件的 focusPolicy ≠ NoFocus| 2.1.1            |
| `tests/gui/test_wcag_aa_compliance.py`          |每个 `QPushButton` sizeHint ≥ 20×20 像素|2.5.5（桌面版）|
| `tests/gui/test_wcag_aa_compliance.py`          |每个屏幕都有一个命名的子类（角色暴露）| 1.3.1, 4.1.2     |
| `tests/unit/test_gui_accessibility.py`          |每个交互式组件都有 `accessibleName()`| 4.1.2            |

测试套件是合同：回归导致低于 AA 的情况会在构建发布前使 CI 失败。

<a id="desktop-adaptations"></a>

## 桌面适配

一些 AA 标准是为网页编写的，不能字面上直接应用到 Qt 桌面应用。我们遵循 [WCAG2ICT](https://www.w3.org/WAI/standards-guidelines/wcag/wcag2ict/) 工作组的指导意见，当文字内容不适用时。

| SC          |网页用语|我们应用的桌面解释|
|-------------|----------------------------------------|--------------------------------------------------------------------------------------------|
| 2.5.5 AAA   |目标 ≥ 44×44 CSS 像素|≥ 20×20 设备像素用于 `QPushButton`（符合 Qt 各平台默认 sizeHint 下限：Linux ≈ 22，Windows ≈ 20，macOS ≈ 22-24）。触控模式用户可使用操作系统级放大镜。|
| 1.4.4       |文本可放大到 200% 而无需滚动|通过 `QApplication.font()` + 操作系统 DPI 缩放获得支持；`QT_FONT_DPI` 和 `QT_SCALE_FACTOR` 也受到尊重。|
| 3.2.5       |仅在请求时更改上下文|主题切换需在设置屏幕中选择；聚焦时不会自动切换。|

<a id="keyboard-reference"></a>

## 键盘参考

每个屏幕都可以完全通过键盘操作。完整的快捷键列表：

|快捷键组合|操作|
|------------------------------|---------------------------------------------|
| `Tab` / `Shift+Tab`          |向前 / 向后移动焦点。|
| `Ctrl+1` … `Ctrl+9`          |跳转到侧边栏项目 1–9。|
| `Ctrl+0`                     |跳转到设置（侧边栏项目 10）。|
| `Enter` / `Space`            |激活聚焦的按钮或复选框。|
| `Esc`                        |取消正在运行的任务（运行屏幕，批处理）。|
| `Ctrl+R`                     |运行当前任务（运行屏幕）。|
| `F1`                         |打开应用内帮助（如可用）。|

侧边栏是键盘的主基地——如果你失去焦点，请按
`Ctrl+1` 着陆到运行和选项卡。

<a id="screen-reader-manual-test-guide"></a>

## 屏幕阅读器手动测试指南

CI 验证静态契约；体验本身最好通过真实屏幕阅读器验证。我们进行以下测试：

- **macOS**: VoiceOver (`Cmd+F5`)。
- **Windows**: NVDA（免费，[nvaccess.org](https://www.nvaccess.org/)）。
- **Linux**: Orca + AT-SPI 桥接（gnome-shell、KDE、XFCE 都可使用）。

<a id="smoke-test-10-minutes"></a>

### 冒烟测试（10 分钟）

1. 启动 `video-uniq-gui`。屏幕阅读器应朗读
   **"video-uniquifier 窗口，主导航列表，运行"**。
2. 按 `Ctrl+1` 到 `Ctrl+0`。每一步都应朗读新屏幕的标题（例如 *"运行屏幕"*，*"设置屏幕"*）。
3. 从运行开始，重复按 `Tab`。每个获取焦点的控件都应朗读其 **角色** 和 **可访问名称**（例如
   *"输入文件，编辑"*，*"浏览，按钮"*）。
4. 使用 `Space` 激活“浏览”按钮。原生文件选择器应该会打开——其可访问性来自操作系统，而不是我们提供的。
5. 切换到设置 (`Ctrl+0`)，切换到主题组合框，更改主题。阅读器应宣布新的主题名称；焦点不应转移到键盘无法关闭的对话框。

如果任何步骤没有声音或宣布 *"未标记按钮"*，请提交
`a11y` 问题，包括屏幕、屏幕阅读器名称和版本，以及失败的快捷键。

<a id="known-limitations"></a>

## 已知限制

- **Web UI 图表**：Plotly 包含自己的 ARIA 设置；我们应用轴标签，但尚未为仅视觉可见的数据点提供表格文本替代选项。（作为 v1.1 工作跟踪。）
- **CLI 进度条**：tqdm 风格的刻度更新比大多数屏幕阅读器的轮询间隔更快。传入 `--no-progress` 可退回到单个运行结束总结行，该行完全可读。
- **Qt 6.7 中的 Mac VoiceOver**：一个已知的上游漏洞 ([QTBUG-118473](https://bugreports.qt.io/browse/QTBUG-118473)) 会偶尔吞掉 `QPushButton` 上的角色公告。名称仍然能正确读取；一旦 PyQt6 发布对应的 wheels，我们将升级到 Qt 6.8。

<a id="reporting-an-a11y-issue"></a>

## 报告可访问性问题

带有 **`a11y`** 标签的 GitHub 问题会进入与安全报告相同的分检队列，预计 5 个工作日内确认。请包括：

- 操作系统 + 版本、屏幕阅读器 + 版本、应用版本 (`video-uniq-gui --version`) 以及已安装的 PyQt6/Qt 版本。
- 失败的确切屏幕 + 组合键。
- 无论故障发生在*公告*（未发声、文本错误、角色错误）还是*交互*（控制无法访问、焦点丢失、键盘陷阱）。

我们将任何AA回归视为v1.0.x补丁版本阻塞问题；AAA改进则会在下一个小版本中发布。
