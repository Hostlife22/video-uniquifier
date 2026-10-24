<a id="architecture"></a>

# Архитектура

Три уровня, с `Plan` (pydantic) в качестве контракта между ними.

```
+---------------------------------------------------------+
| GUI (optional [gui]): PyQt6 — gui/app_pyqt.py           |
| CLI (typer): cli/{app, cmd_run, cmd_probe,              |
|              cmd_preflight, cmd_qa, cmd_batch,          |
|              cmd_calibrate, cmd_corpus,                 |
|              cmd_queue, cmd_worker}.py                  |
+----------------------------+----------------------------+
                             |  Plan + RunOptions
                             v
+---------------------------------------------------------+
| core/  (pure Python, no Qt, no UI)                      |
|                                                         |
|  probe  → planner → preflight → segmenter → pipeline    |
|     │        │                       │          │       |
|     v        v                       v          v       |
| encoder              checkpoint           runner        |
|                                                         |
|  seed_resolver  → divergent per-segment seeds           |
|  audio_windows  → per-window audio seeds (divergent)    |
|  calibration    → bisect intensity vs cid_predict       |
|  qa             → phash + audio_fp + vmaf + ssim        |
|                 + cid_predict + corpus + chunked QA     |
|  queue / worker → shared-FS distributed batch           |
|  sanitizer      → optional libx264 bitstream rewrap     |
|  errors         → typed exception hierarchy             |
|                                                         |
|                concat → (sanitize?) → metadata → qa     |
+---------------------------------------------------------+
                             |
                             v
                 ffmpeg / ffprobe / fpcalc
```

<a id="modules"></a>

## Модули

|Путь|Роль|
|------|------|
| `core/models.py` |Все пайдантические дата-классы: SourceMeta, Plan, Profile, Segment, QAReport|
| `core/probe.py` |`probe(path) -> SourceMeta` через один вызов ffprobe|
| `core/encoder.py` | `detect_encoders()` проверяет реальные кодирования и сохраняет кэш; `pick_encoder()` выбирает кодировщик с его лимитом `max_parallel`. |
| `core/transforms/` |**21 встроенная трансформация** зарегистрирована при импорте (12 видео, 9 аудио — `video_geom.py` регистрирует `crop_resize`, `rotate`, `mirror`); сторонние плагины обнаруживаются через точки входа `video_uniquifier.transforms` (v0.8.0 R1, см. [plugins.md](plugins.md)); см. [filter_graph.md](filter_graph.md)|
| `core/transforms/hdr_wrap.py` | Обёртка zscale для преобразований цвета HDR в линейном свете. |
| `core/pipeline.py` |`FilterGraph.build()` + `build_video_segment_command` (+ `_fused`) + `build_main_audio_command` + `compute_plan_hash`; v0.8.0 R5 добавляет `crf_override` для поддержки повторных попыток target-VMAF по сегментам|
| `core/runner.py` |обертка subprocess с `-progress pipe:1`, потоком RunEvent, CancelToken; v0.8.0 R5 добавляет `target_vmaf` / `target_vmaf_failed` виды событий|
| `core/resource_budget.py` |общий реестр локальных процессов для слотов кодеров и оценки резервов рабочих/финальных байтов; `VIDEO_UNIQ_RESOURCE_LOCK_DIR` выбирает общий реестр|
| `core/segmenter.py` |осознанный ключевыми кадрами разрез (или режим сцены, управляемый PySceneDetect, v0.8.0 R3) + обработка по сегментам (параллельно где безопасно) + конкатенационный демультиплексор; v0.8.0 R5 добавляет обратную связь с целевым VMAF|
| `core/scene_detect.py` |v0.8.0 R3 — `detect_scene_boundaries` (PySceneDetect ContentDetector, по выбору) + `snap_to_keyframes` (сохраняет инвариант копирования потока)|
| `core/checkpoint.py` | Атомарное сохранение `state.json` для возобновления: потокобезопасный `RLock`, fsync и `os.replace`. |
| `core/seed_resolver.py` |`resolve_run_seed(profile, source)` + `derive_segment_seed(plan_hash, idx, run_seed)` для стратегии `divergent`|
| `core/audio_windows.py` |`~60 s` звуковое окно для стратегии `divergent` — генерация начальных значений для каждого окна через `derive_segment_seed(plan_hash, window_idx + 1_000_000, run_seed)` с кроссфейдом `0.1 s`; loudnorm остаётся глобальным|
| `core/metadata.py` |аргументы `-metadata` + шаблоны заголовков|
| `core/preflight.py` |матрица целей YouTube + проверка HDR + пробные фильтры dry-run (`_ffmpeg_filter_works`) для `rubberband`, `zscale` и зависимостей тональной карты|
| `core/sanitizer.py` |нормализация взаимодействия с libx264 по желанию (`--sanitize-bitstream`); предупреждение о генерационной потере, бездействие на libx264, отклоняет контракты HDR/HEVC/AV1|
| `core/orchestrator.py` | `run_full(plan, options, on_event, cancel_token) -> RunSummary` |
| `core/profile_loader.py` |YAML → `Profile` с проверкой pydantic (`extra=forbid`)|
| `core/errors.py` |Иерархия исключений с типами: `VideoUniquifierError`, `ProbeError`, `EncoderError`, `FfmpegNotFoundError`, `PipelineError`, `CheckpointError`, `PreflightFailure`|
| `core/utils/ffmpeg_paths.py` | `ffmpeg_bin()` / `ffprobe_bin()` — единая точка определения путей исполняемых файлов. |
| `core/qa/` |хэши, phash, audio_fp (сходство + расстояние Хэмминга), vmaf, ssim, cid_predict, корпус (на основе SQLite через `corpus_db.py` с версии v0.8.0 R2, см. [corpus.md](corpus.md)), качество (цепочка резервирования), отчет + HTML|
| `core/qa/sscd.py` |v0.8.0 R4 — опциональное ML-класса сходство через SSCD embedding от Meta (`[ml]` дополнительный), см. [sscd.md](sscd.md)|
| `core/qa/corpus_db.py` |v0.8.0 R2 — хранилище корпуса SQLite (WAL + `BEGIN IMMEDIATE`); одноразовая автоматическая миграция с устаревшего `index.json`|
| `core/calibration/` |`intensity.scale_profile` (мультипликативное масштабирование вокруг идентичности) + `loop.calibrate` (разделение по выбранной метрике: chromaprint `cid_predict` по умолчанию, или SSCD через v0.8.0 R6 `metric="sscd"`)|
| `core/queue/leasing.py` |Атомарная очередь файлов POSIX-rename (`pending/`, `in_progress/`, `done/`, `failed/`) с heartbeat, reaper и надежным восстановлением commit с fenced-output|
| `cli/cmd_worker.py` | Долгоживущий исполнитель очереди вызывает `orchestrator.run_full` для каждого файла, полученного по аренде. |

<a id="data-flow-for-one-input"></a>

## Поток данных для одного входа

```
input.mp4
  ├─ probe()              → SourceMeta (streams, HDR, chapters)
  ├─ load_profile()       → Profile (transforms, audio_tracks, keep_hdr, seed_strategy…)
  ├─ pick_encoder()       → EncoderCandidate (quality/balanced/speed + strict override)
  ├─ compute_plan_hash()  → Plan (frozen)
  ├─ resolve_run_seed()   → run_seed (per_run / per_file / fixed / divergent base)
  ├─ preflight()          → list[PreflightFinding] (fail → stop)
  ├─ plan_segments()      → list[Segment] (keyframe-aligned)
  ├─ checkpoint init/resume
  ├─ process_video_segments_parallel(workers=N, cap=encoder.max_parallel):
  │     acquire shared process CPU/vendor capacity per FFmpeg child
  │     for each pending segment:
  │       seg_plan = plan_for_segment(plan, idx)   # divergent: per-seg seed
  │       stream_copy_extract → seg_NNNN_src.mkv
  │       filter_complex      → seg_NNNN.mkv
  │       state.json mark done
  ├─ process_main_audio() ← runs on full source; two-pass loudnorm cached in state.json
  │   (divergent strategy: audio_windows.plan_windows → per-window seed + 0.1 s crossfade)
  ├─ concat_segments()    → concat demuxer + stream-copy mux of main audio
  ├─ sanitize_bitstream() → optional libx264 rewrap (opt-in via --sanitize-bitstream)
  └─ build_report()       → output.qa.json + output.qa.html
output.mp4
```

<a id="distributed-flow"></a>

## Распределённый поток

```
Worker A (machine 1) ──┐
                       │
Worker B (machine 2) ──┼── pending/   ◄── queue add
                       │   ▲
Worker C (machine 3) ──┘   │ atomic rename
                           │
                       in_progress/<host>.<file>  + <host>.alive (heartbeat)
                           │ (success)
                           v
                       done/                          ◄── prune by mtime
                           │ (failure)
                           v
                       failed/<file>.err
```

Каждый рабочий вызывает `orchestrator.run_full` для каждого арендованного файла. Общего состояния, кроме директорий очереди, нет; см. [distributed.md](distributed.md).

<a id="why-a-separate-orchestrator"></a>

## Зачем нужен отдельный оркестратор

`core/orchestrator.run_full()` это **единственная точка входа**, к которой обращаются команды CLI (`cmd_run`, `cmd_batch`, `cmd_worker`) и GUI Worker. Он получает обратный вызов `on_event`, чтобы любой UI мог передавать `RunEvent` без внедрения логики отображения в ядро. Это исправляет архитектурный долг старого прототипа AB, который встраивал весь pipeline внутри PyQt
`QThread`.

<a id="why-split-process-concat-not-keyframe-seek"></a>

## Зачем split-process-concat (а не поиск по ключевым кадрам)

- Один ffmpeg `-ss <T>` при возобновлении теряет весь прогресс в случае сбоя.
- Обработка по сегментам делает возобновление O(1) и даёт чистый, MD5-стабильный результат для одного и того же `(plan_hash, run_seed)`.
- Основной аудио сигнал обрабатывается **вне** сегментации на полном исходнике — loudnorm и изменение тональности имеют переходные эффекты на стыках, поэтому мы никогда не разрезаем аудио.

<a id="seed-strategy"></a>

## Стратегия зерна (Seed)

`Profile.seed_strategy` контролирует изменчивость на запуск:

- `fixed`     — `profile.seed` дословно; каждый запуск идентичен.
- `per_run`   — новый случайный seed при каждом вызове (устаревший стандарт).
- `per_file`  — детерминированный хэш пути источника; одинаковый вход → одинаковый seed.
- `divergent` — новый базовый seed на запуск И seed на сегмент, полученный через
                `sha256(plan_hash, segment_idx, run_seed)`. Соседние сегменты
                получают различные фазы параметров преобразования. По умолчанию для v0.3.3
                Профили с поддержкой CID.

Смотрите [seed_strategy.md](seed_strategy.md) для примеров использования и последствий для воспроизводимости.

<a id="runevent-contract"></a>

## Контракт RunEvent

`core/runner.RunEvent` — это замороженный dataclass с дискриминатором `kind: EventKind` и свободной формой `payload: dict[str, object]`.
`on_event` callback — это единственный путь, по которому информация покидает основной слой, поэтому его поверхность является частью публичного контракта — добавление нового
`kind` является обратно совместимым расширением; **переименование** одного из них — это нарушение совместимости.

| `kind`               |Производитель|Ключи полезной нагрузки (несущие нагрузку)|
|---|---|---|
| `progress`           |`runner._run_once` (ffmpeg `-progress`)|`out_time_us` *или* `out_time_ms`, `frame`, `phase`, `segment`|
| `log`                |оркестратор / сегментатор / наблюдатель запуска|`phase` (например, `preflight`, `plan`, `segment`, `main_audio`, `paused`, `resumed`, `concat`, `sanitize`, `cleanup`), `message`|
| `error`              |любой слой| `phase`, `message`, `returncode`, `tail`, `findings` |
| `done`               |`runner.run` (успешный выход)| `duration_sec`, `output` |
| `divergence_sample`  |`orchestrator._maybe_emit_divergence` (v0.7 R4 / F2)|`segment`, `phash_similarity` (по сегменту), `running_phash` (EMA, α=0.25), `frames_sampled`|

Фазовые инварианты, используемые GUI-потребителями:

- `phase=segment` несет `segment: int`, чтобы агрегаторы прогресса могли сопоставить локальный для потока `out_time_us` ffmpeg с правильным общим сегментом. Замыкание `_wrap` в `segmenter.py` оркестратора вводит его; конечные потребители не должны предполагать, что `segment` установлен для каждого события.
- `phase=main_audio` предназначен для прохода loudnorm + повторной перекодировки аудио и управляет вторичной шкалой прогресса "Audio" в GUI; главный индикатор остается привязанным к значению, полученному из видеосегментов.
- `phase=paused` / `phase=resumed` срабатывают ровно один раз при каждом переходе состояния (v0.7 R6 / F5) — наблюдатель runner отслеживает примененное состояние SIGSTOP и устраняет дублирующиеся переключения токена.

<a id="cancel-pause-plumbing-v07-r6-f5"></a>

## Канал отмены + паузы (v0.7 R6 / F5)

Ядро предоставляет два примитива кооперативной отмены, оба
поддерживаются `threading.Event`, поэтому запись из любого потока (кнопка GUI → QThread, обработчик сигнала → основной цикл) корректно фиксируется на рабочем потоке:

```
                              ┌──────────────────────────┐
            GUI Run screen ──►│ RunWorker (QThread)      │
            (Esc / Space)     │                          │
                              │  cancel_token: CancelToken
                              │  pause_token:  PauseToken
                              └────────────┬─────────────┘
                                           │ run_full(plan, options,
                                           │   on_event=…,
                                           │   cancel_token=…,
                                           │   pause_token=…)
                                           v
                              ┌──────────────────────────┐
                              │ orchestrator             │
                              │  ├─ pause observer thread│
                              │  │   writes paused_at    │
                              │  │   to state.json on    │
                              │  │   pause/resume        │
                              │  │   enforces 24h        │
                              │  │   auto-cancel         │
                              │  │                       │
                              │  └─ process_video_segments_parallel
                              │     ↓ pause_token forwarded
                              └──────────────────────────┘
                                           │
                                           v
                              ┌──────────────────────────┐
                              │ runner.run / _run_once   │
                              │  watcher thread:         │
                              │    cancel → SIGTERM      │
                              │    pause  → SIGSTOP via  │
                              │      process_control     │
                              │    resume → SIGCONT      │
                              └────────────┬─────────────┘
                                           v
                                       ffmpeg
```

`PauseToken` является **идемпотентным** (повторные `pause()` / `resume()` вызовы не выполняют никаких действий), фиксирует временную метку паузы по системным часам для сохранения state.json и предоставляет `should_auto_cancel()` — демон оркестратора `_start_pause_observer` опрашивает его раз в секунду и срабатывает `cancel_token.cancel()`, если пауза превышает
`PauseToken.AUTO_CANCEL_SEC` (по умолчанию 24 ч).

`core/process_control.py` является кросс-ОС абстракцией: POSIX использует stdlib `os.kill(pid, SIGSTOP|SIGCONT)`; Windows использует `psutil`, устанавливаемый автоматически через платформозависимую runtime-зависимость. Оба обходят дерево процессов (psutil children или `/proc` в качестве fallback на Linux), чтобы дочерние вспомогательные процессы ffmpeg тоже были приостановлены. Все операции выполняются с наилучшими усилиями и никогда не вызывают исключений — сбой `os.kill` логируется как WARN, а возвращаемое значение сообщает количество подтверждений.
