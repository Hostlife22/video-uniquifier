<a id="transform-plugins"></a>

# Плагины преобразований

> Добавлено в версии v0.8.0. Усилено в v1.2.0 с манифестом + проверкой возможностей + хуком аудита
> песочница (Задача 23).

Встроенные трансформации (обрезка+масштабирование, изменение цвета, нормализация громкости, высота+темп …) находятся в
`src/video_uniquifier/core/transforms/` и самостоятельно регистрируются через `register(TransformSpec(…))` при импорте. **Плагин** — это просто внешний пакет Python, который делает точно то же самое — он поставляет модуль, который вызывает `register(...)`, и рекламирует этот модуль в группе точек входа `video_uniquifier.transforms`, чтобы video-uniquifier обнаруживал его автоматически.

Вилка не требуется. Изменения в `core/` не нужны. Плагин, опубликованный на PyPI, становится видимым для каждой установки video-uniquifier в том же виртуальном окружении после `pip install`.

<a id="manifest-v120"></a>

## Манифест (v1.2.0)

Каждое стороннее распространение плагина ОБЯЗАНО содержать файл `video_uniquifier_plugin.toml` в корне пакета. Манифест объявляет, какие типы трансформаций плагин разрешено регистрировать; попытка зарегистрировать тип, на который манифест не дал согласия, вызывает `PluginViolation` во время загрузки.

```toml
[plugin]
name = "my-uniq-pingpong"
version = "0.1.0"
capabilities = ["video_transform"]   # add "audio_transform" to register audio
# sha256 = "…"                       # optional self-declared wheel hash
```

`name` и `version` обязательны. `capabilities` — это список:

|Возможность|Разрешает `TransformSpec.kind`|Примечания|
|--------------------|------------------------------|-------|
| `video_transform`  | `"video"`                    |Обязательно для любого ID `video.*`|
| `audio_transform`  | `"audio"`                    |Обязательно для любого ID `audio.*`|

Плагин, пропускающий `capabilities`, загружаем, но не может зарегистрировать ни одну трансформацию — полезно как бездействующий тест для проверки подключения обнаружения.

Поместите манифест как данные пакета, чтобы `importlib.metadata.distribution(...).files` включал его. Пример фрагмента `pyproject.toml`:

```toml
[tool.setuptools.package-data]
my_uniq_pingpong = ["video_uniquifier_plugin.toml"]
```

<a id="trust-model-v120"></a>

## Модель доверия (v1.2.0)

Плагины — это обычные пакеты Python, поэтому загрузка одного из них выполняет произвольный код третьей стороны. v1.2.0 добавляет два уровня защиты поверх точки входа
`try/except`, введённая в v0.8.0:

1. **Контроль возможностей манифеста** — вызовы `register()` из плагина без манифеста или с манифестом, который не содержит соответствующей возможности, отклоняются до того, как трансформация достигнет реестра.
2. **Песочница аудита хуков** — код каждого плагина при импорте и каждый построитель трансформаций, который он предоставляет, выполняется внутри `sys.addaudithook`-контроля. Запрещённые операции (запись в файловую систему — `os.unlink`/`os.remove`/`os.rename`, выход в сеть — `socket.connect`/`socket.bind`, запуск подпроцессов —
   `subprocess.Popen`/`os.exec*`, динамические `exec`/`compile`) вызывают
   `PluginViolation` вместо тихого успешного выполнения.

Песочница реализована с помощью [PEP 578 audit hooks](https://peps.python.org/pep-0578/) и является кроссплатформенной (CPython, без кода, зависящего от ОС). Она перехватывает всё, что проходит через runtime CPython; плагин, содержащий C-расширение и выполняющий прямые системные вызовы, обходит этот уровень. Linux `seccomp` является кандидатом для более сильного второго уровня в будущем выпуске.

<a id="operator-controls"></a>

### Управление оператором

|Флаг / переменная окружения|Эффект|
|---|---|
| `--no-plugins`  /  `VIDEO_UNIQ_NO_PLUGINS=1`               |Пропустить все сторонние плагины. Переменная окружения активируется до импорта; флаг CLI фильтрует реестр после импорта, так что побочные эффекты во время импорта уже применены.|
| `--plugins-allowlist a,b`  /  `VIDEO_UNIQ_PLUGINS_ALLOWLIST=a,b` |Сохранять только плагины, чей `[plugin].name` находится в списке, разделённом запятыми.|
| `--unsafe-plugins`                                       |Отключить песочницу audit-hook. Использовать только с доверенными внутренними плагинами; не использовать с установками из PyPI.|

Предпочитайте форму переменной окружения в производственных развертываниях: она вступает в силу до любого импорта плагина, поэтому `__init__.py` злонамеренного плагина никогда не выполняется.

<a id="minimal-plugin-hello-world"></a>

## Минимальный плагин (hello-world)

Структура проекта:

```
my-plugin/
├── pyproject.toml
└── src/
    └── my_uniq_pingpong/
        └── __init__.py
```

`src/my_uniq_pingpong/__init__.py` — регистрация выполняется как побочный эффект импорта, точно так же, как встроенные:

```python
from pydantic import BaseModel, Field
from video_uniquifier.core.transforms import FilterChain, LabelAllocator, TransformSpec, register


class PingPongParams(BaseModel, extra="forbid"):
    strength: float = Field(0.0, ge=0.0, le=1.0)


def build(params: PingPongParams, alloc: LabelAllocator, in_label: str) -> FilterChain:
    out = alloc.next("v")
    # Trivial example: identity filter wrapped to demonstrate the contract.
    return FilterChain(in_label=in_label, out_label=out, filter_str="null")


register(TransformSpec(id="video.pingpong", kind="video", schema=PingPongParams, build=build))
```

`pyproject.toml` — объявление точки входа — это то, что его подключает:

```toml
[project]
name = "my-uniq-pingpong"
version = "0.1.0"
dependencies = ["video-uniquifier", "pydantic>=2"]

[project.entry-points."video_uniquifier.transforms"]
pingpong = "my_uniq_pingpong"
```

Установите в той же среде, что и video-uniquifier:

```bash
pip install -e ./my-plugin
video-uniq probe --list-transforms | grep pingpong
# video.pingpong
```

Обращайтесь к новому преобразованию из любого YAML профиля:

```yaml
transforms:
  - id: video.pingpong
    params: { strength: 0.5 }
```

<a id="contract-reminder"></a>

## Напоминание о контракте

Построитель преобразования ДОЛЖЕН:

* возвращать один `FilterChain`, чей `filter_str` **не** оборачивается в
  `[in_label]...[out_label]` — пайплайн добавляет это оборачивание (см.
  `CLAUDE.md` § Архитектурные инварианты).
* быть детерминированным при одинаковом `(params, in_label, rng)` кортеже. Если конструктор использует случайность, примите `rng: random.Random | None = None` и используйте его вместо того, чтобы создавать собственный `Random(...)` — в противном случае возобновленные запуски будут расходиться недетерминированно.
* используйте `LabelAllocator` для каждой новой метки, никогда не прописывайте `v1`, `a3`, …

Построитель преобразований НЕ ДОЛЖЕН:

* изменять `params` или любой объект, предоставленный вызывающей стороной,
* вызывать `subprocess` или читать файловую систему (это забота `core/`),
* импортировать дополнительные зависимости на уровне модуля — отложите до первого вызова, чтобы отсутствие вызывало ясную ошибку, а не сбой во время импорта.

<a id="failure-modes-and-where-to-look"></a>

## Режимы отказа (и где смотреть)

|Симптом|Вероятная причина|Где искать|
|---|---|---|
| `WARNING: third-party transform plugin '<name>' failed to load` |Импорт плагина вызвал ошибку|Запустите `python -c "import <module>"` и прочитайте трассировку стека|
|Плагин установлен, но `video-uniq probe --list-transforms` его не показывает|Опечатка в имени точки входа или неверная группа| `python -c "from importlib.metadata import entry_points as e; print(list(e(group='video_uniquifier.transforms')))"` |
|`KeyError: 'video.pingpong'` на `video-uniq run` несмотря на установку|Профиль загружен до порядка импорта плагина — удалите и переустановите в чистой виртуальной среде|Проверка `pip show <plugin>` подтверждает, что местоположение установки совпадает с `python -c "import sys; print(sys.path)"`|
|Возобновление после изменения профиля все еще использует кэшированное состояние|Ожидаемо — хэш плана изменился, поэтому ключ кэша возобновления другой. Либо перезапустите чисто, либо верните профиль| `core/pipeline.py::compute_plan_hash` |

<a id="versioning"></a>

## Версионирование

Публичная область `register` / `TransformSpec` / `FilterChain` / `LabelAllocator` **стабильна начиная с v0.8.0**. Ломающие изменения будут происходить только при крупных обновлениях версии с руководством по миграции в заметках к выпуску.
