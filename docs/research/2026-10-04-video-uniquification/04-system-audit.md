# Аудит video-uniquifier: что система действительно умеет и где заканчиваются доказательства

Дата исследования: **4 октября 2026 года**. Проверенный код: `main`,
`03c707a5c4a68397511cb38f881335a00990f271`, версия проекта **2.0.0**.
Проверка относится к исходникам этой ревизии, а не к любой будущей сборке.

Этот отчёт сопоставляет технические категории советов об «уникализации» с реальным
кодом. Распространённость советов, конкретные публикации и проверка внешних заявлений
разобраны в остальных отчётах исследования. Здесь источник доказательств — реализация,
схемы профилей, тесты и сохранённые инженерные результаты самого проекта.

## 1. Главный вывод

У системы уже есть почти весь обычный набор изменения изображения и звука:
кроп, изменение цвета, зеркалирование, скорость, шум, pitch/tempo, EQ, наложение
второго видео и субтитров. Сильная сторона проекта — автоматизация обработки,
воспроизводимость, возобновление, контроль медиаконтракта и измеримый QA.
Количество фильтров само по себе не подтверждает качество результата.

**В проекте нет верифицированного предсказателя YouTube Content ID.** Модуль с
историческим именем `cid_predict` прямо описывает свой результат как локальную,
некалиброванную эвристику похожести. Имена `cid_aware`, `cid_aggressive` и поля
`match_probability_self` сохранены ради совместимости; они не придают числам смысл
вероятности обнаружения. Это непосредственно следует из [описания и формулы
`cid_predict.py`][cid].

Для развития системы важнее устранить несоответствия параметров калибровки,
завершить проверку длинных файлов и обновить смысл отдельных метрик, чем добавить
ещё один случайный эффект. Эти выводы относятся к обработке принадлежащих оператору
или лицензированных материалов.

## 2. Как проводился аудит

Прочитаны реестр преобразований, реальные Pydantic-схемы и построители фильтров,
поставляемые YAML, планирование/выполнение, QA, калибровка, профильная документация,
`BENCHMARKS.md`, `RISK_REGISTER.md` и релевантные тесты. Для независимого подтверждения
двух проблем выполнены короткие вызовы настоящего `scale_profile`, без обработки
чужих материалов, загрузок на YouTube или изменений кода.

Уровни доказательств в этом отчёте:

| Уровень | Что подтверждает | Чего не подтверждает |
|---|---|---|
| Реализация | Функция существует и строит соответствующее действие | Пользу на любом материале или платформе |
| Схема и профиль | Параметр допустим; конкретный профиль его включает | Что каждый интерфейс показывает отдельную настройку |
| Unit test | Локальный контракт в заданном сценарии | Реальный FFmpeg/GPU, качество фильма, реакцию YouTube |
| Интеграционный тест | Работа с настоящими декодерами/фильтрами на fixture | Весь парк GPU, любой HDR, человеческое принятие |
| Зафиксированный benchmark | Конкретные измерения указанной версии и корпуса | Автоматический перенос результата на 2.0.0 и новый корпус |
| Комментарий или README | Намерение автора или описание | Независимую экспериментальную проверку |

Особенно важно последнее различие: научно звучащий комментарий в исходниках
остаётся заявлением автора, пока он не связан с подходящим исследованием и
воспроизводимым тестом именно этого эффекта.

## 3. Реальный набор преобразований

Runtime-проверка с отключёнными сторонними плагинами показала **21 зарегистрированный
ID**. В списке импортируемых модулей есть `hdr_wrap`, однако это инфраструктурный
помощник, а не двадцать второе пользовательское преобразование. Источник:
[реестр встроенных модулей][registry]. Возможность в таблице означает наличие
преобразования в core и конфигурирование через профиль; отдельный переключатель
во всех GUI/web-экранах здесь не квалифицировался.

| Преобразование | Реальное действие | Ограничение, важное для сравнения с социальными советами |
|---|---|---|
| `video.crop_resize` | Случайный кроп по двум осям, Lanczos-масштабирование, SAR=1 | Теряет края и повторно интерполирует детали. `max_strength` сейчас означает общий кроп по оси, а не независимо каждую сторону |
| `video.fit_aspect` | Холст заданного соотношения; crop, чёрные или размытые поля | Геометрическая адаптация не добавляет авторского содержания. По умолчанию запрещает upscale, но отдельные shipped-профили разрешают его |
| `video.rotate` | FFmpeg rotate и crop | Поворот может дать интерполяцию, потерю углов/рамку; нужен просмотр |
| `video.mirror` | `hflip` | Переворачивает текст, логотипы, направление действия; ни один эффект не доказывает реакцию внешнего детектора |
| `video.color_eq` | Яркость, контраст, gamma, saturation | Может испортить кожу, тени и светлые участки; похожесть и качество — разные цели |
| `video.noise` | Видеошум | Добавляет кодируемую сложность, расход битрейта и риск артефактов следующей компрессии |
| `video.subpixel_sharpen` | Unsharp только для luma | Это реальная резкость, а не доказанный «невидимый» метод против нейросетевого обнаружения |
| `video.blend_b` | Подмешивание второго видео, приведённого к размерам первого | Требует второй вход; не является универсальным редактором picture-in-picture, экранной композиции и авторского монтажа |
| `video.temporal_jitter` | Замена выбранных временных интервалов серым/чёрным кадром и удаление кадров | Разрушительный временной эффект, возможны вспышки и judder. `blackout_blur` фактически выбирает серый, а не пространственное размытие |
| `video.speed` | Изменение видеовремени | Требует согласования с audio tempo и сохранения таймингов потоков |
| `video.tonemap_sdr` | Явное HDR→SDR преобразование | Это цветовой pipeline с отдельными ограничениями качества; сохранение HDR и tonemap — разные режимы |
| `video.subtitles` | Вжигание существующего файла субтитров через libass | Автотранскрипция может подготовить текст, но наличие субтитров не равно новому сценарию, анализу или проверенным фактам |
| `audio.pitch_tempo` | Независимые pitch/tempo: asetrate+resample+atempo либо Rubber Band | Asеtrate меняет форманты; Rubber Band дороже и тоже нуждается в прослушивании |
| `audio.eq` | Equalizer по полосам; возможна случайная перестройка | Тональный баланс меняется, но измеренный локальный fingerprint не говорит о распознавании YouTube |
| `audio.resample` | Промежуточный sample rate и возврат | Незначительный промежуточный сдвиг не имеет универсально подтверждённой полезности; в CID-профилях он выключен |
| `audio.compand` | Компрессор/динамическое преобразование | Меняет огибающую; не создаёт новую речь или авторский комментарий |
| `audio.haas_stereo` | Задержка одного канала | Требует стереосигнал; проверяются mono compatibility и фазовые последствия |
| `audio.spectral_smear` | FFmpeg chorus | Название обобщённее реализации: это chorus с параметрами задержки, depth и speed |
| `audio.reverb` | FFmpeg aecho по preset | Добавляет реальные эхо-компоненты; quality-порог не универсален |
| `audio.noise_overlay` | Синтезированный white/pink/brown noise и amix | Шум способен стать слышимым; его уровень не является актуальным порогом Content ID |
| `audio.loudnorm` | Измеряемая нормализация loudness | Финальный encoded peak контролируется отдельно; безопасность peak может снизить достигнутую громкость |

Основные первичные доказательства: [геометрия][geom], [fit-aspect][fit],
[второе видео][blend], [temporal jitter][temporal], [pitch/tempo][pitch],
[Haas][haas], [chorus][smear], [reverb][reverb], [шум звука][noise],
[субтитры][subtitles].

### Что особенно отличает реализацию от простого набора пресетов

- Случайные параметры связаны с seed; `fixed`, `per_file`, `per_run` и `divergent`
  имеют разные назначения. `per_file` основан на строке пути, а не автоматически
  на байтах файла. Повторяемость плана не означает одинаковый bitstream на разных
  версиях FFmpeg, аппаратных кодировщиках и драйверах. [Реализация seed][seed].
- При `divergent` аудио обрабатывается примерно минутными окнами с crossfade;
  loudnorm применяется глобально после преобразований. Это техническая вариативность,
  а не эмпирически проверенная модель внешнего распознавания. [Планирование окон][windows].
- Параметры валидируются, а совместимость графа и риски проверяются до долгой обработки.
  Preflight предупреждает о noise+sharpen, повторном ресемплинге, temporal jitter и
  комбинации нескольких слышимых эффектов. [Проверки quality risks][preflight].
- Полная проверка декодирования готового результата входит в публикационный gate
  `run_full`, включая `--no-qa`. Отключение дополнительного QA не должно позволять
  выдать недекодируемый файл как завершённый. [Финальная проверка][final].

## 4. Поставляемые профили: имена не равны доказательству пригодности

В ревизии есть **16 shipped YAML** в `src/video_uniquifier/profiles/`.
Каталог `profiles/` в рабочей копии пуст: считать его фактическим местом хранения
поставляемых профилей было бы ошибкой.

| Группа | Профили | Реальная роль и оценка |
|---|---|---|
| Умеренные производные | `soft`, `medium`, `aggressive` | Разная сила crop/color/noise/audio. `soft` консервативнее, но сам профиль прямо отказывается гарантировать VMAF или похожесть |
| Сохранение HDR | `medium_hdr` | HDR-ориентированный HEVC-путь; нельзя переносить SDR-порог VMAF на сохранённый PQ/HLG |
| Исторические high-change | `cid_aware`, `cid_aggressive` | Сохранённые экспериментальные идентификаторы; сейчас в описаниях явно нет предсказания внешней системы |
| HDR→SDR derivative | `cid_aware_hdr_to_sdr` | Экспериментальный tonemap-путь; отдельная проверка сцены, цвета и компрессии |
| YouTube landscape | `youtube_1080p`, `youtube_4k`, `youtube_av1`, `youtube_4k_av1` | Delivery canvas/codec плюс микроизменения. 4K/AV1 не означают автоматически лучшее исходное качество или успешную монетизацию |
| Вертикальное видео | `youtube_shorts`, `tiktok_vertical`, `instagram_reels` | Адаптация формата; кроп может удалить главного героя/текст. Семантического выбора момента и полноценного клипмейкера эти имена не гарантируют |
| Квадрат | `instagram_square`, `linkedin_square` | Холст 1:1 и профиль обработки; форматная производная |

Показательные детали реального YAML:

- В [`cid_aware`][profile-aware] включены crop, цвет, noise, sharpen, temporal jitter,
  pitch, EQ, Haas, compand и loudnorm. Промежуточный resample выключен. Профиль
  меняет изображение и звук сильнее, чем консервативные производные.
- [`cid_aggressive`][profile-aggressive] добавляет скорость, chorus, reverb и
  заметную шумовую подложку. Описание прямо говорит, что это не production quality
  default, и требует визуального/слухового контроля.
- [`youtube_1080p`][profile-youtube] разрешает upscale и включает fit-aspect,
  дополнительный crop и noise. На низком исходном разрешении это может создавать
  большой файл без новых деталей; preflight уже умеет объяснить такую ситуацию.
- [`soft`][profile-soft] гарантирует конфигурацию умеренного действия, а не
  эмпирический диапазон качества любого фильма.

Название `cid_*` стоит трактовать как legacy API. Переименование или изменение
поставляемых профилей затрагивает стабильный контракт и должно проходить принятую
в репозитории процедуру RFC/снимков/документации/CHANGELOG.

### Metadata и «санитизация» bitstream

[`metadata.py`][metadata] действительно отключает наследование глобальных metadata,
задаёт чистые поля и восстанавливает нужные language/title/disposition сведения
потоков и главы. Это delivery/provenance operation: разные metadata меняют байты,
но не превращают тот же фильм в другое авторское произведение.

[`sanitizer.py`][sanitizer] — отдельный **опциональный второй encode через libx264**
с audio stream-copy, а не специальное удаление признаков из модели YouTube.
Он нужен для однородного H.264 delivery в определённых workflows, добавляет
generation loss и время. Сохранённый HDR и неподходящий codec отвергаются;
software libx264-путь уже не требует повторного нормализующего encode.
Ни этот модуль, ни смена codec не квалифицированы как метод влияния на Content ID.

## 5. QA: что именно означают числа

### 5.1 Три оси уже разделены в коде

В [`verdict()`][verdict] есть отдельные состояния **correctness**, **quality** и
**visual_similarity**. Высокая pHash-похожесть сама по себе не делает корректный
качественный результат красным. Это полезная архитектура: проблема кодирования
не смешивается с задачей измерения преобразований.

В дефолтном verdict raw VMAF ниже 75 даёт fail, диапазон 75–85 — warning; SSIM
имеет собственную обработку. Это **внутренние эвристические границы проекта**,
а не требования YouTube и не калиброванные универсальные пороги человеческого
качества. Явная `quality_policy` может отдельно требовать raw или registered
VMAF/SSIM. Запрошенное отсутствующее измерение не превращается в успех.
Фактические [модели correctness/loudness/policy][models] уже присутствуют.

### 5.2 Карта метрик и типичных ошибочных прочтений

| Метрика | Реальное вычисление | Допустимый вывод | Недопустимый вывод |
|---|---|---|---|
| MD5 входа/выхода | Hash байтов файла | Файлы побайтово различаются | «YouTube считает видео новым» |
| pHash | Hamming distance между sampled-frame hashes | Выбранные пары отличаются для этого алгоритма | «Видео не узнаваемо человеком/Content ID» |
| Audio Jaccard | Пересечение/объединение множеств 32-битных Chromaprint кодов | Насколько часто совпали коды точно | «Jaccard=0 означает новый звук» |
| Audio Hamming | XOR/popcount пар упорядоченных кодов | Локальная дистанция, требующая проверки выравнивания | «match_confidence — обученная вероятность» |
| `cid_predict_self` | Максимум visual/audio по локальным окнам; затем максимум по окнам | Есть сильно похожий участок в данной эвристике | «Это вероятность жалобы/обнаружения» |
| SSCD raw | Cosine embeddings выбранных пар кадров; mean/min | Image-copy similarity для выбранной сетки и модели | «Полный видео-/аудиодетектор YouTube воспроизведён» |
| VMAF/SSIM raw | Сравнение оригинала и производной | Совокупная разница преобразования и кодирования | «Низкий VMAF доказывает сломанный encoder» при изменённой геометрии |
| VMAF/SSIM registered | Кодированный output против lossless replay точного transformed Plan | Потери кодирования относительно уже преобразованного изображения | «Преднамеренный crop/шум/flash не повредил оригинальный материал» |
| Registered audio/SSCD | Ограниченное выравнивание, coverage/confidence | Дополнительные сведения о сопоставленных samples | «A/V lip sync проверен одним scalar score» |

Например, превосходный registered VMAF может означать точное кодирование уже
испорченного преобразованием изображения. Поэтому нужен просмотр исходника и
производной, а не только сравнение output с transformed reference.

### 5.3 Историческое имя `cid_predict` скрывает важные ограничения

Код [`cid_predict.py`][cid] использует `chunk_sec=4`, но выбирает pHash samples
по нормализованной сетке всей минимальной длительности и распределяет их по
корзинам. Временные подписи корзин формируются отдельно как `i × chunk_sec`.
Это не точная декодерная регистрация каждого четырёхсекундного фрагмента: округление
числа окон и остаток длительности надо учитывать при интерпретации heatmap.

Более существенное различие на фильмах: этот legacy-путь вызывает `_run_fpcalc`,
который ограничивает fingerprint **первыми 600 секундами**, затем делит его на число
корзин всего сравнения. Основной audio QA уже умеет иначе покрывать длинный файл —
пятью разнесёнными 120-секундными окнами. Следовательно, аудиочасть legacy CID-heatmap
нельзя считать честной проверкой всего фильма по четырёхсекундным окнам.
Сравнить [legacy вызов][cid] с [fpcalc/extraction][audio] и
[документированным основным audio QA][qa-doc].

Кроме того, `weakest_chunk` здесь означает **argmax похожести**, а не минимальное
качество. Без пояснения интерфейс способен направить пользователя к неверному
выводу. Отсутствующий fingerprint в legacy-эвристике превращается в audio=0;
это не независимое доказательство низкой похожести.

### 5.4 SSCD полезен как дополнительный local detector

Есть настоящий официальный TorchScript checkpoint SSCD, pinned SHA-256,
детерминированная сетка, extraction через FFmpeg и opt-in ML dependencies.
Обычный путь по умолчанию сравнивает **32 пары кадров**, сначала масштабируя их
до model input. Результат — mean/min cosine, а не временной поиск всех возможных
совпадений и не анализ аудио. [Реализация SSCD][sscd].

Registered SSCD использует ограниченное монотонное сопоставление без повторного
использования выходных кадров, coverage и availability notes. Это сильнее простой
позиционной пары, но остаётся ограниченной локальной моделью. Ни похожесть 0.92,
ни 0.20 не являются порогами Content ID. `sscd_min` — наименее похожая sampled
пара; если вопрос — наличие сильно похожего участка, минимум не отвечает на него.

Локальный [SQLite corpus][corpus] полезен для собственного каталога лицензированных
исходников и производных. Он не содержит базы правообладателей YouTube.

### 5.5 Registered QA уже реализован; target-VMAF loop имеет иной reference

Post-run QA может воспроизвести видеофильтры и seed в lossless FFV1 reference,
зафиксировав source bytes, profile, plan hash, toolchain и seed. Объём reference
ограничен диском и default budget 40 GiB; при недостатке места registered metrics
становятся недоступны с объяснением. Для неизменённой длительности есть single-copy
virtual concat. [Построитель и бюджет reference][registration],
[вызов registered QA][registered-report].

Нельзя из этого заключать, что retry `target_vmaf` уже использует такой же reference:
он всё ещё оценивает source slice. Preflight отвергает сочетание с crop, fit-aspect,
rotate, mirror, blend, temporal jitter, speed, subtitles и tonemap.
[Список и причина запрета][target-vmaf].

## 6. Калибровка: полезный поиск и два воспроизводимых дефекта

### 6.1 Что в ней уже сделано правильно

`calibrate` делит ограниченный clip budget на начало, середину и конец, фиксирует seed,
измеряет anchor factors 1.0/0.25/4.0, затем ищет информативные промежутки без
предположения монотонности. Качество и локальная похожесть — независимые ограничения;
лучший feasible результат выбирается по качеству и мягкости. Полностью оценённые
trials сохраняются; ошибка инфраструктуры повторяется, а не превращается в плохой
балл. Тип качества закрепляется, чтобы не сравнить VMAF одного trial с SSIM другого.
[Реальный loop][calibration], [операторская документация][calibration-doc].

Нюансы: metric `chromaprint` фактически вызывает **смешанную pHash/audio legacy
эвристику**; metric `sscd` использует raw mean cosine. Quality evaluation вызывает
raw source/output `quality_score`, а не plan-registered scorer. Таким образом,
калибровка включает качество преднамеренных изменений в свой raw score и не должна
подаваться как чистая оптимизация кодировщика. [Scoring trial][trial],
[metric dispatch][dispatch], [quality backend][quality].

### 6.2 Подтверждено: сила профиля масштабирует не все реальные эффекты

В [`intensity.py`][intensity] несколько веток используют имена параметров, которых
нет в текущих схемах. Это не теоретическое замечание: runtime-probe на shipped
`cid_aggressive` дал следующую картину.

| Эффект/параметр | Factor=0.25 | Factor=1 | Factor=4 | Причина |
|---|---:|---:|---:|---|
| Sharpen `luma_amount` | 0.10 | 0.10 | 0.10 | Ветка ищет `amount`; реальная схема использует `luma_amount` |
| Temporal `blackout_prob` | 0.05 | 0.05 | 0.05 | Ветка ищет несуществующий `shift_frames` |
| Temporal `drop_prob` | 0.04 | 0.04 | 0.04 | То же |
| Compand `ratio` | 3.0 | 3.0 | 3.0 | Ветка ищет `amount`, не настоящие ratio/threshold |
| Reverb `intensity` | 0.10 | 0.10 | 0.10 | Ветка ищет wet/room_size/damping |
| Audio noise `noise_db` | −12 | −12 | −12 | Ветка ищет amix_weight_noise |
| EQ `jitter_db` | 2.0 | 2.0 | 2.0 | Масштабируется явный band gain, но случайная амплитуда остаётся |
| Haas `randomize_within_ms` | 8.0 | 8.0 | 8.0 | Масштабируется базовый delay, не jitter |

Это не делает весь поисковый алгоритм неработоспособным: crop/color/noise/pitch и
часть других параметров действительно меняются. Однако **factor=0.25 не означает
четверть силы каждого эффекта**. Часть разрушительного стека остаётся, создавая
quality floor, который поиск не способен снять. Схемы: [sharpen][sharpen],
[temporal][temporal], [compand][compand], [reverb][reverb], [audio noise][noise].

### 6.3 Подтверждено: дробный factor способен сделать профиль невалидным

Для `cid_aware` вызов `scale_profile` с factors 0.7, 0.75, 1.5 получает sharpen
`radius=3.5`, `3.75`, `7.5`. Реальная схема требует **int**, поэтому её
`model_validate` возвращает `int_from_float`. Clamp соблюдает диапазон 3–11,
но не дискретный тип поля. Anchor factors могут пройти, а промежуточный trial —
остановиться на build/validation.

Минимальная проверка, повторяющаяся на проверенном checkout:

```python
from pathlib import Path
from pydantic import ValidationError
from video_uniquifier.core.calibration.intensity import scale_profile
from video_uniquifier.core.profile_loader import load_profile
from video_uniquifier.core.transforms import get

profile = load_profile(Path("src/video_uniquifier/profiles/cid_aware.yaml"))
for factor in (0.7, 0.75, 1.5):
    scaled = scale_profile(profile, factor)
    for item in scaled.transforms:
        if item.enabled:
            try:
                get(item.id).schema.model_validate(item.params)
            except ValidationError as error:
                print(factor, item.id, error.errors()[0]["type"], item.params)
```

Существующие тесты не закрывают проблему: часть
[`test_intensity_scaling.py`][intensity-tests] специально передаёт legacy keys
ради покрытия веток, но не валидирует итог настоящей transform schema.
Поэтому они проходят, одновременно пропуская невалидные реальные конфигурации.
Правильная будущая проверка должна использовать shipped-профили, настоящие поля,
дробные factors и schema validation результата, затем ограниченный real-FFmpeg smoke.
Код в рамках этого исследования не исправлялся.

## 7. Где документация и комментарии расходятся с кодом

| Место | Наблюдение | Почему важно |
|---|---|---|
| `docs/qa_report.md:128` | Публичные correctness/loudness и opt-in gates описаны как ещё не реализованные | Модели и independent policy уже есть в коде; пользователь недооценивает либо неверно понимает QA |
| `docs/qa_report.md:186` | Legacy score описан как weighted visual+audio Jaccard | Реально visual — pHash, aggregation — max; формула существенно другая |
| `docs/qa_report.md:71–82` | Утверждается, что audio Jaccard=0 у каждого output, exact codes только при byte-identical audio, Hamming отражает восприятие | Это слишком сильные универсальные формулировки: lossy fingerprint не является инъективной функцией байтов и не заменяет прослушивание |
| `docs/qa_report.md:150–156` | SSCD min описывается через human review, SSCD — через то, что увидит человек | Copy detector — не валидированная модель человеческой оценки качества |
| `video_geom.py:123` | Mirror «полностью уничтожает pHash similarity» | У конкретного кадра/алгоритма результат зависит от содержания; абсолютной гарантии из одной функции hflip не следует |
| `video_subpixel_sharpen.py:1–16` | Universal sub-visible effect и перенос выводов neural audio paper на video high-frequency sensitivity | Сам код доказывает unsharp, а не невидимость или эффективность против современного видеодетектора |
| `audio_noise_overlay.py` | Старый эксперимент 2009/2010 используется в комментариях о breaking CID threshold | Это историческая мотивация, а не квалификация YouTube 2026 |
| `audio_windows.py:3–6` | Делается предположение о temporal-aware audio CID | Инженерная гипотеза; внешней calibration dataset у проекта нет |

Источники этой таблицы: [QA-документация][qa-doc], [актуальные QA-модели][models],
[geom][geom], [sharpen][sharpen], [noise][noise], [audio windows][windows].
Внешняя проверка конкретных научных и исторических ссылок вынесена в технический
отчёт исследования. Исправлять такие тексты полезно без превращения research в
непрошенный рефакторинг контрактов.

## 8. Сопоставление с основными категориями социальных советов

Это функциональная карта категорий, а не статистика их частоты или доказательство
правильности конкретного автора.

| Категория совета | Есть в нашей системе | Что система добавляет | Что остаётся за её пределами |
|---|---|---|---|
| Mirror/crop/zoom/color | Да, профильные transforms | Воспроизводимые seeds, preflight, raw/registered QA | Доказательство прав и реакции Content ID |
| Speed/pitch/EQ | Да | Source-aware sample clock, audio peak gate, измерения | Новый авторский голос, корректный dubbing/сценарий, человеческое принятие |
| Фон/смешивание/рамка | Blend и fit-aspect; конкретная функция зависит от режима | Машинно проверяемый профиль | Полноценный монтаж с semantic narrative, многослойными композициями и ручной режиссурой |
| Субтитры | Burn-in и подготовка через transcription workflow | Общая обработка и проверяемый pipeline | Фактическая проверка текста, перевод с редактурой, оригинальный анализ |
| Новое имя/metadata/hash | Metadata очищается/перезаписывается, hash считается | Управление delivery и точной идентичностью | Преобразование правового статуса либо творческой ценности |
| «Новый codec/GPU/4K» | H.264/HEVC/AV1, software/hardware candidates | Явная политика encoder и медиаконтракт | Универсальный «лучший codec для уникализации» или гарантия качества GPU |
| «Сделать много вариантов» | Seeds, batch, resume, очередь/worker | Надёжная автоматизация, локальный corpus | Значимое различие сценариев и аудитория каждого ролика |
| «Проверить уникальность» | pHash/Chromaprint/SSCD/corpus | Несколько independent diagnostics и provenance | YouTube reference database, calibrated claim probability, monetization review |
| «Добавить комментарий, разбор, оригинальную историю» | Полноценная editorial automation здесь не установлена | Можно обработать уже смонтированный авторский master | Планирование аргументов, авторская озвучка, контекст и смысловой монтаж |

Поэтому корректное позиционирование: **система производных, обработки и QA для
своих/лицензированных master-файлов**. Сравнение её возможностей с CapCut/VN/Premiere
или другими редакторами должно учитывать задачу: автоматический reproducible batch
и полноценное творческое редактирование оцениваются разными критериями.

## 9. Что реально подтверждают сохранённые результаты проекта

Исследование не запускало новый полнометражный benchmark. Ниже приведены
**исторические измерения репозитория**, с указанием их ограничений. Полные медиа и
все артефакты заново не проверялись; источник — retained qualification documentation.

| Свидетельство | Зафиксировано | Практическое ограничение |
|---|---|---|
| Короткая natural matrix, 2026-09-05 | На SDR 60 s `soft`: registered VMAF 97.431, SSIM 0.98949; `medium`: 96.925/0.97607 | Это один корпус/окно, не универсальная гарантия. `medium` здесь хуже и дороже |
| Derived HDR→SDR | Registered VMAF примерно 78.8–79.2 на двух ячейках | PQ/HLG получены преобразованием исходного материала; это не независимые native-camera HDR masters |
| Фильм ~95 min | После audio-tail correction 171345 frames, точный sample count, A/V end gap 4.5 ms | Полный registered replay не выполнен из-за места; число кадров/endpoint не доказывает lip sync каждой сцены |
| Архивный источник ~3 h | Старый pipeline завершил full decode, 324395 frames, historical output 2.263× | Это 400×300 fixture на старой версии/encode-policy; зафиксированы внутренний audio drift и отсутствие registered metrics |
| Fresh long-form v6 attempt | Source diagnostics завершены | Encode не начался: disk admission отказал. Результата output/QA/RSS для этого запуска нет |
| Compact-hash stress | 10820 sampled hashes, ~122.85 MiB sampled process-tree RSS | Четырёхсекундная производная проверяла sample count, а не full three-hour QA и diverse natural scenes |
| Intel VideoToolbox | Строгая локальная матрица H.264/HEVC с probed artifacts | NVENC/QSV/AMF и полный другой driver/host парк этим не квалифицированы |

Первичные внутренние свидетельства: [natural matrix и 95-minute run][natural],
[historical three-hour baseline и блокировка fresh run][benchmarks],
[hardware qualification scope][hardware], [регистр оставшихся рисков][risks].

В реестре также открыты VFR keyframe-origin issue, natural audio alignment,
untagged surround, source-derived VBV cap и broader HDR/long-form qualification.
Актуальная функция `list_keyframes` всё ещё получает stream start вместе со scan
и нормализует frame PTS через него; историческая проблема не объявляется здесь
новой воспроизведённой ошибкой без отдельного fixture-run.
[Код планировщика][keyframes].

## 10. Выполненная проверка и рекомендуемые следующие шаги

При исследовании запущена только сфокусированная проверка относящихся к выводам
unit-контрактов, а не полный `make check` и не benchmark всей версии:

```text
VIDEO_UNIQ_NO_PLUGINS=1 .venv/bin/pytest \
  tests/unit/test_intensity_scaling.py \
  tests/unit/test_calibration_v2.py \
  tests/unit/test_cid_predict.py \
  tests/unit/test_qa_evidence_policy.py \
  tests/unit/test_registered_alignment.py \
  tests/unit/test_registered_reference.py \
  tests/unit/test_quality_score.py \
  -q --disable-warnings --no-cov

114 passed in 1.57s
```

Отдельные read-only probes подтвердили неизменяемые реальные параметры и
`int_from_float` на дробном radius. Проходящий suite не снимает эти находки.

Приоритеты для отдельной реализации:

1. **P1: корректность calibration scaling.** Согласовать реальные schema fields,
   масштабирование random amplitudes, integer/odd kernel constraints и явно
   сообщать об эффектах, которые не масштабируются. Приёмка — valid shipped profiles
   на дробных факторах и actual schema validation; для допустимых эффектов реально
   меняются целевые параметры.
2. **P1/P2: честная временная provenance legacy heuristic.** Отразить fingerprint
   availability, 600-sec cap, реальные timestamps и coverage; не представлять
   аудиоданные начала фильма как whole-film heatmap. Изменение публичных полей/CLI
   оформлять через контрактную процедуру, сначала добавлять объяснение без breakage.
3. **P2: актуализировать QA-документацию и научные комментарии.** Различить pHash,
   max aggregation, Jaccard, Hamming, copy detection и человеческое качество; убрать
   неподтверждённые абсолютные гарантии невидимости и актуального CID threshold.
4. **P2: квалифицировать длинные разрешённые материалы.** Provisioned storage,
   source/output full decode, registered metrics, реальные диалог/музыка/motion,
   события A/V в начале/середине/конце и человеческие labels. Сохранить guards.
5. **P2: profile ablation вместо стека всех эффектов.** Baseline encode и затем
   по одному необходимому изменению; измерять качество, размер, wall time и RSS.
   Добавлять сложный эффект только по подтверждённой задаче производной.
6. **P3: редакторские сценарии как отдельный слой.** Если цель — авторские обзоры,
   комментарии и клипы, определить editorial requirements отдельно: существующий
   transcode/QA core можно использовать после такого монтажа.

Цель приёмки — **корректный, качественный, воспроизводимый разрешённый derivative**.
Из исследования социальных советов не следует заменять эту цель минимальным pHash,
максимальным шумом или неподтверждённой вероятностью отсутствия claim.

## Ссылки на проверенную ревизию

Все ссылки ниже закреплены на audited commit; номера строк относятся к нему.

[registry]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/__init__.py#L45
[geom]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/video_geom.py#L25
[fit]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/video_fit_aspect.py#L63
[blend]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/video_blend.py#L33
[temporal]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/video_temporal_jitter.py#L61
[pitch]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/audio_pitch.py#L84
[haas]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/audio_haas.py#L27
[smear]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/audio_spectral_smear.py#L25
[reverb]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/audio_reverb.py#L29
[noise]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/audio_noise_overlay.py#L42
[subtitles]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/video_subtitles.py#L69
[seed]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/seed_resolver.py#L13
[windows]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/audio_windows.py#L1
[preflight]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/preflight.py#L173
[final]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/orchestrator.py#L992
[profile-aware]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/profiles/cid_aware.yaml#L1
[profile-aggressive]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/profiles/cid_aggressive.yaml#L1
[profile-youtube]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/profiles/youtube_1080p.yaml#L1
[profile-soft]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/profiles/soft.yaml#L1
[verdict]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/report.py#L59
[models]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/models.py#L320
[cid]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/cid_predict.py#L1
[audio]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/audio_fp.py#L58
[qa-doc]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/docs/qa_report.md#L58
[sscd]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/sscd.py#L478
[corpus]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/corpus.py#L1
[registration]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/registration.py#L59
[registered-report]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/report.py#L542
[target-vmaf]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/preflight.py#L120
[calibration]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/calibration/loop.py#L100
[calibration-doc]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/docs/calibrate.md#L32
[trial]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/calibration/loop.py#L246
[dispatch]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/calibration/loop.py#L670
[quality]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/qa/quality.py#L30
[intensity]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/calibration/intensity.py#L111
[sharpen]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/video_subpixel_sharpen.py#L1
[compand]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/transforms/audio_compand.py#L33
[intensity-tests]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/tests/unit/test_intensity_scaling.py#L124
[natural]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/BENCHMARKS.md#L398
[benchmarks]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/BENCHMARKS.md#L3
[hardware]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/BENCHMARKS.md#L351
[risks]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/RISK_REGISTER.md#L10
[keyframes]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/segmenter.py#L90
[metadata]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/metadata.py#L26
[sanitizer]: https://github.com/Hostlife22/video-uniquifier/blob/03c707a5c4a68397511cb38f881335a00990f271/src/video_uniquifier/core/sanitizer.py#L1
