# Решения по реализации аудита

Дата: 2026-10-04. Ветка: `fix/audit-implementation-20261004`.

## Контракты и совместимость (AP-04)

Изменения этого пакета классифицируются как PATCH: исправления вычислений,
доступности, cache identity и поясняющего текста. Поля `QAReport`, `Profile`,
`Plan`, nested models, CLI flags, public exports и shipped YAML не меняются.
Новые stable поля не вводятся; отдельный RFC для этого пакета не требуется по
[CONTRIBUTING.md](https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/CONTRIBUTING.md).

| Поверхность | Решение |
|---|---|
| Optional quality/audio/SSCD scores | `None` при недоступности; действительный ноль сохраняется |
| pHash compatibility fields | При недоступности `phash_samples=0`; verdict сообщает unavailable |
| `cid_predict_self` | Nullable maximum similarity; не вероятность |
| `chunk_similarities` | Существующий открытый `dict[str,float]`; недоступный `audio` опущен, причина в notes |
| Coverage/provenance | Пояснения в существующем `notes[]`, structured registration в существующей `QARegistration` |
| CLI/HTML/GUI/web | Существующие nullable scores и notes; HTML объясняет отсутствующий interval audio |
| SSCD локальный максимум | `sscd_per_frame` сохранён; индекс/время/model hash/preprocessing в notes |
| Search objective | Один выбранный backend; отсутствие необходимого audio прерывает search |
| Cache migration | Calibration schema 3 и executable/model identity; keyframe schema 3 |
| Audio noise replay/resume | Явный генератор seed и layout; v7 invalidated older audio segments; current encode policy v8 also invalidates geometry artifacts |
| Crop display geometry | Preserve source DAR/SAR through crop rounding; explicit fit-aspect canvas uses square pixels; no new profile/API fields |

Это не создаёт machine-readable stable availability enum. Его добавление потребует
отдельного MINOR RFC и snapshots; downstream clients сейчас должны читать
существующий null/count и notes. Старые JSON загружаются без изменений схемы.
Legacy dictionaries должны допускать отсутствующие ключи; `.get("audio")` возвращает
недоступность, а не предполагаемый ноль. Формы и набор CLI options сохраняются.

## Калибровка: что означает factor (AP-01/AP-02/AP-09)

| Эффект | Масштабирование |
|---|---|
| sharpen | `luma_amount × factor`; radius — ближайшее нечётное ядро 3…11, tie вверх |
| temporal jitter | `blackout_prob`, `drop_prob × factor`, с bounds схемы |
| reverb | `intensity × factor`; style сохраняется |
| compand | `ratio = 1 + (ratio-1)×factor`; threshold/time constants/boolean jitter сохраняются |
| noise overlay | Линейная амплитуда ×factor: `noise_db + 20 log10(factor)`; bounds -40…-3 dB |
| EQ/Haas/noise jitter | Реальные `jitter_db`, `randomize_within_ms`, `randomize_within_db ×factor` |
| loudnorm, mirror, tonemap, fit-aspect, subtitles | Фиксированные targets, conversions и дискретные операции |

Factor 1 сохраняет эффективные параметры. Disabled transforms остаются disabled
и их параметры не меняются. Bounds могут создавать plateau. Noise при factor 0
достигает -40 dB, но не становится тишиной. Compand сохраняет endpoint `0/-3` и
boolean jitter даже при ratio 1; уменьшение factor не означает полный bypass стека.
Для настоящего bypass отключают соответствующий transform. Factor должен быть
конечным и неотрицательным; область поиска остаётся 0 < min <= 1 <= max.

`chromaprint` остаётся compatibility identifier для max(pHash, prefix audio Jaccard).
Raw comparison не исправляет retiming автоматически. Качество calibration —
raw source/candidate VMAF или SSIM×100; backend pinned внутри поиска. Это отдельный
domain от post-run FFV1 replay. HDR raw reference в calibration явно unsupported.
Нельзя использовать существующие `target_vmaf` retries с неподдержанными geometry,
retiming или tonemap: preflight запреты сохраняются.

## Временной scope (AP-06/AP-07/AP-08)

Legacy heatmap имеет явно ограниченный режим: общий prefix двух файлов, максимум
600 секунд, максимум 600 кадров и 150 окон. Residual duration включается. Одинаковый
absolute span используется для visual samples обоих файлов. Хвост не измерен;
audio Jaccard aggregate не получает вымышленных segment labels. Source/output
разной длительности всё ещё требуют отдельного alignment анализа.

Существующие bounded audio offset/drift и SSCD monotonic alignment сохраняются.
Постоянные fingerprints и static similarity matrix не устанавливают alignment.
Confidence остаётся heuristic, не вероятностью и не независимым lip-sync evidence.
Natural event/listening review должен дополнять синтетические импульсы.

Дополнительный эксперимент выявил downmix в `audio.noise_overlay`: mono
`anoisesrc` заставлял `amix` сводить основной stereo/5.1 сигнал, после чего tail
возвращал число каналов, но не потерянные сигналы speakers. Теперь noise branch
согласует layout выбранного входа до смешивания. Для неизвестного layout используется
unspecified channel count (`nC`), не придуманный speaker mask; warning сохраняется.
Генератор получает seed из того же RNG в pass-1/pass-2/windowed/replay paths.
Старые планы с unseeded noise не объявляются воспроизводимым registered reference;
для квалификации нужен новый render. Encode policy v7 меняет resume identity.

SSCD использует normalized midpoint timestamps каждого файла, а не общую
absolute raw grid. Максимальный sampled cosine локализован только до requested
timestamp; decoder cadence может сместить выбранный кадр. Между samples возможен
пропуск вставки. Это engineering diagnostic изображения, а не человеческое качество.

## Экспериментальные профили (AP-11)

Названия `cid_*`, preset данные и defaults сохраняются ради совместимости.
`cid_aware`, `cid_aggressive`, aggressive и HDR→SDR варианты остаются opt-in
экспериментами. Compound effects могут усиливать шум, фазовые изменения и flicker.
Нет квалифицированных универсальных quality bands; fixed effects перечислены выше.
Pilot seeds — повторы на том же произведении, а не независимые примеры контента.

## Внешняя приёмка

Human A/B labels, native HDR masters, реальные NVENC/QSV/AMF устройства и platform
reference-owner observations не заменяются mocks или зелёным pytest. Их фактический
scope и недостающие ресурсы фиксируются в implementation-plan и evidence report.
Production defaults для bitrate/quality не меняются без соответствующих labels.

Raw VMAF для HDR не вычисляется стандартной SDR-моделью. Audio registration
после stratified concatenation (>600 s) не сообщает физический offset/drift:
это потребует отдельных per-window измерений. Aggregate diagnostics сохраняются.

Legacy ffprobe 5.1 может сообщать absolute end PTS вместо MP4 duration. Parser
нормализует endpoint только при согласованных start/duration всех timed streams
и format origin; incomplete/ambiguous bounds сохраняют прежний conservative path.
На 6.0/9.0.1 относительная duration не сокращается повторно. SourceMeta целиком
входит в plan hash: исправленная длительность исключает reuse ошибочного resume.
Все 33 study sources на pinned 9.0.1 сохранили прежнюю metadata.

## Дополнительная техническая приёмка 2026-10-05 (AP-14/AP-22/AP-24/AP-28)

PCM observations реализованы в private core `qa/_audio_observation.py`.
Developer utility `tools/media_diagnostics.py` декодирует до30s с исходным sample
rate: 8kHz envelope не используется для измерения peaks. Фиксируются sample peak,
RMS, DC, число отсчётов ≥1, доля тишины и signed stereo correlation.
Отсчёт ≥1 — наблюдение PCM, а не доказательство audible clipping или true peak.
Equal-weight mono `(L+R)/2` относится только к stereo; ratio энергии нормирован
на среднюю энергию исходных каналов. Для тишины correlation/ratio недоступны,
полное погашение имеет ratio0 и nullable dB без JSON infinity. Для surround
downmix недоступен без подтверждённых speaker labels/weights.

Политика AP-22 реализована как private experimental core
`core/_quality_size_policy.py` и opt-in developer command
`python -m tools.rate_control_experiment --select-existing`. Stable application
CLI, models, profile YAML, QA contract и defaults не меняются. Интеграция новой
политики в приложение остаётся будущим изменением с необходимым RFC и приёмкой.

Каждый запуск задаёт reference SHA-256, metric/domain, minimum quality,
maximum bytes и maximum average bitrate; optional wall budget поддерживается
core. VMAF допустим только для transformed SDR. SSIM имеет шкалу0…1, VMAF0…100.
Непройденная correctness, missing/nonfinite scores, иной reference/domain,
превышение размера/среднего битрейта/заданного времени исключают кандидат.
Выбирается максимальное качество среди допустимых, затем меньший размер,
затем стабильный ID. Пустой допустимый набор возвращает
`NO_FEASIBLE_CANDIDATE`; лимиты автоматически не ослабляются.

Developer tool повторно декодирует и измеряет VMAF коротких retained файлов,
записывает SHA эталона/выходов и исходного results.json. Размер сравнивается
с минимальным retained `source_cap` output этой ячейки, а не с несопоставимым
исходным контейнером. Битрейт — whole-file average с overhead, не обещание peak
bitrate/VBV. Все limits — явно заданные engineering hypotheses: human labels и
независимые held-out titles требуются для их принятия. Production policy не выбрана.

Hardware utility теперь читает headers и первые64packets, включая stream/frame
side data. Prefix scope не доказывает отсутствие метаданных во всём файле или
аппаратное кодирование. Full decoded timeline собирается отдельным streaming
инструментом для всех declared video/audio streams. HDR display и original
publisher timing не выводятся из authored laboratory proxy.


## Display geometry после пользовательского просмотра — 2026-10-05

Non-square pixels не переводятся в square через одно изменение metadata в
обычном micro-crop: это сжимало изображение. `keep_aspect=1` + explicit frame
SAR refresh сохраняют исходный DAR при Lanczos-rescale и integer rounding.
Для явно выбранного fit-aspect canvas final dimensions и SAR1 закрепляются
вместе. Это исправление вычислений в PATCH scope; stable schemas и shipped
profile values не меняются. Encode policy v8 меняет plan/resume identity,
поэтому v7 renders/scores остаются historical evidence.

Положительный отзыв «все хорошо» относится к пяти metadata-only controls;
числовые оценки не выдумываются. Он не назначает blind bands, mono/HDR/full-file
acceptance. Варианты новых thresholds/defaults по-прежнему требуют своей
квалификации и соответствующего RFC.
