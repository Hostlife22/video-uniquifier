<a id="community-profile-marketplace-f9-v090-r1"></a>

# Каталог сообщества

Просматривайте и устанавливайте YAML-профили, предоставленные сообществом — не покидая CLI или GUI и не доверяя выполнению кода на вашем компьютере. Каталог закреплён по SHA для каждой записи; профиль, который не совпадает с заявленным хэшем, отклоняется до того, как файл попадёт на диск.

<a id="trust-model"></a>

## Модель доверия

* **Только HTTPS.** Каталог и каждый URL профиля, на который он ссылается, принудительно используют `https://`. URL-адрес без HTTPS отклоняется до того, как будут считаны какие-либо байты, независимо от источника URL.
* **Закрепление SHA-256.** Каждая запись каталога содержит шестнадцатеричный SHA-256 для профиля YAML, на который она указывает. `install` загружает, хеширует и отказывается записывать файл, если дайджест не совпадает.
* **Подписи Ed25519 (v1.2.0, задача 25).** Запись каталога может содержать поле `signature` — 64 байта Ed25519 в шестнадцатеричном формате. Подпись создаётся автономным закрытым ключом оператора каталога для поля
  `sha256`. Когда обязательная проверка подписи включена (`require_signature=True` в API `install()` или
  `VIDEO_UNIQ_REQUIRE_SIGNED_PROFILES=1` в окружении), неподписанные записи и записи, чья подпись не проверяется ни одним из встроенных публичных ключей торговой площадки, отклоняются. См. § Политика подписей.
* **С проверкой схемы.** Даже после совпадения SHA, YAML пропускается через `Profile.model_validate` (с `extra=forbid`) *перед* атомарным переименованием в каталог профиля пользователя. Некорректный профиль никогда не достигает окончательного имени файла.
* **Выполнение кода отсутствует.** Профили являются декларативными YAML; загрузка профиля только вызывает схему pydantic. Нет пути, по которому запись в маркетплейсе может выполнить произвольный код на вашей машине.
* **Без тихого падения.** Ошибки транспорта (сеть отключена, сбой TLS) откатываются к локальному кэшу → in-wheel bootstrap, в указанном порядке. Ошибки структуры конфигурации (слишком большой payload, URL не HTTPS, ошибка парсинга JSON) распространяются как фатальные — мы не предоставляем устаревший каталог для неправильно настроенного upstream.

## CLI

```bash
video-uniq profile list-community          # cached + sorted by id
video-uniq profile list-community --refresh
video-uniq profile show cid_aware          # inspect before install
video-uniq profile install cid_aware       # → ~/.config/video_uniquifier/profiles/
video-uniq profile install cid_aware --dest /custom/dir --overwrite
video-uniq profile install-dir             # print default install dir
video-uniq profile purge-cache             # force re-fetch on next call
```

## GUI

На экране редактора профилей есть кнопка **Обзор сообщества…**. Диалоговое окно показывает каждую запись каталога, URL и SHA при выборе, и устанавливает в ваш каталог профиля пользователя при нажатии. Установленные профили появляются в выпадающем списке без перезапуска.

<a id="catalog-format"></a>

## Формат каталога

```json
{
  "version": 1,
  "entries": [
    {
      "id": "cid_aware",
      "name": "CID-aware (balanced)",
      "description": "Conservative micro-transforms…",
      "url": "https://raw.githubusercontent.com/…/cid_aware.yaml",
      "sha256": "d4cdb9e4877387ec259524da6ef9806c…",
      "author": "video-uniquifier core",
      "tags": ["cid", "balanced"],
      "version": "1.0.0",
      "min_video_uniquifier_version": "0.9.0"
    }
  ]
}
```

Схема находится по адресу `core/profile_marketplace.py::Catalog` (с
`extra=forbid`); проверка отклоняет любые неизвестные поля.

<a id="where-things-live"></a>

## Где находятся вещи

|Элемент|Путь|
|----------------------|------------------------------------------------------------|
|Каталог Bootstrap| `<wheel>/video_uniquifier/marketplace/catalog.json`           |
|Кэшированный каталог| `~/.cache/video_uniquifier/marketplace/catalog.json`          |
|Установленные профили|`~/.config/video_uniquifier/profiles/<id>.yaml` (по умолчанию)|
|Каталог проекта| `https://raw.githubusercontent.com/Hostlife22/video-uniquifier/main/src/video_uniquifier/marketplace/catalog.json` |

Каталог bootstrap включён в wheel, поэтому при чистой установке без доступа к сети всё равно отображается несколько стартовых профилей. Тот же каталог размещён в репозитории проекта; успешная загрузка по сети имеет приоритет при обновлении.

<a id="contributing-a-profile"></a>

## Добавление профиля

1. Создайте YAML в соответствии со схемой, описанной в [Profiles](profiles.md). Выполните `video-uniq preflight <some_source> --profile <your.yaml>` для проверки на корректность.
2. Вычислите SHA-256 итогового YAML:

    ```bash
    shasum -a 256 your_profile.yaml
    ```

3. Откройте PR против `Hostlife22/video-uniquifier`, обновив
   `src/video_uniquifier/marketplace/catalog.json` с новой записью. Включите `author`, однострочную
   `description`, и как минимум один `tag`.
4. Укажите URL размещения YAML — каноническим выбором является raw URL GitHub. URL **должен** быть HTTPS.

Рецензенты установят профиль из вашей ветки, запустят его против эталонного источника и проверят, что SHA совпадает.

<a id="signing-policy-v120-task-25"></a>

## Политика подписи (v1.2.0 Задача 25)

Записи каталога могут быть подписаны оператором маркетплейса. Набор встроенных открытых ключей находится в `src/video_uniquifier/keys/marketplace.pub` (поставляется с wheel) — один публичный ключ Ed25519 в шестнадцатеричной кодировке на непустую строку, что позволяет использовать несколько ключей при ротации.

<a id="what-gets-signed"></a>

### Что подпишется

Подпись охватывает ASCII-байты поля `sha256` записи — ту же шестнадцатеричную строку, которая фиксирует тело YAML. Привязка подписи к SHA означает, что одна подпись одновременно аутентифицирует целевой URL и содержимое тела: атакующему, который изменит `url` на другой YAML, также придется изменить `sha256` соответственно, что нарушит подпись, если у него нет приватного ключа оператора.

<a id="signing-workflow"></a>

### Процесс подписания

```bash
# One-off setup: generate the operator's keypair.
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
priv = ed25519.Ed25519PrivateKey.generate()
print('PRIVATE (keep offline!):',
      priv.private_bytes(serialization.Encoding.Raw,
                         serialization.PrivateFormat.Raw,
                         serialization.NoEncryption()).hex())
print('PUBLIC (ship in marketplace.pub):',
      priv.public_key().public_bytes(serialization.Encoding.Raw,
                                     serialization.PublicFormat.Raw).hex())
"

# Per-entry: sign the body SHA.
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIV_HEX))
sha256_hex = '<the entry\\'s sha256 field>'
print(priv.sign(sha256_hex.encode('ascii')).hex())
"
```

Вставьте полученную 128-символьную шестнадцатеричную строку в запись каталога в поле
`signature`.

<a id="key-rotation"></a>

### Смена ключей

1. Сгенерируйте новую пару ключей.
2. Добавьте новый открытый ключ в `marketplace.pub` **над** старым. Оба ключа остаются действительными; проверка принимает подпись с любым указанным ключом.
3. Повторно подпишите все активные записи каталога новым приватным ключом.
4. После того как каждая запись будет повторно подписана, удалите старый открытый ключ из
   `marketplace.pub` в следующем video-uniquifier выпуске.
5. Постоянно уничтожьте старый приватный ключ.

<a id="enforcement"></a>

### Принуждение

Проверка подписи является опциональной для сохранения обратной совместимости с форматом каталога v0.9. Операторам, которые хотят использовать только режим подписи:

* Передайте `require_signature=True` в `install(...)` в коде.
* Или экспортируйте `VIDEO_UNIQ_REQUIRE_SIGNED_PROFILES=1` в оболочке, которая запускает `video-uniq` / `video-uniq-gui`.

Пакет `cryptography` (ссылка на PyCA) включен как
`[crypto]` дополнительный компонент. Установки без дополнительного компонента все еще могут использовать неподписанные каталоги; включение принуждения на установке, не являющейся `[crypto]`, вызывает явную ошибку с указанием отсутствующей зависимости.
