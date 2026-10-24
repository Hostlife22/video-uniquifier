<a id="gui-manual-sweep"></a>

# 界面巡检

PyQt6 GUI有10个屏幕和14个背景工作进程。离屏视觉回归套件（`tests/visual/test_gui_screenshots.py`，
`QT_QPA_PLATFORM=offscreen`）可以捕捉控件形状的回归，但无法捕捉只在真实显示器上才出现的组合器 / 字体 / 高DPI / 拖放 / 对话框缺陷。本文档涵盖填补该漏洞的**仅开发者**手动扫描。

没有 CI 钩子——这些检查需要登录的 macOS（或带有真实 X / Wayland 会话的 Linux）。在发布标签之前、修改任何 `gui/screens/*` 或 `gui/workers/*` 后以及 PyQt6 升级后，本地运行它。

<a id="setup"></a>

## 设置

```bash
make dev                                                # installs PyQt6
# Real-window run, native platform:
.venv/bin/python -m video_uniquifier.gui.app_pyqt          # interactive
# OR drive the harness (fast, automated, captures PNG + Qt log):
.venv/bin/python tools/gui_sweep.py                     # writes out/gui_sweep/<ts>/
.venv/bin/python tools/gui_sweep.py --smoke-worker      # + tiny RunWorker pass
```

`tools/gui_sweep.py` 拒绝 `QT_QPA_PLATFORM=offscreen`——这由视觉回归套件处理。在 macOS 上，脚本使用
`cocoa` 插件；在 Linux 上，它继承 `QT_QPA_PLATFORM`（`xcb` 或
`wayland`）。测试框架写入：

|文件|目的|
|---|---|
| `out/gui_sweep/<ts>/<screen>.png` |每屏 1280×800 PNG|
| `out/gui_sweep/<ts>/qt.log` |捕获的 Qt 消息（警告、严重、致命错误）|
| `out/gui_sweep/<ts>/report.md` |带有图片链接的分类清单|

每次运行后阅读 `report.md`——关于缺失翻译文件或 HiDPI 不匹配的 Qt 警告通常会先在这里出现，然后才会影响用户。

<a id="per-screen-checklist"></a>

## 每屏清单

对于每个屏幕：打开 `MainWindow`，点击侧边栏条目，然后逐项检查“验证”。**失败** = 任何导致崩溃、卡死、无响应、泄漏工作进程线程或显示明显错误内容的情况。

<a id="1-run"></a>

### 1. 运行

- **交互**：将文件拖到输入字段；选择一个配置文件；点击“探测”；点击“预检”；使用默认编码器点击“运行”。
- **验证**：进度条前进；状态栏按段更新；取消按钮在运行中有效；完成后打开 QA 报告。
- **注意**：取消后孤立的 ffmpeg 子进程（点击后 `pgrep -fl ffmpeg`）。

<a id="2-batch"></a>

### 2. 批处理

- **交互**：加载一个测试文件目录；选择一个配置文件；设置工作进程=2；点击“运行批处理”。
- **验证**：每个文件行独立更新；暂停功能有效；恢复时从上次完成的文件继续。
- **注意**：与工作进程的行状态不同步（例如，行显示“完成”，但工作进程仍在运行）。

<a id="3-calibrate"></a>

### 3. 校准

- **操作**：选择参考片段；选择起始配置文件；点击“校准”；查看迭代日志。
- **验证**：每次迭代都会生成指纹差异；建议的配置文件差异渲染；点击“应用”写入新的 YAML。
- **注意**：校准循环在迭代上限（当前为 6）内未收敛 — 已知可接受，但记录性能备注。

<a id="4-qa-viewer"></a>

### 4. QA 查看器

- **操作**：从 `out/runs/` 打开现有 `.qa.json`；在视频 / 音频 / 指纹标签之间切换。
- **验证**：图表渲染（matplotlib 后端）；表格排序正常；每段缩略图加载。
- **注意**：`audio_fp_similarity == 0.0` 是预期的（见
  `docs/en/qa_report.md` 发现 #4）— 不要标记为错误。

<a id="5-profile-editor"></a>

### 5. 配置文件编辑器

- **交互**：打开 `cid_aware.yaml`；切换一个转换；编辑数值参数；另存为新文件。
- **验证**：不良输入会触发 pydantic 验证；保存前显示与原始文件的差异；新文件可被 `video-uniq run` 读取。
- **注意**：原始文件被静默覆盖 — 应始终弹出另存为对话框。

<a id="6-history"></a>

### 6. 历史记录

- **交互**：滚动运行日志；双击某行以打开其 QA 报告。
- **验证**：行显示最新的在前；“打开输出”会在 Finder/文件中显示生成的 mp4。
- **注意**：行无限积累 — 已知：v0.5 中不自动修剪；如果列表超出 10 000 行，请提交单独的工单。

<a id="7-corpus"></a>

### 7. 语料库

- **交互**：生成合成语料库（调用 `_corpus_gen.py`）；确认 `tests/fixtures/.gen/` 已填充。
- **验证**：每个夹具的进度；取消操作有效；重新运行幂等（跳过已有文件，除非 `--force`）。
- **注意**：当多个 GUI 同时运行语料生成时，可能发生跨进程竞争——这是已知可接受的情况，文件锁只是尽力而为。

<a id="8-queue"></a>

### 8. 队列

- **交互**：将 3 个作业入队；暂停队列；重新排序行；恢复队列。
- **验证**：应用重启后队列状态应保持不变；
  每个作业的 `state.json` 个文件均有效。
- **注意**：重启后队列工作进程未能启动（已知边缘情况，如果 `state.json` 在崩溃时处于写入中）。

<a id="9-validation"></a>

### 9. 校验

- **交互**：选择一个“真实 CID”日志（CSV 或 jsonl）；点击“相关联”；查看每段的表格。
- **验证**：相关联运行完成；结果突出显示超出 CID 阈值的行；导出到 CSV 成功。
- **注意**：在重复运行时可能出现 matplotlib 小部件泄漏（在某些 macOS 版本已知；使用强制重载屏幕作为解决方法）。

<a id="10-settings"></a>

### 10. 设置

- **交互操作**：更改主题；切换“以模态方式显示预检”；设置自定义 ffmpeg 路径；点击保存。
- **验证**：通过 `AppState` 到 `~/.video_uniquifier/` 检查更改是否持续存在；无效的 ffmpeg 路径显示行内错误。
- **注意**：主题切换需要重启——目前确实需要；已在工具提示中说明。

<a id="triage-table"></a>

## 分诊表

在每次扫描中填写此表（或从生成的 `report.md` 中复制粘贴）。保持最近 5 条记录在行内；将旧的运行归档至
`out/gui_sweep/<ts>/report.md`.

|日期|操作员|Qt 平台|通过 / 总计|Qt 警告|烟雾工作进程|备注|
|---|---|---|---|---|---|---|
| _YYYY-MM-DD_ |_名称_|cocoa / xcb / wayland| _X_ / 10 | _N_ |通过 / 失败 / 跳过|_运行目录链接_|

<a id="related"></a>

## 相关

- `tests/visual/test_gui_screenshots.py` — CI 基线（离屏）
- `tools/gui_sweep.py` — 这个挂架
- `docs/en/gui.md` — 屏幕参考和架构
- `docs/bug-triage-2026-05-31.md` — 由本文件 + 挂架关闭
