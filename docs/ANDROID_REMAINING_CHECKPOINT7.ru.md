# Android: остаток после контрольной точки C23

25 октября 2026. Это журнал незавершённой работы, **не заявление о полном соответствии Android1.8.2 или готовности к публикации**. База: [сравнение возможностей](REWRITE_STATUS.ru.md), [хронология Wave7](qa/wave7/README.md) и отдельные результаты C23 ниже. Результаты прежних APK не переносятся автоматически на C23.

## Что действительно проверено в C23

Исходники: commit `6a31e98a4890ce94320ba33d807b75626c1ea781`, дерево приложения `c3d61ef35f4177c9508231b91dcc1cf1338d428b`; `.7`/code14. [Debug source/APK identity](qa/wave7/candidate23/source.json), [ARM64 identity](qa/wave7/candidate23-build/provenance/arm64-source.json).

| Проверка | Результат и граница |
| --- | --- |
| Полный API36 | 245 случаев: **240 PASS, 5 SKIP, 0 FAIL**, 1236.115с. [Raw log](qa/wave7/candidate23/raw/wave7-c23-full-5584.txt). Эмулятор, не физический ARM64. |
| Полный API26 | 245 случаев: **239 PASS, 5 SKIP, 1 FAIL**, 813.701с. [Raw log](qa/wave7/candidate23/raw/wave7-c23-full-5582.txt). FAIL на initial real-capture перед native Explain, а не внутри HTTP-пояснения. |
| Отдельный повтор упавшего Stop-сценария API26 | 1 PASS, 20.045с. [Raw log](qa/wave7/candidate23/raw/wave7-c23-isolated-stop-5582.txt). Не заменяет неуспешный полный прогон и не закрывает P1. |
| Automatic soak API26 | 1 PASS, 607.646с. [Raw log](qa/wave7/candidate23/raw/wave7-c23-soak-5588.txt). Подтверждает этот десятиминутный сценарий, не многочасовую работу, батарею или OEM Doze. |
| JVM debug / QA / release | В каждом варианте по **583 PASS, 0 FAIL, 0 ERROR, 0 SKIP**; по99 XML suites. [Debug XML](qa/wave7/candidate23-build/unit-debug), [QA XML](qa/wave7/candidate23-build/unit-qa), [release XML](qa/wave7/candidate23-build/unit-release). Это **1749 выполнений одних583 тестов**. |
| Lint и ARM64 R8 | Сборки успешны; lint0errors, debug58warnings/1hint, release51warnings/1hint. QA/release ARM64 CRC/native16KiB/debug-fixture/проверенный namespace audit PASS. [QA audit](qa/wave7/candidate23-build/apk-audits/qa.json), [release audit](qa/wave7/candidate23-build/apk-audits/release.json). Сборка и статический audit не доказывают запуск на физическом ARM64. |

Пять SKIP полного набора: отдельный soak; два случая с заранее отсутствующей `rus` OCR-моделью; заранее отключённые системные уведомления; ARM64-on-x86 native-bridge условие. SKIP не считается PASS; standalone результаты и версии их APK учитываются отдельно.

## P1 — сначала устойчивость существующего захвата

1. **Редкая самоочистка automatic/CARD и BLOCKS остаётся открытой.** В C23 API26 `ScreenExplanationIntegrationTest.stopRevokesTheNativeTransferredSourceAndRejectsItsRealLateHttpResponse` не прошёл ещё initial capture: карточка оказалась скрыта. [Исходные trace/XML/PNG](qa/wave7/candidate23/failure-initial-ocr-api26) сохранены. Trace содержит две успешные manual verification, публикацию, затем automatic change на50 ячейках `bounds=1,7..13,11`, смену fingerprint и возврат исходного fingerprint. Геометрия согласуется с окрестностью floating button; цвета отклонённого кадра не измерены, причинность не доказана.
2. **Исторический BLOCKS P1 тоже не закрыт.** Ранний watch скрывал блоки до All text; успешные изолированные/полные повторы и ограниченные численные probes не доказывают исправление. [Исходное расследование](qa/wave5/regressions/block-feedback-investigation.json). Не маскировать собственную область, не ослаблять full-frame freshness и assertions ради зелёного набора.
3. Следующий шаг — один различающий численный repro с сохранением исходного FAIL, затем минимальное исправление доказанной причины и повтор релевантных capture/native/rotation/revoke тестов, полных API26/API36 и soak. Не объявлять исправление по одному PASS. Разделять это расследование и уже исправленные конкретные гонки native dispatch/screenshot suppression.

## P2 — функциональное соответствие ещё не достигнуто

| Область | Реализовано | Остаток / отличие |
| --- | --- | --- |
| MT-провайдеры | NiuTrans fixed v1, Youdao text v3, Baidu classic, Tencent MPS и другие описанные новые адаптеры; локальные TLS/signing/cancel/schema проверки | Volcengine text в приложение не интегрирован; Niu Pro v2 отдельно не подключён. Живые аккаунты, активация, квоты, enterprise/domain права и качество платных провайдеров не проверены. Tencent MPS не является автоматическим переносом прежнего TMT; UI временных credentials отсутствует. |
| OCR и фото API | MLKit/Tesseract, Vision и документированный пользовательский HTTP OCR | Отдельные Baidu/Paddle/Tencent/Youdao OCR и прежний Youdao picture endpoint не реализованы. Text-after-local-OCR не доказывает их протокольную эквивалентность. Полный корпус смешанных письменностей/колонок/RTL ещё нужен. |
| Речь | SYSTEM/OpenAI/ElevenLabs/MiniMax и voice studio с контрактными проверками | Generic HTTP, Volcengine и MiMo TTS не интегрированы. Платный synthesis/clone/design/delete, права аккаунта и слышимое качество не проверены. |
| Форматы и библиотеки | TSV/JSON и документированный SQLite schema1; большой ECDICT import/lookup проверялся | Иные raw SQLite/binary/StarDict не поддержаны. Нужны большой export/reimport и сохранение metadata. Японский SFX sample из16 терминов не равен полному прежнему каталогу. |
| Графика и системные возможности | Новый CPU GGUF runtime; официальные MediaProjection/opt-in Accessibility; фото-rendering | Vulkan/GPU acceleration, privileged capture и neural inpainting произвольного цветного фона отсутствуют. Четыре режима темы/пять акцентов заменяют прежний семитемный каталог. Эти отличия не считать автоматически согласованным сокращением scope. |

Каталог117 восстанавливает старые112 choices и все59 MLKit, но поддержка провайдера проверяется отдельно по роли. Он не означает450/454 Niu UI или201 Baidu UI; региональные варианты нельзя молча обрезать. Полный шестиязычный string/layout/error audit, крупный шрифт и длинные подписи ещё требуют проверки.

## P3 — оставшиеся проверки и сохранность данных

- На итоговом optimized APK проверить photo/PNG/SAF/PROCESS_TEXT/исходящий Share с внешним получателем, Resume/Retry после перезапуска, profile/model/settings UI и полный визуальный корпус шести локалей. Batch20 fixtures подтверждают очередь/файлы/lifecycle, не качество20 платных переводов.
- На физических ARM64/OEM-телефонах: API26+, GGUF/native inference, длительный auto/lock/Doze, память/нагрев/батарея, защищённые окна, revoke во время запроса, совместные rotation/revocation, process death/reboot. Эмулятор x86 и ARM64 через bridge этого не заменяют.
- Actual production upgrade1.8.2→новая версия с копией настоящего профиля и прежним signing key не выполнен. Проверить Keystore alias, историю, профили, библиотеки, настройки, launcher aliases и границы переноса credentials. `applicationId`/возрастающий `versionCode`, синтетические миграции и QA-пакет — необходимые отдельные проверки, не доказательство upgrade.
- QA использует существующий тестовый сертификат и отдельный `.rewrite` package; unsigned production APK не обновляет установленную1.8.2. Новый production key не создавать. Публикация/тег/удаление релизов не разрешены текущим журналом и не выполнялись.

## Отложенные черновики

`.tmp/volc-text-adapter-draft` и его `neutral-json` — независимые неинтегрированные Kotlin/JSON drafts с написанными, но не выполненными тестами. Отложенные TTS drafts также не считаются функциями приложения. Они не входят в583 C23 JVM-теста и проверенные APK; их интеграция требует отдельного review/сборки/регрессий. Сейчас приоритет — P1 и проверяемая передача контрольного APK, без разворачивания новых функций.
