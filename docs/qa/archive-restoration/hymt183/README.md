# Android 1.8.3/code37 — кандидат с исправленным шаблоном GGUF

**Кандидат, не полная приёмка.** Основной APK на рабочем столе остаётся code36. Локальный [APK code37](../../../../artifacts/android/1.8.3-code37/ClicknTranslate-Android-1.8.3-code37-candidate.apk) собран из `57704198951c9166b5f64bc1c8b022cba540a38e`, пакет `dev.clickn.translate`, версия1.8.3. Размер **64 396 846 байт**, SHA-256 **`6da6dd272b1f1e1f8ac1a5a7b3c7327600e692f0396dcdf3131877316ae212eb`**. APK — локальный генерируемый артефакт, не файл Git и не опубликованный релиз.

Использован прежний сертификат **`1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85`**. Подписи v2/v3 и статическое ZIP-выравнивание16KB проверены. Новый ключ не создавался, публикации и push отсутствуют. [Подпись](sign-checks/signature.txt), [метаданные APK](sign-checks/badging.txt), [сохранённая квитанция кандидата](sign-checks/candidate.json).

Сборка и прогоны выполнены **10 ноября UTC /11 ноября по Москве**; этот отчёт оформлен20ноября по сохранённым исходным результатам. Повторных сборок и runtime-запусков при оформлении отчёта нет. Только Android; авторские архивные UI и модули используются с разрешения владельца, clean-room переписывание не заявляется.

## Что изменено

Legacy-определитель llama.cpp принимал фактический шаблон Hy-MT2 за Hunyuan-VL: служебный маркер пользователя шёл после содержимого, префикс генерации ответа отсутствовал. Теперь одиночные запросы, независимые batch-запросы и расчёт количества токенов используют Jinja-шаблон из GGUF. CMake применяет правку к upstream binding с exact-match guard; submodule не менялся. Новых runtime-зависимостей нет.

На тех же pinned весах и runtime проведён host replay: **8 Hy-MT2 случаев**, seed42,4CPU-потока; отдельно **2 форматирования Sakura** с её системным запросом. Jinja выдаёт ожидаемый порядок маркеров Hy-MT2. Полные system/user-строки Sakura в проверенном случае совпадают побайтно со старым форматированием. Это **host-проверка**, не Android/ARM64-generation PASS. [Входы, выходы, фактические prompts](hymt-results.jsonl), [Sakura](sakura-results.jsonl), [метаданные и SHA моделей](model-metadata.json), [сводка](host-summary.json), [квитанция процесса](probe-receipt.json), [исходник диагностического инструмента](probe.cpp).

Host-инструмент собран с четвёртой попытки: в первых трёх исправлялись include-путь JSON и Windows10 defines для common/httplib. Их exit1 сохранены в build-receipt/build2-receipt/build3-receipt; успешная четвёртая попытка — в build4-receipt. Это отдельные диагностические сборки, не отрицание и не дополнительные PASS итогового Android-прогона.

## Фактические результаты

| Проверка | Результат и предел |
| --- | --- |
| Debug, DebugAndroidTest, полный JVM-набор, lintDebug, Release | **PASS,38мин40с** одним Gradle-прогоном. **1889 тестов /491 набор**,0 failures/errors/skips; lint0 ошибок/975 warnings/42 info. Обе нативные конфигурации пересобраны. [Gradle](android-build/build.txt), [receipt](android-build/build-receipt.json), [индекс JVM](android-build/unit-summary.json). |
| Первый opt-in Android-прогон | **FAIL до загрузки модели:** неверная SELinux-метка подготовленного contract.json дала EACCES. Исправлен только собственный тестовый файл; APK/исходники/системная SELinux-политика не менялись. [Первый runner](android-device/native-android.txt), [исправление и проверка доступа от UID приложения](android-device-retry/fixture-access-repair.json). |
| Повтор opt-in Android-прогона, API36 x86_64 с ARM native bridge | **FAIL: процесс завершился SIGILL.** Модель загрузилась, в логе виден корректный Jinja user prompt, затем сбой при вычислении. Independent B3 не завершён. Код завершения adb0 не означает успешный тест. [Runner](android-device-retry/native-android.txt), [receipt pass=false](android-device-retry/android-receipt.json), [выдержка native-лога](android-device-retry/native-excerpt.txt), [заголовок сбоя](android-device-retry/crash-header-excerpt.txt). |
| Подписанный Release: чистый профиль, onboarding, Google Text | **PASS одного сценария:** English →Light →экран выбора героя →Auto/Russian; собственная `Silver trains travel beyond the mountain.` → `Серебряные поезда едут за гору.` без аккаунта. [Выбор героя](ui/03-companion.png), [перевод](ui/05-google-result.png), [UI-отчёт](ui-report.json). Это независимый UI scope, не замена failed native-теста. |
| История после настоящего force-stop/cold launch | **PASS одной собственной текстовой записи:** та же фраза и результат остались в истории. [Холодный запуск](android-ui/cold-restart.txt), [экран истории](ui/06-cold-history.png). Не полная проверка миграции/личной истории телефона. |

Стек SIGILL содержит `Guest architecture: arm64` и `/memfd:exec`; в памяти отмечен BERBERIS, используется `libndk_translation.so`. Выбран уже базовый CPU backend ARMv8.0_1. Это указывает на участие слоя трансляции, но **причина сбоя не установлена и физический ARM64 PASS из этого не следует**. В native-логе также видны sampler0.30/0.95/40/1.00 вместо запрошенных тестом значений; гипотеза о передаче environment через bridge отдельно не доказана. Для завершения приёмки требуется действительный ARM64 runtime.

## Открытая ошибка качества

Исправленный шаблон **не устраняет** ошибку «две книги» на наблюдавшемся OCR-варианте `كتابَا`. В контролируемом host replay этот вариант даёт множественное число у обоих форматтеров; правильный tanwin `كتابًا` и невокализованный `كتابا` дают единственное число при том же seed. Это ограниченный сравнительный опыт, не доказательство общей точности и не реконструкция неизвестного historical prompt/context.

Арабский словарь содержит обе отметки U+064B/U+064E. Прежний `PaddleArabicParagraphIntegrationTest` при сравнении удаляет combining marks: его PASS подтверждает нормализованные буквы/абзацы/Latin OCR, **не точные диакритики**. Подмена слова, безусловное удаление огласовок и произвольная смена sampling не применялись.

Физический телефон в последнем ADB-наблюдении20ноября отсутствует. Последняя подтверждённая физическая установка — [code33 поверх1.8.2/code7](../update183/report.json). Code37 не установлен на телефон и не проверен на нём. При пользовательской паузе эмулятор выключен; собственный профиль12 и входная модель оставлены для продолжения, прежние0/10/11 сохранены. Профиль не объявляется удалённым. Сырые приватные БД, ключи, полные memory dumps и бинарные модели в отчёт не включены.

Остаток: завершить физическую приёмку native-пути, Arabic OCR/диакритики и TTS/Accessibility; проверить OnePlus/Shizuku, Android8/runtime16KB/GPU и нужные real/paid API в доступном окружении. Полный объём не объявляется завершённым. [Машинный отчёт](report.json), [сравнительная таблица](../../../ANDROID_FEATURE_STATUS_183.ru.md).
