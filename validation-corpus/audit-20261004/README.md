# Аудит 2026-10-04: краткая запись результатов

Подробные [результаты](../../docs/audit-implementation-results.md),
[план и статусы](../../docs/implementation-plan.md) и
[исследование](../../docs/research/2026-10-04-video-uniquification/index.md)
сохранены в документации. Код, регрессионные тесты и инструменты подготовки/
оценки корпуса остаются в проекте.

Это локальные инженерные измерения, а не утверждение о платформенном обнаружении
или принятые human quality bands. Самостоятельный монтажный редактор не реализован.

## Проверенный код

- Baseline HEAD: `03c707a5c4a68397511cb38f881335a00990f271`; он не обозначает dirty-tree code.
- Metric/long-QA implementation SHA-256: `6180ebd9ab6276e4c5c0902be9a6e465f65eb1999b8886d1e7c35db795a94e80`.
- Snapshot SHA-256: `0a430d0f1c4e11bc6a3f386b99cdb8a2001fc5a96d8655e9f753594dff69da1d`.
- `make check`: 2065 passed, 55 skipped; core coverage 86,73%.
- Installed-wheel smoke, Ruff, strict mypy и strict MkDocs прошли.
- Retained encode использует прежний снимок; encoder/transforms/profile/Plan
  не менялись. Дополнительные sampling/watchdog corrections касаются QA.

## Итоги матриц

| Матрица | Технически измеренные / всего |
|---|---:|
| Pilot | 54 / 54 |
| Evaluation | 30 / 30 |
| Temporal ablation | 16 / 16 |
| Audio ablation | 16 / 16 |
| Surround | 1 / 1 |
| Calibration full outputs | 3 / 3 |
| Hardware initial | 2 / 4 |
| Hardware SDR retry | 2 / 2 |

Отказы первоначальной hardware matrix сохранены, success означает полноту
измерений, а не приёмку качества. Calibration search: три случая по четыре
trial, ни один не converged. Holdout содержит отдельное семейство, но только
один title; это не оценка универсальной точности detector.

Новый 180,4-минутный output полностью проверен: CLI QA exit 0, full decode/PTS,
PSNR 22.798385 dB, registered VMAF 94.454314, registered
SSIM 0.987981, loudness -14.63 LUFS/TP -1.79 dBTP.
Correctness valid; raw quality **red**. Source SHA-256:
`2642337aeabc7ef77e21efba895b6b3c17088e0d033e1e0b3d7f82445c087442`; output SHA-256:
`389224f37a1c14d8b741fb058f934deacac51992cdfad55b87e48d9f374c2f70`. 95-минутный фильм **NOT RUN** по указанию пользователя.

Native HDR: 24 publisher-master frames, authored 24 fps PQ proxy; две local encoder
cells passed color/decode correctness, quality warning. Original cadence/static
metadata, HDR-display/human и остальные devices/OS остаются непроверенными.
Human A/B/listening labels пусты; AP-14/AP-21/AP-22/AP-24 BLOCKED, AP-27 DEFERRED.

Дополнительная техническая проверка 2026-10-05:48native-rate PCM observations,
3mono A/B пары, private experimental quality/size selector и12повторных VMAF
сравнений,5HDR metadata/decode observations. Исправлены truncated hardware probe
и пропуск secondary video streams. Новый source snapshot:
`aa350db73e262020d64d1a5d26ef18e843f70f9a7b3decf947ad2e3f41cf3d27`.
Подробности и текущие gates — в основном отчёте; новые raw artifacts вне Git:
`.qualification-current/audit-20261005-technical-review/`.
Defaults, labels, long source/output и архив очистки сохранены.
Current gate:2118passed/55skipped; unit-only core coverage82.11%; отдельно
18VideoToolbox hardware tests passed. Старые86.73% выше — combined coverage
metric snapshot; scope измерений различается.

## Где лежат подробности

Generated manifests/profiles, per-cell JSON, ресурсные samples и исходная
инструкция воспроизведения сохранены **вне Git** в проверенном локальном архиве:

`.qualification-current/audit-20261004/archives/repository-study-export-before-cleanup.zip`

Archive SHA-256: `2f475bb89595bd6ed028612b4c351e7497bedb70d225fc6cefe5be9bbb26a41d`. Все 63 исходных файла проверены
побайтово через SHA-256 и длину; CRC архива также прошёл. Архив не включает media.

Локальные source/output, Plans, QA JSON/HTML, logs, исходные snapshot archives и
материалы для слушателя остаются в `.qualification-current/audit-20261004/`.
Полная long qualification: `long-after-space/qualification.json`;
HDR: `native-hdr/qualification.json`. Эти данные не удалены.

Для восстановления конфигураций без обработки видео:

```sh
.venv/bin/python -m zipfile -e \
  .qualification-current/audit-20261004/archives/repository-study-export-before-cleanup.zip \
  .qualification-current/audit-20261004/restored-config
```

Исходная инструкция будет в `restored-config/audit-20261004/README.md`.
Для разрешённого длинного случая нужен только `long/archival-only.yaml`;
исторический two-case `long/long.yaml` запускать не следует.
Архив локальный: для воспроизведения на другом компьютере нужны сам архив и
hash-verified источники. Generated exports не входят в поставляемые presets.
