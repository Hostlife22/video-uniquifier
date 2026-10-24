<a id="installation-and-launch"></a>

# Установка и запуск

Руководство описывает настольный выпуск 2.2.0 и установку из исходников. Обрабатывайте только видео, которыми вы владеете или которые разрешено изменять и распространять по лицензии. До публикации релиза используйте исходники; ссылки ниже относятся к v2.2.0.

<a id="desktop-downloads"></a>

## Готовые сборки

Скачивайте файлы из [GitHub Releases](https://github.com/Hostlife22/video-uniquifier/releases). Выпуск содержит контрольные суммы, перечень компонентов CycloneDX (SBOM) и файлы проверки подписи cosign.

| Платформа | Архив | FFmpeg |
|---|---|---|
| Linux x86_64 | `video-uniq-gui-2.2.0-x86_64.AppImage` | Статические FFmpeg/FFprobe внутри |
| macOS Apple Silicon | `video-uniq-gui-macOS.zip` | Устанавливается отдельно |
| Windows 10/11 | `video-uniq-gui-Windows.zip` | Устанавливается отдельно |

Сборка macOS предназначена для Apple Silicon. На Intel Mac и других архитектурах установите приложение из исходников или соберите локально. Для Linux также доступен tar-архив; в отличие от AppImage, ему нужен системный FFmpeg.

### Linux

```bash
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-2.2.0-x86_64.AppImage
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
chmod +x video-uniq-gui-2.2.0-x86_64.AppImage
./video-uniq-gui-2.2.0-x86_64.AppImage
```

### macOS

```bash
brew install ffmpeg
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-macOS.zip
curl -LO https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS
shasum -a 256 video-uniq-gui-macOS.zip
unzip video-uniq-gui-macOS.zip
mv video-uniq-gui.app /Applications/
open /Applications/video-uniq-gui.app
```

Перед распаковкой сравните выведенную сумму со строкой архива в `SHA256SUMS`. Приложение имеет ad-hoc подпись без нотариального заверения Apple Developer ID. Если Gatekeeper блокирует проверенный файл, разрешите запуск этого приложения в настройках конфиденциальности и безопасности macOS. Сборка Intel или universal этим процессом не заявлена.

### Windows

```powershell
choco install ffmpeg
Invoke-WebRequest https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/video-uniq-gui-Windows.zip -OutFile video-uniq-gui-Windows.zip
Invoke-WebRequest https://github.com/Hostlife22/video-uniquifier/releases/download/v2.2.0/SHA256SUMS -OutFile SHA256SUMS
Get-FileHash video-uniq-gui-Windows.zip -Algorithm SHA256
Expand-Archive video-uniq-gui-Windows.zip -DestinationPath .
.\video-uniq-gui\video-uniq-gui.exe
```

Перед распаковкой сравните сумму с `SHA256SUMS`. Сборки Windows не подписаны. Если SmartScreen блокирует проверенный файл, проверьте источник перед разрешением запуска; корпоративная политика AppLocker или WDAC может требовать участия администратора.

<a id="verify-the-release"></a>

### Проверка релиза

Не запускайте архив, сумма которого отличается от `SHA256SUMS`. Для дополнительной проверки подписи GitHub Actions отдельно установите cosign:

```bash
cosign verify-blob \
  --bundle video-uniq-gui-2.2.0-x86_64.AppImage.cosign.bundle \
  --certificate-identity-regexp 'https://github\.com/Hostlife22/video-uniquifier/' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  video-uniq-gui-2.2.0-x86_64.AppImage
```

Для других файлов используйте соответствующий `.cosign.bundle`. Процесс выпуска проверяет подписи до создания черновика релиза. `sbom.cdx.json` и отдельные SBOM сборок описывают состав пакетов, но не удостоверяют отсутствие уязвимостей.

<a id="system-requirements"></a>

## Системные требования

Для исходников нужны Python 3.11 или новее, FFmpeg и FFprobe в `PATH`. CI проверяет Python 3.11 и 3.12 на Linux, macOS и Windows. Время кодирования, память и рабочее место на диске зависят от длительности, разрешения, кодека и преобразований.

Установите FFmpeg через Homebrew на macOS (`brew install ffmpeg`), APT на Debian/Ubuntu (`sudo apt install ffmpeg`) или Chocolatey на Windows (`choco install ffmpeg`). Проверьте возможности конкретной сборки:

```bash
ffmpeg -version
ffprobe -version
ffmpeg -filters
```

Дополнительные возможности: `libvmaf` для оценки качества по совмещённому эталону, `zscale` для HDR, `rubberband` для соответствующего аудиопреобразования и `fpcalc` из Chromaprint для аудиоотпечатков. Если обязательного фильтра нет, установите подходящую сборку или отключите использующее его преобразование.

<a id="install-from-source"></a>

## Установка из исходников

```bash
git clone https://github.com/Hostlife22/video-uniquifier.git
cd video-uniquifier
```

На macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,gui]"
```

В Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,gui]"
```

Для CLI достаточно `-e .`. Набор `[gui]` добавляет PyQt6 и WebEngine, `[dev,gui]` — ещё и инструменты разработки. Дополнительные наборы `[web]`, `[ml]` и `[scene]` включают HTTP-интерфейс, SSCD и определение сцен соответственно.

```bash
video-uniq --version
video-uniq probe --encoders
video-uniq-gui --version
```

Обе команды версии для этого выпуска должны показывать `2.2.0`. Поиск кодировщиков выполняет реальные пробные запуски, поэтому первый вызов может занять несколько секунд.

<a id="first-cli-run"></a>

## Первый запуск CLI

Начните с короткого разрешённого к обработке клипа и щадящего профиля:

```bash
video-uniq probe /path/to/master.mp4
video-uniq preflight /path/to/master.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml
video-uniq run /path/to/master.mp4 \
  --profile src/video_uniquifier/profiles/soft.yaml \
  --out /tmp/derivative.mp4 --encoder libx264
```

Проверьте результат и отчёт QA. Профили находятся в `src/video_uniquifier/profiles/`, примеры бизнес-правил Reels — в `examples/facebook_reels/`. См. [быстрый старт CLI](getting-started.md) и [руководство Reels](facebook-reels.md).

<a id="first-desktop-run"></a>

## Первый запуск приложения

```bash
video-uniq-gui
```

Выберите исходник, путь результата и профиль, запустите предварительную проверку и обработку. Проверьте воспроизведение и отчёт QA перед использованием результата. Рабочая область **Видеодоставка** содержит последовательность Reels: исходник → настройки → результат. Все одиннадцать экранов описаны в [обзоре приложения](gui-walkthrough.md).

<a id="tests-and-local-builds"></a>

## Тесты и локальная сборка

Основной интерфейс разработчика — Makefile. Интеграционные тесты запускают настоящий FFmpeg; полный набор может идти десятки минут в зависимости от оборудования и установленных дополнений.

```bash
make lint
make typecheck
make test-unit
make test-integration
make check
```

Сборка wheel-пакета Python или настольного приложения:

```bash
make build-wheel
make build
```

Wheel появляется в `dist/`. Результат настольной сборки: `dist/video-uniq-gui.app` на macOS, `dist/video-uniq-gui/video-uniq-gui.exe` на Windows, `dist/video-uniq-gui/video-uniq-gui` на Linux. Собирайте приложение на целевой операционной системе.

Просмотр документации на трёх языках:

```bash
python -m pip install -e ".[docs,docs-test]"
make docs-build
make docs-serve
```

<a id="update-and-uninstall"></a>

## Обновление и удаление

Обновление чистой рабочей копии:

```bash
git pull --ff-only
python -m pip install -e ".[dev,gui]" --upgrade
```

Удаление пакета из активного окружения:

```bash
python -m pip uninstall video-uniquifier
```

После этого можно удалить `.venv` проекта, если она больше не нужна. Сохраните нужные результаты, профили и данные корпуса.

<a id="shared-resource-admission"></a>

## Совместное распределение ресурсов

CLI, GUI, веб-интерфейс и исполнители очереди согласуют предполагаемое число кодировщиков и расход диска через общий каталог с правом записи. Для взаимодействующих процессов задайте один абсолютный путь и запускайте их от одной служебной учётной записи:

```bash
export VIDEO_UNIQ_RESOURCE_LOCK_DIR=/shared/video-work/resource-admission
```

В Docker используется `/data/work/.resource-admission`; контейнерам нужен общий том `/data/work`. Не удаляйте реестр во время кодирования. Перед сбросом после изменения оборудования или доступной мощности остановите все процессы. Контроль основан на оценках; для жёсткого ограничения диска нужны квоты файловой системы. Сетевые файловые системы, разные UID и смешанные настройки `CUDA_VISIBLE_DEVICES` пока не проверены.

Контроль отсутствия вывода FFmpeg по умолчанию срабатывает через 600 секунд. `VIDEO_UNIQ_STALL_TIMEOUT_SEC=0` отключает его. `VIDEO_UNIQ_WALL_TIMEOUT_SEC` задаёт жёсткий лимит времени процесса; по умолчанию он отключён.

<a id="troubleshooting"></a>

## Решение проблем

- **FFmpeg не найден:** проверьте `PATH` или задайте абсолютные пути `VIDEO_UNIQ_FFMPEG` и `VIDEO_UNIQ_FFPROBE`.
- **Нет PyQt6:** установите набор `[gui]` в окружение, из которого запускается приложение.
- **Встроенный просмотрщик QA недоступен:** используйте **Открыть в браузере**; WebEngine необязателен при запуске без экрана.
- **В Linux отсутствует плагин xcb:** установите системные библиотеки:

```bash
sudo apt install libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
  libxkbcommon-x11-0 libgl1
```

- **В Homebrew нет HDR/rubberband-фильтра:** проверьте список фильтров. Полную сборку можно выбрать явно:

```bash
brew install ffmpeg-full
export VIDEO_UNIQ_FFMPEG="$(brew --prefix ffmpeg-full)/bin/ffmpeg"
export VIDEO_UNIQ_FFPROBE="$(brew --prefix ffmpeg-full)/bin/ffprobe"
```

- **В Wayland не работает перетаскивание:** используйте **Обзор…** или запускайте с `QT_QPA_PLATFORM=xcb`, если доступен XWayland.
- **Нужно повторно определить кодировщики:** после замены FFmpeg или изменения GPU используйте **Настройки → Сбросить кеш кодировщиков**.

Дополнительные настройки описаны в разделах [профили](profiles.md), [безопасность](security.md) и [содержание документации](documentation.md).
