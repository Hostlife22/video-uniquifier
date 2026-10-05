# Реализация аудита: результаты и границы проверки

Дата обновления: **2026-10-05**. Ветка: `fix/audit-implementation-20261004`.
Baseline HEAD: `03c707a5c4a68397511cb38f881335a00990f271`, версия 2.0.0.
Реализация находится в рабочем дереве; baseline SHA **не обозначает код новых encodes**.
[План и статусы](implementation-plan.md), [совместимость и решения](audit-implementation-decisions.md).

Последнее дополнение — «Принятие контрольных роликов и исправление геометрии»:
пользователь положительно оценил пять контролей; core crop сохраняет исходный
DAR, destination canvas — свой aspect; encode policy v8 исключает старые artifacts.
Earlier matrix/long результаты и gates привязаны к своим историческим snapshots.

2026-10-05 полный QA обнаружил ещё один дефект: registered VMAF не получал
long-form subsample. После роста swap и падения свободного диска ниже 9 GiB
проход остановлен; exit −15 и метрики ресурсов сохранены. Добавлена регрессия
и передача существующей sampling policy. Следующий full-file тест обнаружил
ложный 600-second stall watchdog: cancellable VMAF/SSIM отключали progress.
Теперь null output использует os.devnull, runner получает progress; two watchdog
regressions падают до исправления и проходят после. 92 focused checks прошли;
Новый full gate2065/55 и разрешённая full-file квалификация180.4min завершены;
correctness valid, raw quality verdict red, human acceptance открыта.
Результат 2060/55 ниже относится к снимку **до** этой дополнительной коррекции.

## Исправленные ошибки

- Scaler работает с настоящими параметрами transforms и defaults schemas.
  Нечётный sharpen radius сохраняет целый тип, bounds и kernel semantics.
  До исправления 17 проверок на настоящих профилях падали; после — все 107 проходят.
- Compand движется к ratio 1; noise dB изменяется через линейную амплитуду.
  Disabled эффекты не включаются. Fixed conversions/targets и неполный bypass
  compand/noise явно описаны. Все 16 shipped YAML проходят validation/build_plan.
- Отсутствующая similarity/audio/SSCD не превращается в успешный ноль.
  Calibration прерывается при отсутствии требуемого audio fingerprint;
  video-only источники допускают явно visual objective.
- Legacy visual heatmap ограничена реальным общим prefix до 600 секунд.
  Aggregate audio не получает вымышленные chunk timestamps; остаток длительности
  учитывается, хвост обозначается как unmeasured.
- Constant fingerprints и static/invalid SSCD matrices не устанавливают уверенный
  offset/drift. Длинная stratified audio concatenation не выдаёт clock искусственной
  склейки за physical timeline. Natural retention и lip-sync остаются разными проверками.
- SSCD report сохраняет sampled maximum, requested timestamps, число пар,
  официальный model hash и preprocessing. Между samples возможен пропуск вставки.
- Raw HDR VMAF не вычисляется стандартной SDR-моделью. Calibration сообщает
  backend, units и raw reference; SSIM×100 и VMAF не объявляются одной шкалой.
- VFR origin читается независимым pre-scan probe. Реальный fixture на
  ffprobe 5.1, 6.0 и 9.0.1:
  первоначальный start=0, совместный старый scan сообщал start=2.803 s;
  правильные keyframes — 0 / 0.834 / 1.668 / 2.503 / 3.337 s.
  Integration проверяет настоящий planner вместо подстановки boundaries.
- Новая проверка каналов обнаружила mono downmix в `audio.noise_overlay`:
  count сохранялся, speaker signals терялись. Noise branch теперь получает layout
  входа, а генератор — seed из run RNG. Регрессия падает до исправления и проходит
  после для stereo и tagged 5.1; повторные encodes дают одинаковый decoded PCM.
  Unknown surround layout остаётся явно unverified.
- Trial/keyframe caches переходят на schema 3; scores привязаны к executable/model
  identity. Encode policy v7 исключает reuse старых segments и scored plans после
  исправления noise. Stable schemas, exports, CLI options и shipped presets сохранены.

## Проверки кода

Первые общие проверки завершились с **2022 passed, 55 skipped**. Это предварительный
результат: обнаруженный позднее noise defect потребовал нового regression и нового
полного запуска. Промежуточный `make check` и QA refresh были остановлены с сохранением
логов; они не считаются финальными успешными запусками.

**Окончательный `make check` на новом metric-corrected snapshot прошёл:
2065 passed,55 skipped,1 warning за1517.47s (25:17). Ruff и strict mypy passed;
165 source files.** Core combined line/branch coverage на новой отдельной базе:
**86.73%**, порог80% пройден. Лог:
`logs/video-uniquifier-audit-check-metric-final-20261005.log`;
`metric-final-coverage.json`, без append старых данных.
Предыдущие2060/55,86.67% относятся к снимку до двух дополнительных QA-исправлений.
Два остановленных промежуточных full gates после sampling-only фикса не считаются
финальными;92 focused checks и установленный wheel проверены на metric-corrected snapshot.

Отдельно подтверждены:

| Проверка | Результат / scope |
|---|---|
| Shipped-profile scaler | 107 passed; 16 профилей × anchors/fractional factors и parameter regressions |
| Real calibration + все scaled build_plan | 20 passed; search, сохранение YAML, cache/resume |
| CFR/VFR, temporal PTS, labelled 5.1 events | 18 passed; реальные FFmpeg fixtures |
| SSCD, включая официальный real backend | 42 passed |
| Noise identity/layout/windowed regressions | 39 passed; два actual encode/replay для каждого speaker fixture |
| Ruff / strict mypy | Passed; 165 source files |
| Contract snapshots / focused regressions | 274 passed; схемы не регенерировались |
| Полный unit scope + coverage | 1679 passed; preliminary core combined line/branch coverage 81.48%; итоговый full-suite результат — 86.73% на новой базе |
| GUI / accessibility | 27 widget checks + 12 accessibility checks passed; поздний focused scope 31 passed; native Qt screenshots сохранены в `gui/` evidence-каталога |
| Metric domain integration | 2 passed: настоящий 620-second fingerprint clock и derived HDR raw-VMAF guard |
| Wheel | Собран в отдельном каталоге; installed-wheel imports, template и 16 profiles ×3 factors passed; версия не менялась, release не публиковался |
| Study manifests | 10 lightweight manifests и их 10 local counterparts passed; sources существуют, development/holdout разделены |
| `mkdocs build --strict` | Passed на итоговой документации |

Skips сохраняются как skips, включая отсутствующее оборудование; зелёный pytest
не доказывает human acceptance, native HDR или платформенное обнаружение.

## Воспроизводимость и корпус

Использованы existing `benchmark`, `natural_corpus`, QA, calibration, media diagnostics,
listening и rate-control APIs. Новые tools готовят корпус и оценивают локальные
метрики; второго encode pipeline не создано.

Рабочий каталог evidence: `.qualification-current/audit-20261004/`.
Большие media не коммитятся. В `validation-corpus/audit-20261004/README.md`
сохранена краткая запись результатов и SHA-256 локального архива. Generated
manifests/profiles, source/derivation provenance, полные JSON и исходная инструкция
повторения перенесены в проверенный архив вне Git:
`.qualification-current/audit-20261004/archives/repository-study-export-before-cleanup.zip`.
Все 63 исходных файла сверены по SHA-256 и длине до удаления 62 новых выгрузок
из рабочего дерева и индекса. Для другого компьютера нужен этот архив и источники;
полная конфигурация эксперимента больше не поставляется с репозиторием.
Для каждого render доступны точный Plan, effective profile, run seed, source/output
SHA-256, команды, decode timeline, availability/domain, wall time, process-tree RSS
и sampled logical disk footprint. Подписанная release/новый commit не создавались.

Окружение: Intel macOS, Python 3.12.3, FFmpeg/ffprobe 9.0.1, fpcalc 1.6.1;
SSCD — официальный pinned checkpoint, Torch CPU с двумя threads для detector study.
Exact package versions, snapshot исходников и SHA каждого файла сохранены локально.
Первый pilot шёл во время QA/documentation fixes и имеет несколько implementation
hashes; он остаётся предварительным. Pilot повторён после исправления noise на
фиксированном core. Original render snapshot и финальный snapshot хранятся отдельно.
Поздние изменения CLI help/GUI и новый domain regression перечислены в
`implementation-final-identity.json`. В core позднее удалён неиспользуемый
fingerprint-slicing helper и исправлен legacy MP4 absolute duration endpoint.
AST действующих CID-функций совпадает; остальные core-файлы, кроме `probe.py`,
побайтово идентичны render snapshot. `finalize_identity.py` дополнительно сравнил
metadata всех 33 study sources старым и новым parser на pinned FFmpeg 9.0.1:
все идентичны. Новый parser меняет доказанный legacy offset case; corrected
SourceMeta входит в plan hash и не переиспользует ошибочный resume. QA/model
hashes не заменяют render provenance.

Корпус — **30 восьмисекундных 320×180 excerpts**, а не 30 независимых произведений:
20 development из двух семей (Tears of Steel/Meridian), 10 holdout из одной (Big Buck
Bunny). Split задан до tuning; pilot не содержит holdout family. Есть disjoint-window
и unrelated-work negatives. Animation/live action, 24/30/60 FPS, derived VFR и
silence/video-only представлены, но это маленький инженерный scope.

Meridian master — опубликованный untagged 8-bit P3/PQ файл; conversion assumptions
записаны. HDR10 fixture derived с явными BT.2020/PQ/static tags. Camera-native HDR,
полный современный фильм и native Windows/Linux этим корпусом не квалифицированы.
Attribution/source pages/license metadata сохранены в study `open-sources.yaml`:
[Blender Foundation / Tears of Steel](https://commons.wikimedia.org/wiki/File:Tears_of_Steel_in_4k_-_Official_Blender_Foundation_release.webm),
[Big Buck Bunny](https://commons.wikimedia.org/wiki/File:Big_Buck_Bunny_4K.webm),
[Netflix Open Content](https://opencontent.netflix.com/).

## Pilot и качество

Предварительный pilot: **54/54 measurement-complete**, correctness valid во всех
ячейках. Из 45 raw SDR quality verdicts все 45 — fail по действующему legacy VMAF
порогу; для девяти HDR→SDR raw VMAF unavailable. Это не 54 принятых по качеству renders.
Registered VMAF 94.689…96.358 измеряет encode относительно replay, не приемлемость эффектов.
Пример soft: raw 23.440 против registered 96.240; намеренные изменения сильно влияют
на raw metric. Ни один score не заменяет human review.

**Повторный pilot завершён: 54/54 measurement-complete, correctness valid.**
Manifest/source bytes сохранены; во время повторного pilot SHA всех core-файлов
совпадал с render snapshot. Full-src SHA тогда менялся только из-за CLI help;
поздние изменения отдельно перечислены в финальном identity, описанном выше.
Raw VMAF доступен для 45 SDR ячеек (0.888…53.805, median 20.005), registered — для
всех 54 (94.689…96.358, median 95.731). Sampled encode RSS 97,868…183,472 KiB;
QA RSS 184,628…233,180 KiB; encode wall 1.54…6.71 s, size ratio 0.288…5.222.
Это технически завершённые измерения; human/production acceptance не подтверждена.

Natural calibration завершена
на трёх development clips, 4 trial/clip, 6-second stratified probe. `min_quality=0`
используется лишь для измерения пути, не как production policy или quality band.
Все три searches исчерпали 4-trial budget без convergence при target=0.95;
факторы 1.224745 / 1.0 / 0.7, sample self-match 1.0 / 0.96875 / 1.0.
Выбранные профили сохранены и реально обработали полные 8-second inputs: 3/3
measurement-complete, full self-match 1.0, raw VMAF 28.845 / 33.533 / 48.610,
registered 96.281 / 94.915 / 95.902. Это демонстрирует отличие sampled objective
от full-file результата и отсутствие обещания convergence; best effort не выдаётся
за удовлетворённую цель.

Temporal ablation завершена: **16/16** outputs (24/30/60 FPS и VFR × baseline,
blackout, drop, combined+sharpen), полный decode/timeline. Raw VMAF 88.628…96.451;
registered 93.483…96.499. Преобразование и encode loss показаны раздельно.
Дополнительный local CRF23 transcode восьми baseline/combined outputs даёт VMAF
85.545…91.952 относительно immediate parent. Это дополнительная локальная генерация,
а не YouTube transcode. Monotonic PTS/длительность не устанавливают приемлемость flicker.

Audio ablation после исправления: **16/16** outputs, 44.1/48 kHz, baseline/pitch/EQ/
compand/reverb/noise/Haas/compound, исходный gain сохранён в float-WAV review excerpts.
Измеряются LUFS/dBTP, PCM finite/clipping, channel correlation, arithmetic mono energy
и 0/2.5/5 s envelope windows. Ambiguous envelope peaks остаются `not_verified`;
по ним нельзя объявлять сдвиг речи или исправленный lip-sync.

Tagged original 5.1 mix дополнительно прошёл новый natural render, QA и full decode.
Это supplement к известным speaker-labelled synthetic markers; listening acceptance
natural mix ещё отсутствует. Сохранение count/mask отдельно от speaker identity.

## Локальная copy-detection оценка

Параметры выбраны на development, затем заморожены перед holdout. Основной experiment:
30 positive и 30 disjoint-window negatives; supplement добавляет 30 unrelated-work
negatives **без retuning thresholds**. Label означает совпадение excerpt identity,
не semantic similarity, авторские права или решение платформы.

| Detector | Замороженный threshold | Holdout TP/FP/TN/FN | Precision / recall | Missing |
|---|---:|---|---|---:|
| pHash, 4 pairs | 0.90625 | 9 / 0 / 20 / 1 | 1.00 / 0.90 | 0 |
| SSCD, 4 midpoint pairs | 0.684735 | 10 / 0 / 20 / 0 | 1.00 / 1.00 | 0 |
| Aggregate audio Jaccard | 0.0 | 10 / 20 / 0 / 0 | 0.333 / 1.00 | 0 |

Development audio имеет 40 unavailable measurements в combined 60 rows: video-only
Meridian и пары с ним. Missing positives считаются missed, не успешным нулём.
Audio threshold=0 — результат слабого development разделения; он принимает любой
available score, включая ноль. Это свидетельство **непригодности выбранной настройки
как production detector**, а не хороший recall или новый рекомендованный threshold.

Original 60-pair study: 324.82 s, process-tree RSS 896,492 KiB; supplement 137.60 s,
857,492 KiB. Runs происходили рядом с тестами, wall times не являются isolated-host
performance comparison. Один holdout title и зависимые пары не дают population
confidence intervals или универсальных precision/recall.

Scene-aware experiment выбирает до четырёх midpoint самых длинных сцен (threshold 27).
На первоначальных holdout 20 pairs F1 1.0 против fixed pHash 0.9474; delta +0.0526.
Это достаточный preliminary comparison, но короткие вставки не размечены и sampling
longest-scenes может их пропускать. Решение: **не внедрять новый default**, сохранить
fixed sampling до более широкого независимого recall/decoder-budget исследования.
Дополнительно создано шесть natural-picture fixtures с известными вставками
150 ms / 500 ms / 2 s в другом development title. На requested grid 1/3/5/7 s
вставка 1.0…1.15 s даёт local cosine **0.998611** при mean лишь 0.226974;
report показывает maximum и requested timestamp. Вставка 0.2…0.35 s между grid
точками даёт maximum −0.003511: она пропущена. Ground-truth commands, hashes,
per-frame values и QA JSON/HTML сохранены. Scene comparison/known inserts позволяют
завершить исследовательский шаг AP-25 с решением retain/reject изменения default;
continuous segment localization этим экспериментом не реализована.

## Bitrate и оборудование

Rate-control: 12 six-second encodes, 4 clips двух development titles × source cap,
2× cap, CRF-only, одинаковый transformed reference. Все decoded contracts прошли.
Observed VMAF 87.817…95.738; bands являются описанием выборки, не quality gates.
В данном rate-control experiment human labels, новые семьи и native HDR отсутствуют; source-derived cap
не удаляется, production defaults не меняются.

| Ячейка | Результат |
|---|---|
| SDR 320×180/libx264 | encode + QA + full decode passed |
| Derived HDR10 static/libx265 | encode + QA + full decode; HDR raw VMAF unavailable |
| SDR 320×180/H.264 VideoToolbox | job-specific probe rejected; count как failure |
| SDR 640×360/H.264 VideoToolbox | новый retry encode + QA + full decode passed |
| Derived HDR10 static/HEVC VideoToolbox | preflight rejects unverified static metadata reinjection |
| NVENC/QSV/AMF, native-camera PQ/HLG, native Linux/Windows | NOT VERIFIED |

FFmpeg 5.1/6.0 Intel archives не удалось получить по проверенным provider URLs (404);
отказы сохранены. Затем из официальных release sources локально собраны минимальные
ffprobe 5.1/6.0 (H.264 decoder/parser, MOV/Matroska/file). На всех трёх probes
5.1/6.0/9.0.1 legacy combined scan меняет origin 0→2.803 s; исправленный planner
возвращает одинаковые пять keyframes и непрерывные segments. Source URLs, archive/
binary SHA-256, configure/make commands и raw probes сохранены в `toolchains/`.
Минимальные probes затем расширены AAC/FFV1/FLAC/PCM и concat/WAV support для
интеграционных checks; первоначальные component failures сохранены. Проверка
ffprobe 5.1 выявила отдельный absolute duration endpoint: offset MP4 сообщает
`format.duration=10.0` вместо span 5.021333. Normalization применяется только
при полном согласовании границ timed streams и origin. До исправления unit
regression и real offset encode падали; после — 25 probe unit checks и 15 real
integration checks с expanded ffprobe 5.1 passed. На expanded ffprobe 6.0
те же 15 checks passed. Кодеки encode/decode в этих hybrid tests — FFmpeg 9.0.1;
успех не переносится на полный FFmpeg 5/6 encoder stack.
Это расширяет qualification чтения timestamps; encodes/decode в этом пакете
используют FFmpeg 9.0.1. Полные encode toolchains 5/6 этим не квалифицированы.

## Дополнительный HDR master-origin тест — 2026-10-05

Получены 24 последовательных TIFF кадра №1200…1223 из Sparks (2017),
[Netflix Open Content](https://opencontent.netflix.com/), CC BY 4.0.
Издатель описывает источник как снятый Sony PMW-F55 материал и публикует отдельную
HDR10 PQ BT.2020 image sequence. Декодер подтвердил 4096×2160 `gbrp16le`.
Все оригинальные кадры, license и полученный файл закреплены локальными SHA-256.
Attribution, URL, полные команды и результаты:
`.qualification-current/audit-20261004/native-hdr/qualification.json`;
копия прежнего repository export сохранена в локальном архиве.

TIFF не содержит embedded color tags: interpretation PQ/BT.2020 явно взята из
описания издателя. Для существующего video pipeline создан lossless FFV1 proxy:
RGB16 → limited YUV420 10-bit, PQ и BT.2020 сохранены, без tone map. Cadence
**задана для лабораторного proxy: 24 fps, одна секунда**; исходные camera/presentation
PTS этим тестом не проверены. Mastering-display, MaxCLL/FALL и Dolby Vision
metadata отсутствуют в proxy и не выдумываются из названия ассета.

| Кодер / Intel macOS | Encode wall / RSS | QA wall / RSS | Raw / registered SSIM | Decode / PTS |
|---|---|---|---|---|
| libx265 | 33.37 s / 2764.3 MiB | 95.42 s / 4599.5 MiB | 0.809792 / 0.889597 | 24 кадра; missing/non-increasing PTS = 0 |
| hevc_videotoolbox | 15.27 s / 1149.9 MiB | 140.60 s / 4440.0 MiB | 0.818841 / 0.885112 | 24 кадра; missing/non-increasing PTS = 0 |

Обе ячейки имеют correctness `valid`, но quality **warning**, не human acceptance.
SSIM/PSNR здесь — coded-PQ diagnostics, не HDR perceptual qualification.
Raw/registered VMAF **N/A** по HDR policy. SSCD **N/A**: backend извлёк 31/32
requested frames; отсутствующее значение не подставлено как ноль. Audio не применим.
Матрица выполнялась на общем host одновременно с long QA, поэтому wall не является
изолированным сравнением скорости двух кодеров.

Это независимые graded HDR master pixels в коротком authored proxy. Original Sony
RAW bitstream, исходные HFR/VFR timestamps, static/dynamic metadata preservation,
длинный HDR файл, HDR-display/human review и NVENC/QSV/AMF остаются **NOT VERIFIED**.
Предыдущий отказ VideoToolbox для source со static HDR10 metadata сохраняется:
новый успешный PQ-тест относится к источнику **без** этой metadata.

## Длинный фильм: полный результат после возобновления — 2026-10-05

По указанию пользователя проверен только **180,4-минутный архивный фильм**.
95-минутный случай исключён до обработки. Новый encode выполнен в этом аудите и
сохранён до паузы; исторический release output не переиспользовался. После паузы
повторён только QA и завершены недостающие измерения. Encoder, transforms,
profile, seed и Plan после encode не менялись. Две дополнительные QA-коррекции
имеют отдельный снимок `implementation-metric-identity.json` с SHA-256
`6180ebd9ab6276e4c5c0902be9a6e465f65eb1999b8886d1e7c35db795a94e80`.

| Результат | Значение и область проверки |
|---|---|
| Полный encode | libx264, soft, fixed seed 11, workers 1; 19 сегментов |
| Encode wall / sampled tree RSS | 4340,26 s / 263176 KiB |
| Размер исходника / результата | 769585376 / 1748441349 bytes |
| Итоговый production CLI QA | exit 0, JSON/HTML валидированы; 3944.17 s / 10042992 KiB tree RSS |
| Raw / registered VMAF | 21.305849 / **94.454314**; каждый 7-й кадр по полному timeline |
| Raw / registered SSIM | 0.787082 / **0.987981** |
| Raw / registered SSCD | 0.923325 / **0.979004**; 32 sampled pairs |
| Raw PSNR | **22.798385 dB**, исходник масштабирован к размеру candidate |
| Полная громкость выходного AAC | **-14.63 LUFS**, true peak **-1.79 dBTP** |
| Correctness / quality verdict | **valid / fail (red)**: legacy raw VMAF <75; registered score не отменяет этот verdict |
| Отдельная проверка cancellable VMAF wrapper | 94.454314, subsample 7; 813,46 s / 10012760 KiB; реальный CancelToken, весь timeline |
| Начало / середина / конец аудио | Три 20 s окна; per-channel envelope lag 0 / −10 / −10 ms, без компенсации tempo |
| Аудио на границах сегментов | 18 фактических границ ×6 s; 36 channel measurements, lag −10…0 ms, correlation ≥0,89459 |
| Материалы для слушателя | 3 opaque A/B пары, 6 float-PCM WAV, отдельный reveal key; **0 human labels** |

Полный проход по каждому заявленному потоку дал следующие результаты:

| Поток | Исходник | Результат |
|---|---:|---:|
| Video frames | 324395 | 324395 |
| Video last frame end | 10823.990658 s | 10823.983000 s |
| Decoded audio samples/channel | 477325312 @ 44100 Hz | 519551552 @ 48000 Hz |
| Audio last sample end | 10823.703220 s | 10823.990667 s |
| Missing / non-increasing PTS | 0 / 0 | 0 / 0 |
| Decode errors | 0 | 0 |

В исходнике audio заканчивается примерно на 287 ms раньше video. Конечный
original excerpt содержит 869324 samples/channel при 44,1 kHz (19,713 s),
candidate — 960000 при 48 kHz (20 s). Разная длина реального EOF сохранена:
correlation сравнивает только общий доступный интервал. Порог 40 ms задан до
измерения, разрешение lag — 10 ms. Эти проверки не устанавливают named-event
или lip-sync соответствие, слуховое качество либо speaker identity без меток.
В результате audio end находится на7.667 ms после video end; endpoints
и одинаковое число кадров сами по себе не доказывают внутреннюю A/V синхронизацию.

Registered audio offset/drift остаются unavailable: concatenation пяти
stratified fingerprint windows не устанавливает физический offset/drift.
SSCD: 32 пары охватывают midpoint grid с интервалом 338,25 s и не локализуют
все короткие вставки. Локальные chunk similarity diagnostics ограничены 600 s
общего prefix. Высокие registered scores не меняют **красный raw quality verdict**
и не являются результатом проверки YouTube/Content ID. Human acceptance открыта.

Observer corrected QA + post-QA diagnostics измерил whole-tree RSS peak
**9.660 GiB**, temporary/result logical peak
**37.416 GiB**, minimum host free
**28.771 GiB**. CPU lower bound —
19289.29 s: сумма последних наблюдаемых own
user/system по PID/create-time; короткие процессы и хвост между samples не
охвачены. Observer начал после QA child; actual CLI QA wall/RSS измерены от
самого запуска отдельно. Post-QA PSNR/loudness/timeline заняли
2304.30 s, RSS peak
3144532 KiB. Shared-host disk/swap
включают чужую активность, wall не является изолированным speed baseline.

Неуспешные попытки сохранены отдельно: QA после первого resume остановлен при
быстром росте swap (exit −15, затем остановлен orphan metric); отдельный full-file
VMAF получил ложный 600 s inactivity watchdog из-за выключенного progress.
Оба дефекта исправлены и имеют регрессии: 92 focused checks, metric-snapshot gate
2065/55 и installed-wheel smoke прошли. Предыдущие partial scores не переиспользуются.

20 временных FFV1 files первого неуспешного QA (38425053186 bytes) hash-indexed;
логи сохранены, файлы удалены после успешной отдельной проверки VMAF. Свежий QA
создал новый reference и штатно удалил его после отчёта. Исходник, готовый MP4,
Plan, benchmark и все итоговые отчёты сохранены. Default reservations и 40 GiB
reference cap не ослаблялись. 64 MiB payload cache pHash не означает 64 MiB RSS;
общего снижения RAM не заявляем. Технический результат относится к одному
архивному development title на Intel Mac/FFmpeg 9/libx264; другие OS/devices,
full-length virtual/retimed references и человеческая приёмка не квалифицированы.

## Реально установленные ограничения

Новые 180/95-minute попытки использовали rehashed pinned retained inputs и новый
work/output path. После удаления **только новых дубликатов загрузок** (байтовое/hash
сравнение с retained media; оригиналы и чужие данные сохранены) admission повторён.

| Input | Свободно | Начальная combined work/final reservation | Исход |
|---|---:|---:|---|
| 180.4 min archival | 12.412 GiB | 26.728 GiB | preflight: требуется ~13.7 GiB даже для первого disk check; output отсутствует |
| 95.3 min dialogue | 12.412 GiB | 14.118 GiB | final reservation 6.14 GiB против 4.14 GiB unreserved; output отсутствует |

Это новые **неуспешные admission attempts**, не новые full-film encodes и не
full-file QA outputs. Registered reference дополнительно требует места.
На момент этих отказов AP-17/AP-23 требовали больше storage. Затем пользователь
освободил диск до69.47GiB. Получен новый 180.4-minute encode, а после паузы и двух
QA-only corrections — свежий CLI QA с exit0, JSON/HTML, full-file PSNR, loudness
и output timeline. Все заявленные streams декодированы: missing/non-increasing
PTS и decode errors отсутствуют. Source/output/Plan/profile hashes проверены.
Default reserves и40GiB reference cap сохранены. Failed/paused attempts и
отдельные wrapper failures остаются историческими evidence, их partial scores
не переиспользуются. Native Mac/FFmpeg9/libx264 scope и ресурсы см. выше;
shared-host wall не является изолированным performance baseline.
95-минутный случай отменён пользователем **до обработки**; output/source
processing diagnostics для него отсутствуют. Original two-case manifest сохранён
как provenance; воспроизводимый разрешённый scope — `long/archival-only.yaml`.

AP-14/AP-21 требуют настоящего listening/A/B/event review. Подготовлены opaque A/B
файлы, отдельный reveal key, CSV с пустыми labels и протокол условий. Автоматические
метрики не назначают reviewer и не заполняют эти оценки. HDR сравнения требуют
соответствующего display/reference domain. Quality bands пока не установлены.
AP-22 зависит от этих labels. AP-24 дополнен коротким master-origin PQ proxy
на доступном Intel Mac; original timing/static metadata, остальные devices
и human HDR acceptance остаются непроверенными.

AP-26 выполнен как первый design step: отдельный draft, MVP/reuse/criteria и восемь
задач EDL-01…08. Новый монтажный редактор этим пакетом не реализован.
AP-27 остаётся conditional/deferred: reference owner, baseline claim и условия
контролируемого платформенного наблюдения не подготовлены; внешние действия не выполнялись.

## Evidence и продолжение

**AUDIT-G01** получил полный технический результат в разрешённом one-case Mac
scope; универсальные capacity/OS/performance выводы не делаются. Открыты
**AUDIT-G02** human audio/
A/B/quality bands; **AUDIT-G03** native HDR/devices/OS; **AUDIT-G04** segment labels/
short-insert coverage. Новые дефекты **AUDIT-N01** noise downmix и **AUDIT-N02** unseeded
noise и **AUDIT-N03** legacy offset duration исправлены и проверены. Остальные historical production/NFS/supply-chain риски
сохраняют свой scope. Ни local scores, ни эти исправления не подтверждают обход Content ID.

Краткая запись результатов сохранена в `validation-corpus/audit-20261004/README.md`.
Полный `evidence.json` с исходами матриц и SHA подробных JSON находится в проверенном
локальном архиве; исходные logs, Plans, QA JSON/HTML, outputs и human review assets
остаются в рабочем каталоге evidence. Сначала закрывают внешние acceptance gates,
затем AP-28; отсутствующие результаты не переводятся в `DONE`.

Итог реестра:22 локальных результата и AP-28 находятся `IN_REVIEW`; AP-00 `DONE`,
четыре обязательных задачи `BLOCKED` (AP-14/21/22/24), AP-27 `DEFERRED`.
AP-17/AP-23 имеют завершённую разрешённую техническую квалификацию и переданы
на приёмку. Общий план не объявляется завершённым.

## Дополнительная техническая проверка по запросу пользователя — 2026-10-05

Работа относится к AP-14/AP-21/AP-22/AP-24/AP-28. Использованы сохранённые короткие
материалы, без нового full-film encode/QA. 95-минутный фильм не запускался.
Новые сырые observations, policy reports, logs и mono WAV находятся в ignored
`.qualification-current/audit-20261005-technical-review/`; предыдущие результаты
и архив удалённых repository exports сохранены без перезаписи.

### Ревью и исправления

1. `hardware_qualification_report.py` запрашивал frames всего файла, затем обрезал
   stdout до128000символов. Для реального 1200-frame MP4 получался невалидный JSON,
   structured probe отсутствовал. Регрессия до исправления упала; после исправления
   проходит. Теперь headers/side data и first64packets имеют явный prefix scope,
   stdout/stderr truncation обозначены, parse error сообщает недоступность.
   На настоящих retained180-minute source/output новый probe также сохранил
   structured metadata: по2streams и63decoded prefix frames; это headers и
   первые64packets, без full-movie decode/encode/QA.
2. `decoded_timeline()` проверял только первый video stream. Теперь проверяет
   все declared video/audio streams; реальный two-video FFV1 fixture подтверждает
   учёт обеих дорожек по12frames. Audio EOF сравнивается с первым video stream;
   это не доказательство lip-sync.
3. Из docstring VMAF убрано неподтверждённое универсальное обещание convergence
   ±0.5points. Алгоритм sampling сохранён; error зависит от конкретного материала.

### AP-14/AP-21: звук и материалы для оценки

Выполнены **48 observations** на native-rate decoded PCM: 16 готовых ablation
outputs, review WAV, stereo/5.1 и opaque A/B пары. Максимальная длина наблюдения30s.
Среди этих окон нет отсчётов ≥1 и полного погашения stereo при `(L+R)/2`.
Это не full-file clipping test, true-peak тест или слуховая приёмка. Сохранённый
full-file loudness/true-peak результат длинного output относится к предыдущему
проверенному snapshot и не объявляется новым измерением.

Для трёх long-output WAV максимальный sample peak≈0.786266, signed stereo correlation
0.998619…0.998647, mono attenuation −0.034892…−0.033749dB;
DC offset каналов ≤0.0000105. Исходный end WAV имеет869324samples@44100Hz,
output960000@48000Hz: source EOF gap сохранён, trimming/нормализация для его
сокрытия не выполнялись. Ранее измеренные envelope lag/drift/seams остаются
отдельным evidence и не подтверждают соответствие звука событиям изображения.

Haas требует особенно внимательной проверки mono: correlation около−0.07,
mono attenuation около−3.33dB; reverb около−2.13dB. Это измеренное изменение
энергии, не оценка слышимости/приемлемости. Для surround channel stats собраны,
mono downmix/correlation оставлены unavailable без speaker labels/weights.

Подготовлены ещё **три mono A/B пары**, `(L+R)/2`, float PCM, без loudness/peak
normalization; ID A/B совпадают с исходным blind набором, reveal остаётся отдельно.
Все три существующие `labels.csv` проверены SHA-256 до/после: изменения отсутствуют,
human evaluations added0. AP-14/AP-21 остаются `BLOCKED` на actual listening,
visual A/B и event-based A/V review. Оценки компьютера не записываются как human.

### AP-22: реализованная экспериментальная политика

Private core selector и opt-in developer tool реализованы и покрыты регрессиями.
Задаются minimum quality, maximum bytes, average bitrate и optional core wall
budget; правильный reference/domain и passed correctness обязательны. Missing,
nonfinite, wrong-domain или failed correctness не могут пройти. При отсутствии
допустимого варианта возвращается `NO_FEASIBLE_CANDIDATE`, лимиты не ослабляются.
Правила и границы контракта описаны в
[решениях](audit-implementation-decisions.md).

Повторно измерен VMAF всех12retained outputs против четырёх одинаковых для arms
transformed SDR references, проверены decoded frames/PTS/endpoints и SHA файлов.
Новые VMAF совпали с сохранёнными до6decimal places. Два явно заданных
engineering сценария, оба с average bitrate≤8Mbps:

| Hypothesis | Допустимые случаи | Отказ |
|---|---|---|
| VMAF≥95, bytes≤2×source_cap output | Meridian tone-map:95.738260 | Meridian SDR:92.839473; ToS00:92.359063; ToS03:87.817050 |
| VMAF≥90, bytes≤1×source_cap output | Meridian tone-map; Meridian SDR; ToS00 | ToS03 |

В каждом из четырёх случаев source_cap/CRF-only/cap×2 дали одинаковый VMAF.
Tie-break выбрал CRF-only за размер на70bytes меньше; это не измеренное улучшение
качества и не основание включить CRF-only в production. Сравнение размера идёт
с baseline output, не source file; bitrate включает container overhead и не
гарантирует peak/VBV. Повторы и окна двух title families не являются independent
held-out evaluation. Thresholds90/95/1×/2×/8Mbps — hypotheses, не approved bands.
Production profiles/encoder defaults/QA policy не менялись. AP-22 остаётся
`BLOCKED` для human/independent acceptance и будущей application integration.

### AP-24: дополнительные HDR observations

Проверены5retained HDR files: FFV1 master-origin proxy, software/VideoToolbox
HEVC outputs, derived HDR10 reference и его software output. Во всех5decoded
streams отсутствуют missing/non-increasing PTS;24/24/24/240/240frames.
Pixel format `yuv420p10le`, transferPQ, primariesBT.2020 и matrixBT.2020nc
сохранены. HDR10 Mastering Display и CLL/FALL derived source/output совпадают
в проверенном prefix, включая1000/400nit CLL/FALL. Это лабораторная derived
пара, не проверка original mastering metadata Netflix TIFF.

Master-origin proxy и оба24-frame outputs не содержат static HDR side data
в stream headers/проверенных frames; эта authored proxy не устанавливает
metadata/timestamps исходного camera master. Prefix probe не доказывает отсутствие
динамических metadata в иных участках длинного файла. Original timing, HDR-display
image review, NVENC/QSV/AMF и остальные OS/devices остаются `NOT VERIFIED`.
AP-24 не переводится в `DONE`.

Доступные H.264/HEVC VideoToolbox дополнительно проверены **18passed,
3skipped,37deselected,84.69s**, отдельный real-bitstream scope:

```sh
VIDEO_UNIQ_HARDWARE_ENCODERS=h264_videotoolbox,hevc_videotoolbox \
  .venv/bin/pytest tests/integration/test_encoder_bitstream_matrix.py \
  -k videotoolbox -q
```

Production commands используют `-allow_sw 0`: silent software fallback не может
дать pass. Проверены bitstream/tag/profile/10-bit HLG, VFR timestamps,1080p/UHD,
две параллельные sessions, отмена после реального progress без partial delivery,
и отказ при unverified static HDR metadata. Auto-policy fallback test использует
real probes и затем **моделирует** loss hardware; physical hot-unplug не проверен.
AV1 VideoToolbox не был requested и не квалифицирован этой матрицей. Эти synthetic
fixtures расширяют local hardware scope, но не заменяют original HDR master,
HDR-display review или NVENC/QSV/AMF на других устройствах.
Отдельная bounded AV1 VideoToolbox availability probe вернула exit8,
`Unknown encoder 'av1_videotoolbox'`: текущая FFmpeg build не предоставляет
этот encoder. Это отсутствие в сборке, не оценка AV1 quality или другой машины.

### AP-28: техническая готовность и приёмка

Новые focused regressions: **70passed**, Ruff и strict mypy167sourcefiles проходят.
Отдельный unit coverage run:1741passed,1warning,111.34s; core line+branch
coverage **82.105694%**, обязательные80% выполнены. Новый PCM module покрыт100%,
policy module97.10%. Это unit-only coverage; прежние86.73% относятся к другому
combined run/snapshot и не объявляются текущим одинаковым измерением.

Wheel собран и установлен в отдельный target:167Python sourcefiles,16shipped
profiles и HTML template byte-equal рабочей копии; private modules импортируются
без eager NumPy, selector smoke проходит. SHA-256 wheel:
`71311c3bc38b9b68a6b07426fa20d61027fb918c0109dd1dee8c9252981cb079`.
Строгая MkDocs сборка проходит. **Fresh `make check`:2118passed,55skipped,
1warning,1019.60s (16:59), exit0; Ruff/mypy прошли.** Промежуточные остановленные
gates сохраняются отдельно и не считаются успешными. Hardware cases, которые
нужно явно запросить для runner, дополнительно проверяются отдельным scope;
результат VideoToolbox записан ниже.

Текущий working-tree implementation fingerprint:
`aa350db73e262020d64d1a5d26ef18e843f70f9a7b3decf947ad2e3f41cf3d27`.
Метод: SHA-256 compact sorted JSON mapping432Python paths→fileSHA256;
identity дополнительно содержит16profile hashes. Новый local snapshot archive:
`9434a9d09956abf79577bf40411dc7de361d0fd35f7b905c89ab6018bcc5368e`.
Encoder/segmenter/orchestrator/model/transform sources byte-equal previous metric
snapshot; shipped profiles byte-equal HEAD. Обработка старого180-minute output
не повторялась: source/output SHA-256 совпадают с прежней qualification,
архив repository cleanup не изменён, label CSV hashes не изменены.
Исторические encode/QA scores остаются привязаны к своим snapshots.

Это внутреннее техническое ревью Codex; независимая owner/PR acceptance не
назначается автоматически. Четыре внешних gates и общий статус плана сохранены.

## Первый пользовательский просмотр и диагностика размытия — 2026-10-05

Получены реальные оценки **Serafim**, оборудование «макбук», экспорт
`2026-10-05T14:31:44.586Z`, bundle `video-review-20261005`.
Протокол `labelled_source_candidate`, `blind=false`: оригинал и обработка были
подписаны. Это новая пользовательская оценка, отдельная от ранее подготовленных
слепых A/B таблиц, которые по-прежнему не заполнены. Предыдущие записи «0 human
labels» описывают состояние на момент соответствующего технического запуска.

Raw values сохранены локально в
`.qualification-current/audit-20261005-review-feedback/serafim-20261005.json`
(форматирование JSON изменено, значения, включая пробелы комментариев, сохранены).
SHA-256: `bf7b7d8af65f53d4bb99261a9c7621989d9171efb28946c205d0db07ab96c1cf`.
Derived scope записан рядом в `analysis.json`. Исходный review bundle и его ZIP
не изменены; диагностические материалы сохраняются вне Git.

| Пары | Изображение | Звук | Sync / приемлемость | Замечания |
|---|---|---|---|---|
| 01–05: мягкая/средняя/сильная, речь/лица, движение (Tears of Steel) | 3/5 во всех пяти | 5/5 | Рассогласование не замечено; все `yes` | Размытие; пользователь отдельно подтвердил потерю чёткости и предположил сужение |
| 06: Meridian | 5/5 | N/A | Визуальная приемлемость `yes`; audio/sync N/A | Raw audio5/sync retained, но в этой паре нет аудио |
| 07–09: анимация, Haas, reverb | 5/5 | 5/5 | Рассогласование не замечено; все `yes` | Без комментариев |
| 10–12: начало/середина/конец ранее обработанного длинного фильма | 5/5 | 5/5 | Рассогласование не замечено; все `yes` | Только выбранные 20-second окна |

Таким образом, 12 визуальных оценок, из них пять3/5 и семь5/5; 11 применимых
аудиооценок5/5 и 11 наблюдений «рассогласование не замечено». `acceptable=yes`
сохраняется как ответ пользователя, но не отменяет зарегистрированный дефект
чёткости. Все записи `mp4_preview`, `mono_listened=false`. Один слушатель на
MacBook не подтверждает mono compatibility, speaker identity шестиканального
фрагмента07, blind quality bands, HDR или синхронизацию полного фильма.

### Подтверждённое изменение пропорций

В exact clips и MP4 previews всех пяти проблемных пар исходник имеет **320×180,
SAR2883:2288, DAR961:429≈2,2401:1**. Обработанные файлы имеют **SAR1:1**:
01/03 —320×180, DAR16:9; 02/04/05 —320×178, DAR160:89.
При одинаковой высоте отображения ширина уменьшается примерно на19,7–20,6%;
при одинаковой ширине изображение занимает большую высоту. Это подтверждённое
изменение геометрии, а не предположение по впечатлению от браузера.

Причина воспроизведена из сохранённых Plans и текущего неизменённого builder:
`video.crop_resize` завершает цепочку `setsar=1`, игнорируя неквадратные пиксели
этого источника. `tools/audit_corpus.py` создавал прокси `scale=320:180`, сохраняя
DAR через SAR; взаимодействие этого прокси и transform обнаружило потерю aspect.
В логе реального encode исходный SAR2883:2288 и выходной SAR1:1 также зафиксированы.
Размеры/графы/кадры сохранены в `stream-dimensions.json`, `rebuilt-graphs.json`,
`frames-48-grid.png` в feedback evidence root. Графы rebuilt, не выдаются за
сохранённый точный argv исторического запуска.

### Чёткость и контрольные ролики

У всех пяти исходников низкое разрешение320×180. Crop+Lanczos-resize выполняется
до кодирования; сильный профиль дополнительно поворачивает кадр. Эти операции
могут терять мелкие детали. Их отдельный вклад в наблюдаемое размытие ещё не
измерен; обнаруженное сужение не объясняет автоматически весь дефект чёткости.
Данные preview/native VMAF≈97–98 из manifest характеризуют дополнительное
кодирование preview относительно того же native clip, а не качество обработки
относительно оригинала. Они не опровергают пользовательский отзыв.

Созданы пять `out/video-review-20261005-aspect-check/*-processed-aspect-only.mp4`:
метаданные H.264/MP4 приведены к исходному DAR с небольшим округлением
(56:25 против961:429, относительная разница0,0042%). Stream copy, без нового
encode. **1008/1008 decoded frame MD5 совпадают с прежними processed previews**;
итоговый DAR проверен у всех пяти. Команды, SHA-256 и размеры записаны в
`verification.json`; инструкция сравнения — в README рядом. Это контроль
влияния пропорций, не восстановление потерянных деталей и не исправление кода.
Новые файлы не наследуют старые человеческие оценки.

Следующий обязательный quality follow-up: исправить сохранение геометрии для
non-square-SAR источников с regression tests (square/non-square, micro-crop,
platform exact dimensions), отдельно проверить crop/rotate и кодирование на
коротких исходниках в родном разрешении. Затем повторить визуальную оценку.
Shipped profiles/production defaults пока не менялись. AP-14 получил частичные
listening observations; AP-21 получил первый labelled review. Оба остаются
`BLOCKED` в оставшемся scope, AP-22 требует обоснования bands после устранения
наблюдаемой деградации. 95-минутный фильм не запускался.

## Принятие контрольных роликов и исправление геометрии — 2026-10-05

На просьбу сравнить пять aspect-only контролей с оригиналами пользователь ответил
**«все хорошо»**. Ответ сохранён в
`.qualification-current/audit-20261005-review-feedback/aspect-control-followup.json`
как положительная общая оценка контрольного набора. Отдельных числовых оценок и
раздельных ответов о форме/чёткости нет: исходные пять visual3/5 сохранены,
автоматически в5/5 не превращаются. Это labelled просмотр, не blind acceptance.

`video.crop_resize` исправлен в core: `crop:keep_aspect=1` сохраняет исходный DAR,
`setsar=sar:max=65535` явно переносит вычисленный SAR с filter link на кадры,
затем Lanczos scale сохраняет геометрию при округлении размеров. Прежнего
принудительного `setsar=1` в этом transform больше нет. Назначение `keep_aspect`
и правила SAR описаны в [официальной документации FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#crop).
Отдельный локальный showinfo probe показал, что одного `keep_aspect` недостаточно:
в текущем FFmpeg link SAR обновлялся, а frame SAR оставался исходным.

Для явного `video.fit_aspect` final canvas guard закрепляет настроенные размеры
и квадратные пиксели. Обычные профили сохраняют DAR источника; destination profile
сохраняет выбранный canvas aspect. Capability probe распознаёт обновлённый guard.
API/CLI/profile schemas, параметры YAML и encoder quality defaults не изменены.
Internal encode policy **v8** исключает reuse сегментов и score-cache identity
предыдущей версии обработки; v7 measurements ниже/выше остаются историческими.

Добавлен `tests/integration/test_crop_display_aspect.py`: whole/segment/fused,
square и non-square sources, soft/medium/aggressive crop, zero strength, rotate,
anamorphic720×576, destination crop/pad_black/pad_blur. Проверяется фактический
DAR, чётность размеров, количество декодированных кадров и точные platform
canvas dimensions для square/non-square source. Обновлены два внутренних graph
assertions на square-pixel tail. Pre-fix regression действительно падал:
отношение выходного DAR к исходному0.8025348 вместо1. Это не mock-only проверка.

Перекодированы только пять исходных восьмисекундных ToS proxies и отдельный
восьмисекундный source excerpt **1920×858** в родном разрешении. У всех шести
выходов исходный DAR≈2.2401:1 сохранён, frame counts совпадают. У пяти proxies
**1008/1008 decoded frame hashes равны прежним retained pipeline outputs**:
исправление геометрии не добавляет потери пиксельных деталей. Это сравнение с
основными outputs старого pilot, а не с дополнительно кодированными previews.

Во всех шести проверены также извлечённые elementary H.264 streams: DAR сохранён
с относительной погрешностью менее0.01%, корректность не зависит только от MP4
container metadata. Native-resolution case имеет192frames до/после. Это проверка
video stage, не новая аудио или human qualification. Fresh outputs, Plans,
команды, SHA-256, размеры и logs находятся в
`.qualification-current/audit-20261005-aspect-fix/qualification.json`.

Дополнительная strict-hardware попытка H.264 VideoToolbox на320×178 завершилась
`Cannot create compression session:-12903`, output packets0. Контроли с
ограниченным SAR и с принудительным SAR1 дали тот же отказ. Поэтому этот
hardware case **NOT QUALIFIED**; причины resolution/device/session по этой
пробе не разделены, SAR-specific regression не установлена. Auto `build_plan`
для этого реального source/profile выбирает `libx264`, который проверен выше.
Команды/logs/negative controls — в `hardware-aspect-check.json` рядом.
Silent software VideoToolbox fallback не включался (`-allow_sw0`).

Первый full gate остановлен после дополнительной non-square destination проверки,
которая выявила необходимость закрепить canvas aspect; его exit2 и reason
сохранены в `interrupted-gate/`, это **не успешный gate**. Следующий full gate также остановлен: один старый B3 test требовал SAR1:1
независимо от rounded dimensions. На320×178 корректный SAR89:90 сохраняет
исходный DAR16:9; принудительный SAR1 снова менял бы форму. В этом тесте
сохранены проверки duration/PTS/frame count/audio, а SAR assertion заменён
проверкой равенства исходного и выходного DAR. Все4B3real integration tests
после этого прошли за35.06s. Reproduced failure и interrupted snapshot
сохранены отдельно; calibration-cache test independently passed27.47s.
Итоговый full gate завершён успешно на финальном test/source snapshot;
результат и fingerprint приведены ниже.

AP-13/AP-28: исправление геометрии `IN_REVIEW`, положительный контрольный отзыв
зафиксирован. AP-14/AP-21/AP-22 сохраняют остающийся mono/blind/quality-band scope;
AP-24 требует прежних HDR/device evidence. Пересчёт исторического pilot/holdout
или повторная обработка длинных фильмов не выполнялись. 95-minute case не запускался.

### Итоговые gates исправления геометрии

- Focused transforms/pipeline/geometry: **95passed,22.51s**, включая36real
  FFmpeg geometry/platform cases; B3full-orchestrator scenarios: **4passed,35.06s**.
- Fresh **`make check`:2154passed,55skipped,1warning,1054.65s pytest;
  полный make wall1057.64s, exit0**. Ruff и strict mypy167source files проходят.
  Skips включают недоступные/не запрошенные hardware runners и opt-in heavy GUI
  сценарий; они не объявляются проверенными. Warning — существующий
  Starlette/httpx deprecation.
- Отдельный unit-only coverage run: **1743passed,1warning,109.07s**, core
  line+branch **82.0893076608%** при требуемых80%. Source/unit files byte-equal
  финальному gate; после coverage изменена только B3integration assertion.
- Wheel собран isolated hatchling1.32.4;167Python sources и16shipped profiles
  byte-equal рабочему дереву. SHA-256:
  `c32337d706ec737df8bc6f2bb1d2cb59da419a2095f25691d91a239a860542fd`.
  Начальная no-isolation попытка не имела установленного hatchling и не
  считается успешной; последующая isolated сборка успешна.

Финальный code/test fingerprint433Python paths:
`5bafc777bf5b6d739b7f3d4fd24759187ccccad7135b7628349a0913506f50fe`.
Метод — SHA-256 compact sorted mapping path→SHA-256. Local source/profile
archive SHA-256:
`7b2e8575b33329c63eb3334f620dda6b65b128c79c3a5ae0345bafb279b884bd`.
Short encode qualification fingerprint
`a929499894edc24b305eb05644f53b406826446b18a07474290c1a36d9953b0d`
отличается только файлом B3integration assertion: все167application sources
одинаковы с финальным gate/wheel. Эти identities отдельно подтверждены в
`snapshot-validation.json`; исторические v7 metrics не переписываются.

Положительный отзыв о пяти контролях принят в своём scope; исправление
геометрии технически проверено. AP-13/AP-28 остаются `IN_REVIEW` до code/owner
приёмки; blind bands, mono review, HDR/devices остаются прежними внешними gates.
