"""Translation catalogues for the GUI (v0.9.0 R5).

* ``SOURCE_KEYS`` is the canonical set of strings the GUI wraps in
  ``self.tr(...)`` and is the only place we list them.
  ``coverage_ratio`` checks each locale against this set.
* ``TRANSLATIONS[<locale>][<source>]`` is what the runtime
  translator returns. Missing keys fall back to the source string,
  which is the documented graceful-degradation contract.

Contributing a new locale: copy the ``ru_RU`` block, replace the
right-hand values, add the locale code to ``TRANSLATIONS``. Run
``pytest tests/unit/test_i18n.py -v`` — the coverage test will
report your locale's coverage ratio in its log line.

Bilingual style for v0.9 (en → ru):

* CTAs use the Russian imperative (``Запустить``, ``Сохранить``).
* Status nouns stay nominative (``готово``, ``ошибка``).
* Mnemonics: the trailing ``&`` in source strings is preserved in
  the translation so Qt can mark the shortcut letter. The Russian
  side picks a Cyrillic letter close to the English mnemonic.
"""

from __future__ import annotations

# Source-of-truth list of every translatable string the v0.9 GUI
# wraps. Add an entry here when you wrap a new string with tr().
# Keep alphabetised within sections; section headers are comments.
SOURCE_KEYS: tuple[str, ...] = (
    # ---- Run screen ----
    "&Run",
    "&Cancel",
    "&Pause",
    "Auto-tune for this source",
    "Input file",
    "Output file",
    "Profile",
    "Encoder",
    "Workers",
    "Status: idle",
    "Status: running",
    "Status: completed",
    "Status: failed",
    "Status: cancelled",

    # ---- Settings screen ----
    "Settings",
    "Appearance",
    "Defaults",
    "Maintenance",
    "Language",
    "Theme",
    "Default profile",
    "Local telemetry (opt-in)",
    "Post-job notifications (webhook + SMTP)",
    "&Save",
    "&Reset encoder cache",
    "Open &log folder",
    "Open &config folder",

    # ---- Common dialogs ----
    "OK",
    "Cancel",
    "Apply",
    "Close",
    "Yes",
    "No",
)


# locale → {source: translation}. Missing keys fall back to source.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru_RU": {
        # ---- Run screen ----
        "&Run": "&Запустить",
        "&Cancel": "&Отмена",
        "&Pause": "&Пауза",
        "Auto-tune for this source": "Автонастройка для этого источника",
        "Input file": "Исходный файл",
        "Output file": "Выходной файл",
        "Profile": "Профиль",
        "Encoder": "Кодировщик",
        "Workers": "Потоки",
        "Status: idle": "Статус: ожидание",
        "Status: running": "Статус: выполняется",
        "Status: completed": "Статус: завершено",
        "Status: failed": "Статус: ошибка",
        "Status: cancelled": "Статус: отменено",

        # ---- Settings screen ----
        "Settings": "Настройки",
        "Appearance": "Внешний вид",
        "Defaults": "По умолчанию",
        "Maintenance": "Обслуживание",
        "Language": "Язык",
        "Theme": "Тема",
        "Default profile": "Профиль по умолчанию",
        "Local telemetry (opt-in)": "Локальная телеметрия (по согласию)",
        "Post-job notifications (webhook + SMTP)":
            "Уведомления о завершении (webhook + SMTP)",
        "&Save": "&Сохранить",
        "&Reset encoder cache": "&Сбросить кэш кодировщиков",
        "Open &log folder": "Открыть папку &логов",
        "Open &config folder": "Открыть папку &конфигурации",

        # ---- Common dialogs ----
        "OK": "ОК",
        "Cancel": "Отмена",
        "Apply": "Применить",
        "Close": "Закрыть",
        "Yes": "Да",
        "No": "Нет",
    },
    # v1.3.0 Task 35 — Simplified Chinese.  Mainland-form punctuation
    # ("：" rather than ":") so the screen reader cadence reads cleanly
    # for zh-CN users.  Mnemonics: the trailing "&" is preserved; Qt
    # ignores it when the next character has no underline-able glyph
    # (Chinese ideographs are non-mnemonic in Qt's renderer), so the
    # accelerator falls back to the canonical menu position.
    "zh_CN": {
        # ---- Run screen ----
        "&Run": "&运行",
        "&Cancel": "&取消",
        "&Pause": "&暂停",
        "Auto-tune for this source": "为此源自动调优",
        "Input file": "输入文件",
        "Output file": "输出文件",
        "Profile": "配置",
        "Encoder": "编码器",
        "Workers": "工作进程",
        "Status: idle": "状态：空闲",
        "Status: running": "状态：运行中",
        "Status: completed": "状态：已完成",
        "Status: failed": "状态：失败",
        "Status: cancelled": "状态：已取消",

        # ---- Settings screen ----
        "Settings": "设置",
        "Appearance": "外观",
        "Defaults": "默认值",
        "Maintenance": "维护",
        "Language": "语言",
        "Theme": "主题",
        "Default profile": "默认配置",
        "Local telemetry (opt-in)": "本地遥测（自愿加入）",
        "Post-job notifications (webhook + SMTP)":
            "任务结束通知（webhook + SMTP）",
        "&Save": "&保存",
        "&Reset encoder cache": "&重置编码器缓存",
        "Open &log folder": "打开&日志文件夹",
        "Open &config folder": "打开&配置文件夹",

        # ---- Common dialogs ----
        "OK": "确定",
        "Cancel": "取消",
        "Apply": "应用",
        "Close": "关闭",
        "Yes": "是",
        "No": "否",
    },
    # v1.3.0 Task 35 — Spanish (neutral / Spain).  Verb forms use the
    # imperative-formal usted register for CTAs ("Ejecute", "Cancele")
    # so the strings read appropriately on enterprise installs; status
    # nouns stay in the passive participle ("completado", "fallido").
    "es": {
        # ---- Run screen ----
        "&Run": "&Ejecutar",
        "&Cancel": "&Cancelar",
        "&Pause": "&Pausar",
        "Auto-tune for this source": "Auto-ajustar para esta fuente",
        "Input file": "Archivo de entrada",
        "Output file": "Archivo de salida",
        "Profile": "Perfil",
        "Encoder": "Codificador",
        "Workers": "Procesos paralelos",
        "Status: idle": "Estado: inactivo",
        "Status: running": "Estado: en ejecución",
        "Status: completed": "Estado: completado",
        "Status: failed": "Estado: fallido",
        "Status: cancelled": "Estado: cancelado",

        # ---- Settings screen ----
        "Settings": "Configuración",
        "Appearance": "Apariencia",
        "Defaults": "Valores predeterminados",
        "Maintenance": "Mantenimiento",
        "Language": "Idioma",
        "Theme": "Tema",
        "Default profile": "Perfil predeterminado",
        "Local telemetry (opt-in)": "Telemetría local (voluntaria)",
        "Post-job notifications (webhook + SMTP)":
            "Notificaciones al finalizar (webhook + SMTP)",
        "&Save": "&Guardar",
        "&Reset encoder cache": "&Restablecer caché del codificador",
        "Open &log folder": "Abrir carpeta de &registros",
        "Open &config folder": "Abrir carpeta de &configuración",

        # ---- Common dialogs ----
        "OK": "Aceptar",
        "Cancel": "Cancelar",
        "Apply": "Aplicar",
        "Close": "Cerrar",
        "Yes": "Sí",
        "No": "No",
    },
    # v1.3.0 Task 35 — Portuguese (Brazil).  Distinct from European
    # Portuguese in tense and lexicon: "salvar" (BR) vs "guardar" (PT),
    # gerundive present ("em execução") common in BR enterprise UIs.
    "pt_BR": {
        # ---- Run screen ----
        "&Run": "&Executar",
        "&Cancel": "&Cancelar",
        "&Pause": "&Pausar",
        "Auto-tune for this source": "Auto-ajustar para esta fonte",
        "Input file": "Arquivo de entrada",
        "Output file": "Arquivo de saída",
        "Profile": "Perfil",
        "Encoder": "Codificador",
        "Workers": "Processos paralelos",
        "Status: idle": "Status: ocioso",
        "Status: running": "Status: em execução",
        "Status: completed": "Status: concluído",
        "Status: failed": "Status: falhou",
        "Status: cancelled": "Status: cancelado",

        # ---- Settings screen ----
        "Settings": "Configurações",
        "Appearance": "Aparência",
        "Defaults": "Padrões",
        "Maintenance": "Manutenção",
        "Language": "Idioma",
        "Theme": "Tema",
        "Default profile": "Perfil padrão",
        "Local telemetry (opt-in)": "Telemetria local (opcional)",
        "Post-job notifications (webhook + SMTP)":
            "Notificações pós-execução (webhook + SMTP)",
        "&Save": "&Salvar",
        "&Reset encoder cache": "&Limpar cache do codificador",
        "Open &log folder": "Abrir pasta de &logs",
        "Open &config folder": "Abrir pasta de &configuração",

        # ---- Common dialogs ----
        "OK": "OK",
        "Cancel": "Cancelar",
        "Apply": "Aplicar",
        "Close": "Fechar",
        "Yes": "Sim",
        "No": "Não",
    },
}

# Desktop workspace vocabulary. Technical profile IDs and metric names stay unchanged.
_STUDIO_RU = {
    "HDR samples are unavailable; use full processing to preserve HDR metadata.":
        "Тестовый фрагмент HDR недоступен. Используйте полную обработку с сохранением HDR.",
    "Process video": "Обработка видео",
    "Batch processing": "Пакетная обработка",
    "Auto-tune": "Автонастройка",
    "Quality reports": "Отчёты о качестве",
    "Profiles": "Профили обработки",
    "History": "История",
    "Reference library": "Библиотека эталонов",
    "Processing queue": "Очередь обработки",
    "Experiments": "Эксперименты",
    "WORKSPACE": "РАБОТА С ВИДЕО",
    "TUNING & QUALITY": "НАСТРОЙКА И КАЧЕСТВО",
    "LIBRARY": "БИБЛИОТЕКА",
    "TOOLS": "ИНСТРУМЕНТЫ",
    "Local processing": "Локальная обработка",
    "Ready": "Готово к работе",
    "Choose a video, adjust processing and save the result.":
        "Выберите видео, настройте обработку и сохраните результат.",
    "Process a folder of videos with one profile and track each result.":
        "Обработайте папку видео одним профилем и следите за результатом каждого файла.",
    "Find profile settings that balance visual change and measured quality.":
        "Подберите настройки, которые сбалансируют изменение изображения и его качество.",
    "Compare source and output, or open a report from a previous run.":
        "Сравните исходное и обработанное видео или откройте готовый отчёт.",
    "Adjust processing recipes and inspect their settings before saving.":
        "Настройте эффекты обработки и проверьте параметры перед сохранением.",
    "Find completed jobs, open their videos and revisit quality reports.":
        "Найдите завершённые задачи, откройте видео и отчёты о качестве.",
    "Manage your own reference videos for local similarity comparisons.":
        "Храните свои эталонные видео для локального сравнения сходства.",
    "Organize pending videos and control background workers.":
        "Организуйте очередь видео и управляйте фоновыми обработчиками.",
    "Generate variants of owned or licensed videos and record observations.":
        "Создавайте варианты своих или лицензированных видео и записывайте наблюдения.",
    "Personalize appearance, defaults and optional integrations.":
        "Настройте оформление, параметры по умолчанию и дополнительные интеграции.",
    "01  Source & destination": "01  Исходник и сохранение",
    "02  Processing": "02  Настройки обработки",
    "03  Progress & result": "03  Прогресс и результат",
    "Input video": "Исходное видео",
    "Source video": "Исходное видео",
    "Source": "Исходник",
    "Output video": "Обработанное видео",
    "Output": "Результат",
    "Save result to": "Куда сохранить",
    "Choose…": "Выбрать…",
    "Save as…": "Сохранить…",
    "No video selected": "Видео не выбрано",
    "Choose an output file": "Файл не выбран",
    "Drop a video here": "Перетащите видео сюда",
    "Processed video · MP4": "Результат · MP4",
    "Choose a source video to see its details.":
        "После выбора видео здесь появятся его характеристики.",
    "Reading video details…": "Читаем характеристики видео…",
    "Could not read this video. See the activity log.":
        "Не удалось прочитать видео. Подробности — в журнале.",
    "Advanced settings": "Дополнительные настройки",
    "Expand encoder selection, profile editing and auto-tuning.":
        "Показать выбор кодировщика, редактор профиля и автонастройку.",
    "Edit profile…": "Изменить профиль…",
    "Your result will appear here after processing.":
        "Здесь появится результат после обработки.",
    "Video processing progress": "Прогресс обработки видео",
    "Open processed video": "Открыть видео",
    "Open quality report": "Отчёт о качестве",
    "Activity log": "Журнал обработки",
    "Expand detailed processing messages.": "Показать подробные сообщения обработки.",
    "Processing messages will appear here.": "Здесь появятся сообщения обработки.",
    "Check video": "Проверить видео",
    "Start processing": "Начать обработку",
    "Choose a video to get started.": "Выберите видео, чтобы начать.",
    "Choose a processing profile.": "Выберите профиль обработки.",
    "Choose where to save the result.": "Выберите, куда сохранить результат.",
    "Choose a different output file to preserve the source.":
        "Выберите другой выходной файл, чтобы сохранить исходник.",
    "Resolve the issues shown above before processing.":
        "Перед запуском устраните проблемы, указанные выше.",
    "Checking video…": "Проверяем видео…",
    "Ready to process": "Всё готово к обработке",
    "Processing…": "Идёт обработка…",
    "Auto-tuning…": "Подбираем настройки…",
    "Soft · Subtle changes. A good starting point for reviewing quality.":
        "Мягкая обработка · Небольшие изменения. Подходит для первого сравнения качества.",
    "Medium · More visible changes. Compare a short clip before a full run.":
        "Средняя обработка · Заметные изменения. Сначала сравните короткий фрагмент.",
    "Strong · Pronounced changes that may reduce picture quality.":
        "Сильная обработка · Выраженные изменения, которые могут снизить качество картинки.",
    "Custom profile · Review its settings in the profile editor.":
        "Специальный профиль · Проверьте его параметры в редакторе.",
    "Automatic (recommended)": "Автоматически (рекомендуется)",
    "Notifications": "Уведомления",
    "Expand optional notification settings.": "Показать дополнительные настройки уведомлений.",
    "Expand optional local event recording.": "Показать настройки локального журнала событий.",
    "Expand cache and diagnostic tools.": "Показать инструменты кэша и диагностики.",
    "File pattern": "Шаблон файлов",
    "When a file fails": "При ошибке файла",
    "Maximum similarity": "Максимальное сходство",
    "Minimum quality (0–100)": "Минимальное качество (0–100)",
    "Search iterations": "Количество попыток",
    "Sample duration (seconds)": "Длительность образца (сек.)",
    "Similarity metric": "Метрика сходства",
    "Parallel workers": "Параллельные обработчики",
    "When the queue is empty": "Когда очередь пуста",
    "Transform settings": "Настройки эффектов",
    "YAML preview": "Просмотр YAML",
    "Input directory:": "Папка исходников:",
    "Output directory:": "Папка результатов:",
    "&Browse…": "&Выбрать…",
    "Bro&wse…": "&Выбрать…",
    "&Continue on error": "&Продолжать при ошибке",
    "&Run batch": "&Обработать папку",
    "Cance&l": "&Отмена",
    "&Calibrate": "&Подобрать настройки",
    "&Save tuned profile as…": "&Сохранить подобранный профиль…",
    "Base profile:": "Базовый профиль:",
    "Open existing": "Открыть отчёт",
    "Compute new": "Сравнить видео",
    "Open in &browser": "Открыть в &браузере",
    "QA report (.qa.html):": "Отчёт (.qa.html):",
    "&Compute QA": "&Сравнить качество",
    "Profile:": "Профиль:",
    "Save &as…": "Сохранить &как…",
    "&Reload list": "&Обновить список",
    "&Browse community…": "&Каталог профилей…",
    "Filter:": "Поиск:",
    "&Clear all": "&Очистить историю",
    "Open output": "Открыть видео",
    "Corpus root:": "Папка библиотеки:",
    "&Add file…": "&Добавить видео…",
    "&Remove selected": "&Удалить выбранное",
    "Re&fresh": "&Обновить",
    "Queue root:": "Папка очереди:",
    "&Init queue here": "&Создать очередь",
    "Out dir:": "Папка результатов:",
    "Output dir:": "Папка результатов:",
    "Default profile:": "Профиль по умолчанию:",
    "Theme:": "Тема:",
    "Language:": "Язык:",
    "Open &log dir": "Открыть &журналы",
    "Open &config dir": "Открыть &настройки",
    "Date": "Дата", "File": "Файл", "Status": "Статус",
    "Notes": "Примечания", "Actions": "Действия",
    "Path": "Путь", "Added": "Добавлено", "Samples": "Образцы",
    "Audio FP": "Аудиоотпечаток", "Transform": "Эффект", "Enabled": "Включён",
    "Params (JSON)": "Параметры (JSON)",
}
_STUDIO_RU.update({
    "Saved encoder; availability is checked before processing.":
        "Сохранённый кодировщик; доступность проверяется перед обработкой.",
    "Not selected": "Не выбрано", "&Copy": "&Копировать", "C&lear": "О&чистить",
    "Measured metrics": "Технические измерения",
    "Expand quality and similarity values.": "Показать измеренные значения качества и сходства.",
    "Generate variants": "Создать варианты", "Analyze observations": "Проанализировать наблюдения",
    "Start worker": "Запустить обработчик",
    "No matching jobs. Process a video or change the search to find previous results.":
        "Задачи не найдены. Обработайте видео или измените поиск, "
        "чтобы увидеть прошлые результаты.",
    "Add your own reference videos to compare similarity with future outputs.":
        "Добавьте свои эталонные видео, чтобы сравнивать их с результатами обработки.",
    "Completed: {file}": "Готово: {file}",
    "Failed.": "Ошибка. Подробности — в журнале обработки.",
    "Cancelled.": "Обработка отменена.", "Cancelling…": "Останавливаем обработку…",
    "Paused — encode suspended.": "Обработка приостановлена.",
    "Resumed.": "Обработка продолжена.", "&Resume": "&Продолжить",
    "Auto-tuning profile…": "Подбираем параметры профиля…",
    "Auto-tune failed.": "Не удалось подобрать настройки.",
    "Dark studio": "Тёмная студийная", "Light": "Светлая", "System (dark)": "Системная (тёмная)",
    "Variant count": "Количество вариантов", "Audio": "Звук",
    "Audio processing progress": "Прогресс обработки звука",
    "Open a quality report above, then use Open in browser to view it.":
        "Выберите отчёт выше и нажмите «Открыть в браузере», чтобы его посмотреть.",
})
_STUDIO_RU.update({
    "Preview original": "Посмотреть исходник",
    "Test a short fragment": "Проверить короткий фрагмент",
    "Compare a processed sample before starting the full video.":
        "Сравните обработанный фрагмент перед запуском всего видео.",
    "Start (seconds)": "Начало (сек.)",
    "{seconds} s": "{seconds} сек.",
    "Process sample": "Обработать фрагмент",
    "Uses the selected profile. The full output destination stays unchanged.":
        "Используется выбранный профиль. Фрагмент сохраняется отдельно от полного результата.",
    "Could not prepare the selected sample.": "Не удалось подготовить выбранный фрагмент.",
    "Sample ready: {file}": "Тестовый фрагмент готов: {file}",
    "Compare before / after": "Сравнить до / после",
    "Before / after": "Сравнение до / после",
    "Side by side": "Рядом",
    "Original only": "Только исходник",
    "Result only": "Только результат",
    "Fit to window": "По размеру окна",
    "Sync by time": "По времени",
    "Sync by duration": "По длительности",
    "Listen to original": "Звук исходника",
    "Listen to result": "Звук результата",
    "Original": "Исходник", "Processed": "Результат",
    "Shared timeline": "Общая шкала времени",
    "Play": "Воспроизвести", "Pause": "Пауза", "Paused": "На паузе",
    "Previous frame": "Кадр назад", "Next frame": "Кадр вперёд",
    "Loading video…": "Загружаем видео…",
    "Could not play {video}: {error}": "Не удалось воспроизвести {video}: {error}",
    "Shared time; choose duration sync when the clip tempo changes.":
        "Общая шкала времени. При изменении темпа выберите синхронизацию по длительности.",
    "Preparation": "Подготовка", "Video": "Видео", "Saving": "Сохранение",
    "Quality check": "Качество",
    "Elapsed: {time}": "Прошло: {time}",
    "Remaining in this stage: ≈ {time}": "Осталось на этапе: ≈ {time}",
    "Estimating stage time…": "Оцениваем время этапа…",
    "Finding the adjacent frame…": "Находим соседний кадр…",
    "Frame ready": "Кадр готов",
    "Frame step unavailable: {error}": "Не удалось перейти по кадрам: {error}",
})
_STUDIO_RU.update({
    "Gentle": "Мягкая", "Balanced": "Сбалансированная", "Pronounced": "Выраженная",
    "Small crop, subtle color correction and light noise.":
        "Небольшая обрезка, мягкая коррекция цвета и лёгкий шум.",
    "More visible crop, color correction and noise.":
        "Более заметная обрезка, коррекция цвета и шум.",
    "Stronger changes plus a slight rotation. Review picture quality.":
        "Более сильные изменения и небольшой поворот. Проверьте качество картинки.",
    "Audio: pitch adjustment and loudness normalization.":
        "Звук: изменение высоты тона и нормализация громкости.",
    "Audio: pitch, equalizer and loudness normalization.":
        "Звук: высота тона, эквалайзер и нормализация громкости.",
    "Video preview": "Превью видео", "Source video thumbnail": "Миниатюра исходника",
    "Start time": "Начало", "Sample timeline": "Шкала выбора фрагмента",
    "Video thumbnails": "Миниатюры видео",
    "Click or drag to choose the sample start; arrow keys move by one second.":
        "Выберите начало нажатием или перетаскиванием. Стрелки перемещают на одну секунду.",
    "Save sample…": "Сохранить фрагмент…", "Save sample": "Сохранить фрагмент",
    "Saving sample…": "Сохраняем фрагмент…",
    "Sample saved: {file}": "Фрагмент сохранён: {file}",
    "Could not save sample. Try another destination.":
        "Не удалось сохранить фрагмент. Выберите другое место сохранения.",
    "Saving cancelled; the temporary sample is still available.":
        "Сохранение отменено. Временный фрагмент остаётся доступен.",
    "Return to task": "Вернуться к задаче", "Active tasks": "Активные задачи",
    "Task progress": "Прогресс задачи",
    "Draggable divider": "Разделитель", "Before / after divider": "Разделитель до / после",
    "Drag the divider; drag the image to pan when zoomed. Arrow keys move the divider.":
        "Перетаскивайте разделитель или увеличенное изображение. "
        "Стрелки перемещают разделитель.",
    "Use this time for sample": "Начать фрагмент отсюда",
    "Use native video panels for HDR comparison.":
        "Для сравнения HDR используйте режимы с отдельными видеопанелями.",
    "Image comparison unavailable; use side by side.":
        "Разделитель недоступен для этих кадров. Используйте режим «Рядом».",
})
SOURCE_KEYS = (*SOURCE_KEYS, *(key for key in _STUDIO_RU if key not in SOURCE_KEYS))
TRANSLATIONS["ru_RU"].update(_STUDIO_RU)
