<a id="filter-graph"></a>

# Граф фильтров

Конвейер объединяет преобразования линейно в один граф `-filter_complex` для каждого вызова ffmpeg. Для каждого входа существует ровно один этап на стороне Python (без `bgr24` возвратно через `subprocess.stdin`).

<a id="building-blocks"></a>

## Строительные блоки

```
TransformSpec(id, kind="video"|"audio", schema, build)
  ↓ build(params, alloc, in_label, rng=...) ↓
FilterChain(in_label, out_label, filter_str, extra_inputs)
```

`LabelAllocator` выдает уникальные метки (`v1`, `v2`, …, `a1`, `a2`, …), чтобы конвейер мог соединять фрагменты без координации между преобразованиями.

Сборщики, выбирающие вариативность для каждого запуска, принимают необязательный аргумент `rng=random.Random`, инициализированный из `Plan.run_seed`. Один и тот же seed → идентичный граф фильтров.

<a id="registered-transforms-21"></a>

## Зарегистрированные преобразования (21)

| ID |Вид|Примечания|
|---|---|---|
| `video.crop_resize` |видео|микро-кадр + масштабирование Lanczos|
| `video.rotate` |видео|вращение на 0.05–0.5° с заполнением краев|
| `video.color_eq` |видео|разброс яркости/контрастности/гаммы/насыщенности|
| `video.noise` |видео|зернистость пленки через `noise=alls=N:allf=t+u`|
| `video.mirror` |видео|горизонтальное отражение (только при выборе пользователем)|
| `video.blend_b` |видео|смешение кадров с вторым `-i B.mp4`|
| `video.speed` |видео| `setpts=PTS/rate` |
| `video.temporal_jitter` |видео|потемнение на период + выпадение на фазе с случайным RNG (Fojcik 2025)|
| `video.tonemap_sdr` |видео|линейная шкала zscale → тональная карта (hable/reinhard/mobius/aces) → SDR|
| `video.fit_aspect` |видео|обрезка/буквенное окно до целевого соотношения сторон и размера|
| `video.subpixel_sharpen` |видео|мягкая маска резкости только для яркости|
| `video.subtitles` |видео|опциональное встраивание субтитров SRT с проверкой пути/возможностей|
| `audio.pitch_tempo` |аудио|`rubberband` (с сохранением формант) или каскад `asetrate`+`atempo`|
| `audio.eq` |аудио|параметрические `equalizer` полосы|
| `audio.resample` |аудио|`aresample` в необычный промежуточный SR и обратно|
| `audio.compand` |аудио|джиттер динамического диапазона|
| `audio.reverb` |аудио|`aecho` пресеты (маленькая комната / средняя комната / зал / пластина)|
| `audio.spectral_smear` |аудио|мягкий `chorus` для смещения chromaprint|
| `audio.haas_stereo` |аудио|`adelay=0|N` стереоширитель, совместимый с моно (Smitelli 2010)|
| `audio.noise_overlay` |аудио|параметрический розовый/белый/коричневый шум через `anull` + `anoisesrc` + `amix`|
| `audio.loudnorm` |аудио|двухпроходный EBU R128; первый проход кэшируется в `state.json`|

<a id="composition-for-a-typical-profile-cid_aware"></a>

## Композиция для типичного профиля (cid_aware)

```
[0:v:0]
   crop=iw*0.96:ih*0.96:iw*0.02:ih*0.02,
   scale=round(iw/0.96/2)*2:round(ih/0.96/2)*2:flags=lanczos            [v1]
[v1]
   eq=brightness=0.015:contrast=1.022:gamma=0.99:saturation=1.04        [v2]
[v2]
   noise=alls=5:allf=t+u                                                 [v3]
[v3]
   geq=lum='if(eq(mod(N\,30)\,8)\,128\,p(X\,Y))':
       cb='if(eq(mod(N\,30)\,8)\,128\,p(X\,Y))':
       cr='if(eq(mod(N\,30)\,8)\,128\,p(X\,Y))',
   select='not(eq(mod(n\,50)\,17))'                                     [v4]
[v4]
   scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p                    [vout]

[0:a:0]
   rubberband=pitch=1.058:tempo=1.000                                   [a1]
[a1]
   equalizer=f=120:t=q:w=1.0:g=-0.6,
   equalizer=f=4500:t=q:w=1.0:g=0.4                                     [a2]
[a2]
   adelay=0|17                                                          [a3]
[a3]
   aresample=47999,aresample=48000                                      [a4]
[a4]
   compand=attacks=0.05:decays=0.5:points=-80/-80|-20.7/-8.3|0/-3       [a5]
[a5]
   loudnorm=I=-14.0:TP=-1.5:LRA=11.0:
   measured_I=-21.8:measured_TP=-17.69:measured_LRA=0.1:
   measured_thresh=-31.8:offset=-0.0:linear=true:print_format=summary  [aout]
```

Затем:

```bash
ffmpeg -hide_banner -y \
  -i input.mp4 \
  -filter_complex "<above>" \
  -map "[vout]" -map "[aout]" \
  -map "0:a:1?" -c:a:1 copy \
  -map "0:s?" -c:s copy \
  -map_chapters -1 \
  -c:v libx264 -preset slow -crf 18 \
  -c:a:0 aac -b:a:0 256k \
  -movflags +faststart \
  -map_metadata -1 \
  output.mp4
```

<a id="even-dimensions-guard"></a>

## Защита четных размеров

Хвост всегда вставляет `scale=trunc(iw/2)*2:trunc(ih/2)*2` перед
`format=yuv420p`. `libx264` отвергает нечетные ширины/высоты; микроподрезка может оставить кадр 319×180, который мы здесь округляем вниз до 318×180.

<a id="hdr-linear-light-wrap"></a>

## HDR линейный свет wrap

Когда источник HDR (PQ / HLG) и `Profile.keep_hdr=true`, конвейер оборачивает каждое *цветовое преобразование* (в настоящее время `video.color_eq` +
`video.noise`) в обход zscale через `core/transforms/hdr_wrap.py`:

```
zscale=transfer=linear:matrix=gbr:npl=100,
format=gbrpf32le,
  eq=brightness=0.012:contrast=1.018:gamma=0.995:saturation=1.03,
  noise=alls=4:allf=t+u,
zscale=transfer=smpte2084:matrix=bt2020nc:npl=100,
format=yuv420p10le
```

Требуется линейный свет, так что "+1 % яркости" означает одно и то же в верхней и нижней части кривой PQ. Также требуется явный формат RGB с плавающей запятой: обработка только передачи в субдискретизированной YUV может создавать сильные цветовые искажения, оставляя HDR-метаданные на вид правильными. Геометрические преобразования (обрезка / изменение масштаба / вращение / скорость) и временные (temporal_jitter) работают в любой области и не обернуты.

Если профиль выбирает `video.tonemap_sdr` (HDR → SDR), обертка пропускается: тональная карта сжимает HDR-передачу в начале цепочки, а остальная часть графа работает в обычном SDR BT.709. Выход `pix_fmt` всегда
`yuv420p` в этом случае.

<a id="the-videoblend_b-special-case"></a>

## Специальный случай `video.blend_b`

`video.blend_b` — это единственное преобразование, которое требует дополнительного входа. Его
`FilterChain.extra_inputs` указывает вторичный файл. Конвейер:

1. Добавляет `-i B.mp4` к argv ffmpeg (индекс входа 1).
2. Перезаписывает замещающий токен `__B__` в `filter_str` на `[1:v]`.

```
[0:v:0][1:v]scale2ref=w=iw:h=ih[b_scaled][a_ref];
[a_ref][b_scaled]blend=all_expr='A*0.97+B*0.03'                       [v_out]
```

<a id="the-audionoise_overlay-side-chain"></a>

## Боковая цепочка `audio.noise_overlay`

`anoisesrc` является *источником* фильтром (0 входов, 1 выход), поэтому он не может находиться в линейной цепочке. Трансформация создает три подцепи внутри своей структуры
`filter_str`:

```
anull[main];
anoisesrc=c=pink:r=48000:amplitude=1[noise];
[main][noise]amix=inputs=2:weights=0.75 0.25:duration=first
```

Ведущий `anull` потребляет входную метку, предоставленную конвейером, и создает метку `[main]`-узла, с которым окончательный `amix` может сочетаться `[noise]`.

<a id="segment-mode-vs-full-mode"></a>

## Режим сегмента против полного режима

Для длинных входов `core/segmenter.py` вызывает `build_video_segment_command` (только видеотрансформации, аудио = копирование потока) один раз на сегмент, и
`build_main_audio_command` один раз на полном источнике (только аудиотрансформации, кэшировано двухпроходное loudnorm). Финальный мультиплекс использует демультиплексор concat и копирование потока, поэтому стыки не вводят шум повторного кодирования.

Под `seed_strategy: divergent`, `segmenter._plan_for_segment` подставляет семя, полученное для каждого сегмента, перед вызовом `build_video_segment_command`, чтобы стохастические преобразования каждого сегмента (фаза обрезки, смещения джиттера, семя шума и т.д.) были различными.

<a id="quality-args-per-encoder"></a>

## Параметры качества для каждого кодера

|Поставщик|Параметры качества|
|--------|--------------|
| `nvenc` | `-preset p6 -rc vbr -cq 19 -b:v 0 -maxrate ~1.25× -bufsize 2×maxrate` |
| `qsv` | `-global_quality 19 -look_ahead 1` |
| `amf` | `-rc cqp -qp_i 19 -qp_p 19` |
| `videotoolbox` | `-q:v 50` |
| `x264` / `x265` | `-preset slow -crf 18` |

Сохранение HDR: конвейер выбирает `yuv420p10le` вместо `yuv420p`, когда источник HDR, `keep_hdr=true`, и кодер поддерживает 10-битное кодирование (`hevc_nvenc`, `hevc_qsv`, `hevc_videotoolbox`, `libx265`). `libx264` не поддерживает 10-битные профили; проверка перед запуском завершается с ошибкой.
