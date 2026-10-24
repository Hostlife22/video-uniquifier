"""Simplified Chinese desktop catalogue; keys remain the English source text."""

STRINGS: dict[str, str] = {
    # Workflow guidance and navigation descriptions.
    "Import video": "导入视频",
    "Adjust and preview": "调整与预览",
    "Export result": "导出结果",
    "Current step": "当前步骤",
    "Complete": "已完成",
    "Next": "接下来",
    "Add a video to begin": "从一个视频开始",
    "Drop a video here, or choose a file. Your original is kept.":
        "将视频拖入此处，或选择文件。原始视频会保留。",
    "Choose video…": "选择视频…",
    "Preview before exporting": "导出前，先看看效果",
    "Natural look": "自然观感",
    "Visible changes": "明显变化",
    "Bold changes": "大幅调整",
    "Recommended first: subtle picture and sound adjustments.":
        "初次使用推荐。轻微调整画面与声音。",
    "More noticeable changes. Compare a sample before exporting.":
        "画面变化更明显。建议先对比样片，再导出完整视频。",
    "Largest visual changes. Check detail and sound carefully.":
        "调整幅度最大。请仔细检查画面细节与声音效果。",
    "Process only a short sample; the full video is exported separately.":
        "仅处理短片段；确认效果后，再导出完整视频。",
    "Choose a video and wait for its details before previewing a sample.":
        "请先选择视频，读取信息后即可处理样片。",
    "Preview and export": "单个视频 · 样片预览",
    "Process a folder": "整批视频 · 统一处理",
    "Find suitable settings": "寻找合适的处理参数",
    "Compare output quality": "检查画面与声音质量",
    "Manage processing recipes": "编辑与保存处理方案",
    "Revisit previous results": "查看结果与历史报告",
    "Compare with your videos": "管理用于比较的素材",
    "Manage background jobs": "安排后台处理任务",
    "Record observations": "记录不同版本的表现",
    "Appearance and preferences": "外观与个人偏好",
    "Local telemetry": "本地使用统计",
    "Help improve video-uniquifier with local-only telemetry?":
        "是否通过本地使用统计帮助改进 video-uniquifier？",
    (
        "When enabled, each completed or failed encode appends one "
        "anonymous summary event (profile name, encoder, wall-clock, "
        "segment count, OS) to a JSONL file in your per-user data "
        "directory.\n\n"
        "Telemetry is OFF by default. Nothing is sent over the "
        "network in this release — you can review or export events "
        "from Settings → Local telemetry, or via "
        "`video-uniq telemetry status`.\n\n"
        "Your choice is remembered; change it any time in Settings."
    ): (
        "启用后，每次编码完成或失败时，都会在用户数据目录的 JSONL 文件中记录一条匿名摘要"
        "（配置名称、编码器、处理耗时、分段数量和操作系统）。\n\n"
        "此功能默认关闭。当前版本不会通过网络发送数据。您可以在“设置 → 本地使用统计”"
        "中查看或导出事件，也可以运行 `video-uniq telemetry status`。\n\n"
        "您的选择会被保存，之后可随时在设置中更改。"
    ),
    "&Enable": "启用(&E)",
    "&Keep disabled": "保持关闭(&K)",
    "not connected": "尚未连接",
    "seed_strategy:": "随机种子策略：",
    "now: —": "当前值：—",
    "avg: —": "平均值：—",
    "min: —": "最低值：—",
    "samples: 0": "采样数：0",
    "{count} entries": "共 {count} 条记录",
    "Refresh failed: {message}": "刷新失败：{message}",
    # Navigation and page introductions.
    "WORKSPACE": "工作区",
    "TUNING & QUALITY": "调优与质量",
    "LIBRARY": "资料库",
    "TOOLS": "工具",
    "Process video": "视频处理",
    "Batch processing": "批量处理",
    "Auto-tune": "自动调优",
    "Quality reports": "质量报告",
    "Profiles": "处理配置",
    "History": "历史记录",
    "Reference library": "参考视频库",
    "Processing queue": "处理队列",
    "Experiments": "实验",
    "Ready": "就绪",
    "Local processing": "本地处理",
    "Main navigation": "主导航",
    "01  Source & destination": "01  输入与输出",
    "02  Processing": "02  处理设置",
    "03  Progress & result": "03  进度与结果",
    "Choose a video, adjust processing and save the result.": "选择视频、调整处理参数并保存结果。",
    (
        "Process a folder of videos with one profile and track each result."
    ): (
        "使用同一配置处理文件夹中的视频，并跟踪每个文件的结果。"
    ),
    (
        "Find profile settings that balance visual change and measured quality."
    ): (
        "寻找兼顾画面变化与质量指标的处理参数。"
    ),
    (
        "Compare source and output, or open a report from a previous run."
    ): (
        "比较原始视频与处理结果，或打开之前的质量报告。"
    ),
    (
        "Adjust processing recipes and inspect their settings before saving."
    ): (
        "调整处理配置，检查参数后保存。"
    ),
    (
        "Find completed jobs, open their videos and revisit quality reports."
    ): (
        "查找已完成的任务，打开视频或查看质量报告。"
    ),
    (
        "Manage your own reference videos for local similarity comparisons."
    ): (
        "管理自己的参考视频，用于本地相似度比较。"
    ),
    "Organize pending videos and control background workers.": "管理待处理视频与后台工作进程。",
    (
        "Generate variants of owned or licensed videos and record observations."
    ): (
        "为自有或已获授权的视频生成不同版本，并记录观察结果。"
    ),
    (
        "Personalize appearance, defaults and optional integrations."
    ): (
        "自定义外观、默认设置和可选集成。"
    ),
    # Common controls and tables.
    "&Browse…": "浏览(&B)…",
    "Bro&wse…": "浏览(&W)…",
    "&Add file…": "添加文件(&A)…",
    "&Add files…": "添加文件(&A)…",
    "&Remove selected": "移除所选项(&R)",
    "&Clear all": "清空全部(&C)",
    "C&lear": "清空(&L)",
    "Re&fresh": "刷新(&F)",
    "Cance&l": "取消(&L)",
    "&Copy": "复制(&C)",
    "Choose…": "选择…",
    "Save as…": "另存为…",
    "Save &as…": "另存为(&A)…",
    "Not selected": "未选择",
    "Enabled": "启用",
    "Disabled": "禁用",
    "Status": "状态",
    "File": "文件",
    "Path": "路径",
    "Date": "日期",
    "Actions": "操作",
    "Notes": "备注",
    "Source": "原始视频",
    "Output": "输出",
    "Added": "添加时间",
    "Samples": "采样片段",
    "Audio FP": "音频指纹",
    "Pending": "等待中",
    "Running": "处理中",
    "Completed": "已完成",
    "Failed": "失败",
    "Cancelled": "已取消",
    "All statuses": "全部状态",
    "Filter by status": "按状态筛选",
    "Search files": "搜索文件",
    "Search file, path or notes…": "搜索文件、路径或备注…",
    "Select visible rows": "选择当前显示的行",
    "Select all visible rows": "选择当前显示的所有行",
    "Select or clear all visible rows in this table.": "选择或取消选择表格中当前显示的所有行。",
    "Copy paths": "复制路径",
    "Copy selected paths": "复制所选路径",
    "Open file": "打开文件",
    "Open containing folder": "打开所在文件夹",
    "File unavailable": "文件不可用",
    "{count} files matched": "匹配到 {count} 个文件",
    "{visible} shown · {selected} selected": "显示 {visible} 项 · 已选择 {selected} 项",
    (
        "No matching jobs. Process a video or change the search to find previous results."
    ): (
        "没有匹配的任务。请处理视频，或修改搜索条件查找以前的结果。"
    ),
    # Settings.
    "Dark studio": "深色工作室",
    "Light": "浅色",
    "System (dark)": "跟随系统（深色）",
    "Animations": "动画",
    "Reduce interface motion": "减少界面动画",
    "Default profile:": "默认配置：",
    "Notifications": "通知",
    "Language switched to {loc}.": "界面语言已切换为 {loc}。",
    "Expand cache and diagnostic tools.": "展开缓存和诊断工具。",
    "Expand optional notification settings.": "展开可选通知设置。",
    "Expand optional local event recording.": "展开可选本地事件记录设置。",
    "Open &log dir": "打开日志文件夹(&L)",
    "Open &config dir": "打开配置文件夹(&C)",
    "Recents cap:": "最近文件数量上限：",
    "History cap:": "历史记录数量上限：",
    "Webhook URL:": "Webhook 地址：",
    "Send notifications:": "发送通知：",
    "on completion": "任务完成时",
    "on failure": "任务失败时",
    "SMTP host:": "SMTP 服务器：",
    "SMTP port:": "SMTP 端口：",
    "SMTP username:": "SMTP 用户名：",
    "Encryption:": "加密方式：",
    (
        "STARTTLS (uncheck for implicit TLS / port 465)"
    ): (
        "STARTTLS（使用隐式 TLS / 465 端口时取消勾选）"
    ),
    "smtp.example.com (leave blank to skip SMTP)": "smtp.example.com（留空则不使用 SMTP）",
    "Sender (From):": "发件人地址：",
    "Recipients (one per line):": "收件人（每行一个）：",
    "&Apply notifications": "应用通知设置(&A)",
    "Send &test notification": "发送测试通知(&T)",
    "Notifications saved.": "通知设置已保存。",
    "Notifications disabled (no webhook or SMTP).": "通知已禁用（未配置 Webhook 或 SMTP）。",
    "Sending test…": "正在发送测试通知…",
    "Test failed: {error}": "测试失败：{error}",
    "Preferences saved.": "设置已保存。",
    "Record one anonymous summary event per run": "每次处理记录一条匿名摘要",
    "Strip $HOME from any path-like field": "从路径字段中移除用户主目录（$HOME）",
    "Enabled:": "启用：",
    "Redact paths:": "隐藏路径：",
    "Events folder": "事件文件夹",
    "&Apply telemetry": "应用统计设置(&A)",
    "Open &events folder": "打开事件文件夹(&E)",
    "&Purge events": "清除事件(&P)",
    "Recording is off": "记录已关闭",
    "Recording is on": "记录已开启",
    "{recording} · Saved events: {count}": "{recording} · 已保存事件：{count}",
    (
        "Events stay on this device and are never sent over the network."
    ): (
        "事件仅保存在本设备上，不会通过网络发送。"
    ),
    "Could not load saved config: {error}": "无法加载已保存的配置：{error}",
    "Status unavailable": "无法获取状态",
    # Main processing workspace.
    "Source video": "原始视频",
    "Input video": "输入视频",
    "Output video": "输出视频",
    "Video files": "视频文件",
    "Drop a video here": "将视频拖到此处",
    "No video selected": "尚未选择视频",
    "Choose a video to get started.": "选择视频以开始处理。",
    "Choose a processing profile.": "请选择处理配置。",
    "Choose where to save the result.": "请选择结果保存位置。",
    (
        "Choose a different output file to preserve the source."
    ): (
        "请选择其他输出文件，以保留原始视频。"
    ),
    "Resolve the issues shown above before processing.": "请先解决上方列出的问题，再开始处理。",
    "Checking video…": "正在检查视频…",
    "Ready to process": "可以开始处理",
    "Processing…": "正在处理…",
    "Auto-tuning…": "正在自动调优…",
    "Choose a video to preview it here.": "选择视频后可在此预览。",
    "Choose a source video to see its details.": "选择原始视频以查看详细信息。",
    "Choose an output file": "选择输出文件",
    "Save result to": "结果保存至",
    "Processed video · MP4": "处理后的视频 · MP4",
    "Processing profile": "处理配置",
    "Parallel workers": "并行工作进程",
    "File pattern": "文件匹配规则",
    "When a file fails": "文件处理失败时",
    "&Continue on error": "出错后继续(&C)",
    "Gentle": "轻柔",
    "Medium": "适中",
    "Strong": "强烈",
    "Subtle": "轻微",
    "Moderate": "中等",
    "Intense": "强烈",
    (
        "Soft · Subtle changes. A good starting point for reviewing quality."
    ): (
        "轻柔 · 细微调整，适合初次检查画面质量。"
    ),
    (
        "Medium · More visible changes. Compare a short clip before a full run."
    ): (
        "适中 · 变化更明显，请在完整处理前对比短片段。"
    ),
    (
        "Strong · Pronounced changes that may reduce picture quality."
    ): (
        "强烈 · 变化明显，可能降低画面质量。"
    ),
    (
        "Custom profile · Review its settings in the profile editor."
    ): (
        "自定义配置 · 请在配置编辑器中检查参数。"
    ),
    "Balanced": "均衡",
    "Pronounced": "明显",
    "Small crop, subtle color correction and light noise.": "轻微裁剪、细微调色及少量噪点。",
    "More visible crop, color correction and noise.": "更明显的裁剪、调色及噪点。",
    (
        "Stronger changes plus a slight rotation. Review picture quality."
    ): (
        "更强烈的调整，并加入轻微旋转。请检查画面质量。"
    ),
    "Audio: pitch adjustment and loudness normalization.": "音频：音高调整和响度标准化。",
    "Audio: pitch, equalizer and loudness normalization.": "音频：音高、均衡器和响度标准化。",
    (
        "Small crop, subtle color correction and light noise.\nAudio: pitch adjustment an"
        "d loudness normalization."
    ): (
        "轻微裁剪、细微调色及少量噪点。\n音频：音高调整和响度标准化。"
    ),
    "What this profile changes": "此配置的调整内容",
    "Advanced and custom profiles": "高级与自定义配置",
    "Advanced settings": "高级设置",
    (
        "Expand encoder selection, profile editing and auto-tuning."
    ): (
        "展开编码器选择、配置编辑与自动调优设置。"
    ),
    "Expand picture and audio processing details.": "展开画面与音频处理详情。",
    "Expand detailed processing messages.": "展开详细处理消息。",
    "Edit profile…": "编辑配置…",
    "Automatic (recommended)": "自动（推荐）",
    (
        "Saved encoder; availability is checked before processing."
    ): (
        "已保存编码器；处理前将检查其可用性。"
    ),
    "Try a short sample": "先试处理一个短片段",
    "Choose sample interval": "选择试处理片段范围",
    "Start time": "开始时间",
    "Duration": "时长",
    "{seconds} s": "{seconds} 秒",
    "Process sample": "处理样片",
    "Test a short fragment": "试处理短片段",
    (
        "Compare a processed sample before starting the full video."
    ): (
        "开始处理完整视频前，先对比处理后的样片。"
    ),
    "Start (seconds)": "开始时间（秒）",
    (
        "Uses the selected profile. The full output destination stays unchanged."
    ): (
        "使用所选配置，不改变完整视频的输出位置。"
    ),
    (
        "HDR samples are unavailable; use full processing to preserve HDR metadata."
    ): (
        "HDR 视频暂不支持样片处理；请使用完整处理以保留 HDR 元数据。"
    ),
    "Check picture and sound before a full run.": "完整处理前，先检查样片的画面与声音。",
    "Progress & result": "进度与结果",
    "Your result will appear here after processing.": "处理完成后将在此显示结果。",
    "Open processed video": "打开处理后的视频",
    "Open quality report": "打开质量报告",
    "Compare before / after": "对比处理前后",
    "Save sample…": "保存样片…",
    "Save sample": "保存样片",
    "Check video": "检查视频",
    "Start processing": "开始处理",
    "&Resume": "继续(&R)",
    "Reset workspace layout": "重置工作区布局",
    "Activity log": "活动日志",
    "Processing messages will appear here.": "处理消息将显示在此处。",
    "Resize panels": "调整面板大小",
    "Drag to resize; use arrow keys when focused.": "拖动以调整大小；获得焦点后也可使用方向键。",
    "Audio": "音频",
    "Sound": "声音",
    "Video processing progress": "视频处理进度",
    "Audio processing progress": "音频处理进度",
    "Source video thumbnail": "原始视频缩略图",
    "Video preview": "视频预览",
    "Reading video details…": "正在读取视频信息…",
    "Could not read this video. See the activity log.": "无法读取此视频，请查看活动日志。",
    "Saving sample…": "正在保存样片…",
    "Sample saved: {file}": "样片已保存：{file}",
    "Sample ready: {file}": "样片已就绪：{file}",
    "Completed: {file}": "已完成：{file}",
    "Could not save sample. Try another destination.": "无法保存样片，请尝试其他位置。",
    "Saving cancelled; the temporary sample is still available.": "已取消保存；临时样片仍可使用。",
    "Could not prepare the selected sample.": "无法准备所选样片。",
    "Failed.": "处理失败。",
    "Cancelled.": "已取消。",
    "Cancelling…": "正在取消…",
    "Paused — encode suspended.": "已暂停编码。",
    "Resumed.": "已继续处理。",
    "Auto-tuning profile…": "正在自动调优配置…",
    "Auto-tune failed.": "自动调优失败。",
    "Elapsed: {time}": "已用时间：{time}",
    "Remaining in this stage: ≈ {time}": "当前阶段剩余时间：约 {time}",
    "Estimating stage time…": "正在估算当前阶段用时…",
    "Preparation": "准备中",
    "Video": "视频",
    "Saving": "保存中",
    "Quality check": "质量检查",
    "Processing": "处理中",
    "Video processing": "视频处理中",
    "Audio processing": "音频处理中",
    "Validation": "验证中",
    "Active tasks": "活动任务",
    "Task progress": "任务进度",
    "Return to task": "返回任务",
    # Player, samples and comparison.
    "Play": "播放",
    "Pause": "暂停",
    "Paused": "已暂停",
    "Original": "原始视频",
    "Processed": "处理结果",
    "Preview original": "预览原始视频",
    "Preview track": "预览轨道",
    "Preview timeline": "预览时间轴",
    "Sample timeline": "样片时间轴",
    "Video thumbnails": "视频缩略图",
    "Set sample start": "设置样片起点",
    "Use this time for sample": "将当前时间用作样片起点",
    (
        "Click or drag to choose the sample start; arrow keys move by one second."
    ): (
        "点击或拖动选择样片起点；方向键每次移动一秒。"
    ),
    "Loading video…": "正在加载视频…",
    "Preview unavailable: {error}": "无法预览：{error}",
    "Could not play {video}: {error}": "无法播放 {video}：{error}",
    "Before / after": "处理前后对比",
    "Before / after divider": "处理前后分隔线",
    "Side by side": "并排对比",
    "Original only": "仅显示原始视频",
    "Result only": "仅显示处理结果",
    "Fit to window": "适应窗口",
    "Listen to original": "播放原始声音",
    "Listen to result": "播放处理后的声音",
    "Previous frame": "上一帧",
    "Next frame": "下一帧",
    "Sync by time": "按时间同步",
    "Sync by duration": "按时长同步",
    "Shared timeline": "同步时间轴",
    (
        "Shared time; choose duration sync when the clip tempo changes."
    ): (
        "使用统一时间；片段速度改变时请选择按时长同步。"
    ),
    "Draggable divider": "可拖动分隔线",
    (
        "Drag the divider; drag the image to pan when zoomed. Arrow keys move the divider"
        "."
    ): (
        "拖动分隔线；放大后可拖动画面平移。方向键可移动分隔线。"
    ),
    "Use native video panels for HDR comparison.": "请使用原生视频面板对比 HDR 视频。",
    "Finding the adjacent frame…": "正在查找相邻帧…",
    "Frame ready": "画面已就绪",
    "Frame step unavailable: {error}": "无法逐帧浏览：{error}",
    "Image comparison unavailable; use side by side.": "无法使用图像对比，请切换为并排对比。",
    # Secondary workflows.
    "Input directory:": "输入文件夹：",
    "Output directory:": "输出文件夹：",
    "Output dir:": "输出文件夹：",
    "Out dir:": "输出文件夹：",
    "Profile:": "处理配置：",
    "Base profile:": "基础配置：",
    "Corpus root:": "参考库目录：",
    "Queue root:": "队列目录：",
    "CSV path:": "CSV 文件路径：",
    "QA report (.qa.html):": "质量报告（.qa.html）：",
    "&Run batch": "开始批量处理(&R)",
    "Files: %v / %m (%p%)": "文件：%v / %m（%p%）",
    "&Calibrate": "开始调优(&C)",
    "Minimum quality (0–100)": "最低质量（0–100）",
    "Maximum similarity": "最高相似度",
    "Search iterations": "搜索迭代次数",
    "Sample duration (seconds)": "采样时长（秒）",
    "Similarity metric": "相似度指标",
    "&Save tuned profile as…": "调优配置另存为(&S)…",
    "Measured metrics": "实测指标",
    "Expand quality and similarity values.": "展开质量与相似度指标。",
    "Filter:": "筛选：",
    "Open output": "打开输出文件",
    "Theme:": "主题：",
    "Language:": "语言：",
    "Open existing": "打开已有报告",
    "Compute new": "生成新报告",
    "&Compute QA": "生成质量报告(&C)",
    "Open in &browser": "在浏览器中打开(&B)",
    (
        "Open a quality report above, then use Open in browser to view it."
    ): (
        "在上方打开质量报告，再点击“在浏览器中打开”查看。"
    ),
    "Transform": "变换",
    "Transform settings": "变换设置",
    "Params (JSON)": "参数（JSON）",
    "YAML preview": "YAML 预览",
    "&Reload list": "重新加载列表(&R)",
    "&Browse community…": "浏览社区配置(&B)…",
    (
        "Add your own reference videos to compare similarity with future outputs."
    ): (
        "添加自己的参考视频，用于与之后的输出比较相似度。"
    ),
    "&Init queue here": "在此初始化队列(&I)",
    "&Reset stale (>5 min)": "重置超时任务（超过 5 分钟）(&R)",
    "When the queue is empty": "队列为空时",
    "E&xit when queue empty": "队列为空时退出(&X)",
    "Start worker": "启动工作进程",
    "Sto&p": "停止(&P)",
    (
        "Add files, then select a profile, encoder and output folder in the worker tab."
    ): (
        "添加文件后，在工作进程选项卡中选择配置、编码器和输出文件夹。"
    ),
    (
        "Buckets live on the shared filesystem — refresh updates every 2s automatically o"
        "nce a queue root is set."
    ): (
        "队列分区位于共享文件系统；设置队列目录后，每 2 秒自动刷新一次。"
    ),
    "Generate variants": "生成不同版本",
    "Process selected": "处理所选项",
    "Analyze observations": "分析观察记录",
    "Variant count": "版本数量",
    "<b>Step 1 of 3 — Generate variants</b>": "<b>第 1 步，共 3 步 — 生成不同版本</b>",
    "<b>Divergence</b>": "<b>差异程度</b>",
    "&Next →": "下一步(&N) →",
    "← &Back": "← 上一步(&B)",
    "&Save to validation_log.csv": "保存到 validation_log.csv(&S)",
    (
        "Choose an owned or licensed source, a profile and an output folder; generate a s"
        "mall number of variants."
    ): (
        "选择自有或已获授权的视频、处理配置和输出文件夹，生成少量不同版本。"
    ),
    (
        "Use owned/licensed material and record Studio observations with timestamps. Clai"
        "m experiments require a reference owner and confirmed baseline match; recheck ob"
        "servations over time."
    ): (
        "使用自有或已获授权的素材，并记录带时间的 Studio 观察结果。版权声明实验需要参考内"
        "容所有者及已确认的基线匹配；请定期复查观察记录。"
    ),
    (
        "Use this section after sample review; local similarity alone cannot verify platf"
        "orm behavior."
    ): (
        "检查样片后再使用本功能；仅凭本地相似度无法判断平台行为。"
    ),
    # Contextual help.
    "How to use": "使用说明",
    "Quick start": "快速入门",
    "Key terms": "关键术语",
    "Hide guide": "收起说明",
    "Show or hide this page's guide (F1)": "显示或隐藏本页说明（F1）",
    "Guide expanded. Click to hide.": "说明已展开，点击收起。",
    "Guide collapsed. Click to show.": "说明已收起，点击展开。",
    (
        "Choose a source video and a separate destination for the result."
    ): (
        "选择原始视频，并为结果设置单独的保存位置。"
    ),
    (
        "Start with Gentle and click Process sample. Expand Choose sample interval if you"
        " want to review a different moment."
    ): (
        "先选择“轻柔”并点击“处理样片”。如需检查其他时间段，请展开“选择试处理片段范围”。"
    ),
    (
        "Compare before / after, listen to the sound, then start full processing."
    ): (
        "对比处理前后的画面并试听声音，再开始完整处理。"
    ),
    (
        "Profile — a saved recipe for picture and sound changes."
    ): (
        "处理配置：一组已保存的画面与声音调整参数。"
    ),
    (
        "Encoder — how the result is compressed. Start with Automatic (recommended); para"
        "llel workers can increase speed and memory use."
    ): (
        "编码器：决定结果的压缩方式。建议先选择“自动（推荐）”；增加并行工作进程可提高速度"
        "，但也会增加内存用量。"
    ),
    (
        "If the picture looks soft, try a gentler profile on the same sample first."
    ): (
        "如果画面变模糊，请先在同一样片上尝试更轻柔的配置。"
    ),
    (
        "Choose the folder containing your videos and a separate output folder."
    ): (
        "选择存放视频的文件夹，并设置单独的输出文件夹。"
    ),
    (
        "Select a profile and encoder that you have already checked on a sample."
    ): (
        "选择已通过样片检查的配置和编码器。"
    ),
    (
        "Run the batch and review the status and notes for each file."
    ): (
        "启动批量处理，并检查每个文件的状态与备注。"
    ),
    "One profile is applied to every video in the batch.": "批量任务中的所有视频使用同一处理配置。",
    (
        "Continue on error — process the remaining files if one fails."
    ): (
        "出错后继续：某个文件失败时，继续处理其余文件。"
    ),
    (
        "Test one representative video in Process video before processing the whole folde"
        "r."
    ): (
        "处理整个文件夹前，请先在“视频处理”页测试一个有代表性的视频。"
    ),
    "Choose a source video and a base profile to adjust.": "选择原始视频和待调整的基础配置。",
    (
        "Keep the initial limits for your first search and click Calibrate."
    ): (
        "首次搜索请保留默认限制，然后点击“开始调优”。"
    ),
    (
        "Review the result, save a tuned profile and test it in Process video."
    ): (
        "检查结果，保存调优配置，并在“视频处理”页测试。"
    ),
    (
        "Minimum quality — the measured picture-quality floor; higher is stricter."
    ): (
        "最低质量：实测画面质量的下限；数值越高，要求越严格。"
    ),
    (
        "Maximum similarity — a local fingerprint limit. Iterations control the number of"
        " trials; longer samples take more time."
    ): (
        "最高相似度：本地指纹的相似度上限。迭代次数决定尝试次数；采样片段越长，耗时越多。"
    ),
    (
        "Local scores do not predict platform decisions. Always watch and listen to a sam"
        "ple."
    ): (
        "本地分数无法预测平台判断。请务必观看和试听样片。"
    ),
    (
        "Open an existing .qa.html report, or switch to Compute new."
    ): (
        "打开已有的 .qa.html 报告，或切换到“生成新报告”。"
    ),
    (
        "For a new report, select the matching source and processed video, then click Com"
        "pute QA."
    ): (
        "生成报告时，选择相互对应的原始视频和处理后视频，然后点击“生成质量报告”。"
    ),
    (
        "Read the report here or open it in your browser; check the videos as well."
    ): (
        "在此阅读报告或用浏览器打开，同时也请检查实际视频。"
    ),
    (
        "VMAF / SSIM — picture-quality estimates; higher usually means closer to the sour"
        "ce."
    ): (
        "VMAF / SSIM：画面质量估算指标；数值越高，通常表示越接近原始视频。"
    ),
    (
        "Similarity — how close local fingerprints are, not a quality rating."
    ): (
        "相似度：反映本地指纹的接近程度，不代表质量评分。"
    ),
    (
        "Numbers can miss blur, sound defects and sync problems; compare the actual clips"
        "."
    ): (
        "数值可能无法反映模糊、声音缺陷和不同步问题，请对比实际片段。"
    ),
    (
        "Select an existing profile to see its transforms and settings."
    ): (
        "选择已有配置，查看其变换与参数。"
    ),
    (
        "Change one setting at a time and check the YAML preview."
    ): (
        "每次只调整一项设置，并检查 YAML 预览。"
    ),
    (
        "Use Save as to create your own copy, then test it on a short sample."
    ): (
        "使用“另存为”创建自己的副本，再用短样片测试。"
    ),
    "Enabled — whether this transform is included in processing.": "启用：是否在处理时应用此变换。",
    (
        "Params (JSON) — transform settings. YAML preview — the complete profile recipe."
    ): (
        "参数（JSON）：变换设置。YAML 预览：完整的处理配置。"
    ),
    (
        "For your first video, use a shipped profile; you can return to editing later."
    ): (
        "首次处理视频建议使用内置配置，之后再进行编辑。"
    ),
    "Use the filter to find a previous processing job.": "使用筛选功能查找以前的处理任务。",
    (
        "Open its output video or quality report from the Actions column."
    ): (
        "通过“操作”列打开输出视频或质量报告。"
    ),
    (
        "Check the recorded profile, encoder and status before comparing results."
    ): (
        "比较结果前，先检查记录的配置、编码器和状态。"
    ),
    (
        "Completed means processing finished; it does not replace a quality review."
    ): (
        "“已完成”表示处理结束，仍需检查结果质量。"
    ),
    (
        "History records point to files on disk; moved or deleted files cannot be opened."
    ): (
        "历史记录关联磁盘上的文件；已移动或删除的文件将无法打开。"
    ),
    (
        "Clear all removes history records, not your source or output videos."
    ): (
        "“清空全部”仅移除历史记录，不会删除原始视频或输出视频。"
    ),
    (
        "Add a video that you own or are licensed to use as a local reference."
    ): (
        "添加自有或已获授权的视频作为本地参考。"
    ),
    (
        "Wait for its samples and fingerprints to be prepared, then refresh the list."
    ): (
        "等待采样片段和指纹生成完成，再刷新列表。"
    ),
    (
        "Keep the references relevant to the comparisons you want to make."
    ): (
        "请添加与预期比较内容相关的参考视频。"
    ),
    (
        "Samples — short pieces used to describe the reference video."
    ): (
        "采样片段：用于描述参考视频的短片段。"
    ),
    (
        "Audio FP — an audio fingerprint used for local similarity comparisons."
    ): (
        "音频指纹：用于本地相似度比较的音频特征。"
    ),
    (
        "You can process your first video without adding a reference library."
    ): (
        "无需添加参考视频库，即可处理第一个视频。"
    ),
    (
        "Choose a queue folder and initialize it if this is a new queue."
    ): (
        "选择队列文件夹；如为新队列，请先初始化。"
    ),
    (
        "Start the worker and follow each file through the queue buckets."
    ): (
        "启动工作进程，并在队列分区中查看各文件的处理进展。"
    ),
    (
        "Pending / leased / done / failed — waiting, assigned to a worker, completed or u"
        "nsuccessful."
    ): (
        "等待 / 已分配 / 完成 / 失败：分别表示等待处理、已分配给工作进程、已完成或未成功"
        "。"
    ),
    (
        "Exit when queue empty — stop after current jobs; unchecked keeps waiting for new"
        " files."
    ): (
        "队列为空时退出：当前任务结束后停止；取消勾选则持续等待新文件。"
    ),
    (
        "For a one-time folder of videos, Batch processing is the simpler starting point."
    ): (
        "一次性处理文件夹中的视频时，建议使用更简单的“批量处理”。"
    ),
    (
        "Move to the next step and record your observations with dates and notes."
    ): (
        "进入下一步，记录观察结果、日期和备注。"
    ),
    (
        "Save the CSV, then analyze the recorded observations in the final step."
    ): (
        "保存 CSV，然后在最后一步分析已记录的观察结果。"
    ),
    (
        "Variant count — how many processed versions are generated for comparison."
    ): (
        "版本数量：生成多少个处理版本用于比较。"
    ),
    (
        "CSV — the saved observations table used by the analysis step."
    ): (
        "CSV：分析步骤使用的观察记录表。"
    ),
    "Choose your language and theme in Appearance.": "在“外观”中选择语言和主题。",
    "Set a default profile and history limits if needed.": "按需设置默认处理配置和历史记录上限。",
    (
        "Click Save to keep the settings for your next session."
    ): (
        "点击“保存”，下次启动时继续使用这些设置。"
    ),
    (
        "Default profile — the starting recipe for future processing sessions."
    ): (
        "默认配置：之后处理视频时默认使用的参数。"
    ),
    (
        "Encoder cache — remembered hardware detection; reset it after changing hardware "
        "or drivers."
    ): (
        "编码器缓存：已保存的硬件检测结果；更换硬件或驱动后请重置。"
    ),
    (
        "Notifications and local telemetry are optional; leave them off for your first ru"
        "n."
    ): (
        "通知和本地统计均为可选功能；首次使用可保持关闭。"
    ),
}
