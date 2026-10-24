<a id="reference-corpus-sqlite"></a>

# Библиотека эталонов

> Переделано в v0.8.0 R2.

Корпус — это локальный индекс `video-uniquifier` «видео, которое может быть почти дубликатом». Он поддерживает шаг `cid_predict` в QA отчёте: отпечатки (хеш chromaprint + последовательность pHash) каждого выхода сравниваются с каждой записью корпуса, а наивысшее сходство отображается как `match_probability_corpus`.

v0.7 сохранял индекс как один файл `index.json`. Это было нормально, чтобы
~5 тыс. записей; после этого каждая проверка сканировала файл, и одновременные записи (два экземпляра `video-uniq run` на одном NAS или `video-uniq batch` с несколькими рабочими процессами) конкурировали при перезаписи. v0.8.0 меняет хранилище на SQLite, сохраняя при этом публичное API v0.7 (`Corpus.add`)
`Corpus.remove`, `Corpus.list_all`, `Corpus.search_match`) полностью совместимы по битам.

<a id="storage-layout"></a>

## Структура хранения

```
<corpus-dir>/
├── index.sqlite               # SQLite (WAL mode)
├── index.sqlite-wal           # WAL journal (auto)
├── index.sqlite-shm           # shared-memory index (auto)
└── index.json.migrated.<ts>   # one-shot backup of pre-v0.8.0 store
```

По умолчанию `<corpus-dir>` используется `~/.cache/video_uniquifier/corpus/` (можно переопределить с помощью `--corpus-dir`). Файл SQLite открывается в [режиме WAL](https://www.sqlite.org/wal.html), поэтому чтение никогда не блокируется писателем, удерживающим блокировку; писатели из разных процессов упорядочиваются через
`BEGIN IMMEDIATE`, поэтому два рабочих процесса `video-uniq batch` на одной общей файловой системе не могут перемежать частичную вставку.

Последовательности отпечатков (кадры chromaprint uint32, кадры pHash uint64) хранятся как упакованные BLOB через `struct.pack(f"<{n}Q", *seq)` — без накладных расходов JSON, без строки на кадр, и `pickle` **не** используется (поверхность атаки мала, а сериализация произвольного Python — это потенциальная ошибка).

<a id="migration-from-indexjson"></a>

## Миграция с `index.json`

В первый раз, когда `Corpus` открывается с устаревшим `index.json` "сиблингом"
**и** пустым хранилищем SQLite, записи автоматически мигрируются. JSON-файл переименовывается в `index.json.migrated.<ts>` и **никогда не удаляется** — повторное открытие устаревшего JSON-соперника НЕ выполняет повторное слияние (так что удалённые данные остаются удалёнными).

Для скриптового управления (снапшоты корпуса CI, развертывания NAS):

```bash
video-uniq corpus migrate --dry-run            # report counts, write nothing
video-uniq corpus migrate                      # explicit migration pass
video-uniq corpus migrate --corpus-dir /mnt/x  # alternative location
```

Команда идемпотентна: повторный запуск после успешной миграции не выполняет никаких действий и сообщает текущее количество записей в SQLite.

<a id="cli-subcommands"></a>

## Подкоманды CLI

```bash
video-uniq corpus add <video> [--name NAME]    # ingest a reference video
video-uniq corpus list [--limit N]             # tabular listing
video-uniq corpus remove <id>                  # delete one entry by id
video-uniq corpus migrate [...]                # see above
```

Все команды принимают `--corpus-dir <path>` для переопределения расположения по умолчанию.

<a id="public-api"></a>

## Публичное API

`video_uniquifier.core.qa.corpus.Corpus` является лёгким фасадом над
`CorpusDB`. Существующий код v0.7, который импортирует `Corpus`, продолжает работать — внутри него SQLite не используется.

Для нового кода, который требует прямого доступа к базе данных (массовый импорт, пользовательские запросы), используйте `CorpusDB`:

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

`CorpusDB` является менеджером контекста; `close()` также доступен для вызывающих, которые управляют временем жизни вручную. Каждый публичный изменяющий метод (`add_entry`,
`purge`) получает `threading.RLock` *и* открывает немедленную транзакцию SQLite, поэтому безопасно использовать один экземпляр между потоками (тот же контракт, что и у `CheckpointStore` версии v0.5).

<a id="field-schema"></a>

### Схема поля

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

Схема v2 идентифицирует медиа по передаваемому содержимому SHA-256, а не по пути к файлу. Перемещение или переименование идентичных байт, таким образом, сохраняет идентификатор корпуса и обновляет сохранённое местоположение. Замена байт в одном и том же месте создаёт новый ID и удаляет устаревшую строку пути в той же транзакции, поэтому старые отпечатки не могут совпасть с заменой. Поля size/mtime предназначены только для диагностики; идентичность никогда не зависит от временных меток файловой системы. Существующие строки схемы v1 обновляются на месте и получают метаданные содержимого при следующем их обработке.

<a id="concurrency"></a>

## Конкурентность

* **Безопасно для многопроцессного использования.** Два вызова `video-uniq`, использующие один и тот же каталог корпуса, не повредят индекс. Запись происходит последовательно через
  `BEGIN IMMEDIATE`; чтение никогда не блокируется.
* **Безопасно для многопоточного использования.** `RLock` позволяет повторный доступ из одного и того же потока (используется строителем отчета QA, который удерживает блокировку на протяжении прохода `iter_entries` + `add_entry`).
* **Захват блокировки осуществляется быстро.** Нет долговременных блокировок: каждый мутатор выполняется в одном операторе внутри контекста `_tx()`.

<a id="performance"></a>

## Производительность

Обновление с v0.7 на v0.8 ориентировано на диапазон 10k–50k ссылок. При 50k записей на SSD ноутбука:

* Холодный `Corpus.search_match`: ~80 мс (в сравнении с ~9 с при сканировании JSON).
* `add_entry`: ~3 мс (в сравнении с полной перезаписью файла, ~1,2 с).
* Одновременные писатели от 4 рабочих `video-uniq batch`: не наблюдалось конкуренции, превышающей глубину очереди `BEGIN IMMEDIATE`.

Для корпусов с количеством записей более ~500 тысяч доминирует цикл сравнения pHash; это отдельная оптимизация (см. `core/qa/cid_predict.py`).

<a id="failure-modes"></a>

## Режимы сбоев

* **`index.json` поврежден.** Авто-перенос регистрирует ошибку синтаксического анализа и оставляет SQLite пустым; файл **не** переименовывается (чтобы вы могли исправить его и повторить попытку). `video-uniq corpus migrate --dry-run` явно покажет ту же ошибку.
* **Файл SQLite доступен только для чтения.** `Corpus.add` вызывает `PipelineError` с вложенным `OperationalError` — без скрытого подавления.
* **Схема изменилась.** `_init_schema()` выполняется при каждом открытии соединения и добавляет отсутствующие столбцы v2 после проверки `PRAGMA table_info(entries)`; `schema_info` фиксирует активную версию.

<a id="see-also"></a>

## См. также

* [`docs/en/qa_report.md`](qa_report.md) — как совпадения корпуса отображаются в артефакте QA
* [`docs/en/distributed.md`](distributed.md) — блокировка корпуса в режиме пакетной обработки с несколькими хостами
* [`docs/en/sscd.md`](sscd.md) — метрика схожести уровня ML (без зависимости от корпуса)
