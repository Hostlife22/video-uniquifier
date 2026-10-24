<a id="api-contracts"></a>

# Контракты API

Эта страница является авторитетным справочником для `video-uniquifier`
**публичный, стабильный API** в рамках обязательства SemVer в [Версионировании](versioning.md). Каждая приведенная ниже запись проверяется с помощью снапшот-теста под `tests/contracts/`; отклонение контракта приводит к сбою CI с указанием на `tools/regen_contract_goldens.py`.

<a id="stability-labels"></a>

## Метки стабильности

- **`stable`** — покрывается обязательством SemVer. Для удаления или нарушения требуется MAJOR-бамп; MINOR может добавлять поля.
- **`experimental`** — покрывается, но МОЖЕТ быть удалено в MINOR с `DeprecationWarning`. Зафиксируйте `==2.2.*`, если вы от него зависите.
- **`internal`** — не покрывается. Значение по умолчанию для всего, что не указано.

<a id="how-to-import"></a>

## Как импортировать

Версия 2.0.0 переименовывает дистрибутив в `video-uniquifier`, Python импорты в
`video_uniquifier`, а исполняемые файлы в `video-uniq`, `video-uniq-gui` и
`video-uniq-web`. Обновите точки входа плагина на `video_uniquifier.transforms` и префиксы окружения на `VIDEO_UNIQ_*`, `VIDEO_UNIQUIFIER_*` и `VU_*`. Старые алиасы импорта/команд удалены. Настройки GUI/история мигрируют путем копирования предыдущей директории данных, если новое состояние отсутствует; предыдущие кэши остаются отдельными и восстанавливаются заново. Исторические бенчмарки/релизы сохраняют свои оригинальные имена артефактов. Решение по автору-владельцу относительно именования зафиксировано в
[specs/29-project-rename-rfc.md](https://github.com/Hostlife22/video-uniquifier/blob/d6af67ac05eb0689f958f18cca08cfdb6cb7c4db/specs/29-project-rename-rfc.md) в архивной ревизии.

Поддерживаемая точка входа — это бочка `video_uniquifier.core`:

```python
from video_uniquifier.core import (
    Plan, Profile, RunOptions, RunSummary, RunEvent,
    build_plan, run_full, compute_plan_hash,
)
```

Импорт из подмодулей (`from video_uniquifier.core.orchestrator import ...`) по-прежнему работает, но **не** покрывается SemVer — эти пути могут быть перераспределены внутри между MINOR-релизами.

<a id="locked-surfaces"></a>

## Закреплённые интерфейсы

<a id="pydantic-models-stable"></a>

### Модели Pydantic (`stable`)

Каждая модель ниже имеет полностью заблокированную схему JSON от
`tests/contracts/test_pydantic_schemas_stable.py`. Золотые версии находятся в
`tests/fixtures/contracts/schemas/`.

|Модель|Источник|Примечания|
|---|---|---|
| `HDRInfo` | `core/models.py` |`frozen=True`. Цветовые характеристики плюс необязательные статические/динамические метаданные HDR.|
| `VideoStream` | `core/models.py` |`frozen=True`. Один видеопоток из `ffprobe`.|
| `AudioStream` | `core/models.py` |`frozen=True`. v1.4 добавляет необязательные `title` и `dispositions`.|
| `SubtitleStream` | `core/models.py` |`frozen=True`. v1.4 добавляет необязательные `title`, `is_default` и `dispositions`.|
| `Chapter` | `core/models.py` | `frozen=True`. |
| `SourceMeta` | `core/models.py` |`frozen=True`. Стабильный результат пробника сериализованных A/V/субтитров/глав. Вспомогательная вложенная/данные/топология обложки намеренно приватная/внутренняя, поэтому это корректирующее изменение не изменяет схему v1.|
| `EncoderCandidate` | `core/models.py` |`frozen=True`. `max_parallel ∈ [1, 64]`; включает поставщиков программного обеспечения AV1 `svtav1` и `libaom`.|
| `TransformConfig` | `core/models.py` |`extra="forbid"`. `params: dict[str, object]` — словарь параметров проверяется по форме в модели `*Params` самого преобразования, а не здесь. `video.fit_aspect.allow_upscale` — это добавочный булев тип и по умолчанию `false`; поставляемые профили с фиксированным холстом выбирают его явно ([RFC #11](https://github.com/Hostlife22/video-uniquifier/issues/11)).|
| `SegmentationConfig` | `core/models.py` |`extra="forbid"`. v0.8.0 добавила опцию `mode="scene"`.|
| `Profile` | `core/models.py` |`extra="forbid"`. Схема YAML для пользователя; v1.3 добавляет `skip_watermark_check`.|
| `Plan` | `core/models.py` |`frozen=True`. Содержит `plan_hash` (ключ резюме) + `run_seed` (НЕ является частью хэша).|
| `QAReport` | `core/models.py` |`frozen=True`. Все метрики ML/отпечатков пальцев `Optional`; в версии 1.5 добавлены nullable поля метрик, зарегистрированных в плане, и вложенное ограниченное происхождение регистрации при сохранении всех исходных полей.|

### Dataclasses (`stable`)

RFC №21 (v1.6.0) добавляет nullable `QAReport.correctness`, `loudness`, и
`quality_policy` с вложенными замороженными моделями доказательств/политик. См. [QA evidence and gates](qa_report.md#explicit-evidence-and-optional-gates-v160) для значений полей, поведения в старом JSON и контракта выхода по выбору CLI. Опции команды QA также заблокированы `tests/contracts/test_qa_cli_contract.py`.

Исправления октябрьского аудита сохраняют эти схемы и флаги CLI. Недоступные оценки остаются null (или `phash_samples=0`); недоступное значение звукового интервала опускается из существующего открытого словаря `chunk_similarities`, с указанием причины в `notes`. Клиенты должны использовать `.get("audio")`, вместо того чтобы считать отсутствующее значение равным нулю. См. [audit compatibility decisions](https://github.com/Hostlife22/video-uniquifier/blob/d6af67ac05eb0689f958f18cca08cfdb6cb7c4db/docs/audit-implementation-decisions.md).

Формы полей (имя + представление типа + есть ли значение по умолчанию) заблокированы
`tests/contracts/test_runoptions_dataclass_stable.py` и
`tests/contracts/test_runevent_kinds_stable.py`. Значения по умолчанию **явно НЕ заблокированы** — допустима корректировка поведения по умолчанию (`target_segment_sec=600` → `900`) в пределах PATCH.

|Датакласс|Источник|Заблокированные поля|
|---|---|---|
| `RunEvent` | `core/runner.py` | `kind`, `payload` |
| `RunResult` | `core/runner.py` | `returncode`, `duration_sec`, `output_path` |
| `RunOptions` | `core/orchestrator.py` | `work_dir`, `output`, `encoder_override`, `title_template`, `target_segment_sec`, `keep_segments`, `enforce_preflight`, `force_new_variant`, `workers`, `sanitize_bitstream`, `sample_phash`, `notifications`, `telemetry`, `run_id`, `accept_watermark_risk`, `audit_log_path`, `audit_principal` |
| `RunSummary` | `core/orchestrator.py` |`output`, `plan`, `segments_done`, `preflight_findings`, необязательное `decode_evidence` (v1.6.0; непрозрачный токен процесса, не сериализуемая/постоянная аттестация)|

<a id="runevent-kinds-stable"></a>

### Виды RunEvent (`stable`)

`tests/contracts/test_runevent_kinds_stable.py` перечисляет точный кортеж. Начиная с v1.0.0:

| `kind` |Переносится|Контракт полезной нагрузки|
|---|---|---|
| `progress` |`runner.run_ffmpeg` за блок `-progress pipe:1`|Словарь, повторяющий поля прогресса ffmpeg (`out_time_ms`, `fps`, `speed`, ...)|
| `log` |Оркестратор / сегментатор / исполнитель|`phase: str` и свободная форма контекста. Рассматривайте ключи полезной нагрузки как **экспериментальные** — добавления являются MINOR.|
| `done` | `runner.run_ffmpeg`, `orchestrator.run_full` |`duration_sec` или `output`|
| `error` |любая фаза|`reason`, `phase`, опционально `returncode`, `tail`|
| `divergence_sample` |`orchestrator._maybe_emit_divergence` (v0.7 R4)| `segment_idx`, `phash_similarity`, `ema` |
| `target_vmaf` |`segmenter._encode_once` за попытку (v0.8 R5)| `segment`, `vmaf`, `crf`, `attempt`, `target` |
| `target_vmaf_failed` |`segmenter._encode_once` после исчерпания|как выше, плюс `best_attempt`|

Добавление нового типа является **МИНОРНЫМ**; потребители ДОЛЖНЫ воспринимать неизвестные типы (например, через стандартный `if-elif-else` блок, который логирует и отбрасывает). Удаление или переименование типа является **МАЖОРНЫМ** и требует RFC.

<a id="profile-yaml-schema-stable"></a>

### Схема YAML профиля (`stable`)

Каждая отправляемая форма профиля блокируется
`tests/contracts/test_shipped_profiles_stable.py` (goldens под
`tests/fixtures/contracts/profiles/`). Сама выборка блокируется
`shipped_profiles.json`. Начиная с v2.2.0:

|Профиль|Контейнер|Кодек| LUFS |Примечания|
|---|---|---|---|---|
| `soft` |mp4|h264| -14 |Консервативная авторизованная производная; диапазон корпуса естественных данных ожидается.|
| `medium` |mp4|h264| -14 |Умеренная обработка; диапазон корпуса естественных данных ожидается.|
| `medium_hdr` |mp4|hevc| -14 |Сохраняет путь HDR через `zscale` с линейной оберткой.|
| `aggressive` |mp4|h264| -14 |Экспериментальный стек с высокой изменчивостью; требуется проверка оператором.|
| `cid_aware` |mp4|h264| -14 |Профиль наследственной экспериментальной совместимости; предсказание внешней системы отсутствует.|
| `cid_aware_hdr_to_sdr` |mp4|h264| -14 |Экспериментальный путь HDR → SDR.|
| `cid_aggressive` |mp4|h264| -14 |Наследственный стек с максимальными изменениями; качество не в приоритете.|
| `youtube_4k` |mp4|h264| -14 |Геометрия и битрейт целевого YouTube 4K.|
| `youtube_1080p` |mp4|h264| -14 |Цель YouTube 1080p.|
| `youtube_av1` |mp4|av1| -14 |Цель YouTube 1080p AV1.|
| `youtube_4k_av1` |mp4|av1| -14 |Цель YouTube 4K AV1.|
| `youtube_shorts` |mp4|h264| -14 |Вертикальное видео 9:16, ожидается ≤60 с.|
| `tiktok_vertical` |mp4|h264| -16 |Вертикальное видео 9:16, громкость TikTok.|
| `instagram_reels` |mp4|h264| -16 |Вертикальное видео 9:16.|
| `instagram_square` |mp4|h264| -16 |Квадрат 1:1.|
| `linkedin_square` |mp4|h264| -16 |Квадрат 1:1, громкость LinkedIn.|
| `facebook_reels_base` | mp4 | h264 | -16 | Базовый профиль подготовки Reels; добавлен в v2.2.0. |

Добавление профиля — МЕЛКОЕ изменение; удаление — ВАЖНОЕ (RFC).

<a id="public-python-surface-stable"></a>

### Публичный Python API (`stable`)

`video_uniquifier.__all__` и `video_uniquifier.core.__all__` заблокированы `tests/contracts/test_public_surface_stable.py`. Добавление имени является МЕНЬШОЙ операцией; удаление — БОЛЬШОЙ.

<a id="cli-subcommands-stable"></a>

### Подкоманды CLI (`stable`)

Каждая подкоманда `video-uniq` является частью контракта. Добавление подкоманды или флага является МЕНЬШОЙ операцией; удаление или переименование — БОЛЬШОЙ.

|Подкоманда|Источник|
|---|---|
| `version` | `cli/app.py` |
| `probe` | `cli/cmd_probe.py` |
| `preflight` | `cli/cmd_preflight.py` |
| `run` | `cli/cmd_run.py` |
| `batch` | `cli/cmd_batch.py` |
| `qa` | `cli/cmd_qa.py` |
| `calibrate` | `cli/cmd_calibrate.py` |
| `worker` | `cli/cmd_worker.py` |
| `corpus` | `cli/cmd_corpus.py` |
| `queue` | `cli/cmd_queue.py` |
| `profile` |`cli/cmd_profile.py` (v0.9 R1)|
| `subtitles` |`cli/cmd_subtitles.py` (v0.9 R2)|
| `telemetry` |`cli/cmd_telemetry.py` (v0.9 R3)|
| `update` |`cli/cmd_update.py` (v1.3 Task 33)|

<a id="plugin-entry-point-group-stable"></a>

### Группа точек входа плагина (`stable`)

`video_uniquifier.transforms` (v0.8.0 R1) является точкой обнаружения для сторонних преобразований. Протокол, которому должны удовлетворять зарегистрированные объекты, это `core.transforms.base.TransformSpec` — поля заблокированы схемой pydantic, указанной выше.

<a id="surfaces-marked-experimental"></a>

## Поверхности, отмеченные `experimental`

Закрепите `video-uniquifier==2.2.*`, если вы зависите от любого из них.

|Поверхность|Причина|
|---|---|
|`[web]` HTTP API (`src/video_uniquifier/web/routes/*`)|v0.9 R4 выходит как v1; маршруты могут быть расширены до продвижения.|
|`RunEvent` ключ полезной нагрузки установлен (сам словарь стабилен; отдельные ключи нет)|Ожидается аддитивный рост между МИНОРНЫМИ релизами.|
| `core.telemetry.TelemetryConfig` |v0.9 R3 поставляется с UX согласия; будущие МИНОРНЫЕ могут добавлять поля.|
| `core.notifications.NotificationConfig` |Автоопределение провайдера может развиваться.|
|GUI `gui/screens/*` и Python API `gui/workers/*`|Экраны / рабочие процессы внутренние; их *поведение* (горячие клавиши, доступные имена, расположение экрана) является видимым для пользователя контрактом.|

<a id="out-of-scope-internal"></a>

## Внутренние интерфейсы (`internal`)

Все, что не указано выше. В частности:

- Модули с ведущим подчеркиванием (`core/_internal/`, `_*`).
- Вспомогательные модули `cli/_*` и `gui/_*`.
- Любая утилита в рамках `core/utils/`.
- Фикстуры тестов и инструменты разработки (`tools/*`).

Если вы завязаны на чем-то внутреннем, откройте [RFC](versioning.md#rfc-process-for-breaking-changes), чтобы запросить продвижение к `stable` или `experimental`.

<a id="snapshot-tests-reference"></a>

## Справочник тестов контрактов

|Файл теста|Что он блокирует|Золотой каталог|
|---|---|---|
| `test_pydantic_schemas_stable.py` |`model_json_schema()` каждого модели| `tests/fixtures/contracts/schemas/` |
| `test_shipped_profiles_stable.py` |`model_dump(mode="json")` каждого YAML + набор имен поставляемых профилей| `tests/fixtures/contracts/profiles/` + `shipped_profiles.json` |
| `test_runevent_kinds_stable.py` |Литеральные члены `EventKind` + форма dataclass `RunEvent`| `tests/fixtures/contracts/runevent_*.json` |
| `test_runoptions_dataclass_stable.py` |Формы полей `RunOptions`, `RunSummary`, `RunResult`| `tests/fixtures/contracts/dataclasses/` |
| `test_public_surface_stable.py` |`video_uniquifier.__all__` и `video_uniquifier.core.__all__`| `tests/fixtures/contracts/public_surface/` |

<a id="see-also"></a>

## См. также

- [Версионирование и совместимость](versioning.md) — обязательство SemVer и процесс RFC.
- [`SECURITY.md`](https://github.com/hostlife22/video-uniquifier/blob/main/SECURITY.md) — политика раскрытия информации.
- [`CHANGELOG.md`](https://github.com/hostlife22/video-uniquifier/blob/main/CHANGELOG.md) — здесь записывается каждое принятое изменение контракта.
