# Состояние Android на 24 ноября 2026 — code44

Подписанная 1.8.3 (code44) использует прежний ключ приложения. На Android 15 она обновила исходную 1.8.2 (code7) с сохранением тестовой истории, тёмной темы, языка перевода и времени первой установки. На Android 16 повторно экспортирована сохранённая фотозадача code43. Проверены оба перевода и непрозрачность подложки в двух внутренних участках PNG. [APK](../artifacts/android/1.8.3-code44/ClicknTranslate-Android-1.8.3-code44-candidate.apk) · [Отчёт](qa/archive-restoration/gallery44/README.md).

Прошли 1 895 JVM-тестов и 110 инструментальных тестов. Из инструментальных ещё 5 пропущены по условиям запуска. Lint сообщил 0 ошибок, 975 предупреждений и 42 информационные записи. Телефон отсутствует в ADB. На физическом ARM64 остаются установка code44, локальные модели, Shizuku и время экранного перевода. Другие пробелы в приёмке перечислены в матрице. [Матрица возможностей](ANDROID_FEATURE_STATUS_183.ru.md).

## Состояние на 20 ноября 2026 — code38

Code38 (`f14cd0e5`) собран и подписан прежним сертификатом. DataStore защищает выбор переводчика и языков от позднего завершения загрузки офлайн-модели, в том числе при смене и возврате к прежнему выбору. Повторный прогон подтвердил 1 893 JVM-теста и lint без ошибок. Обновление code37→38 на эмуляторе сохранило историю и выбранный сервис. [Отчёт code38](qa/archive-restoration/selection38/README.md).

Физическая установка code38 и новый прогон Hy-MT2 на ARM64 впереди. Сведения о предыдущем кандидате ниже относятся к code37.

## Кандидат code37

Source57704198, версия1.8.3/code37. Исправлены три пути GGUF-форматирования; код сохранён в коммите. Подписанный кандидат вынесен в `artifacts/android/1.8.3-code37/`, SHA6da6dd27…16ae212eb; основной Desktop APK остаётся36. [Текущая передача](ANDROID_HANDOFF_183.ru.md), [новый отчёт](qa/archive-restoration/hymt183/README.md).

Сборка38мин40с/1889JVM/lint0 — PASS. NativeAndroid: первый FAIL при чтении подготовленного файла(EACCES), затем после его исправления FAIL/SIGILL при вычислении; нет завершённого B3. Подписанный ReleaseGoogleText+onboarding+coldHistory — PASS собственной фразы. Host8HyMT+2Sakura-format случая не являются Android-generation PASS. Неверное количество книг на повреждённой OCR-огласовке не исправлено; прежний Arabic-тест удаляет диакритики при сравнении.

Публичные доказательства и сравнительная таблица актуализированы по сохранённым прогонам, без новых тяжёлых запусков. Source-приложение после57704198 не менялось. Восстановленные legacy UI/модули разрешены владельцем; clean-room не заявляется. Без публикации/нового ключа. Телефон отсутствует вADB, последнее физическое обновление33поверх7. Эмулятор выключен, собственный профиль12 оставлен с тестовой моделью для продолжения, не объявляется удалённым.

Остаток: завершение native наARM64, HyMT2/Arabicдиакритики, OnePlus/Shizuku и непроверенные TTS/Accessibility/Android8/runtime16KB/GPU/paidAPI. Защита поздней MLKit-активации пока value-only: ABA/same-value intent не закрыты. Общая цель не завершена.

## Исторические checkpoints

# Состояние Android на 10 ноября 2026 — code36

Подписанный **1.8.3/code36**, исходники `b997ee3c750bd441dde2ffd334c1c69665d17e46`. [APK](C:/Users/Home-PC/Desktop/ClicknTranslate-Android-1.8.3.apk): **64 396 846 байт**, SHA-256 `716f9de1d70a6700178b709bb8cacc4bd7e96574879d8c6a770f86c17def9f17`. Прежний сертификат1746bfc2…cafe85, без нового ключа/публикации/push. Code35 сохранён отдельно.

Исправлены частичные фотопереводы и повтор только пропущенных блоков, cleanup/timeout Shizuku-процесса и поздняя активация ML Kit. Старые ложные SUCCEEDED фото исправляются без сети и удаления хороших результатов. Room-схема/DataStore не менялись. Сборка3ноября PASS19мин11с; **1889 JVM/491 набор,19 Android**, lint0 ошибок/975 warnings/42 info.

10ноября завершён оставленный настоящий Release update35→36 в том же собственном профиле12, без uninstall/clear: firstInstallTime и ID сохранились. Открытие старой задачи исправило статус наPARTIAL безHTTP; Retry failed отправил ровно второй абзац, итогSUCCEEDED/missing0, оба перевода. Свидетельства в [recovery183](qa/archive-restoration/recovery183/README.md). Успешные сборка/тесты повторно не запускались. Собственный профиль12 удалён, прежние0/10/11 сохранены, эмулятор/provider остановлены, MediaProjection null.

Телефон не виден вADB; последняя физическая установка — code33 поверх1.8.2/code7. Свежийcode36/Arabic OCR, OnePlus/Shizuku, слышимостьTTS/частьAccessibility, Android8/runtime16KB/GPU/платныеAPI остаются без нужного подтверждения. Ошибка смыслаHy-MT2 сохраняется. **Полная готовность не объявляется.** [Текущая передача](ANDROID_HANDOFF_183.ru.md), [матрица32 возможностей](ANDROID_FEATURE_STATUS_183.ru.md).

## Исторические checkpoints, сохраняющие свой scope

# Состояние Android на 3 ноября 2026 — code35

Текущий подписанный APK — **1.8.3/code35**, исходники `931eb5ae176547863759c6fe0105b6456338f9c4`. [Файл](C:/Users/Home-PC/Desktop/ClicknTranslate-Android-1.8.3.apk): **64 384 558 байт**, SHA-256 `de1fb2432b050397f2312eb333163bc15d62f2c7c861e6d10173c90293ed493b`. Прежний сертификат `1746bfc2…cafe85`, без нового ключа, публикации и push. Code34 сохранён отдельно локально.

Закрыт обнаруженный в настоящем UI пропуск темы/акцента/языка меню/героя в экспорте. V3 переносит эти поля, V1/V2 сохраняют локальный UI. После COMMITTED работает восстановление и защита поздних/ABA-изменений. Подсказка разрешения использует фактическое имя Clickn; имя файла имеет одно `.zip`. Room-история и формат DataStore не менялись, прежние UI-ключи сохранены.

Один Gradle-прогон **22 мин 5 с PASS**: Debug/AndroidTest/полный JVM/lint/Release. На срезе сборки **1871 PASS / 488 наборов**, без failures/errors/skips; один тест константы затем удалён, production не менялся. Lint **0 ошибок / 974 warnings / 42 info**. Android: **19 PASS / 11,22 с**, реальные локальные хранилища, собственные фикстуры и симулированные fatal checkpoints.

Подписанный Release API36 установлен в собственном чистом профиле13, SHA совпал. Onboarding → V3 экспорт → смена четырёх UI-полей → импорт → настоящий force-stop/cold launch — **PASS**, снова чёрная тема/Океан/ru/Док. Диалог разрешения действительно показывает Clickn. Ранее на code34 отдельно подтверждены готовность4/5→5/5, запуск capture/Док поверх launcher и остановка MediaProjection; новый code35 этим наблюдениям не приписывается. Собственные профили12/13 удалены, прежние0/10/11 сохранены, эмулятор выключен.

На телефоне последняя подтверждённая установка — **1.8.3/code33 поверх 1.8.2/code7**. Code35 на физический телефон не установлен: ADB видел только эмулятор. Остаются физические проверки новой сборки/Arabic OCR, ограничение Shizuku на OnePlus, слышимость TTS/часть Accessibility, Android8/runtime16KB/платные API/другие OEM и языки. Ошибка смысла Hy-MT2 остаётся. **Полное функциональное соответствие не объявляется.**

[Текущая передача](ANDROID_HANDOFF_183.ru.md), [точный отчёт](qa/archive-restoration/ui-settings183/README.md). Предыдущий [Arabic code34 checkpoint](qa/archive-restoration/arabic-latin183/README.md) сохранён. Ниже — исторический журнал со своими исходными срезами.

## Исторический журнал до 3 ноября 2026

# Состояние Android на 27 октября 2026

Актуальная версия по запросу пользователя — **1.8.3/code33**, source **`0abd1b9d920e24985acacbde8b02477f007a1e39`**. APK `C:\Users\Home-PC\Desktop\ClicknTranslate-Android-1.8.3.apk`, SHA256 `ebec8a26df443ab1418ff1eff130445cda5a788d5091bc6c414877da4c7777b5`, подписан прежним production-ключом с сертификатом `1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85`. **На телефоне выполнено обновление основного `dev.clickn.translate` с1.8.2/code7 до1.8.3/code33**, без uninstall/clear, исходное время установки сохранено. Холодный запуск Main успешен; личные production-история и секреты не читались. GitHub-релиз, push и публикация не выполнялись. Прежний ключ проверен; новый не создавался. Закрытая копия подписи находится вне репозитория, исходные разрешения папки не менялись.

Прикладные исходники идентичны проверенной партии `2131073d` ([исторический1.9.4](qa/archive-restoration/phone194/README.md)); изменена только версия сборки. Там40 целевых unit PASS, lint0 errors/977 warnings/42 info, физические два Arabic-параграфа и отдельная English-кнопка. **Точный native reference-тест остаётся FAIL:** `OCR` распознаётся как `O` на эмуляторе и `OR` на телефоне; Hy-MT также ошибся в числе книг. Полная точность OCR/MT и полное функциональное соответствие не объявляются. Shizuku на этом OEM ограничен ADB; системный захват работает. Дальнейший остаток и сравнительная таблица сохраняются в отчётах; новых модулей в партии1.8.3 не добавляли.

Далее сохранён исторический checkpoint1.9.1 с исходными результатами и ограничениями. Его номера APK и статусы не являются отчётом о новой1.9.3.

**CHECKPOINT APK — 1.9.1 / code29**, source **`6976c086268e8643e4f42f991f347ffd9487b2f1`**, ветка `codex/android-rewrite`. APK не менялся: QA SHA256 `912d65ec8deef916d2567ca2a6f20596860f5a6c3803c2dde70fe284e62b9e90`. Контролируемый [capture191 follow-up](qa/archive-restoration/capture191-followup/report.json) подтвердил перевод static page0 без исправления приложения. **Прежнее объявление page0 подтверждённым критическим блокером было поспешным; полной готовности приложения по-прежнему не заявляется.**

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

## Содержание текущей партии

- ProviderSheet дожидается успешного durable save перед закрытием и переходом Advanced; запись переживает отмену UI, поздняя навигация защищена, повторные действия при сохранении блокируются, ошибка допускает явный повтор.
- Settings editor принимает поздний repo commit через rebase, сохраняя пользовательские правки. Save применяет только field delta относительно baseline внутри DataStore update, сохраняя поздние нетронутые provider/URL/key/model и preset/export metadata. Один mapper формы используется повторно; normalized form baseline отделён от persisted baseline. Секреты остаются в памяти; SavedState, файлы и логи для них не добавлены. Явная правка того же поля побеждает latest; вложенный объект/список считается одним полем.
- Добавлены **8 Settings policy/integration cases и4 provider save-coordinator cases**: delayed file-backed DataStore, сохранение нетронутых полей, failure/retry и UI cancellation. Они входят в исторический предыдущий набор1838; после callback-исправления не повторялись.

- Восстановление после ошибки MT ограничено неудачными единицами перевода и image MT. При включённом `retryFailedTranslation` используются задержки 2/4/8/16/30 с; уже удачные единицы не должны отправляться повторно. Не заявляется бесконечный повтор всей страницы.
- `WAIT_FOR_TEXT_COMPLETE` / `FIXED_INTERVAL` получают чистые кадры под открытым наложением; асинхронное наблюдение отменяет устаревшую работу. Bootstrap без text watch не отменяется только из-за фоновых изменений; перед MT добавлена проверка актуального OCR в ROI.
- Journal settings import получил общий process-local lock, чтение актуального intent перед изменением, owner UUID и запрет поздних изменений terminal record. После `AtomicFile.finishWrite` ошибка directory fsync больше не должна вызывать уничтожающий опубликованный record `failWrite` на API26. Recovery gate повторно проверяется перед queued DataStore transform, различает поколения восстановления и освобождает retry после отменённого запуска. Fatal import закрывает gate, сохраняя intent; CAS rollback не превращается в общую транзакцию stores.
- Для публикации font добавлен guard границы `finishWrite` / directory fsync.
- В галерее убрано автоматическое удаление SAF-документов; добавлен token ожидающей явной UI-проверки результата. Неопределённый исход и неизвестный URI после смерти процесса остаются отдельным ограничением.

## Исторический кандидат CDA внутри 1.9.1

Это предыдущий кандидат, **не финальный source 6976c086268e8643e4f42f991f347ffd9487b2f1**. Его фактические результаты не считаются новым прогоном после Settings/provider-исправлений.

| Проверка CDA | Фактический результат и граница |
|---|---|
| Пять Gradle-задач | **PASS, 17 мин 20 с**; 1826 JVM / 478 XML suites, failures/errors/skips = 0. |
| Lint | **0 errors / 977 warnings / 42 info**. |
| Runtime | **16 PASS, 5 мин 22 с**: 13 SourceObservationCaptureRuntimeTest + 3 GalleryExportRecoveryRuntimeTest. |
| Полный Android | **97 PASS, 46,105 с**, с `downloadModels=true`, без переноса assumptions в PASS. |
| WAIT / FIXED 2000 мс | **PASS в наблюдавшихся сценариях**: фон анимировался вне OCR-блоков, page change под открытым overlay переводился. Это не весь игровой/OEM corpus. |
| WAIT + AUTO + dialog-only=true | Подтверждён только этот dialog-only scope; **обещание перевода всей страницы не делается**. |
| SETTLED 500 мс, статический фон | Page0 → page1 → page0: оба наблюдавшихся результата RU. На PNG40 виден RU-результат, хотя XML того же сохранения содержит raw source. XML и PNG сняты неатомарно; их нельзя считать одним моментом состояния. |
| HTTP503 / последующее восстановление | На CDA: PARTIAL, recovery NOT_VERIFIED. Позднейшие controlled recovery79/81 и late-response86 относятся к follow-up выше. |
| Shizuku 1.9.1 | В историческом CDA не проверялся; позднейший реальный прогон финального APK1.9.1 приведён в follow-up выше. PASS1.9.0 сохраняет отдельную область проверки. |

Ручная проверка CDA также обнаружила отдельный Settings-дефект: Advanced, открытый до завершения async ProviderSheet save, показывал прежний ML Kit. Main после commit показывал OpenAI; повторный свежий вход Advanced — тоже OpenAI. Это окно async save/одноразового чтения, **не доказательство retained locale draft**. Исправление вошло в текущую партию; финальный ручной OpenAI → ML Kit → Advanced PASS приведён выше. Полный набор вариантов формы этим не закрыт.

## Историческая партия 1.9.0: что было изменено

Подтверждённый дефект 1.8.9: смена двух абзацев под собственным наложением в течение 20 секунд оставляла старый перевод. Закрытие наложения открывало новую страницу и запускало перевод. Маскирование собственных окон исключало закрытый текст из наблюдения. Это сохранённый **FAIL**, а не успешный длительный прогон.

В 1.9.0 добавлены обратимые lease скрытия собственных окон для ограниченных по частоте чистых наблюдений, получение свежего кадра MediaProjection, наблюдение за распознанными текстовыми областями и возврат ticket после временной ошибки наблюдения. Скрытие сохраняет последние желаемые состояния окон, распространяется на новые streaming roots и не восстанавливает удалённые окна. Активные жесты, выделение, меню и обучение пропускают наблюдение. Перемещение героя не обнуляет перевод; смена влияющих на результат настроек удаляет устаревшее содержимое.

Партия `f50e22e` в 1.9.0 исправляла только OCR поверх `c3b6731`: английское уточнение разрывало связный абзац на `Gentle winds carry the autumn` / `leaves.`. Реальная геометрия — высоты **61/46 px, промежуток 24 px**. Допуск расширен только для короткого завершённого строчного Latin-хвоста меньшей ширины, с сохранением проверок parent/column/alignment/script. Добавлены собственный PNG 1080×2400 и Hilt-bound Auto OCR integration case. SHA256 изображения: `b8af7ceb62191bbcad1a6f1f11f5be5f366d9af2b551da354aa1c09fa73fafba`.

Темы, шрифтовые кнопки, preview и доступность при 200% сохраняют исправления 1.8.9. Их отдельные UI-проверки 1.8.9 остаются историческими, а не новым визуальным прогоном каждого экрана 1.9.0.

## Исторические реально выполненные проверки 1.9.0

| Проверка | Результат и границы доказательства |
|---|---|
| Общая партия `f50e22e`: Debug, Validation R8, DebugAndroidTest, unit, lint | **PASS, 17 мин 17 с**. 1806 JVM / 476 XML suites, failures/errors/skips = 0. Lint: 0 errors / 977 warnings / 42 info. |
| Android instrumentation на `f50e22e` | **89 уникальных PASS, 0 failures/errors/skips**: основной запуск20,21с дал87PASS+2assumption skips; отдельный запуск только этих двух с `downloadModels=true` дал2PASS за135,025с. Включён реальный Auto OCR двух полных абзацев. Это не все пользовательские сценарии телефона. |
| R8 1.9.0, снимки 05/06 | **PASS:** page0 → page1 под открытым переводом, без ручного dismiss; запрос переводчику содержит целое `Gentle winds carry the autumn leaves.`. |
| R8 1.9.0, поворот | Снимки 07/08 через 12 с в landscape/portrait ещё показывали обработку. Поздний portrait 09 содержит полный перевод: **восстановление portrait PASS; готовый landscape-перевод не подтверждён**. |
| Две отдельные замены по одному слову под наложением | **PASS на 1.9.0 (`f50e22e`) через Shizuku:** forests и purple, без закрытия перевода. Исторический System-прогон c3b сохранён отдельно. |
| 13 runtime capture cases | **Исторический PASS**, test-only source `e4b85f66126013bae0fba0ecab0098eadc48c55d`. В 1.9.0 не повторялись: тогда соответствующий production-код после PASS не менялся. Для CDA позже выполнены 16 runtime PASS; финальный 6976c086268e8643e4f42f991f347ffd9487b2f1 требует собственного итога batch. |
| Неподвижная страница Debug | **Исторический `c3b6731`, 10 мин 4 с:** 376 наблюдений, 368 с textSimilarity 1.000, один первый OCR start. Это не чередование страниц, не измерение батареи/нагрева телефона и не новый soak `f50e22e`. |
| Остановка | По окончании прогона 1.9.0 System и Shizuku остановлены, обоих CaptureService нет, projectionnull. System выбран обратно, Main6/6/en→ru/MLKit сохранён; эмулятор выключен. |
| Shizuku 1.9.0 | **PASS:** настоящий server PID6096/UID2000shell, без root, MediaProjection и Accessibility. Page0→1 под наложением и обе замены одного слова отображены правильно. |

В первом 13-case runtime запуске было 8 FAIL из-за harness: имён потоков с ` @coroutine#N` и копирования стандартного исключения coroutine debug recovery. Исправлен только harness; повтор дал PASS за 1 мин 22 с. Провал сохранён, он не заменён успешным отчётом. Пять отдельных Android Bitmap cases также имели PASS; Android-прогон 1.9.0 указан отдельной строкой выше.

Предупреждение lint `ViewConstructor` относится к программно создаваемому `SourceObservationRoot`, XML-инфляция не используется. Пересборка ради косметического предупреждения не требуется.

## Исторические отчёты и доказательства 1.9.0

- Финальные данные 1.9.0: [metadata/report](qa/archive-restoration/covered-source190/final/report.json) и [ручные результаты](qa/archive-restoration/covered-source190/final/device/manual-results.json) содержат106файлов evidence и проверенный хеш установленногоR8; installed APK побайтово совпал с DesktopQA. Пути evidence внутри manual-results отсчитываются от каталогаdevice.
- Рабочие evidence 1.9.0: `.tmp/soak190/build-checks` и `.tmp/soak190/final-checks` — исторические `f50e22e` build receipts, Android результаты, XML/PNG/logs. Снимки 05/06 и 07/08/09 относятся к R8 1.9.0.
- Предыдущая партия перенесена в `.tmp/soak190/candidate-c3b-build-checks` и `.tmp/soak190/candidate-c3b-device-checks`; не смешивать её результаты с 1.9.0 или 1.9.1. Старый не прошедший OCR кандидат: `docs/qa/archive-restoration/covered-source190/candidate-c3b/result.json`.
- Исходный FAIL 1.8.9: `docs/qa/archive-restoration/covered-source190/baseline189/result.json`. Первичные снимки `06-page0-result-late`, `07-page1-covered-after20s`, `08-dismiss-reveals-page1`, `09-page1-after-dismiss` и соответствующие PNG/logs относятся к baseline. Независимый fixture APK: SHA256 `cda7b3c64b01dbc1fec8919aad10078fec6500d381f94f974cd06d1751effe17`.
- Прерванная первая сборка: `.tmp/soak190/attempt1-interrupted-review`; неудачный runtime harness: `.tmp/soak190/attempt2-runtime-harness`. Успешная компиляция прерванной сборки не считается unit/lint/device PASS.
- [Сравнение возможностей и остаток](ANDROID_ARCHIVE_RESTORATION.ru.md), [последний выданный 1.8.9](qa/archive-restoration/usability189/report.json), [функциональный срез 1.8.8](qa/archive-restoration/gesture188/report.json). Исторические отчёты, резервные Git-ветки и ранее выданные APK сохраняются; историю не переписывать.

## Исторический инцидент Debug preferences: восстановление частичное

Во время диагностики `c3b6731` root повредил Debug DataStore protobuf прямой записью через stdin `adb shell`: Windows Ctrl-Z усёк бинарный файл, появился `CorruptionException`. Пользователь уведомлён. Опасный `debug-region-config.py` **DISABLED**.

Debug приведён в работоспособное состояние из **двух полных исходных entries, восьми известных non-secret fields и безопасных QA defaults**. Известные исходные `render=FLOATING_WINDOW`, `merge=true` и ROI entry возвращены, известная metadata геометрии — 1080×2400. **Остальные утраченные исходные Debug-настройки не восстановлены и не считаются восстановленными.** Состояние «все прежние настройки сохранены» заявлять нельзя.

QA и production не изменены этим восстановлением. QA preferences SHA256 до/после совпал: `8bee9fbaa7fcb79708531cb83e6d53eb22166048fc1aa0e9a7331d9c7bfc50a1`. Восстановление не меняло Room, историю и модели.

Точный receipt: `.tmp/soak190/candidate-c3b-device-checks/debug-config-recovery.json`. `PRIVATE*.pb`, `damaged*.pb` и другие приватные бинарные копии **не публиковать и не коммитить**. Дальнейшую диагностику настроек выполнять через штатный UI; прямую диагностическую подмену preferences не повторять.

## APK и подпись

Это checkpoint APK для review/продолжения, **не production Release и не полная готовность**. Точные метаданные: `.tmp/recovery191/device-checks/apk-delivery.json` и [финальный отчёт](qa/archive-restoration/recovery191/report.json).

| Выданный Desktop APK1.9.1 | Package | Байты | SHA256 |
|---|---|---:|---|
| [Full](C:/Users/Home-PC/Desktop/ClicknTranslate-Android-1.9.1-Full.apk) | `dev.clickn.translate.debug` | 93 942 902 | `7951efd3219cf53ee991ec4464af2b07fc4f28b90729effd222926404a68122c` |
| [QA](C:/Users/Home-PC/Desktop/ClicknTranslate-Android-1.9.1-QA.apk) | `dev.clickn.translate.validation` | 64 659 672 | `912d65ec8deef916d2567ca2a6f20596860f5a6c3803c2dde70fe284e62b9e90` |

Оба APK — version1.9.1/code29, существующий debug certificate `4a627d18c2e9597f691314d7d01ee1699b9e1f74189c13d0aa213b0c53eba5ad`. Zipalign16KB — статический PASS; 19 ARM64 ELF побайтово совпадают с соответствующим вариантом1.8.9. Это не16KB runtime телефона. Production ID `dev.clickn.translate` сохранён; Debug/QA не обновляют production.

Исторические выдачи сохранены; их файлы и SHA256 не являются текущим checkpoint:

| Desktop APK1.9.0 | Размер, SHA256 |
|---|---|
| `ClicknTranslate-Android-1.9.0-Full.apk` |91 874 082B;`e4a85dd6c35e59795d2f24eb9a78fb6b7852b60eb1a91f1d9a67746515c2fe5e`|
| `ClicknTranslate-Android-1.9.0-QA.apk` |64 630 292B;`b5e23e1fd602cf9d5935451908d82c4bc319b8be29a0d1554372dd267c4705a6`|

Full также сохранён в `artifacts/android/ClicknTranslate-1.9.0-full-debug-arm64.apk`. Подписи проверены, zipalign16KBPASS; все19ARM64 ELF совпали с соответствующим вариантом1.8.9. Это статические проверки, не16KB runtime телефона.

Используется существующий debug certificate SHA256 `4a627d18c2e9597f691314d7d01ee1699b9e1f74189c13d0aa213b0c53eba5ad`. Сохранены production applicationId `dev.clickn.translate` и versionCode текущей партии 29; отдельные тестовые packages не обновляют production. Возможность обновления production определяется прежним private signing key, а не публичным сертификатом.

Ожидаемый production certificate SHA256: `1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85`. На Desktop предоставлены публичные `release-certificate.pem`, `release-identity.json`, `README.txt`; они не являются private signing key. Новый ключ не создавать, production Release не собирать и не публиковать без нового явного запроса.

Предыдущая выдача 1.8.9 остаётся исторической:

| Desktop APK | Размер, SHA256 |
|---|---|
| `ClicknTranslate-Android-1.8.9-Full.apk` | 93 233 411 B; `5c977436580c9cf56caad7768cd5487b5575fade15da6b189f86aab2738ee365` |
| `ClicknTranslate-Android-1.8.9-QA.apk` | 64 614 860 B; `f9e4128f26cdd12569b021ce02fb207bd023def84807edee11a1697e4d694b35` |

## Что действительно осталось

Основные пользовательские модули по журналу реализованы. Пункты1–3 ниже — оставшееся покрытие совместимости и поведения; пункты4–5 — известные границы хранения. Они не означают отсутствия экранного, текстового или фотоперевода. Production-подпись не блокирует текущую Debug/QA-сборку.

1. Physical ARM64: Android8, Hy-MT2/Sakura decode, GPU/Vulkan и16KB runtime. API26 ARM64 AVD на Windows отказал; API36 x86_64 с ARM bridge не заменяет телефон и ранее падал на NEON при LLM decode.
2. Звук TTS, длительная работа/батарея/нагрев телефона; полный OCR/RTL/колонки/смешанные языки corpus, OEM/Accessibility/клавиатуры, paid/custom API и оставшиеся permission/rotation сочетания. Контролируемый Shizuku landscape PASS не закрывает все способы захвата.
3. Ручной partial-unit recovery, image-MT и остальные сбои/отмены провайдеров: HTTP503→оба markers и late-response rejection уже PASS в описанном scope, но не доказывают все варианты. Полный editor/provider corpus и автоматические наборы после callback-исправления не повторялись.
4. Cross-store transaction/snapshot isolation отсутствует; same-value/ABA edits и glossary admission/read→write race остаются. Editor same-field edits побеждают latest; агрегат считается одним полем. Simulated fatal tests не равны смерти процесса или отключению питания.
5. SAF unknown URI / неопределённый исход после смерти процесса остаётся. Gallery review сохраняет исход для явной проверки; auto-delete не объявляется решением. Общие legacy cache PNG не удалять без доказанного владения. Частичная утрата Debug-настроек не считается полностью восстановленной.
6. Production upgrade — только прежним private key и по отдельному запросу. Production Release, новый ключ, push и публикацию не выполнять; `main` и Desktop-исходники не трогать. Причина старого Google FAIL1.8.5 неизвестна.

## Среда и ограничения продолжения

- Canonical: `C:\Users\Home-PC\.codex\worktrees\android-rewrite\clickntranslate`.
- Отдельный build checkout: `C:\Users\Home-PC\.codex\worktrees\android-restored-baseline\clickntranslate`; source текущей партии — указанный в начале `6976c086268e8643e4f42f991f347ffd9487b2f1`, старый pin 68599 не считать текущей сборкой.
- SDK: `C:\Users\Home-PC\Desktop\clickntranslate\.tmp\android-sdk`; JDK17 Adoptium; NDK `28.2.13676358`; CMake `3.22.1`; native staging `C:/ct-native/archive054-vulkan`.
- Owned AVD `ClicknRewrite36` / `emulator-5584` после follow-up выключен через `adb emu kill`; подключённых устройств и процессов qemu/Java нет, fixture18791 остановлен; пользователи0/10/11 сохранены. Использовались2guest CPU, hostaffinity15/четыре ядра, BelowNormal. В историческом прогоне1.9.0 и текущем follow-up adbd и Shizuku server работалиUID2000shell, безroot.
- Одновременно только один тяжёлый job, JavaCPU4/affinity15/BelowNormal. Пока работает эмулятор, тяжёлый Gradle не запускать. Общая сборка checkpoint завершена; параллельную сборку не запускать и код без причины не менять. Прямую диагностическую подмену preferences не повторять.
