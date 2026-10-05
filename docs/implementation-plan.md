# План работ по аудиту video-uniquifier

Создан: **2026-10-04**; обновлён: **2026-10-05**. Состояние: **локальная реализация и разрешённая full-file квалификация завершены; приёмка и внешние gates открыты**.
База: версия **2.0.0**, commit `03c707a5c4a68397511cb38f881335a00990f271`.

Этот файл — рабочий реестр будущих задач по
[аудиту системы](research/2026-10-04-video-uniquification/04-system-audit.md) и
[рекомендациям R-01…R-10](research/2026-10-04-video-uniquification/05-recommendations.md).
[Обзор исследования](research/2026-10-04-video-uniquification/index.md) содержит
остальные источники. Исторические production-результаты сохраняются в
[PRODUCTION_PLAN.md][production] и [RISK_REGISTER.md][risks]; их старые статусы
не считаются автоматически актуальной квалификацией версии 2.0.0.

Цель: исправить подтверждённые ошибки калибровки, сделать QA понятным и
воспроизводимым, проверить качество на разрешённом корпусе и закрыть выбранные
ограничения длинных видео. Локальная похожесть остаётся отдельной диагностикой;
из неё не выводится вероятность решения YouTube Content ID.

## 1. Как вести статусы

**Единственный актуальный статус каждой задачи находится в таблице раздела 3.**
Карточки ниже описывают работу и приёмку. Пустой исполнитель, PR или дата завершения
означает, что их ещё нет; назначать фиктивные значения нельзя.

| Статус | Значение | Условие перехода |
|---|---|---|
| `TODO` | Работа не начата; сначала проверить зависимости | Зависимости закрыты, ресурсы и контрактный путь определены → `READY` |
| `READY` | Можно брать следующей; обязательные зависимости закрыты | Начата работа, записаны исполнитель и ветка → `IN_PROGRESS` |
| `IN_PROGRESS` | Исполнитель делает изменения или эксперимент | Получен проверяемый результат и пройдены нужные проверки → `IN_REVIEW` |
| `IN_REVIEW` | Результат готов к проверке | Выполнены критерии приёмки, сохранены доказательства и закрыт review → `DONE` |
| `DONE` | Результат принят, есть ссылка на доказательства | Не означает квалификацию непроверенного оборудования или контента |
| `BLOCKED` | Реально установленное препятствие мешает продолжать | Записать причину, что необходимо для снятия, дату и доступный независимый шаг |
| `DEFERRED` | Условная работа вне обязательного первого пакета | Зафиксировано решение включить её в scope и выполнены prerequisites → `READY` |

Ожидание обычной зависимости — `TODO`, а не `BLOCKED`. Отсутствие известного заранее
внешнего ресурса нельзя объявлять установленной блокировкой без проверки.
Приоритет `P1` — корректность и достоверность основных результатов; `P2` — расширение
квалификации и улучшение качества. Это очередность плана, не severity GitHub issue.

При каждом изменении статуса обновлять строку реестра, поле «Обновлён» и журнал
раздела 8. Добавлять фактические ветку/PR/commit, команды, результат, scope и
оставшиеся ограничения. Для задачи `DONE` ссылка на evidence обязательна.
Счётчики ниже пересчитываются после каждого изменения реестра.

**Текущее состояние:** 29 задач: `DONE` — 1, `IN_REVIEW` — 23,
`BLOCKED` — 4, `DEFERRED` — 1. `READY`, `TODO`, `IN_PROGRESS` — 0.
Выполненная AP-00 — исходный аудит; 22 локальных результата и общая приёмка AP-28
находятся IN_REVIEW.
До дополнительного QA-исправления make check: 2060 passed, 55 skipped, coverage 86.67%.
Предыдущий metric snapshot прошёл2065tests/55skips; fresh coverage86.73%.
Дополнительная техническая работа2026-10-05: native-rate PCM observations,
mono A/B материалы, private experimental quality/size selector, HDR side-data
проверки и два исправления developer diagnostics. Новый gate фиксируется
в [результатах](audit-implementation-results.md):2118passed/55skipped,
Ruff/mypy167files; unit-only core coverage82.11%; wheel/docs passed.
Human/device acceptance открыта.
Четыре BLOCKED требуют labels/listening, HDR human/display и отсутствующие devices;
короткий независимый master-origin PQ proxy уже проверен на двух local encoders.
После освобождения диска AP-17/AP-23 получили полный технический результат для
180.4-минутного фильма: новый encode, CLI QA JSON/HTML с exit 0, full-file
PSNR/loudness/output decode, source/output hashes и ресурсные измерения.
После паузы повторён только QA; encoder/transforms/profile/Plan сохранены,
две дополнительные QA-коррекции имеют отдельный проверенный снимок.
Correctness valid, legacy raw quality verdict **red**; human listening/синхронизация
и приёмка качества остаются открыты. 95-минутный фильм отменён пользователем
до обработки. Общий план не объявляется завершённым.

## 2. Порядок выполнения и контрольные точки

1. **Пакет A — калибровка:** AP-01 → AP-02 → AP-03.
   AP-15 проверяет исторический VFR-риск параллельно, в отдельной ветке.
   Gate A: реальные shipped-профили валидны, search/resume работают на коротком
   ffmpeg fixture; не остаётся подтверждённых невалидных кандидатов.
2. **Пакет B — измерения:** AP-04 → AP-05…AP-09.
   AP-10 и AP-12 можно начать независимо; AP-11 завершить после AP-10.
   Gate B: доступность, реальные временные окна, backend и reference domain
   явно обозначены; отсутствующее измерение не выдаётся за успешный ноль.
3. **Пакет C — качество и pilot:** AP-13…AP-19.
   Gate C: воспроизводимый pilot из 54 результатов, корректные streams/timeline,
   понятные failures/unsupported и реальный full-file QA выбранных кандидатов.
4. **Пакет D — независимая квалификация:** AP-20…AP-24.
   Gate D: holdout и human review, bounded quality/size policy, новые long-form
   результаты; аппаратная поддержка обозначена только в проверенном scope.
5. **Пакет E — приёмка:** AP-28 для конкретного выбранного пакета изменений.
   AP-25…AP-27 остаются отдельными условными направлениями и не препятствуют
   принятию исправлений пакетов A/B.

Не откладывать небольшой исправленный пакет до завершения всего исследования.
AP-28 применяется к каждому готовому пакету, а становится `DONE` только после
приёмки всех обязательных задач AP-01…AP-24 либо документированного изменения scope.

## 3. Реестр задач

Исполнитель текущего пакета: Codex; ветка `fix/audit-implementation-20261004`. Новых PR пока нет. В колонке «Результат»
записываются именно фактические доказательства, а не планируемые файлы.

| ID | Задача | Приоритет | Статус | Зависимости | Основание / тип | Результат, исполнитель, PR |
|---|---|---|---|---|---|---|
| AP-00 | Зафиксировать аудит и воспроизведение находок | — | `DONE` | — | Исследование | [Аудит](research/2026-10-04-video-uniquification/04-system-audit.md): runtime-probes, 114 passed, pinned code links |
| AP-01 | Валидные дискретные параметры при дробном factor | P1 | `IN_REVIEW` | AP-00 | R-01, подтверждённый дефект | Codex; [evidence](audit-implementation-results.md): 107 regressions; valid integer kernels |
| AP-02 | Масштабирование настоящих параметров transforms | P1 | `IN_REVIEW` | AP-01 | R-02, подтверждённый дефект | Codex; [evidence](audit-implementation-results.md): Current fields/defaults; amplitude dB; fixed/disabled semantics |
| AP-03 | Реальные профили и полный путь calibration | P1 | `IN_REVIEW` | AP-01, AP-02 | Регрессия пользовательского сценария | Codex; [evidence](audit-implementation-results.md): 20 real FFmpeg tests; 3 natural calibrations ×4 trials + full QA |
| AP-04 | Решения о QA-контрактах и миграции | P1 | `IN_REVIEW` | AP-00 | R-03/R-04/R-06, проектирование | Codex; [evidence](audit-implementation-results.md): PATCH; stable schemas/CLI/presets preserved; caches 3 / current encode policy v8 |
| AP-05 | Missing/error/unsupported отдельно от числовых scores | P1 | `IN_REVIEW` | AP-04 | R-03, достоверность метрик | Codex; [evidence](audit-implementation-results.md): Null/count/notes; valid zero retained; required audio fails closed |
| AP-06 | Честные временные окна legacy similarity | P1 | `IN_REVIEW` | AP-04, AP-05 | R-06, 600-second/heatmap ограничение | Codex; [evidence](audit-implementation-results.md): Real common-prefix windows ≤600s; no invented interval audio |
| AP-07 | Выравнивание visual/audio и coverage | P1 | `IN_REVIEW` | AP-06 | R-06, design gap | Codex; [evidence](audit-implementation-results.md): Known shift/drift/speaker events + natural retention; ambiguous results unavailable |
| AP-08 | SSCD sampling и локальные совпадения | P1 | `IN_REVIEW` | AP-04, AP-05, AP-07 | R-05/R-06, qualification gap | Codex; [evidence](audit-implementation-results.md): Official SSCD/model hash/max/timestamps; insertion hits and misses |
| AP-09 | Backend, units и reference policy calibration | P1 | `IN_REVIEW` | AP-04 | R-04/R-07, интерпретация результата | Codex; [evidence](audit-implementation-results.md): Backend units/raw/registered/HDR policy explicit |
| AP-10 | Исправить устаревшие тексты QA и комментарии | P1 | `IN_REVIEW` | AP-00 | R-04, подтверждённые расхождения | Codex; [evidence](audit-implementation-results.md): QA/calibration/SSCD/comments and CLI help reconciled |
| AP-11 | Описания и статус экспериментальных профилей | P2 | `IN_REVIEW` | AP-10 | R-08, compatibility | Codex; [evidence](audit-implementation-results.md): Experimental opt-in preserved; shipped YAML unchanged |
| AP-12 | Manifest и воспроизводимость экспериментов | P1 | `IN_REVIEW` | AP-00 | R-05, evidence infrastructure | Codex; [evidence](audit-implementation-results.md): Plans/seeds/hashes/commands/environment/resource records; failures retained |
| AP-13 | Качество temporal-эффектов и profile ablation | P1 | `IN_REVIEW` | AP-03, AP-05, AP-09, AP-12 | R-07, измерение деградации | Codex; [evidence](audit-implementation-results.md): 16 temporal ablations +8local second-generation encodes; crop DAR fix +positive aspect-control review; blind acceptance AP-21 |
| AP-14 | Внутренний A/V sync и слышимые аудиоэффекты | P1 | `BLOCKED` | AP-05, AP-07, AP-12 | R-07, natural alignment gap | Codex; [evidence](audit-implementation-results.md): 48 native-rate PCM observations; phase/mono/DC/sample peaks, envelopes/seams; Haas mono loss identified; Serafim: 11 applicable audio5/5, no observed mismatch in labelled previews; mono/full event review remains missing (AUDIT-G02) |
| AP-15 | Перепроверить и закрыть VFR keyframe origin | P1 | `IN_REVIEW` | AP-00 | Исторический OPEN-риск, требует revalidation | Codex; [evidence](audit-implementation-results.md): Native ffprobe 5.1/6.0/9.0.1 origin fixed; 15 integration checks each on 5.1/6.0; legacy duration fixed; full 5/6 encoder stacks NOT VERIFIED |
| AP-16 | Идентичность каналов surround | P2 | `IN_REVIEW` | AP-12, AP-14 | Исторический qualification gap | Codex; [evidence](audit-implementation-results.md): Distinct stereo/5.1 markers + tagged natural mix; unknown speaker warning |
| AP-17 | Подготовить disk/resource budget для квалификации | P1 | `IN_REVIEW` | AP-00 | Исторический отказ admission | Codex; [evidence](audit-implementation-results.md): One 180-minute case complete; default reserves/40 GiB reference cap retained; encode/QA RSS, temporary bytes and guard observations recorded |
| AP-18 | Pilot: 6 клипов × 3 профиля × 3 seed | P1 | `IN_REVIEW` | AP-03, AP-06, AP-08, AP-09, AP-13, AP-14, AP-15, AP-17 | R-05/R-07, новый эксперимент | Codex; [evidence](audit-implementation-results.md): Final 54-cell pilot on fixed core + calibration probe/full-file comparison |
| AP-19 | Корпус 20 development + 10 holdout | P1 | `IN_REVIEW` | AP-12 | R-05, подготовка данных | Codex; [evidence](audit-implementation-results.md): 20 development +10 disjoint-family holdout; 90 identity pair labels |
| AP-20 | Независимая оценка detector/quality/resource metrics | P1 | `IN_REVIEW` | AP-18, AP-19 | R-05, qualification | Codex; [evidence](audit-implementation-results.md): Dev-frozen thresholds; 60 original +30 unrelated pairs; cost/uncertainty |
| AP-21 | Human A/B review и обоснованные quality bands | P1 | `BLOCKED` | AP-13, AP-14, AP-20 | R-07, human evidence gap | Codex; [evidence](audit-implementation-results.md): Blind stereo/3 mono pairs, reveal key/protocol prepared; 3 label CSV hashes unchanged; First labelled review: Serafim,12 visual ratings; blur in01–05, aspect loss confirmed; blind/mono bands still missing (AUDIT-G02) |
| AP-22 | Ограниченная политика bitrate/quality/size | P2 | `BLOCKED` | AP-09, AP-19, AP-20, AP-21 | Исторический source-VBV tradeoff | Codex; [evidence](audit-implementation-results.md): Private selector and offline tool implemented/tested; 12 outputs freshly re-scored; 2 explicit budget scenarios; human/held-out/application acceptance missing; defaults retained |
| AP-23 | Новая full-file квалификация длинных видео | P1 | `IN_REVIEW` | AP-03, AP-06, AP-07, AP-09, AP-14, AP-15, AP-17, AP-18 | Аудит §9, historical gap | Codex; [evidence](audit-implementation-results.md): Fresh 180-minute output, CLI QA exit0, full decoded timeline/PSNR/loudness; valid correctness/red raw quality; 95-minute case excluded by user, human acceptance open |
| AP-24 | Natural HDR и аппаратная qualification matrix | P2 | `BLOCKED` | AP-12, AP-15, AP-17, AP-18 | Аудит §9, hardware/HDR gap | Codex; [evidence](audit-implementation-results.md): 5 files rechecked for 10-bit/PQ/BT2020/decode/PTS; derived source/output static HDR metadata match in prefix; original timing/static metadata, missing devices/human remain unverified (AUDIT-G03) |
| AP-25 | Scene-aware sampling / segment localization | P2 | `IN_REVIEW` | AP-20 | R-09, исследовательская гипотеза | Codex; [evidence](audit-implementation-results.md): Scene comparison +6 known short inserts; retain defaults, no continuous localization claim |
| AP-26 | Монтажный workflow: EDL, narration, B-roll | P2 | `IN_REVIEW` | AP-00 | R-10, условное расширение продукта | Codex; [evidence](audit-implementation-results.md): specs/30 editorial design; MVP/reuse/criteria + EDL-01…08 backlog; first step only |
| AP-27 | Контролируемое платформенное наблюдение | P2 | `DEFERRED` | AP-18 | Дополнительный внешний эксперимент | Codex; [evidence](audit-implementation-results.md): Conditional platform observation not run; owner/reference/baseline match not configured |
| AP-28 | Приёмка пакетов, quality gates и обновление evidence | P1 | `IN_REVIEW` | Готовый пакет; итоговый scope AP-01…AP-24 | Delivery gate | Codex; [evidence](audit-implementation-results.md): Geometry fix/policy v8,95focused +4B3 checks; fresh make check2154/55, unit-only core coverage82.09%; wheel/docs passed; owner/external acceptance remains open |

### Где выполнять изменения

Префикс `core/`, `cli/`, `gui/`, `web/` здесь означает подкаталог
`src/video_uniquifier/`. Файлы ниже существуют на baseline; новые helpers/tests
добавляются только по потребности задачи, с соблюдением структуры проекта.

| Задачи | Основные места реализации и проверок |
|---|---|
| AP-01…AP-03 | `core/calibration/intensity.py`, `core/calibration/loop.py`, `core/transforms/`, `tests/unit/test_intensity_scaling.py`, `tests/unit/test_calibration_v2.py`, `tests/integration/test_calibration_v2_ffmpeg.py` |
| AP-04…AP-09 | `core/models.py`, `core/qa/cid_predict.py`, `core/qa/phash.py`, `core/qa/audio_fp.py`, `core/qa/sscd.py`, `core/qa/report.py`, `core/qa/quality.py`, `core/qa/registration.py`, `cli/cmd_qa.py`, `cli/cmd_calibrate.py`; соответствующие unit/integration и `tests/contracts/` |
| AP-10, AP-11 | `docs/qa_report.md`, `docs/calibrate.md`, `docs/sscd.md`, `docs/profiles.md`, `docs/transform_reference.md`, `core/transforms/video_geom.py`, `core/transforms/video_subpixel_sharpen.py`, `core/transforms/audio_noise_overlay.py`, `core/audio_windows.py`, `src/video_uniquifier/profiles/` |
| AP-12, AP-17…AP-24 | `tools/benchmark.py`, `tools/natural_corpus.py`, `tools/rate_control_experiment.py`, `tools/hardware_qualification_report.py`, `BENCHMARKS.md`, `RISK_REGISTER.md`; `tests/integration/` и выбранный внешний каталог результатов |
| AP-13…AP-16 | `core/pipeline.py`, `core/segmenter.py`, `core/transforms/`, `tests/integration/test_temporal_jitter_pts.py`, `tests/integration/test_vfr_segmentation.py`, `tests/integration/test_surround_event_identity.py`, `tests/unit/test_keyframe_cache.py` |
| AP-25…AP-27 | Existing QA/scene detection, RFC в `specs/` при новом контракте, `docs/validation_harness.md`; сначала design/evaluation, затем выбранный implementation scope |
| AP-28 | `Makefile`, `tests/contracts/`, `docs/api-contracts.md`, `CHANGELOG.md`, qualification docs и этот реестр |

## 4. Карточки пакета A: исправления калибровки

### AP-01 — дискретные параметры

**Проблема:** `scale_profile(cid_aware, 0.7/0.75/1.5)` создаёт дробный
`video.subpixel_sharpen.radius`; реальная schema возвращает `int_from_float`.

**Сделать:** сначала failing regression на настоящем YAML; определить округление
и допустимые значения дискретных параметров, соблюсти clamp и требования filter
kernel, проверить границы. Исправить внутренний scaler без изменения public schema.
Проверить, нужна ли инвалидация scored-trial cache при изменении effective profile
или правил поиска; старое evidence не должно подменить новое измерение.

**Область:** `core/calibration/intensity.py`, реальная sharpen schema,
`tests/unit/test_intensity_scaling.py`, calibration/cache tests.

**Приёмка:** перечисленные factors проходят transform validation и `build_plan`;
целые параметры сохраняют требуемый тип, допустимый диапазон и kernel semantics.
Regression падает на старом коде и проходит после исправления.

### AP-02 — реальные поля и физический смысл силы

**Сделать:** составить mapping «масштабируется / участвует в поиске / фиксирован»
для `luma_amount`, `blackout_prob/drop_prob`, compand `ratio/threshold_db`, reverb
`intensity`, `noise_db`, EQ `jitter_db`, Haas `randomize_within_ms` и остальных
реальных полей. Удалить зависимость проверок от вымышленных legacy keys.
Для noise dB и compand определить движение к нейтральному эффекту; умножение
отрицательных dB на factor не считается автоматически корректным ослаблением.
Фиксированные эффекты объявлять явно, а не обещать четверть силы всего стека.

**Приёмка:** при 0.25/1/4 меняются именно выбранные настоящие поля, neutral direction
обоснован, disabled transforms не включаются. Изменения воспроизводимы; каждый
кандидат валиден. Изменение shipped YAML само по себе в этот fix не требуется.

### AP-03 — кандидат, поиск, сохранение и resume

**Сделать:** проверить все 16 shipped-профилей на anchors, дробных search factors
и ограничениях реальных schemas; затем bounded ffmpeg smoke на подходящих fixtures.
Проверить baseline/bounds/intermediate trial, feasible/non-feasible outcome,
ошибку evaluator, сохранение effective profile и повторный запуск с cache/resume.
Fixtures HDR, subtitles, second video или нужные filters предоставляются явно;
unsupported не превращается в фиктивное прохождение.

**Приёмка:** candidate → schema → plan → render → scoring проходит для заявленной
матрицы; resume не переиспользует несовместимые trials. CLI и существующий GUI
worker используют один исправленный core. Тесты проверяют реальный результат.

## 5. Карточки пакета B: корректные измерения и объяснения

### AP-04 — контрактный дизайн

**Сделать:** проверить, что уже покрывают существующие nullable metrics,
`QARegistration`, `correctness/loudness/quality_policy` и notes. Не реализовывать
эти существующие механизмы заново. Описать минимальную схему availability,
coverage/time provenance, единиц и metric/domain labels; определить старое JSON/CLI
поведение и миграцию. Для новых stable fields, CLI flags, profile identifiers
использовать RFC-процесс; внутренний helper не требует RFC.

**Приёмка:** сохранено решение по каждой затрагиваемой поверхности и classification
PATCH/MINOR/MAJOR. Если нужен RFC, он принят перед соответствующей реализацией;
совместимость, snapshots/API docs/CHANGELOG включены в её scope. Основание:
[API contracts](api-contracts.md), [CONTRIBUTING.md][contributing].

### AP-05 — отсутствие метрики не равно нулю

**Сделать:** различить missing `fpcalc`, отсутствующую audio track, silence,
ошибку extraction, отсутствующие ML dependencies/model, unsupported domain и
успешное числовое измерение. Сохранить корректные нулевые значения. Отдельно
проверить влияние availability на objective калибровки и выбор кандидата.
Протянуть согласованный результат в JSON, HTML, CLI и существующие GUI/web views.

**Приёмка:** ни один failure/missing не даёт ложную успешную уникальность или quality;
все потребители показывают доступность/причину. Требуемая отсутствующая метрика
не проходит acceptance gate; default graceful behavior явно документирован.

### AP-06 — legacy окна и лимит аудио

**Сделать:** заменить недостоверное распределение fingerprint первых 600 секунд
по всему фильму на измерения с реальными timestamp/coverage либо явно ограниченный
режим. Проверить visual grid, остаток длительности, последние окна, короткий файл
и retiming. Не обозначать sampled coverage как полный анализ.
Проверить cache semantics version, когда меняются sampling/scored значения.

**Приёмка:** interval heatmap относится к действительно измеренным samples;
непроверенный хвост отмечен. Regression на файле >600 s или эквивалентном
управляемом fixture отличает начало от конца; есть короткий real-ffmpeg smoke.
Бюджет памяти/декодирования остаётся ограниченным.

### AP-07 — alignment и независимые события

**Сделать:** исследовать offset/speed/drift alignment visual/audio в пределах
заданного resource budget, сохранить confidence/coverage и failure reason.
Сверить результат с известными импульсами и scene events, включая начало,
середину, конец и window seams. Не вычислять внутренний lip sync из одних endpoints.

**Приёмка:** известные сдвиги и time scaling обнаруживаются в заявленной точности;
неоднозначный материал не получает уверенный alignment. Границы сравнения и
threshold rationale записаны; natural content проверен отдельно от синтетики.

### AP-08 — SSCD и локальные похожие участки

**Сделать:** сохранить model hash, preprocessing, sampling timestamps, количество
пар и coverage. Оценить worst/highest-similarity evidence и необходимость segment
aggregation; current mean/min не объявлять полной локализацией. Старые поля
сохранять согласно AP-04. Измерить дополнительные decoder/model costs.

**Приёмка:** если известная похожая вставка попадает в sampling grid, показывается
её local similarity с timestamp, а не только mean/min. Для вставки между samples
фиксируется ограничение coverage/пропуск, без обещания обнаружить любой короткий
участок; полная локализация остаётся AP-25. Unsupported/missing видны. Результат
называется SSCD diagnostic, не человеческим quality score и не воспроизведением
Content ID.

### AP-09 — calibration backend и reference domain

**Сделать:** явно описать, что legacy `chromaprint` mode сейчас смешивает pHash/audio,
а SSCD objective другой. Развести raw quality, registered encode-quality и reference
в `target_vmaf` retry; определить поддержанные domains и backend-specific thresholds.
Сохранить один backend/domain внутри поиска. Не включать запрещённые crop/retiming
режимы retry без корректного reference и отдельной квалификации.

**Приёмка:** отчёт указывает алгоритм, units/backend/domain и почему кандидат прошёл;
не сравнивает SSIM×100 с VMAF как одну шкалу. При отсутствии корректного reference
есть unsupported, а не подмена. Требуемые CLI/schema изменения проходят AP-04.

### AP-10 — sweep документации и комментариев

**Сделать:** исправить `docs/qa_report.md`: «ещё не реализовано», weighted-vs-max,
Jaccard byte-identity, Hamming/perception, SSCD human-review interpretation.
Проверить абсолютные заявления mirror в `video_geom.py`, extrapolation audio paper
→ sharpen video, исторические noise/CID threshold и `audio_windows.py` гипотезы.
Объяснить `weakest_chunk = argmax similarity` и compatibility имя
`match_probability_self`. Позднее синхронизировать текст с AP-05…AP-09.

**Приёмка:** описание соответствует текущему коду; научные ссылки поддерживают
именно заявленное утверждение; нет обещаний внешнего предсказания. Strict docs build
проходит. Исторический отчёт аудита не переписывается под исправленную ревизию.

### AP-11 — экспериментальные профили

**Сделать:** проверить описания `cid_*` и aggressive, compound warnings и сохранение
opt-in scope. Описать, что остаётся fixed при calibration и какое quality evidence
есть. Если решено переименовать/изменить профили, сначала migration/RFC; старые
идентификаторы и данные не удалять в обычной правке документации.

**Приёмка:** пользователь видит назначение и ограничения; настройки default не
усиливаются ради similarity. Contract snapshots согласованы при фактическом
изменении shipped profiles.

### AP-12 — manifest исследования

**Сделать:** использовать существующие benchmark/natural-corpus helpers, не создавать
второй pipeline. Сохранять source/output hashes, разрешённое происхождение,
commit, effective profile, seed, toolchain/model versions, hardware, timestamps,
metric availability/domain, budget, actual commands и результаты.

**Приёмка:** другой запуск воспроизводит условия; пропуск/ошибка не теряется из
таблицы. Новая evidence записывается в отдельный каталог; исторические артефакты
не перезаписываются. Manifest — исследовательский/internal формат, пока не принят
public contract.

## 6. Карточки квалификации: пакеты C/D

### AP-13 — temporal damage и ablation

**Сделать:** baseline encode → один эффект → обоснованные комбинации на одинаковых
source/seed/toolchain. Проверять blackout/drop, motion/text details, кадры/PTS,
24/30/60 FPS/VFR, размер и вторичное кодирование. Развести потери эффекта и encode.

**Приёмка:** сохранены измерения и доступные для A/B образцы; similarity reduction
не скрывает flicker/judder/crop loss. Профильная рекомендация основана на измерениях,
не на количестве фильтров.

### AP-14 — звук и A/V

**Сделать:** сравнить речь/музыку, pitch/EQ/compand/reverb/noise/Haas, window seams,
true peak/LUFS, mono compatibility и natural event timing. Проверить 44.1/48 kHz,
tempo и delayed audio. Сохранить исправленные clock/padding/headroom guards.

**Приёмка:** event/envelope evidence дополняет fingerprints; начало/середина/конец
сверены, диапазон timing error установлен заранее. Низкий Jaccard не оправдывает
неразборчивость или фазовое исчезновение речи; есть listening review.

### AP-15 — VFR keyframe origin

**Сделать:** воспроизвести retained OPEN-риск из risk register на текущей ревизии
и доступных FFmpeg 5/6/9. Проверить совместный frame scan/start-time, независимый
pre-scan origin, offset origins и cache schema. Если дефект подтверждён — failing
fixture, отдельный probe origin и инвалидация несовместимого cache.

**Приёмка:** planner получает реальные keyframe boundaries, сохраняет CFR/VFR
seams/PTS и не использует подставленные boundaries вместо проверки planner.
Если риск не воспроизведён, сохранить доказательства и точный version scope,
а не объявлять универсальное исправление.

### AP-16 — surround speakers

**Сделать:** проверить tagged 5.1 и ambiguous untagged input, speaker-specific
markers и actual mux/encode layout. Для неустановленного расположения определить
явный diagnostic/early-reject путь по действующему контракту.

**Приёмка:** проверены позиции конкретных каналов, не только число каналов;
неизвестная speaker identity отмечена. Существующая multitrack policy сохранена.

### AP-17 — ресурсы

**Сделать:** измерить доступное место, workspace/final/reference reserves, временный
рост, процессное дерево RAM/CPU, tool availability и budget выбранной матрицы.
Учесть одно-/двухкопийный registered reference и retimed physical concat guard.
Подготовить достаточный scratch/results storage для AP-18/AP-23/AP-24.

**Приёмка:** получен capacity report и воспроизводимая конфигурация; admission
guards сохранены. Исторический отказ из-за диска не объявляется нынешним `BLOCKED`
без нового измерения; чужие данные не удаляются ради benchmark.

### AP-18 — 54-result pilot

**Сделать:** выбрать 6 разрешённых клипов с SDR/HDR, FPS/VFR, speech/music/silence,
разной динамикой; 3 подходящих профиля × 3 seed. Сохранить каждый исход, включая
отказы. Сравнить calibration samples и full-file QA готовых кандидатов.

**Приёмка:** 54 комбинации учтены без silent skips; каждый success имеет correctness,
metric availability, domain и manifest. Unsupported combinations не названы
успешным render. После pilot зафиксировать, достаточно ли evidence для перехода.

### AP-19 — development и holdout

**Сделать:** подготовить 30 разрешённых клипов: 20 development, 10 holdout.
Разделить по произведениям/семействам, добавить unrelated negatives и похожие,
но разные сцены; сохранить labels и source rights/provenance. Зафиксировать split
до подбора параметров, не использовать holdout как tuning set.
Исходники pilot и любого предыдущего tuning исключить из holdout по семействам.

**Приёмка:** manifest проверяется existing corpus tools; нет утечки одного master
между split. Данные/labels доступны для повторения, большие media не коммитятся
в репозиторий; результатов эксперимента пока не приписывают подготовке корпуса.

### AP-20 — независимое измерение

**Сделать:** оценить local copy detection precision/recall и при наличии segment
labels localization; сравнить pHash, SSCD и audio подходы, raw/registered quality,
wall time, process-tree peak RSS, disk и output size. Параметры выбрать на development,
после чего один раз оценить зафиксированную конфигурацию на holdout.

**Приёмка:** результаты по типам контента, negative pairs, failures и uncertainty
опубликованы; proxy tuning не выдаётся за независимую проверку. Это qualification
локальных detectors, а не статистика обхода YouTube.

### AP-21 — human review

**Сделать:** определить протокол слепого A/B/прослушивания, конкретные labels для
speech, motion, gradients, text, flashes и sync; записать reviewer и условия.
Установить quality bands на development; проверить их на holdout, сохранить
расхождения метрик с оценкой людей.

**Приёмка:** критерии объяснимы, scope ограничен корпусом и domain; SSCD/Hamming
не подменяют человеческое восприятие. При новом tuning получить новый независимый
split/evaluation, не подгонять старый holdout.

### AP-22 — bitrate/size

**Сделать:** расширить существующий paired rate-control experiment по отдельным
произведениям и native HDR/SDR; определить bounded quality/size policy вместо
слепого удаления source-derived VBV cap. Проверить disk admission и CRF/encoder
совместимость для каждой выбранной стратегии.

**Приёмка:** показаны quality, output size, runtime и tradeoff; подтверждение на
held-out families и human labels. Defaults меняются только по обоснованному
результату; конкретное contract/compatibility решение записано.
Политика выбирается на development; если результат прежнего holdout повлиял
на её настройку, для новой приёмки нужен новый независимый split.

### AP-23 — длинные файлы

**Сделать:** запустить новые разрешённые длинные материалы на pinned
commit/toolchain, без изменения processing pipeline посреди попытки. Scope обновлён
2026-10-05 по указанию пользователя: только 180.4-minute archival; 95-minute
материал исключён до обработки. QA-only corrections после encode имеют отдельные
snapshot/identity; encoder/transforms/profile/Plan не менялись. Full decode всех
заявленных A/V streams, frame/sample/PTS/seam evidence, registered QA при бюджете,
event checks и listening начало/середина/конец; RSS/disk/time/output size.

**Приёмка:** есть новый output и его QA, не только source diagnostics. Отказ admission
не считается завершённой обработкой. Legacy 180-minute run и compact synthetic
hash stress не подменяют fresh full-film evidence. Native Linux/Windows scope
отмечается отдельно от Mac qualification.

### AP-24 — HDR и оборудование

**Сделать:** для доступных устройств определить matrix по encoder/device/driver/OS,
SDR/PQ/HLG, static metadata, VFR, transformed cadence и bitrate mode. Использовать
native-camera/independent HDR masters, где доступны; derived HDR обозначать явно.
NVENC/QSV/AMF проверять на настоящем соответствующем оборудовании.

**Приёмка:** подтверждены output bitstream, HDR metadata/color, cadence, decode и
human review для конкретных ячеек. Неисследованные — `NOT VERIFIED`; отсутствие
устройства не скрывается mock-тестом. При невозможности расширения scope сохранять
точную поддержанную матрицу, отражая ограничение в AP-28.

## 7. Условные направления и приёмка

### AP-25 — scene-aware и локализация

После AP-20 сравнить fixed и scene-aware sampling на одном замороженном корпусе,
проверить быстрые сцены, короткие вставки, temporal attacks, recall и затраты.
Продолжать реализацию только при измеренной пользе и явном budget.
**Приёмка:** опубликовано сравнение и решение adopt/reject; отрицательный результат
исследования тоже допустим. Новые public outputs проходят AP-04.

### AP-26 — редакционный workflow

Сначала описать потребность в EDL, narration, B-roll, PiP/masks и subtitle editing,
источники разрешённых assets, track/timing/reference policy и связь с существующим
core. Не считать segmenter готовым сюжетным редактором.
**Приёмка первого шага:** самостоятельный дизайн/RFC, scope MVP, reuse existing core,
criteria и отдельный implementation backlog. Полный редактор этим пунктом не
объявляется автоматически спланированным или созданным.

### AP-27 — платформенное наблюдение

Опционально продолжить existing [validation harness](validation_harness.md) на
собственных/разрешённых материалах. Если исследуется именно claim detection,
нужны соответствующий reference owner и подтверждённое baseline match; иначе
измерять только ingestion/transcode, не делать вывод об эффективности фильтра.
Хранить claimant/type/segments/territory/policy, время, все исходы. Контрольные
24 h/7 d/30 d — дизайн исследования, не официальные сроки или гарантия результата.
**Приёмка:** точный наблюдаемый исход без обобщения на все фильмы; отсутствие этого
эксперимента не препятствует локальным bugfix и QA qualification.

### AP-28 — общий Definition of Done

Для каждого выбранного пакета:

- Закрыты его acceptance criteria и сохранены evidence по commit/toolchain/scope.
- При изменении scored semantics, sampling или probe construction проверена
  инвалидация trial cache; прежние scores не подменяют новые. Fixed seed/search
  и resume воспроизводят те же кандидаты в неизменённых условиях.
- Пройдены focused regression и real ffmpeg smoke, когда меняется медиаповедение.
  Затем `make check` перед review; для public changes — contract snapshots,
  API docs и CHANGELOG; для GUI — принятые в проекте GUI/screenshot checks.
- `mkdocs build --strict` проходит; terminology/defaults соответствуют реализации.
- Проверены PR diff и compatibility; зафиксировано решение о неподдержанных cases.
- `BENCHMARKS.md`, `RISK_REGISTER.md` и актуальные operation docs обновлены фактами.
  Старое evidence остаётся привязанным к старой ревизии.
- Статусы данного файла и журнал обновлены; новые unresolved findings имеют
  собственный ID/следующий шаг. Зелёный CI не выдаётся за human/HDR/hardware evidence.

Финальная приёмка плана — все обязательные AP-01…AP-24 приняты либо scope изменён
с записанной причиной и новым статусом задач; AP-25…AP-27 остаются отдельно.
Номер следующей версии и release/tag этим планом не назначаются заранее.

Существующие supply-chain/SBOM и production NFS риски не закрываются данным аудитом.
Они остаются в [risk register][risks] и проверяются по [production plan][production]
в соответствующем delivery/deployment scope; никаких `RESOLVED` без evidence.

## 8. Журнал и следующий шаг

Пакет реализован в указанной ветке; финальный make check текущего кода прошёл
(2065 passed, 55 skipped), core coverage 86.73%. Реализованные пункты остаются IN_REVIEW до
приёмки; закрытые локальные проверки не заменяют human/device gates.
Исходные staged research-файлы пользователя сохранены. Peer/PR review ещё не
проводился. Human/device gates не заменяются автоматическими tests.

| Дата | Задача / событие | Статус | Доказательство / следующий шаг |
|---|---|---|---|
| 2026-10-04 | AP-00: завершён аудит | `DONE` | Historical probes и 114 focused tests |
| 2026-10-04 | Начало реализации | `IN_PROGRESS` | fix/audit-implementation-20261004; staged research сохранён |
| 2026-10-04 | Calibration/QA/VFR fixes | `IN_REVIEW` | Failing regressions затем passes; contracts сохранены |
| 2026-10-04 | AUDIT-N01/N02: noise | Fix + regression | Distinct stereo/5.1 выявили hidden downmix; layout и generator seed исправлены |
| 2026-10-04 | Corpus/pilot/ablation/detector | `IN_REVIEW` | Final 54-cell pilot повторён после noise fix; все исходы сохранены |
| 2026-10-04 | AP-17/AP-23: storage | `BLOCKED` | Fresh 95/180-minute admission refusals и после retirement новых дублей |
| 2026-10-04 | AP-14/AP-21/AP-22/AP-24 | `BLOCKED` | Assets готовы; actual reviewer/labels/native masters/devices отсутствуют |
| 2026-10-04 | AP-25/AP-26 | `IN_REVIEW` | Sampling comparison/reject decision; editorial design, implementation backlog |
| 2026-10-04 | VFR / legacy offset duration | Проверено | Реальные native probes 5.1/6.0/9.0.1; MP4 duration regression исправлен; metadata 33 study sources неизменна |
| 2026-10-04 | Финальный quality gate | Passed | make check: 2060 passed, 55 skipped, 1 warning; свежий core coverage 86.67%; review остаётся открытым |
| 2026-10-04 | AP-27 | `DEFERRED` | Owner/reference/baseline match не настроены; platform actions не выполнялись |
| 2026-10-04 | AP-17/AP-23: пользователь освободил диск | `IN_PROGRESS` | 69.47 GiB свободно; current snapshot и SHA masters проверены; fresh natural-corpus run начат, guards сохранены |
| 2026-10-05 | AP-17/AP-23: уточнение scope пользователем | `IN_PROGRESS` | 95-минутный фильм не запускать; original two-case runner приостановлен до перехода к нему; scope ограничен первым output |
| 2026-10-05 | Пользователь попросил остановиться до завтра | Пауза по запросу | Все processing/continuation jobs остановлены; новый 180-minute output/Plan/benchmark/source timeline/logs сохранены; QA неполный, partial scores не объявляются результатом; resume только по новому указанию |
| 2026-10-05 | Пользователь возобновил работу | `IN_PROGRESS` | Source/output/implementation SHA совпали; запускается только QA сохранённого 180-minute output и недостающие diagnostics; 95-minute case остаётся NOT RUN |
| 2026-10-05 | AP-24: bounded master-origin PQ | `BLOCKED` (partial evidence) |24 publisher HDR frames, authored 24fps proxy; libx265/VideoToolbox: correctness valid, quality warning; no HDR-display/original timing/static-metadata acceptance |
| 2026-10-05 | AP-17/AP-23/AP-28: long QA выявил дефект | `IN_PROGRESS` | Registered VMAF не передавал long-form subsample; рост swap и free-disk ниже 9 GiB потребовали остановки только QA. Failed exit/resources сохранены; добавлена регрессия, policy передаётся; новый full-file metric и полный make check запущены |
| 2026-10-05 | AP-23/AP-28: ложный metric watchdog | `IN_PROGRESS` | Cancellable VMAF/SSIM отключали progress, поэтому active FFmpeg считался stalled через600s. Portable null output и progress исправлены;2 before-fix failures,92 focused checks passed; новый snapshot6180ebd9 и full gate |
| 2026-10-05 | AP-28: текущий full gate | `IN_REVIEW` | 2065 passed, 55 skipped,1 warning; Ruff/mypy165files; independent core combined coverage 86.73%; installed-wheel profiles/templates/QA-source equality passed; на момент этого gate long CLI QA ещё выполнялся; завершение записано ниже |

| 2026-10-05 | AP-17/AP-23: разрешённая full-file квалификация | `IN_REVIEW` | 180.4min; fresh encode 4340.26s; CLI QA exit0, 3944.17s /10042992KiB; registered VMAF 94.454314; raw quality red; output full decode/PSNR/loudness complete,18 audio seams/3 listening windows; 95-minute case NOT RUN |

| 2026-10-05 | Очистка repository exports по запросу пользователя | Проверено | 63 dated study files сохранены в локальном ZIP и сверены по SHA-256; 62 generated YAML/JSON удалены из Git, краткая запись оставлена в validation-corpus/audit-20261004/README.md; code/tests/research и original media/results сохранены |

| 2026-10-05 | AP-14/AP-21/AP-22/AP-24: дополнительная техническая работа | Partial evidence; внешние gates `BLOCKED` | 48 PCM observations, 3 mono A/B pairs; labels unchanged; private policy selector/tests and12fresh VMAF comparisons; 5 HDR decode/metadata observations; defaults preserved |
| 2026-10-05 | AP-28: developer diagnostics review | `IN_REVIEW` | Fixed truncated hardware probe and missed secondary video streams; real regressions;70focused checks; fresh full gate/package/docs recorded in results |
| 2026-10-05 | AP-28: current source snapshot gate | `IN_REVIEW` | make check2118passed/55skipped/1warning,1019.60s; strict mypy167files; independent unit core coverage82.11%; source/profile/template installed-wheel equality; owner acceptance open |
| 2026-10-05 | AP-24: явно включённые VideoToolbox tests | Partial hardware evidence; `BLOCKED` | H.264/HEVC strict hardware:18passed/3AV1skips/37deselected; VFR/HLG/UHD/parallel/cancel/static-HDR refusal; original masters/display/other devices still unverified |

| 2026-10-05 | AP-14/AP-21: первый фактический пользовательский просмотр | Partial evidence; `BLOCKED` | Serafim/MacBook,12 labelled SDR previews; five visual3/5 with blur, seven5/5; 11 applicable audio5/5; no mono/blind/full-file acceptance |
| 2026-10-05 | AP-13/AP-28: диагностика размытия и сужения | Quality follow-up `OPEN` | All five ToS inputs non-square SAR2883:2288; crop_resize forces1:1, DAR2.24 becomes1.78–1.80; five metadata-only controls verified1008/1008decoded frames; product correction/native-resolution review pending |

| 2026-10-05 | AP-13/AP-28: принятие aspect controls и core fix | `IN_REVIEW` | User «все хорошо» for five controls, no numeric scores inferred; crop preserves source DAR, explicit destination canvas keeps dimensions/SAR1; policy v8; real regression/native excerpt checks; final full gate recorded in results |

Исправление non-square geometry выполнено и прошло финальный full gate.
Пять контрольных MP4 положительно оценены пользователем; числовые оценки из
этого ответа не выводятся. На пяти fresh proxies1008decoded frames byte-equal
старым retained outputs; native1920×858eight-second excerpt и elementary H.264
aspect также проверены. Полный blind/mono review и утверждение quality bands
остаются отдельной приёмкой. Повторная оценка всего pilot/holdout не выполнялась.

| 2026-10-05 | AP-13/AP-28: финальные gates geometry fix | `IN_REVIEW` | make check2154passed/55skipped/1warning,1057.64s; core unit coverage82.09%; source/wheel equality; positive qualitative controls; fingerprint5bafc777; old v7 study scores retained |

Дальнейшие шаги, требующие внешних данных или приёмки:

1. AP-14/AP-21: провести настоящий blind A/B/listening/event review по готовым
   материалам, заполнить blind/mono labels. Первый labelled review уже получен;
   перепроверить чёткость после устранения aspect loss, raw quality red и source audio EOF gap;
   автоматические scores не закрывают слуховую оценку или lip-sync.
2. AP-22: private experimental selector уже реализован и проверен. После labels
   принять quality bands/bitrate policy и application integration через RFC.
   Tuning по holdout feedback требует нового независимого evaluation.
3. AP-24: получить original HDR timing/static metadata и actual devices/OS;
   выполнить metadata/cadence/decode/human matrix. Непроверенные ячейки сохраняют
   NOT VERIFIED; короткий master-origin proxy не закрывает весь HDR scope.
4. PR/owner review пакета и evidence, затем приёмка AP-28. AP-27 остаётся
   DEFERRED до появления owner/reference/baseline и отдельного решения.
   Release/tag этим планом не назначается. 95-минутный фильм не запускать.

## 9. Прослеживаемость рекомендаций

| Основание | Покрытие в плане |
|---|---|
| R-01: fractional integer scaling | AP-01, AP-03 |
| R-02: actual transform parameter mapping | AP-02, AP-03 |
| R-03: metric availability | AP-04, AP-05 |
| R-04: QA names/docs/backend semantics | AP-04, AP-09, AP-10 |
| R-05: independent qualification | AP-08, AP-12, AP-18…AP-20 |
| R-06: windows/coverage/alignment | AP-06…AP-08, AP-14 |
| R-07: temporal/audio quality | AP-09, AP-13, AP-14, AP-21 |
| R-08: legacy experimental profiles | AP-11 |
| R-09: scene-aware/localization research | AP-25 |
| R-10: editorial workflow | AP-26 |
| Аудит §9: long-form, VFR, surround, VBV, HDR/hardware | AP-15…AP-17, AP-22…AP-24 |
| Рекомендации §5: controlled platform observation | AP-27 |
| Контракты и текущие production evidence | AP-04, AP-28 |

[production]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/PRODUCTION_PLAN.md
[risks]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/RISK_REGISTER.md
[contributing]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/CONTRIBUTING.md

Начало реализации: 2026-10-04; исходные staged research-файлы сохранены.
