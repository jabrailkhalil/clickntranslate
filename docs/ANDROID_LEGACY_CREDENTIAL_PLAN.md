# Явный перенос API-ключей Android 1.8.2

Дата: 25 октября 2026. **Реализован ограниченный перенос per-preset credentials с явной привязкой к новому профилю.** Ниже сохранены аудит формата и требования к оставшимся вариантам. Реальные приватные файлы, значения ключей и старые Keystore-записи не открывались; сетевые запросы с ключами не выполнялись.

## Реализованный объём и границы

`LegacyCredentialMigration` показывает публичный каталог источников, проверяет выбранный новый Room-профиль и переносит совместимую запись после отдельного подтверждения. Интерфейс доступен в Настройки → Перенос данных → Перенос API-ключей. Поддерживаются группы OPENAI, ANTHROPIC, LIBRETRANSLATE, DEEPL и TTS_MINIMAX при совпадении фактических протокола и сервера. Реестр распознаёт16 групп/22 поля; распознавание группы не означает наличия её нового адаптера.

Global credentials, неизвестные/`fb:` оболочки и остальные сервисы не переносятся автоматически. Отсутствующий старый Keystore alias не создаётся. MiniMax China/international, DeepL custom/official и Anthropic-compatible/official считаются разными назначениями. Существующий целевой ciphertext или его `.bak` не заменяется. Источник повторно проверяется по fingerprint; профиль удерживается под общей блокировкой изменений и транзакцией Room. После записи проверяется новый envelope с полным AAD, затем публикуется revision. Секреты не передаются в Compose и не включаются в отчёты/экспорт.

Добавлены8 JVM и8 Android integration fixtures с синтетическими секретами и отдельными тестовыми Keystore aliases. В целевом прогоне Wave4 на API36 все8 Android-случаев прошли; окончательные повторные прогоны учитываются в [журнале](REWRITE_STATUS.ru.md). Это не доказывает доступ к Keystore реальной production1.8.2: такая проверка требует прежней подписи и исходного application UID. Новый production signing key не создавался.

## Подтверждённые форматы

Источник — `backup/android-remote-before-rewrite-20261024`, commit `05493e63c6c07d206547182db6828a4dd73ca0ca`. Форматы подтверждены по `data/PresetCredentialPolicy.kt`, `SettingsRepository.kt`, `SettingsSecretCodec.kt`, `SettingsSecretCipher.kt`, публичным полям `Settings.kt` и синтетическим тестам старого репозитория. Старые классы/алгоритмы не подключаются к новой сборке.

- DataStore: `files/datastore/clickntranslate_settings.preferences_pb`.
- Публичные профили: `translation_presets_json`, поле `id` задаёт владельца локальной credential-записи. Имя профиля не является идентификатором владельца.
- Ключ отдельной записи: `local_preset_credentials_v1_<presetId>`.
- Расшифрованная структура: объект `ownerId` и `groups`; каждая группа содержит `binding` и словарь строковых `values`.
- Старый binding — имя группы, двоеточие и её endpoint после trim и удаления завершающих `/`. Некоторые группы имели пустую endpoint-часть. Это исходная проверка формата, а не разрешение отправлять ключ любому новому адресу.
- `ownerId` обязан точно совпасть с запрошенным исходным `presetId`; binding обязан совпасть с ожидаемым binding из соответствующих публичных настроек.
- У групп нет самостоятельной версии JSON. Распознавание по известной оболочке и строгой allowlist структуры; неизвестные поля/группы не должны превращаться в другой поддерживаемый сервис.

Основная зашифрованная оболочка: `enc:v1:ak:` + Base64 байтов `[IV-length=12][IV:12][ciphertext + GCM tag:16]`, AES-256-GCM, tag128. Alias прежнего Android Keystore: `clickntranslate_settings_secret_aes_gcm_v1`.

**В старом шифровании AAD отсутствовал.** Подпись GCM защищает JSON целиком, а owner/group/server проверяются в его содержимом. Нельзя требовать от старого ciphertext новый AAD и затем при ошибке пробовать другие identities. После переноса новая запись должна защищаться полным `CredentialIdentity.authenticatedIdentity`.

Подтверждены также старые читаемые варианты `enc:v1:fb:` и `enc:v1:<Base64>` без `ak:`. Для `fb:` ключ зависел от исходных package/ANDROID_ID/подписи устройства. Минимальная реализация вправе явно сообщать `UNSUPPORTED_FORMAT` для этих вариантов и предлагать повторный ввод; исходники остаются нетронутыми. Нельзя молча включать device-derived fallback, принимать plaintext как authenticated credential или создавать отсутствующий старый alias.

## Реестр групп и совпадение серверов

| Старая группа | Поля values | Условие будущего переноса |
| --- | --- | --- |
| `OPENAI` | `apiKey` | Только совпавший сервер/путь и явно выбранный новый OpenAI, DeepSeek либо compatible context |
| `ANTHROPIC` | `anthropicApiKey` | Сохранить исходный URL: старый default `https://api.deepseek.com/anthropic`, новый default Anthropic — другой сервер |
| `LIBRETRANSLATE` | `libreTranslateApiKey` | Совпадение исходного и нового LibreTranslate endpoint |
| `DEEPL` | `deeplApiKey` | Binding был `DEEPL:`; free/pro задавался публичным `deeplPro`. Нужна эта метаинформация либо явный отказ от переноса при неоднозначности |
| `DEEPL_CUSTOM` | `deeplCustomToken` | Другая авторизация/протокол; не переносить в официальный DeepL slot без совместимого адаптера |
| `TTS_MINIMAX` | `ttsMiniMaxApiKey` | Старый default `https://api.minimaxi.com`, новый fixed host `https://api.minimax.io`: автоматическое связывание запрещено |
| `TTS_HTTP` | `ttsHttpBearerToken` | Нужен совместимый generic HTTP speech adapter с тем же endpoint; новый OpenAI/ElevenLabs slot не эквивалентен |
| `TTS_VOLC` / `TTS_MIMO` | `ttsVolcengineApiKey` / `ttsMimoApiKey` | Сохранять только для соответствующих будущих совместимых адаптеров и серверов |
| `NIUTRANS` | `niuTransApiKey`, `niuTransAppId` | Нужен составной credential-контракт совместимого сервиса |
| `YOUDAO` | `youdaoAppKey`, `youdaoAppSecret` | То же; прежняя группа могла обслуживать OCR и MT |
| `VOLC` | `volcAccessKeyId`, `volcSecretAccessKey` | Не преобразовывать пару в одиночный Bearer token |
| `BAIDU_FANYI` | `baiduFanyiAppId`, `baiduFanyiSecretKey` | Совместимый MT-адаптер отсутствует |
| `TENCENT` | `tencentSecretId`, `tencentSecretKey` | Группа общая для OCR/MT; нельзя связать с Google Vision/HTTP по сходству назначения |
| `BAIDU_OCR` | `baiduOcrApiKey`, `baiduOcrSecretKey` | Только совместимый Baidu OCR-контракт |
| `PADDLE` | `paddleAiStudioToken` | Только совместимый Paddle AI Studio-контракт |

`OPENAI` использовалась также как fallback старых LOCAL_SAKURA/LOCAL_HY_MT2. Это не основание записывать ключ в новые OFFLINE/LOCAL_LLM slots. Для них нужен отдельный явно выбранный compatible-профиль с тем же сервером.

Обязательны две независимые проверки: сначала точный прежний owner/group/binding, затем новая серверная identity. Новый `CredentialIdentity.canonicalEndpoint` сохраняет path и encoded slashes, нормализует host/default port и запрещает userinfo/query/fragment. Недопустимый старый URL отклоняется до отображения в UI; сырой binding с потенциальными credentials в адресе не логируется. Нельзя сокращать identity до host, удалять tenant path или заменять старый endpoint новым provider default.

## Минимальный новый API

Реализованные контракты разделены между `LegacyCredentialTypes`, `LegacyCredentialSourceReader`, `LegacyCredentialCipher`, `LegacyCredentialDecoder` и `LegacyCredentialMigration`:

```text
LegacyCredentialHint(sourceToken, ownerLabel, group, sourceEndpoint, status)
preview(publicSources): List<LegacyCredentialHint>
bind(sourceToken, expectedSourceFingerprint, destinationIdentity): BindResult
SecretStore.bindLegacyIfAbsent(destinationIdentity, source): BindResult
```

`sourceToken` — внутренний selector, не пользовательский UUID/package ввод. Preview возвращает только публичные метаданные, доступность зашифрованной записи и фиксированные статусы. Секретные DTO в UI не передаются. JSON/parser/cipher остаются отдельными от `LegacyPublicCipher`, чей контракт разрешает только публичные поля.

Для минимального безопасного варианта пользователь явно выбирает старый источник и текущий новый профиль/основные настройки. Новая Room-таблица не обязательна. Если потребуется автоматическое соответствие, нужен receipt `legacyPublicIdentity → destinationProfileId` с проверкой публичного snapshot: нынешний `legacy_imports` хранит только identity. Вычислять связь по одинаковому имени профиля нельзя.

## Последовательность явного Bind

1. Прочитать только публичные profiles/settings и presence выбранной зашифрованной записи. Не перечислять все preference values. Ограничить число профилей/размер источника; не менять DataStore.
2. Показать имя исходного владельца, сервис, проверенный исходный сервер и целевой профиль/сервер. До подтверждения не расшифровывать credential-record и не делать API-пробу.
3. После подтверждения повторно прочитать публичный источник и авторитетный Room-профиль назначения; при удалении/смене identity или fingerprint вернуть `SOURCE_CHANGED`/`DESTINATION_CHANGED`.
4. Получить **только существующий** старый alias через `containsAlias/getKey`; при отсутствии — `KEY_UNAVAILABLE`. Никакого get-or-create для старого alias.
5. Bounded decode оболочки, GCM authentication и строгий UTF-8/JSON. Предлагаемые пределы:1MiB на record,100 владельцев,16 известных групп, ключ не более16384 UTF-8 bytes; точные пределы подтвердить fixtures. Для каждого уровня проверять duplicate fields, типы и allowlist; неизвестное не угадывать.
6. Проверить owner и выбранную группу/набор fields/binding. Не материализовывать значения других групп без необходимости. Unsupported группы сохраняются в старом хранилище с явным отчётом.
7. Под lock `SecretStore` проверить отсутствие целевого ciphertext и `.bak`. Записать новый envelope атомарно с полным AAD канала/провайдера/профиля/endpoint. Существующий target не заменять; исходный ciphertext не удалять и не переписывать.
8. Только после успешной записи публиковать credential revision и успешный receipt. На исключении не публиковать успех; отмену передавать дальше. Временные plaintext bytes очищать. Невозможность гарантированно очистить Java String не скрывать: не сохранять его в StateFlow/Compose/логах.

Повторный Bind не должен перезаписывать актуальный ключ. Для нового v2 ciphertext wrong AAD — окончательная ошибка; нельзя пробовать global/другой профиль/old slot. Расшифровка старого envelope без AAD разрешена только в явно выбранном migration path.

## Отличие от раннего rewrite-формата

Новый `SecretStore` уже имеет endpoint/profile/service-bound v2 identity и explicit `bindUnbound()` для `clickn_next_credentials_v1/*.bin` предыдущего этапа переписывания. Этот путь использует **новый** alias `dev.clickn.translate.next.credentials.v1` и другой envelope/AAD. Он не читает записи Android1.8.2 и не считается их миграцией.

Публичный сертификат production APK не даёт доступа к старому Keystore. Настоящая upgrade-проверка требует прежней подписи/того же application UID и существующих данных на устройстве. QA `.rewrite` package и синтетический alias-injection тестируют новый контракт, не реальную доступность ключа старой установки.

## Контрольные сценарии и оставшаяся production-проверка

- Синтетический существующий AES key; отсутствие alias не вызывает генерацию. Правильная старая оболочка читается, wrong key/tag/IV/prefix/UTF-8/deep JSON/duplicate fields отклоняются.
- Перенос record между preference keys с разными ownerId, смена группы/поля/endpoint, model-only edit, path/encoded-slash различия, HTTP downgrade и credentials в URL.
- MiniMax China/international, Anthropic-compatible/official и DeepL-custom/official не смешивают аккаунты; неподдерживаемые составные группы явно остаются неперенесёнными.
- Старый источник/новый профиль изменён или удалён после preview; импорт одноимённого профиля не заимствует ключ другого владельца.
- Целевой key уже существует, появился одновременно с Bind, имеет только `.bak` или повреждён: ничего не перезаписывается. Ошибка записи не оставляет успешный receipt/revision.
- Wrong AAD и копирование нового ciphertext между профилями/каналами/серверами всегда fail closed без fallback.
- Отмена/закрытие UI до подтверждения не читает plaintext и не пишет key; ни один этап не вызывает сеть. Исходные bytes/SHA сохраняются.
- Fixtures с отличимыми секретными маркерами не обнаруживаются в reports/toString/исключениях/export/логах/Compose semantics. Реальные ключи для таких проверок не нужны.

До реализации и центральных проверок этого механизма статус переноса credentials1.8.2 остаётся **«не реализована с объяснением причины»**.
