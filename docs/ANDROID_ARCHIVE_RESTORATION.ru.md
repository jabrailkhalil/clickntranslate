Актуальная передача на20ноября2026: **основная1.8.3/code36 и кандидатcode37**. [APK и границы](ANDROID_HANDOFF_183.ru.md), [матрица32 возможностей](ANDROID_FEATURE_STATUS_183.ru.md), [новый отчёт](qa/archive-restoration/hymt183/README.md). Code37 исправляет GGUF-шаблон; сборка1889JVM/lint0 и независимый ReleaseUI — PASS, native-generation на ARM bridge — FAIL/SIGILL. Не публиковался, прежний ключ сохранён. Полная приёмка не объявляется; нижние таблицы сохраняют свой исторический scope.

# Android: функции, проверки и остаток

Актуальная версия по запросу пользователя — **1.8.3/code33 (`0abd1b9d`)**, подписана исходным сертификатом `1746bfc2…cafe85` и установлена **поверх production1.8.2/code7** на телефоне. Базовый ID `dev.clickn.translate` и первое время установки сохранены, uninstall/clear не выполнялись, публикаций нет. Функциональный код идентичен [исторической партии1.9.4](qa/archive-restoration/phone194/README.md):40 целевых unit PASS, lint без errors, оба Arabic-параграфа переводятся новым локальным пакетом. Точный native reference остаётся FAIL из-за потери букв в `OCR`; качество OCR/MT ещё требует доработки. [Рабочий журнал](ANDROID_WORK_STATE.ru.md) содержит текущие APK/SHA/подпись. Далее — исторические данные1.9.1, которые сохраняются со своим исходным scope.

27 октября 2026. **CHECKPOINT APK — 1.9.1 / code29**, source **`6976c086268e8643e4f42f991f347ffd9487b2f1`**, ветка `codex/android-rewrite`. APK не менялся: QA SHA256 `912d65ec8deef916d2567ca2a6f20596860f5a6c3803c2dde70fe284e62b9e90`. Контролируемый [capture191 follow-up](qa/archive-restoration/capture191-followup/report.json) подтвердил перевод static page0 без исправления приложения. **Прежнее объявление page0 подтверждённым критическим блокером было поспешным; полной готовности приложения по-прежнему не заявляется.**

[Первичный recovery191-отчёт](qa/archive-restoration/recovery191/report.json), 356 evidence-файлов, сохраняется без изменения JSON вместе с первоначальной оценкой. Новые выводы и их границы приведены ниже. Каталог `.tmp/static192` — имя диагностической партии; версия приложения остаётся **1.9.1**, новой версии192 нет.

Только Android. По разрешению владельца используются и дорабатываются его архивные UI, персонажи и модули 1.8.2; независимая перепись всей реализации не заявляется. `main`, настольные исходники, другие платформы, production-ключ и опубликованные релизы не менялись; Git-история не переписывалась. Production Release, новый ключ, push и публикация не выполнялись.

## Финальный checkpoint: что реально проверено

| Проверка source `6976c086268e8643e4f42f991f347ffd9487b2f1` | Фактический результат |
|---|---|
| compileDebug | **PASS, 2 мин 45 с** |
| assembleDebug + assembleValidation | **PASS, 9 мин 27 с** |
| Сигнатуры Kotlin до DEX, Debug и Validation | В обоих вариантах: **473 класса / 3676 методов; максимум 251 слот при лимите 255** |
| ProviderSheet → Advanced | **PASS в проверенном сценарии:** OpenAI → ML Kit, durable save; Advanced показывает ML Kit и открывается без crash |
| Settings Save / повторный вход | **PASS:** retry false → true → Save → reopen true; затем restore false → Save |
| Первоначальные capture-наблюдения |24: page1 оба RU;21/26: page0 без результата. Эти snapshots сохранены; объявление подтверждённого page0-блокера пересмотрено контролируемым follow-up ниже |
| Stop / окружение | **PASS:** CaptureService отсутствует, MediaProjection null; AVD выключен, production не затронут |

Первоначальные NoResult21/26 не удалены из истории. Их причины отдельно не доказаны, но текущий контролируемый static page0 PASS на том же APK не поддерживает прежнее утверждение о подтверждённом блокере. Гипотеза HTTP cache poisoning ранее отклонена: engine keys раздельны, ошибки в cache не записываются. Полное функциональное соответствие из этих сценариев не следует.

## Контролируемое уточнение capture191: тот же APK, без app fix

[Отчёт follow-up](qa/archive-restoration/capture191-followup/report.json); первичные evidence находятся в `.tmp/static192`. Source и APK те же, что в checkpoint: `6976c086268e8643e4f42f991f347ffd9487b2f1` /1.9.1/code29. Новый полный unit/runtime/Android/lint запуск не выполнялся.

| Контролируемый сценарий | Наблюдавшийся результат |
|---|---|
| QA text page0 | RU, случай05 |
| Debug page0, реальный OCR → MT | RU, случай12 |
| QA FIXED page0 | RU, случай40 |
| QA SETTLED500 после live Settings | Автоперевод возобновился без дополнительных тапов по герою:47 page0 RU,49 page1 RU,52 возврат page0 RU |
| QA developer=false, force-stop, холодный Main | Main60 → ровно один запуск тапом65 →66: оба RU-перевода page0 |
| HTTP503 → recovery, источник page0 не менялся |79: ошибка;81: оба синтетических `ВОССТАНОВЛЕНО`-маркера |
| Отложенный старый HTTP-ответ | Ответ forests/seq21 удерживался30с и был отправлен после нового purple/seq22; после deadline PNG/XML86 соответствуют только page3(valleys+purple), старого forests нет |
| Shizuku1.9.1 | Реальный shell, PID8472; без root, MediaProjection null, Accessibility0.115 page0 RU,117 page1 RU,119 landscape RU,121 portrait RU |
| Фото, одно owned-изображение |139: подтверждение →141: Complete1/1, оба связных абзаца RU →148: SAF export successful1 |
| Холодный запуск и конкретные записи истории | После force-stop/cold149 текстовая история сохранена в150; задача изображения в152 — Complete1/1 сRU |

В конкретном операторском эпизоде36 уже шёл countdown, а лишний тап привёл к OFF в37. Это согласуется с `CaptureService`: resume после собственной UI в строках394/400, loopON до countdown около1730, повторный тап выключает loop около1708. Данный эпизод подтверждает ошибку управления тестом. **Он не доказывает, что все прежние NoResult, включая21/26, имели ту же причину.** Прежние снимки остаются фактами наблюдения, но новый контролируемый прогон прошёл без изменения кода/подписи/APK; source patch для page0 не потребовался.

HTTP-сервер возвращал только owned synthetic markers: подтверждены recovery/wiring и отбрасывание старого ответа в указанных сценариях, а не качество перевода реального сервиса. Ручной partial-unit recovery (часть единиц уже успешна, повторяются только оставшиеся) ещё не подтверждён. Landscape подтверждён здесь для Shizuku; это не весь provider/OEM/rotation corpus.

### Фото, SAF-экспорт и история после холодного запуска

Приложение не менялось: source `6976c086268e8643e4f42f991f347ffd9487b2f1`, APK1.9.1/code29. Использован собственный tracked input `gentle-page1-source.png`, SHA256 `b8af7ceb62191bbcad1a6f1f11f5be5f366d9af2b551da354aa1c09fa73fafba`. Случаи139/141 подтверждают один завершённый перевод с двумя связными RU-абзацами,148 — успешный SAF-экспорт одного результата.

Экспортированный PNG: **67 285 байт**, SHA256 `e5fc1041b78129f4a2cacac0d789f194ba9f6c17fd3ddc3f57d0a70bd7d5134a`; изображение визуально осмотрено в ручном прогоне. После force-stop и холодного входа149/150 конкретная текстовая история сохранилась; в152 сохранённая задача изображения показывала Complete1/1 иRU. Это не подтверждает весь batch/EXIF corpus, миграцию production или сохранность всех пользовательских данных. **PRIVATE151 не экспортируется.**

Захват к концу этого прогона остановлен, MediaProjection null; восстановлены accelerometer_rotation=1 и user_rotation=0. Эмулятор завершён через `adb emu kill`: подключённых устройств и процессов qemu/Java нет, локальный HTTP fixture больше не слушает18791.

## Предыдущий кандидат: автоматические PASS, ручной VerifyError FAIL

До финального исправления прошли **1838 JVM / 482 XML suites**, failures/errors/skips = 0; **16 runtime-проверок** (два выполненных набора и один пустой); **97 Android за 40,855 с**; lint **0 errors / 977 warnings / 42 info**. Это исторические результаты предыдущего кандидата, **не текущий PASS финального source**.

Ручной запуск того кандидата выявил **VerifyError**: closure-конструктор SettingsScreen имел 260 параметров / 262 register slots, а DEX count стал 6. Исправлены 21 строка: callback `::buildSnapshot` вместо восьми прямых широких захватов формы. Максимум стал 251 слотом. После исправления выполнены перечисленные compile/assemble/closure checks, ограниченный ручной QA и последующий контролируемый follow-up на том же APK. **1838 JVM, 16 runtime, 97 Android и lint на финальном source не повторялись.**

## Изменения текущей партии

ProviderSheet ждёт успешное durable save до закрытия/Advanced; запись принадлежит ViewModel, UI cancellation не вызывает позднюю навигацию, busy/error/retry ограничены безопасными локализованными состояниями. Чистый Settings editor следует repo, dirty Save применяет только field delta внутри DataStore update. Секреты остаются в памяти, без нового SavedState/файлов/логов; явная правка того же поля побеждает latest, вложенный объект/список считается одним полем.

MT recovery повторяет failed units и image MT с паузами2/4/8/16/30с при включённой настройке. WAIT/FIXED используют чистые кадры, bootstrap и свежую OCR/ROI validation. Journal/gate получили locking/owner/generation guards, font/import — правильную границу finishWrite/fsync. Gallery сохраняет неопределённый исход для явной UI-проверки вместо автоматического удаления. Предыдущие автоматические PASS и текущая ограниченная ручная проверка разграничены выше; общей транзакции stores и решения unknown SAF URI не заявляется.

## Исторические проверки предыдущего кандидата CDA

Результаты относятся к CDA внутри 1.9.1, **не к финальному 6976c086268e8643e4f42f991f347ffd9487b2f1**:

- Пять Gradle-задач **PASS за 17 мин 20 с**; **1826 JVM / 478 XML suites, 0 failures/errors/skips**. Lint **0 errors / 977 warnings / 42 info**.
- **16 runtime PASS за 5 мин 22 с**: 13 SourceObservationCaptureRuntimeTest + 3 GalleryExportRecoveryRuntimeTest.
- Полный Android **97 PASS за 46,105 с**, с `downloadModels=true`.
- Ручные WAIT и FIXED 2000 мс: **PASS в наблюдавшихся сценариях** — фон анимировался вне OCR-блоков, page change переводился под открытым overlay. `WAIT + AUTO + dialog-only=true` подтверждает только dialog-only scope, не обещание всей страницы.
- SETTLED 500 мс на статической странице: page0 → page1 → page0, оба наблюдавшихся результата RU. **PNG40 показывает RU**, XML этого сохранения — raw source: snapshots неатомарны и не относятся к одному моменту состояния.
- На CDA HTTP503 проверен **частично; recovery NOT_VERIFIED**, Shizuku1.9.1 тогда не проверялся. Последующие controlled recovery79/81, late-response86 и shell115/117/119/121 относятся к follow-up выше.

На CDA обнаружено окно async ProviderSheet save / one-shot Advanced load: первый Advanced показывал ML Kit, после commit Main — OpenAI, повторный Advanced — OpenAI. Retained locale draft этим не подтверждён. Исправление вошло в текущую партию; финальный ручной OpenAI → ML Kit → Advanced PASS указан выше. Это не полный повтор editor/provider corpus.

## Исторические доказательства 1.9.0

Предыдущая выдача — **1.9.0 / code28 / `f50e22edc38d5defaedf73488c6dd958b8748ba6`**. Её [финальный отчёт](qa/archive-restoration/covered-source190/final/report.json) и [ручные результаты](qa/archive-restoration/covered-source190/final/device/manual-results.json) сохраняются. Они не являются прогоном новой партии 1.9.1.

- Пять Gradle-задач: **PASS, 17 мин 17 с**, 1806 unit / 476 XML suites, failures/errors/skips = 0. Lint: 0 errors / 977 warnings / 42 info.
- Android: **89 уникальных PASS**. Основной запуск 20,21 с дал 87 PASS и 2 assumption skips; отдельный запуск этих двух с `downloadModels=true` дал 2 PASS за 135,025 с. Включены реальный Auto OCR двух полных абзацев, Arabic/mixed English и отмена нативного OCR.
- R8 System и Shizuku: page0 → page1 под открытым переводом, целый `Gentle winds carry the autumn leaves.` в MT, замены `valleys → forests` и `orange → purple`. Shizuku — UID2000 shell, без root/MediaProjection/Accessibility; Stop проверен. Это наблюдавшиеся сценарии, не весь многоязычный corpus.
- Поворот: полный перевод восстановился после возврата в портрет; промежуточные 12-секундные снимки ещё показывали обработку. Статус **PORTRAIT_RECOVERY**, готовый landscape MT не подтверждён.
- 13 runtime capture cases имеют более ранний PASS на e4b/c3b; они не повторялись на f50. Неподвижный Debug soak c3b: 10 мин 4 с, 376 наблюдений и один первый OCR start. Это не батарея/нагрев телефона и не новый soak 1.9.1.

Собственный regression PNG 1080×2400 с реальной OCR-геометрией h61/h46/gap24 имеет SHA256 `b8af7ceb62191bbcad1a6f1f11f5be5f366d9af2b551da354aa1c09fa73fafba`. Проверки Latin tail сохраняют язык, parent/column/alignment/script guards. Неудачный [кандидат c3b](qa/archive-restoration/covered-source190/candidate-c3b/result.json) и исходный [baseline 1.8.9](qa/archive-restoration/covered-source190/baseline189/result.json) сохранены отдельно; их ошибки не скрыты последующими PASS.

## APK и подпись

Это checkpoint APK для review/продолжения, **не production Release и не полная готовность**. Точные метаданные: `.tmp/recovery191/device-checks/apk-delivery.json` и [финальный отчёт](qa/archive-restoration/recovery191/report.json).

| Выданный Desktop APK1.9.1 | Package | Байты | SHA256 |
|---|---|---:|---|
| [Full](C:/Users/Home-PC/Desktop/ClicknTranslate-Android-1.9.1-Full.apk) | `dev.clickn.translate.debug` | 93 942 902 | `7951efd3219cf53ee991ec4464af2b07fc4f28b90729effd222926404a68122c` |
| [QA](C:/Users/Home-PC/Desktop/ClicknTranslate-Android-1.9.1-QA.apk) | `dev.clickn.translate.validation` | 64 659 672 | `912d65ec8deef916d2567ca2a6f20596860f5a6c3803c2dde70fe284e62b9e90` |

Оба APK — version1.9.1/code29, существующий debug certificate `4a627d18c2e9597f691314d7d01ee1699b9e1f74189c13d0aa213b0c53eba5ad`. Zipalign16KB — статический PASS; 19 ARM64 ELF побайтово совпадают с соответствующим вариантом1.8.9. Это не16KB runtime телефона. Production ID `dev.clickn.translate` сохранён; Debug/QA не обновляют production.

Исторический [Full Debug ARM64 1.9.0](../artifacts/android/ClicknTranslate-1.9.0-full-debug-arm64.apk) и его метаданные в [отчёте1.9.0](qa/archive-restoration/covered-source190/final/report.json) сохраняются без переименования.

## Сравнение возможностей

Каждый статус ограничен указанным сценарием/source. Контролируемый follow-up уточняет прежний вывод о static page0 без изменения APK. Исторические проверки и новые ручные результаты не заменяют полный неповторённый функциональный corpus.

| Возможность прежней версии | Реализация | Статус | Доказательства и предел |
|---|---|---|---|
| MediaProjection, герой, наложение, Stop | Lifecycle/epoch guards и чистое наблюдение | Реализована и протестирована | Follow-up на том же6976: QA FIXED40/SETTLED47,49,52 и cold one-tap66 PASS. Старые21/26 сохранены; Stop checkpoint PASS. Полный corpus не заявляется |
| Shizuku | Backend, разрешения и сохранение выбора | Реализована и протестирована | Follow-up1.9.1: shell PID8472, без root/projection/accessibility;115 page0,117 page1,119 landscape,121 portrait RU. Остальные OEM/revoke случаи не закрыты |
| ROI, resize, сохранение и поворот | Геометрия области и свежая OCR/ROI validation | Реализована и протестирована | Исторические ROI/1.9.0 PORTRAIT_RECOVERY; текущий Shizuku119 landscape→121 portrait RU. Весь rotation/revoke набор не пройден |
| Автоповтор под наложением | SETTLED_PAGE и чистые WAIT/FIXED, async cancellation/bootstrap guards | Реализована и протестирована | Текущий FIXED40 и SETTLED50047/49/52 PASS; CDA WAIT/FIXED на animated source исторический PASS. Dialog-only не означает всю страницу |
| Повтор после MT-ошибки | Failed units/image MT, retryFailedTranslation и паузы до30с | Реализована и протестирована | Follow-up79:503→81:оба synthetic markers на неизменнойpage0;86 отбрасывает старый held forests послеpurple. Ручной partial-unit recovery и весь provider corpus не подтверждены |
| OCR, абзацы, RTL и независимые блоки | ML Kit/Tesseract и подготовка связного текста | Реализована и протестирована | Исторические 1.9.0 Auto OCR, Arabic/mixed English, native cancellation и Gentle; весь corpus не пройден |
| Текст, copy, Share и история | Room, durable history и legacy import | Реализована и протестирована | Текущий cold149/150 сохранил конкретную QA text history; image task152 Complete1/1 сRU. Исторические text/copy/share/upgrade отдельно; все пользовательские данные этим не проверены |
| Фото, Share, batch, EXIF и экспорт | Bounded decode, SAF receipts и явный UI review вместо auto-delete | Реализована и протестирована | Текущий single-image139→141 Complete1/1 сдвумя RU-абзацами,148 SAF export1; cold152 задача сохранена. PNG визуально осмотрен. Весь batch/EXIF corpus не повторялся; старые media184/clean186/1.8.8 сохраняют исходный scope |
| Google text | Сохранённая интеграция | Реализована и протестирована | Исторический 1.8.6 en/auto/postStop; причина FAIL 1.8.5 не установлена |
| Прочие сетевые и пользовательские API | Интеграции, отмена и диагностика | Реализована, но не проверена на устройстве | Контролируемые HTTP recovery и stale-response PASS на собственном endpoint; реальные аккаунты, paid API, все лимиты и ошибки не проверены |
| Offline MT и модели | ML Kit | Реализована и протестирована | Исторический en→ru 1.9.0; все download/delete варианты не повторялись |
| Глоссарий, профили, settings import/export | Room/DataStore, шифрование, journal/gate и editor delta/rebase | Реализована, но не проверена на устройстве | 8Settings+4provider cases прошли в предыдущем1838, не повторялись финально. Текущие provider/Advanced/retry persistence PASS в ограниченном scope; общей cross-store изоляции нет |
| Словари | SQLite packs, normalization/forms | Реализована и протестирована | Исторические 1.8.8 owned v1/v2, invalid/cancel/NFKC/Arabic definitions |
| TTS | System и HTTP | Реализована, но не проверена на устройстве | Init/voices smoke; слышимый звук и весь набор сервисов не подтверждены |
| Local LLM и управление моделями | Библиотеки, загрузка, удаление и импорт | Реализована, но не проверена на устройстве | Physical ARM64 Hy-MT2/Sakura decode, GPU/Vulkan и весь набор моделей не подтверждены |
| Плитка и Process Text | Системные точки входа с guards | Реализована и протестирована | Исторические media184 consent/rotate/replace/cancel и intent integration |
| Accessibility и перевод ввода | Дополнительные модули | Реализована, но не проверена на устройстве | Остались клавиатуры, OEM и варианты отзыва разрешений |
| Onboarding, герой и готовность | Четыре шага, chooser и список действий | Реализована и протестирована | Исторические 1.8.7 user11/rotation/readiness и 1.8.8 regression. Readiness — состояние настроек, не число UI-тестов |
| Темы, AMOLED и шесть языков UI | UI владельца с доработанными controls, шрифтами и preview | Реализована и протестирована | Исторический 1.8.9: locale, normal/200%, 280dp/RTL; все экраны и сочетания не пройдены |
| Production upgrade с сохранением данных | ID сохранён, новый code29, прежний ключ не заменён | Реализована, но не проверена на устройстве | Production-подпись и установка обновлением не выполнялись |

## Исторический Debug-инцидент

При диагностике c3b root повредил внутренний Debug DataStore через stdin `adb shell` — Windows Ctrl-Z усёк protobuf. Пользователь уведомлён. Работа восстановлена из двух полных исходных entries, восьми известных non-secret fields и безопасных QA defaults; известные `FLOATING_WINDOW`, `merge=true` и ROI entry с metadata 1080×2400 возвращены. **Остальные утраченные исходные Debug-настройки не считаются восстановленными.**

QA и production не изменены восстановлением; QA preferences SHA256 до/после совпал: `8bee9fbaa7fcb79708531cb83e6d53eb22166048fc1aa0e9a7331d9c7bfc50a1`. Восстановление не меняло Room/history/models. Receipt: `.tmp/soak190/candidate-c3b-device-checks/debug-config-recovery.json`. Опасный скрипт DISABLED; `PRIVATE*.pb` / `damaged*.pb` не публиковать и не коммитить. Прямую диагностическую подмену preferences не повторять. Новые journal guards не восстанавливают утраченные старые Debug-поля.

## Точный остаток

Основные пользовательские модули по журналу реализованы. Пункты1–3 ниже — оставшееся покрытие совместимости и поведения; пункты4–5 — известные границы хранения. Они не означают отсутствия экранного, текстового или фотоперевода. Production-подпись не блокирует текущую Debug/QA-сборку.

1. Physical ARM64: Android8, Hy-MT2/Sakura decode, GPU/Vulkan и16KB runtime. API26 ARM64 AVD на Windows отказал; API36 x86_64 с ARM bridge не заменяет телефон и ранее падал на NEON при LLM decode.
2. Звук TTS, длительная работа/батарея/нагрев телефона; полный OCR/RTL/колонки/смешанные языки corpus, OEM/Accessibility/клавиатуры, paid/custom API и оставшиеся permission/rotation сочетания. Контролируемый Shizuku landscape PASS не закрывает все способы захвата.
3. Ручной partial-unit recovery, image-MT и остальные сбои/отмены провайдеров: HTTP503→оба markers и late-response rejection уже PASS в описанном scope, но не доказывают все варианты. Полный editor/provider corpus и автоматические наборы после callback-исправления не повторялись.
4. Cross-store transaction/snapshot isolation отсутствует; same-value/ABA edits и glossary admission/read→write race остаются. Editor same-field edits побеждают latest; агрегат считается одним полем. Simulated fatal tests не равны смерти процесса или отключению питания.
5. SAF unknown URI / неопределённый исход после смерти процесса остаётся. Gallery review сохраняет исход для явной проверки; auto-delete не объявляется решением. Общие legacy cache PNG не удалять без доказанного владения. Частичная утрата Debug-настроек не считается полностью восстановленной.
6. Production upgrade — только прежним private key и по отдельному запросу. Production Release, новый ключ, push и публикацию не выполнять; `main` и Desktop-исходники не трогать. Причина старого Google FAIL1.8.5 неизвестна.

[Рабочее состояние и среда](ANDROID_WORK_STATE.ru.md), [срез 1.8.8](qa/archive-restoration/gesture188/report.json), [UI-срез 1.8.9](qa/archive-restoration/usability189/report.json). Старые отчёты и APK сохраняются с исходной областью проверки.
