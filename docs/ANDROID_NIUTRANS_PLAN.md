# NiuTrans: официальный контракт и план Android-интеграции

Дата исследования: **2026-10-25**. Статус: **исследование / код не реализован этим документом**.

Область: собственный NiuTrans Cloud Text API. Это отдельный протокол, а не `CUSTOM`, OpenAI-compatible или партнёрский API iFlytek. Прочитаны текущие `NetworkTranslator`, `ProviderConfiguration`, `TranslationBackend`, `TranslationPipeline`, `TextChunks`, `CredentialIdentity`, `SettingsJson`, `TranslationOptions` и `LanguageCatalog`. Код приложения, тесты и устройства не менялись; запросов к translation endpoint, регистрации, покупок и использования реальных ключей не было.

## Источники и достоверность

Использованы только первичные страницы NiuTrans. На момент исследования прямое чтение ряда SPA-страниц возвращало JavaScript-оболочку; полный контракт доступен в индексированном тексте этих же официальных страниц. Доступного браузерного backend для проверки переключателя версий не оказалось. Поэтому **публикация контракта подтверждена, текущая работоспособность endpoint и соответствие выбранной в консоли версии — нет**. На сайте видны `v1.0/v2.0` и названия Flash/Pro; связывать их автоматически с приведённым ниже протоколом нельзя.

| Первичный источник | Что устанавливает |
| --- | --- |
| [Текстовый перевод](https://niutrans.com/documents/contents/trans_text) | Каноническая страница текстового API; прямое чтение показало оболочку, поэтому она не служит единственным доказательством деталей. |
| [Автоопределение и перевод](https://niutrans.com/documents/contents/trans_detection) | Текстовый endpoint, параметры, content types, ответы, ошибки, лимиты и выбор библиотек. |
| [JSON-перевод](https://niutrans.com/documents/contents/trans_json) | Регистрация/APIKEY, отдельный JSON endpoint и таблица языковых кодов. Не подменять им обычный текстовый запрос. |
| [Терминология](https://niutrans.com/documents/contents/customization_term) | Отдельная операция записи термина и параметры библиотеки. |
| [Описание autodetection](https://niutrans.com/detection_trans) | Один распознаваемый язык за запрос; точность определения не гарантирована. |
| [Тарифы](https://niutrans.com/price/) | Аккаунтная модель с покупаемыми ресурсами; не гарантия бесплатности конкретного запроса. |

Ни примеры сторонних интеграций, ни исходники прежнего приложения/его обвязки не использованы.

## Подтверждённый опубликованный wire-контракт

Ниже — краткая фиксация [официального text/autodetection контракта](https://niutrans.com/documents/contents/trans_detection).

| Поле | Контракт |
| --- | --- |
| Endpoint | `http(s)://api.niutrans.com/NiuTransServer/translation`; приложение выберет **HTTPS POST**. |
| Допустимые методы | GET/POST; свыше длины 1500 рекомендован POST. |
| Content-Type | `application/json` либо `application/x-www-form-urlencoded`; multipart не поддерживается. |
| Обязательные значения | `from`, `to`, `apikey`, `src_text`; текст UTF‑8. |
| Autodetection | `from=auto`. Ответ-пример сохраняет `from:"auto"`, а не обязательно возвращает обнаруженный код. |
| Дополнения | `dictNo`, `memoryNo`: строки, необязательны; пустые выбирают default-библиотеки консоли. |
| Успех | JSON с непустым строковым `tgt_text`; присутствуют языковые поля. |
| Ошибка | Строковые `error_code`, `error_msg`; возможен echo `src_text` и `apikey`. |
| Длина/QPS | Опубликованы длина **5000**, QPS **5** для бесплатного и **50** для платного пользователя. |

Коды: `10000` — пустой ввод; `10001` — QPS; `10003` — длина; `10005` — UTF‑8; `13001` — недостаток ресурса **или** доступа; `13002` — пустой ключ; `13003` — фильтрация; `13005` — одинаковая пара; `13007` — язык; `13008` — timeout; `14001–14004` — обработка; `000000/000001` — параметры/тип запроса. Источник: [та же таблица ошибок](https://niutrans.com/documents/contents/trans_detection).

**Критично для decoder:** `"000000"` обозначает ошибку параметров, а не числовой success=0. Нельзя решать успех через `error_code.toInt()==0`. Нельзя логировать/показывать сырой ответ или `error_msg`: ответ способен отразить ключ и исходник. HTTP 200 сам по себе не означает успешный перевод. Это требования проектируемого адаптера, выведенные из схемы ответа.

## Языки, аккаунт и соседние API

Официальная [таблица кодов](https://niutrans.com/documents/contents/trans_json) содержит, например, `en`, `ru`, `ja`, `ko`, `ar`, `de`, `fr`, `es`; китайские коды — `zh` и `cht`. Есть региональные `pt-BR`, `fr-CA` и нестандартные соответствия: Georgian=`jy`, Kazakh=`ka`, Kazakh(Cyrillic)=`kk`, Mongolian=`mo`, Mongolian(Cyrillic)=`mn`. Это не универсальная ISO/BCP47-таблица. Нужен отдельный provider mapper, а не изменение глобального значения `ka` для всех движков. Полный каталог/доступность всех направлений данным исследованием не проверены.

В [официальном описании подключения](https://niutrans.com/documents/contents/trans_json) требуются регистрация, вход в консоль и APIKEY. Для этого протокола не заявлены AppID, signing secret, Bearer или HMAC. Ресурсы аккаунта и доступ должны быть достаточны; [тарифная страница](https://niutrans.com/price/) и рекламная бесплатная квота не доказывают доступность/бесплатность конкретного аккаунта. Живой аккаунт не использовался.

`/NiuTransServer/translationJson` — другой endpoint с JSON-объектом в `src_text` и JSON-результатом, не текстовая замена текущего `TranslationBackend.translate():String`. Основание: [JSON API](https://niutrans.com/documents/contents/trans_json).

## Что не подтверждено

| Вопрос | Результат исследования / решение для реализации |
| --- | --- |
| Максимум **UTF‑8 bytes** | **Не подтверждён.** «5000» не устанавливает предел raw UTF‑8 bytes, encoded form bytes, Unicode code points или UTF‑16. Нельзя объявлять это 5000/6000 байт либо переносить чужой лимит. |
| Общий размер HTTP body | Не найден нормативный предел с учётом ключа, percent-encoding и опций. |
| Серверный timeout в секундах | Есть `13008`, но нормативная длительность не установлена. Число в SDK-примере не является SLA. |
| Idempotency/retry | Не найден документированный idempotency key, deduplication window или гарантия неповторного списания после timeout/reset. Не утверждается, что их вообще не существует. |
| Retry-After и HTTP status mapping | Отдельная гарантия соответствия JSON-ошибок HTTP-кодам не установлена. Проверять HTTP и vendor JSON независимо. |
| Единица QPS | Привязка к аккаунту, конкретному ключу, IP, endpoint и sliding-window/burst в доступном тексте не уточнена. Другие приложения могут расходовать тот же лимит. |
| Полный результат autodetection | Пример `from:"auto"` не доказывает возврат фактически определённого языка. Дополнительный detection endpoint не выдумывать. |
| Версия Flash/Pro/v2 | Актуальная привязка интерфейса консоли и модельного тарифа к этому endpoint требует отдельного подтверждения до заявления о поддержке Flash/Pro. |
| Особые условия аккаунта | Телефонная/региональная активация, права на конкретные пары и фактические квоты не проверены. |

Эти неизвестные не мешают писать изолированный адаптер опубликованного text-протокола и contract fixtures. Они ограничивают заявления о production-совместимости и требуют явно согласованной проверки аккаунта перед живыми запросами.

## Предлагаемый независимый Android-адаптер

Этот раздел — **наши проектные решения**, не обещания NiuTrans.

1. Добавить `Provider.NIUTRANS` и новый `engine/NiuTransTranslator.kt`, собственный код без SDK/старой обвязки. Цель — документированный text endpoint, без автоматического выбора JSON/Pro/партнёрского сервиса.
2. Фиксированный URL `https://api.niutrans.com/NiuTransServer/translation`. Скрыть произвольный endpoint у этого провайдера; не передавать ключ на другой host/path. Redirects, connection retries и фоновые повторы отключены. Для contract tests — инъекция клиента/контролируемого тестового URL, недоступная через production intent/settings.
3. Предпочесть **form POST**: `FormBody.Builder(Charsets.UTF_8).add("from", code).add("to", code).add("apikey", key).add("src_text", rawText)`. Вызов `.add` получает исходный текст: библиотека выполняет percent-encoding ровно один раз. `addEncoded`/предварительный `URLEncoder` не нужны. Ключ никогда не попадает в URL. Это наш выбор среди опубликованных content types.
4. Наш начальный предел — **4000 UTF‑8 bytes исходного chunk**, отдельно не более **64 KiB encoded body**. Это консервативная граница клиента, **не доказанный предел API**. Считать bytes после glossary protection: маркеры тоже занимают место. Не делить surrogate pairs/защищённые атомы. Невмещающийся атом отклонять, а не разрезать.
5. Переиспользовать отменяемый OkHttp Call и существующие transport timeouts **15/35/45 секунд**; это локальная политика приложения. Проверять `error_code` до `tgt_text`. Неизвестный код, неверный тип поля, пустой/повреждённый JSON → typed failure без отражённого server text. Ограничить response bytes/JSON depth/UTF‑8 и не HTML-decode результат без отдельного контрактного основания. Заимствованный HTTP client/dispatcher не закрывать вместе с одним запросом.
6. Успех/ошибка не меняют провайдера. После неоднозначного сетевого сбоя или `13008` только явный Retry; наличие client text hash не создаёт серверной идемпотентности.
7. Наш консервативный rate gate: сериализованный запуск, интервал не менее **250 ms**; общий для NiuTrans-вызовов с тем же fingerprint ключа/endpoint, включая разные входы приложения. Не хранить/логировать сырой ключ в gate. Ожидание отменяемое. Это не обещание отсутствия `10001`, особенно при использовании того же аккаунта вне приложения. Платную квоту автоматически не предполагать.

Ошибки адаптера: `10001` → RATE_LIMIT; `10003` → REQUEST_TOO_LARGE; `10000` → INPUT_EMPTY; `13002` → KEY_REQUIRED; `13008` → timeout/network failure без retry; `13001` → отдельное понятное «недостаточно квоты или доступа» (не объявлять его однозначно неверным ключом); неподдерживаемый язык/пара и прочее → безопасная локализованная ошибка. Сохранять числовой код как ограниченные метаданные, не полный JSON. На известных одинаковых языках существующий identity short-circuit может обойти API.

## Term / Memory

Передача `dictNo`/`memoryNo` уже входит в [text API](https://niutrans.com/documents/contents/trans_detection). Предлагаются два необязательных несекретных поля профиля `niutransDictNo` / `niutransMemoryNo`, с ограничением длины/управляющих символов. Формат ID в доступном описании — String, поэтому запрещено без доказательства требовать integer. В UI пустое значение должно называться «библиотека по умолчанию сервиса», а не «отключено». Способ полного отключения неизвестен.

Существует отдельный [Term write API](https://niutrans.com/documents/contents/customization_term): `POST https://apis.niutrans.com/NiuTransServerDict/addDictionary`, поля `fromText`, `toText`, `apikey`, `srcText`, `tgtText`, `dictNo`; ограничение source/target term — 100 символов, результат `flag`/`msg`/`id`. Это **мутация удалённого аккаунта на другом host**, а не обычный перевод. Она не входит в минимальный MT-адаптер. Протокол CRUD Memory здесь не подтверждён; URL не угадывается.

Наши локальные glossary/corrections не синхронизируются в эти библиотеки автоматически. Выбор существующего remote ID и загрузка локальных пользовательских записей — разные действия. Будущая remote CRUD требует отдельного явного сценария, credential binding и tests. Изменения библиотек в внешней консоли невидимы локальному `RuleRevision`: IDs должны входить в cache keys, а TTL/ручное обновление результата остаются необходимы. Не обещать немедленную свежесть server-default library при cache hit.

## Точные точки интеграции после разморозки

| Файл / контракт | Минимальное изменение |
| --- | --- |
| `core/Types.kt: Provider` | `NIUTRANS`; все exhaustive `when` должны пройти компиляцию. Наличие enum ещё не означает работающий adapter. |
| `engine/NetworkTranslator.kt` | Отдельный dispatch в `NiuTransTranslator`, а не ветка `CUSTOM`; сохранить общий запрет автоматических retries/redirects. |
| `engine/TranslationBackend.kt` | Передать typed `NiuTransOptions(dictNo,memoryNo)` через configured backend, с defaults для прежних callers; не упаковывать ID в prompt/model/ключ. |
| `engine/ProviderConfiguration.kt` | Обязательный сохранённый ключ NiuTrans, проверка пары/опций; LLM model/prompt не требуются. Никакой сетевой проверки при открытии Settings. |
| `core/CredentialIdentity.kt` | Фиксированный сервис: `(TRANSLATION, NIUTRANS, settings.credentialScope, default)`, endpoint игнорируется и не используется сетью; exact profile/global namespace, существующий vault, никакого fallback к CUSTOM/global/старому unbound slot. |
| `ui/TranslationOptions.kt` | Название NiuTrans, официальный адрес в credential disclosure, штатный ApiKeyEditor, optional library IDs. Не показывать LLM model/prompt/token controls или произвольный URL. |
| `core/Types.kt: AppSettings`, `store/SettingsJson.kt` | При включении library options — additive defaults, validate/encode/decode/export/profile round-trip; секрет в settings JSON не добавляется. Room migration для полей JSON не нужна. |
| `engine/TranslationPipeline.kt` | Явный provider byte policy; добавить options в whole/chunk cache keys и в снимок запроса. Существующие glossary/corrections/scope/history/freshness остаются общими. |
| `engine/EngineFailure.kt` / i18n | Actionable quota-or-access/unsupported-language ошибки на шести языках без server echo. |
| Legacy credential migration | Не включать новый сервис в перенос старых ключей автоматически: контракт переноса и действующий API — разные работы. |

**Существующий app auto важен:** `TranslationPipeline` сначала выполняет локальный `identify(text)`, затем передаёт уже разрешённый source; кроме того, сейчас он отбрасывает региональную часть через `substringBefore('-')`. Минимальный адаптер может сохранить эту логику и отправлять явный язык. Это будет app-level auto, **не доказанная provider-native autodetection**. Если native `from=auto` требуется в этом же этапе, нужно отдельно передать wire-source policy в backend; локальный язык для glossary/corrections и `TranslationResult.source` не подменять строкой `auto` или выдуманным `response.from`. Расширение `cht`/`pt-BR`/`fr-CA` также требует сохранения provider-specific тегов до adapter, а не одной таблицы в UI.

## Проверка следующего кодового этапа

- Настоящий HTTPS MockWebServer с доверенным fixture certificate и **точным SAN/hostname**, без hostnameVerifier/trust-all bypass. Для loopback не использовать reverse-DNS имя из `server.url` без проверки.
- Form serialization: literal `+`, `%`, `&`, переводы строк, CJK/RTL/emoji; ключ только в body, raw текст после server form-decoding совпадает побайтно; `dictNo/memoryNo` точны.
- Текстовый успех; HTTP 200 + каждый vendor error; особенно `"000000"`; missing/wrong-type/empty `tgt_text`, oversized/chunked/malformed UTF‑8/deep JSON; ни ключ, ни source не оказываются в исключении.
- Отмена pending Call/rate wait/body read; late completion/settings/key/profile/source change не публикуют результат. Reset после POST, timeout/`13008`, 307/308 и `10001` не порождают второй запрос или другой host.
- Пределы UTF‑8 до/после marker protection, body bound, surrogate/atomic spans, восстановление разделителей; общий QPS gate для конкурирующих entry points и разных профилей с одним ключом.
- Profile-bound vault isolation, JSON options round-trip, cache separation по library IDs, отсутствие LLM/endpoint controls у NiuTrans. Explanation-модуль продолжает отклонять NIUTRANS: обычный MT не является LLM-пояснением.
- Живой API — отдельный разрешённый account test с минимальным синтетическим текстом и заранее известным бюджетом. Его отсутствие не заменяется localhost fixtures и не доказывает production квоты/качество/все пары.

В текущем этапе создан только этот план. Gradle, ADB, Git и платный API не запускались.
