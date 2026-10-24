<a id="reference-corpus-sqlite"></a>

# 参考库

> 在 v0.8.0 R2 中重新制作。

语料库是 `video-uniquifier` 的本地索引，用于“我可能几乎重复的视频”。它支持 QA 报告的 `cid_predict` 步骤：每个输出的指纹（chromaprint 哈希 + pHash 序列）与每个语料库条目匹配，最高相似度显示为 `match_probability_corpus`。

v0.7 将索引存储为单个 `index.json` 文件。这对于
约 5k 条目是可以的；超过这个数量，每次查找都要扫描文件，并且并发写入者（同一 NAS 上的两个 `video-uniq run` 实例，或 `video-uniq batch` 与多个工作进程）会争抢重写。v0.8.0 将存储后端换成 SQLite，同时保持 v0.7 的公共 API（`Corpus.add`,
`Corpus.remove`, `Corpus.list_all`, `Corpus.search_match`）位对位兼容。

<a id="storage-layout"></a>

## 存储布局

```
<corpus-dir>/
├── index.sqlite               # SQLite (WAL mode)
├── index.sqlite-wal           # WAL journal (auto)
├── index.sqlite-shm           # shared-memory index (auto)
└── index.json.migrated.<ts>   # one-shot backup of pre-v0.8.0 store
```

`<corpus-dir>` 默认为 `~/.cache/video_uniquifier/corpus/`（可通过 `--corpus-dir` 覆盖）。SQLite 文件以 [WAL 模式](https://www.sqlite.org/wal.html) 打开，因此读取操作从不因占用锁的写入操作而阻塞；跨进程的写入通过
`BEGIN IMMEDIATE` 来串行化，因此在同一个共享文件系统上的两个 `video-uniq batch` 工作进程不会交错进行部分插入。

指纹序列（chromaprint uint32 帧，pHash uint64 帧）通过 `struct.pack(f"<{n}Q", *seq)` 以打包的 BLOB 形式存储——没有 JSON 开销，没有每帧行，并且 **不** 使用 `pickle`（表面风险小，序列化任意 Python 是危险操作）。

<a id="migration-from-indexjson"></a>

## 从 `index.json` 迁移

首次在有旧版 `index.json` 兄弟项的情况下打开 `Corpus`
**并且** SQLite 存储为空时，条目会自动迁移。JSON 文件会被重命名为 `index.json.migrated.<ts>`，并且 **永远不会删除**——重新打开陈旧的 JSON 兄弟项不会重新合并它（因此清除的内容保持清除状态）。

用于脚本控制（CI 语料快照，NAS 部署）：

```bash
video-uniq corpus migrate --dry-run            # report counts, write nothing
video-uniq corpus migrate                      # explicit migration pass
video-uniq corpus migrate --corpus-dir /mnt/x  # alternative location
```

该命令是幂等的：在成功迁移后重新运行不会执行任何操作，只会报告当前的 SQLite 计数。

<a id="cli-subcommands"></a>

## CLI 子命令

```bash
video-uniq corpus add <video> [--name NAME]    # ingest a reference video
video-uniq corpus list [--limit N]             # tabular listing
video-uniq corpus remove <id>                  # delete one entry by id
video-uniq corpus migrate [...]                # see above
```

所有命令都接受 `--corpus-dir <path>` 来覆盖默认位置。

<a id="public-api"></a>

## 公共 API

`video_uniquifier.core.qa.corpus.Corpus` 是一个对以下内容的薄外壳
`CorpusDB`。现有导入 `Corpus` 的 v0.7 代码保持工作——其中没有任何部分看到 SQLite。

对于想要直接访问数据库的新代码（批量导入，自定义查询）使用 `CorpusDB`：

```python
from video_uniquifier.core.qa.corpus_db import CorpusDB, CorpusEntry

with CorpusDB(Path("/var/video-uniq/corpus")) as db:
    db.add_entry(CorpusEntry(
        id="2026-canonical-001",
        path=Path("/media/Source A.mkv"),
        added_at=1772755200.0,
        duration_sec=3600.0,
        phash_frames=(...),
        audio_fingerprint=(...),
        sample_count=60,
        content_sha256="...full SHA-256...",
    ))
    print(len(db))
    for e in db.iter_entries():
        ...
```

`CorpusDB` 是上下文管理器；同时也为手动管理生命周期的调用者暴露 `close()`。每个公共变更器（`add_entry`，
`purge`）都会获取 `threading.RLock` *并* 打开一个 SQLite 即时事务，因此在线程之间共享实例是安全的（与 v0.5 `CheckpointStore` 的契约相同）。

<a id="field-schema"></a>

### 字段架构

```
CorpusEntry(
    id: str,                              # stable content SHA-256 prefix
    path: Path,                           # current resolved location
    added_at: float,                      # Unix timestamp
    duration_sec: float,
    phash_frames: tuple[int, ...],        # uint64 perceptual hashes
    audio_fingerprint: tuple[int, ...],   # chromaprint frames
    sample_count: int,
    content_sha256: str | None = None,    # full digest; None for legacy rows
    stat_size: int | None = None,
    stat_mtime_ns: int | None = None,
)
```

Schema v2 是通过流式 SHA-256 内容来识别媒体的，而不是通过路径名。因此，移动或重命名相同的字节会保持语料库 ID 并更新存储位置。在相同位置替换字节会创建一个新的 ID，并在同一事务中删除过时的路径行，因此旧的指纹无法匹配替换内容。size/mtime 字段仅用于诊断；身份从不依赖于文件系统时间戳。现有的 schema-v1 行会就地升级，并在下一次摄取时接收内容元数据。

<a id="concurrency"></a>

## 并发性

* **多进程安全。** 两个共享相同语料目录的 `video-uniq` 调用不会破坏索引。写入者通过
  `BEGIN IMMEDIATE` 串行化；读取者永不阻塞。
* **多线程安全。** `RLock` 允许同一线程的可重入访问（由 QA 报告生成器使用，该生成器在 `iter_entries` + `add_entry` 过程期间持有锁）。
* **锁获取速度快。** 没有长时间持有的锁：每个修改操作都是 `_tx()` 上下文中的单条语句。

<a id="performance"></a>

## 性能

v0.7 → v0.8 的交换目标是 10k–50k 引用范围。在笔记本 SSD 上 50k 条目时：

* 冷 `Corpus.search_match`：~80 毫秒（而使用 JSON 扫描约为 ~9 秒）。
* `add_entry`：~3 毫秒（与全文件重写相比，约 1.2 秒）。
* 来自 4 个 `video-uniq batch` 工作进程的并发写入者：除了 `BEGIN IMMEDIATE` 队列深度外，没有观察到竞争。

对于超过 ~500k 条目的语料库，pHash 相似性循环占主导；这是一个单独的优化（参见 `core/qa/cid_predict.py`）。

<a id="failure-modes"></a>

## 失败模式

* **`index.json` 格式错误。** 自动迁移会记录解析错误并保持 SQLite 为空；文件**不会**被重命名（所以你可以修复后重试）。`video-uniq corpus migrate --dry-run` 将会明确显示相同的错误。
* **SQLite 文件为只读。** `Corpus.add` 引发 `PipelineError`，底层 `OperationalError` 链接 — 不会静默吞掉。
* **模式漂移。** `_init_schema()` 在每次连接打开时运行，并在检查 `PRAGMA table_info(entries)` 后添加缺失的 v2 列；`schema_info` 记录当前版本。

<a id="see-also"></a>

## 另见

* [`docs/en/qa_report.md`](qa_report.md) — 如何在 QA 工件中匹配语料库与表面
* [`docs/en/distributed.md`](distributed.md) — 多主机批处理模式下的语料库锁定
* [`docs/en/sscd.md`](sscd.md) — ML 级相似性度量（无语料库依赖）
