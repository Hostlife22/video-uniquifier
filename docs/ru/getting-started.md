<a id="getting-started"></a>

# Начало работы

5-минутный тур по `video-uniquifier`. Охватывает CLI, GUI и веб — выберите один, и остальные станут знакомыми позже.

<a id="1-install"></a>

## 1. Установка

```bash
pip install "video-uniquifier[gui,web] @ git+https://github.com/Hostlife22/video-uniquifier.git@v2.2.0"
python -c "from importlib.resources import files; from pathlib import Path; Path('review-soft.yaml').write_bytes(files('video_uniquifier').joinpath('profiles/soft.yaml').read_bytes())"
```

Загружает основное CLI, настольный GUI PyQt6 и веб-оболочку FastAPI. Уберите скобку, если эта среда не нужна. См. [Установка](install.md) для требований к бинарным файлам (`ffmpeg`, необязательно `fpcalc`, необязательно Whisper).

<a id="2-pick-or-install-a-profile"></a>

## 2. Выберите (или установите) профиль

Предустановленные профили покрывают большинство сценариев использования:

|Идентификатор профиля|Сценарий использования|
|----------------------|---------------------------------------|
| `soft`               |Наименее влияющий базовый|
| `medium`             |Сбалансированный по умолчанию|
| `aggressive`         |Экспериментально более сильная обработка|
| `cid_aware`          |Экспериментальная совместимость с устаревшими версиями|
| `cid_aggressive`     |Максимальная совместимость с устаревшими версиями|
| `youtube_shorts`     |9:16 изменение кадра для Shorts (≤ 60 с)|
| `youtube_1080p`      |16:9 1080p|
| `youtube_4k`         | 16:9 4K                               |
| `tiktok_vertical`    |9:16 для TikTok|
| `instagram_reels`    |9:16 для Reels|
| `instagram_square`   |1:1 для Instagram|
| `linkedin_square`    |1:1 для LinkedIn|

Также просматривайте профили, внесенные сообществом:

```bash
video-uniq profile list-community
video-uniq profile install cid_aware       # installs into ~/.config/video_uniquifier/profiles/
```

Каталог закреплён по SHA для каждой записи; установщик отказывается записывать файл, если хеш не совпадает. Подробности в [Community marketplace](marketplace.md).

<a id="3-sanity-check-the-input"></a>

## 3. Проверьте исходник

```bash
video-uniq probe ~/Videos/in.mp4
video-uniq preflight ~/Videos/in.mp4 --profile review-soft.yaml
```

`probe` выводит разобранный `SourceMeta` (контейнер, потоки, состояние HDR). `preflight` выполняет ту же матрицу предупреждений, которая используется внутри `run`, и показывает, что бы не прошло до начала кодирования.

<a id="4-run-an-encode"></a>

## 4. Запустите кодирование

=== "CLI"

    ```bash
    video-uniq run ~/Videos/in.mp4 \
        --profile review-soft.yaml \
        --out ~/Videos/out.mp4
    ```

=== "Настольный интерфейс GUI"

    ```bash
    video-uniq-gui
    ```

    Then on the **Run** screen: pick input, pick profile, click
    **▶ Run**. The live divergence indicator on the right shows
    a sparkline of pHash divergence per segment.

=== "Веб-интерфейс (Docker)"

    ```bash
    docker run --rm -p 127.0.0.1:8080:8080 \
        -v $PWD/input:/data/input:ro \
        -v $PWD/output:/data/output \
        -v $PWD/work:/data/work \
        ghcr.io/hostlife22/video-uniquifier:v2.2.0
    ```

    Open http://127.0.0.1:8080 and fill in the form. Full guide
    at [Web UI & Docker](web.md).

<a id="5-inspect-the-qa-report"></a>

## 5. Проверьте отчёт QA

Каждый запуск создаёт `<out>.qa.json` и `<out>.qa.html` рядом с результатом. Откройте HTML в браузере для полного отчёта, включая pHash / chromaprint / VMAF / (по желанию) SSCD. Схема документирована в [QA report](qa_report.md).

<a id="6-next-steps"></a>

## 6. Следующие шаги

* **Автоматически подстроить профиль под этот источник** — `video-uniq calibrate` (или кнопка **Auto-tune** на экране GUI Run) подбирает параметры относительно цели качества. См. [Калибровка](calibrate.md).
* **Обработать папку пакетно** — `video-uniq batch ~/Videos/in/` или экран Batch.
* **Распределить по NAS / лаборатории** — `video-uniq worker` + общая файловая система. См. [Распределённая пакетная обработка](distributed.md).
* **Предварительно сгенерировать субтитры** — `video-uniq subtitles generate`
  ~/Videos/in.mp4`. The `video.subtitles` трансформирует их и встраивает при кодировании.
* **Подключиться к телеметрии** — Настройки → Локальная телеметрия, или передайте
  `--telemetry` в ваших собственных скриптах. Только локальный JSONL; без сети.

Застряли? Откройте `video-uniq <subcommand> --help` для любой подкоманды или создайте issue.
