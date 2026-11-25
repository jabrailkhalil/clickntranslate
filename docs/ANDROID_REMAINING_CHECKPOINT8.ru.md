# Android: остаток для кандидата checkpoint8

25 октября 2026. Это журнал незавершённой работы после [checkpoint7](ANDROID_REMAINING_CHECKPOINT7.ru.md), **не заявление о полном parity с Android1.8.2 или готовности к публикации**. Предыдущие FAIL и APK7 сохраняются; результаты разных APK не объединяются в один PASS.

Зафиксированный кандидат C32: `1.9.0-rewrite.8` / code 15, commit `e40f1046883c7732ca735b78b7dfed71c70e35ee`, app tree `425f357cd441b754deeb19f541010020491375d4`. Точные пары APK: [debug source](qa/wave7/candidate32/provenance/debug-source.json) и [ARM64 source](qa/wave7/candidate32/provenance/arm64-source.json). [QA APK8 подготовлен](../artifacts/android/README.md) и скопирован на рабочий стол. Это промежуточный checkpoint без публикации. C33/C34 меняют только тестовые файлы; targeted C34 прошёл, полный повтор C34 ещё не выполнен.

## Подтверждённые изменения после APK7

| Изменение | Доказательство и граница |
| --- | --- |
| Floating hold во время snapshot suppression | C25 API36: 2 PASS / 1 FAIL из3, 49.250с; настоящий hold не открыл меню. API26 baseline3 PASS. C26: те же2 floating cases PASS на API26/36 за6.988/15.924с. Snapshot-only alpha0 сохраняет native window; настоящий Hide/Stop сохраняет teardown. [Исходный FAIL, diff и proof](qa/wave7/candidate25-26/README.md). Это конкретный input-fix, не доказательство причины старого pixel-feedback P1. |
| Освобождение Bitmap при исключении restore | C30 main + новый C31 ownership fixture: **1 FAIL**, 0.450с — raw Bitmap не recycled. C31: тот же fixture PASS на обеих ОС внутри targeted групп ниже. Проверяются настоящий Bitmap, exception identity и hide `[true,false]`; fake FrameSource не доказывает MP/OCR. Raw: `.tmp/wave7-c30-main-c31-test-ownership-baseline-5584.txt`, `.tmp/wave7-c31-capture-targeted-558{2,4}.txt`. |
| Явный выбор Include system bars | C29 добавляет `includeSystemBars=false`, строгий schema1 JSON/public/internal/profile payload и локализованный UI. C30 actual API36 timer/OCR case: **1 PASS**, 39.692с; C31 повторяет его успешно. Наблюдались реальные timer transitions, повторные producer frames, сохранённый результат и новый результат после изменения настоящего текста. Это отдельный контракт content-capture, не общее устранение P1. |
| JVM | C29 и C31: в каждом сохранённом debug наборе **598 PASS, 0 FAIL/ERROR/SKIP**, 101 XML suites. Источники: `.tmp/wave7-candidate29/unit-debug`, `.tmp/wave7-candidate31/unit-debug`. Это одни598 тестов в разных checkpoint, не1196 уникальных тестов. |
| C31 device targeted | API26: **16 PASS**, 199.111с; API36: **17 PASS**, 315.757с; 0 FAIL/SKIP. Это targeted capture/ownership/system-bar/native группы, **не полный device suite**. |

Сохранённые C30/C31 timer proofs: `.tmp/wave7-c30-proof-5584/system-bars-capture-api36.txt`, `.tmp/wave7-c31-proof-5584/system-bars-capture-api36.txt`. Реальный API36 crop: raw864×1920 → rect`0,103,864,1869`, physical1080×2400; при изменении настоящего абзаца появляется новый принятый документ. [C27/C28 probe](qa/wave7/candidate27-28/README.md) отдельно измеряет visible status128/nav63 и immersive zero; cutout128 сам по себе не вырезается.

## Контракт области и границы поддержки

- Без пользовательской ROI `includeSystemBars=false` исключает только **видимые status/navigation bars**, где доступны точные API30+ metrics. Insets читаются внутри hidden interval до/после кадра. IME, stable/cutout margins и произвольная часть app content этим правилом не вырезаются.
- `includeSystemBars=true` сохраняет полный physical image. **Явная valid ROI всегда имеет приоритет**, включая full-physical `0,0..1,1`; сохраняются точные прежние integer bounds и mapping OCR blocks обратно в physical coordinates. Full-screen mode остаётся доступен.
- На API26–29 и при недоступных/неверных metrics действует full-physical fallback. UI до Android11 показывает фактическое включение bars и disabled toggle с пояснением; сохранённое значение не переписывается. HELP говорит «где поддерживается». Profile callback проверяет актуальный credential scope.
- Старые full-physical P1/native fixtures явно выбирают `includeSystemBars=true`. Новый default не используется для ослабления их freshness, изменения assertions или сокрытия старого FAIL.

## C32 — фактические результаты

**Оба полных device run завершились с FAIL.** Успешные build, JVM, lint и отдельный soak не заменяют эти результаты. [Архив C32](qa/wave7/candidate32/README.md) и [machine-readable сводка](qa/wave7/candidate32/validation.json) сохраняют исходные логи, 303 unit XML и failure TXT/XML/PNG.

| Проверка | Статус |
| --- | --- |
| FULL API26 / 5582 | **242 PASS / 5 SKIP / 1 FAIL из 248**, 786.883 с. [Raw](qa/wave7/candidate32/runs/wave7-c32-full-5582.txt). |
| FULL API36 / 5584 | **244 PASS / 5 SKIP / 1 FAIL из 250**, 1370.37 с. [Raw](qa/wave7/candidate32/runs/wave7-c32-full-5584.txt); исходный footer: `Time: 1,370.37`. |
| Десятиминутный soak API26 / 5588 | **1 PASS**, runner 606.309 с; активный интервал 600000 мс, 56 циклов, max PSS **166483 KiB**. Stop освободил worker и overlay windows. [Raw](qa/wave7/candidate32/runs/wave7-c32-soak-5588.txt), [сводка](qa/wave7/candidate32/soak-summary.json). Только строка `15:55:58.878`, PID 24936 / TID 24954 относится к C32; старая строка C23 `13:46:24.888` исключена. Это не idle CPU, температура или физический ARM. |
| Debug build / JVM / lint | Сборка main + test APK — **SUCCESS, 13 с**; verification — **SUCCESS, 47 с**. JVM **598 PASS**, 101 XML, 0 FAIL/ERROR/SKIP. Lint: **0 ошибок, 59 warnings, 1 hint**. [Логи](qa/wave7/candidate32/logs/debug-unit-lint.txt), [XML summary](qa/wave7/candidate32/unit-debug-summary.json). |
| ARM64 QA / release build и verification | Сборка — **SUCCESS, 118 с**, verification — **SUCCESS, 59 с**. QA и release: по **598 PASS**, 101 XML, 0 FAIL/ERROR/SKIP. Вместе с debug это **1794 выполнения 598 тестов**, не 1794 уникальных теста. Release lint: **0 ошибок, 51 warning, 1 hint**. [Логи](qa/wave7/candidate32/logs/qa-release-unit-lint.txt). |
| APK packaging | SHA и ZIP CRC всех четырёх APK проверены; ELF и native ZIP payloads выровнены на **16 KiB**. QA: v2 signature, прежний Android Debug certificate `4a627d18…`; `zipalign -c -P 16 -v 4` успешен. Release остаётся **unsigned**. ARM audit: 0 unobfuscated legacy namespace descriptors, без debug fixture. [Audit и границы](qa/wave7/candidate32/README.md). Это не ARM device execution или production upgrade proof. |
| Source audit | **469 файлов, 3 backup refs, 0 byte-identical matches и 0 ошибок**. Сохранён исходный audit и независимая проверка pinned Git blobs без чтения рабочих C33 app-файлов. [Отчёт](qa/wave7/candidate32/source-audit/pinned-git-recheck.json). |

API26: `AutomaticDictionaryTapIntegrationTest` получил `StaleObjectException` в `getText` **после реального tap**, при асинхронной замене loading на body. Failure XML уже содержит словарный body с owned marker. Это не подтверждённый отказ локального поиска, но метод остался **FAIL**: последующие Close/Resume assertions не были выполнены. [Исходные артефакты и разбор](qa/wave7/candidate32/failure-analysis.json).

API36: `ScreenBlocksIntegrationTest` упал на ожидании второй карточки. Trace фиксирует второй `manual-published`, затем через 175 мс — изменение 3 ячеек `27,1..29,1` в области настоящего OS sharing timer. Этот сценарий явно включает `includeSystemBars=true`; включённое изменение экрана инвалидирует результат. Отсутствие карточки при более позднем lookup не доказывает ошибку preferred renderer. Исходный **FAIL сохранён**, причина старого own-overlay P1 этим не установлена.

C32 ARM64 QA: **50 224 091 байт**, SHA-256 `1dc7af3ffb788deb4e6dcc3f40adbc888e8a9d84928f9194bb85f63919b0c11b`. Unsigned release: **50 211 795 байт**, SHA-256 `197903819f692cb7abc94eb132545bdc2d5dd7a520af818bd62ef68ef8180237`. Размеры совпадают с C23, но SHA, source и версия новые; прежние APK не переименованы в C32. Файлы скопированы в `artifacts/android` и QA — на рабочий стол с проверкой SHA-256; [идентификаторы](../artifacts/android/build-identity.8.json).

C33/C34 исправляют тестовые наблюдения и подготовку полноэкранного сценария. Исходный C32 остаётся FAIL; новые targeted результаты учитываются отдельно. Полный повтор с финальными fixtures пока не выполнен.

## C34 — выбранные повторные проверки прошли

[Архив C34](qa/wave7/candidate34/README.md): API26 — **2 PASS**, 43.258 с; API36 — **5 PASS**, 128.62 с; 0 FAIL / SKIP. Lint: 0 ошибок, 59 warnings, 1 hint. Исходники тестов `9bde1302c55f9069bd5a26ccfde1df4af1f475b1`; main APK побайтно совпадает с C32. Полный C34 не запускался; новые unit executions не заявляются.

[C33 FAIL](qa/wave7/candidate33/README.md) сохранены. Новый fullscreen fixture закрывает настоящую системную подсказку одним нажатием и создаёт новую test Activity для каждого режима. Full-physical test отдельно наблюдает малое изменение таймера, не требуя от него превышать production-порог; реальное изменение абзаца очищает результат без повторного OCR. Эти проверки не закрывают исторический P1.

Ручной QA APK8 на API36 через ARM native bridge: checksum установленного пакета совпал; проверены текстовый OFFLINE EN→RU, копирование с обратной вставкой, новая запись в истории, настоящий MediaProjection и русская карточка поверх другого UID. Нажатие «Стоп» в уведомлении после асинхронного teardown убрало projection, service и owned overlays. Это частичный набор, без physical ARM или upgrade proof.

**Новый конкретный вопрос качества:** в ручном примере связное `Bright rivers run through quiet valleys.` отображено в переводе отдельными абзацами перед `долины.`. Нужен разбор OCR-группировки и подготовки предложений; видимая русская карточка не означает прохождение проверки качества перевода.

## P1 — оставшиеся причины устойчивости

1. **C23 initial CARD self-clear остаётся открытым:** manual OCR был принят, затем automatic change на50 ячейках рядом с floating button очистил карточку. [Исходный полный API26 FAIL](qa/wave7/candidate23/README.md) не заменяется isolated PASS. Геометрическое совпадение не доказывает собственные pixels; последующие ограниченные palette samples без orange не доказывают причину или отсутствие редкого дефекта.
2. **Исторический BLOCKS self-clear не закрыт.** [Первоначальное расследование](qa/wave5/regressions/block-feedback-investigation.json) сохраняется отдельно. Исправленные native input/source-lease/Bitmap-owner ошибки и новый bars setting не являются доказательством устранения этого P1.
3. C32 сохраняет два отдельных FAIL, описанных выше. C33 test-only работа не закрывает исторический P1 без собственного доказательства. Не маскировать owned regions и не ослаблять full-frame freshness, hold или проверки ради зелёного набора.

## Полный parity-остаток сохраняется

- **MT:** Volcengine text и Niu Pro v2 не интегрированы; Tencent MPS не эквивалентен автоматическому переносу старого TMT, UI временных credentials отсутствует. Живые права/квоты/domain/enterprise/account и качество платных сервисов не проверены.
- **OCR/photo APIs:** отдельные Baidu/Paddle/Tencent/Youdao OCR и прежний Youdao picture endpoint не реализованы. Local OCR→text MT не доказывает их эквивалентность. Нужен корпус смешанных письменностей, колонок/RTL и настоящего качества OCR/MT.
- **TTS/voice studio:** generic HTTP, Volcengine и MiMo TTS остаются неинтегрированными; synthesis/clone/design/delete, права аккаунтов и слышимое качество на физических устройствах требуют отдельно разрешённых проверок. Черновики не считаются функциями.
- **Форматы/библиотеки:** поддержка TSV/JSON/документированного SQLite schema1 не означает raw upstream SQLite/binary/StarDict. Нужны большой export/reimport и сохранность metadata; SFX sample16 не равен прежнему полному каталогу.
- **GPU/графика/система:** Vulkan/GPU acceleration, privileged capture и neural inpainting произвольного цветного фона отсутствуют. Новый CPU GGUF runtime, белые manga balloons, четыре theme modes/пять accents не объявляются автоматически согласованным сокращением старого scope.
- **Каталоги/UI:**117 языков включает прежние112 choices и59 MLKit, но provider/role support проверяется отдельно; это не450/454 Niu или201 Baidu UI. Не обрезать regional tags. Полный six-locale string/error/layout audit, крупный шрифт и длинные labels ещё нужны.

## Проверки после финального APK и данные

- На итоговом optimized APK отдельно проверить photo/PNG/SAF/PROCESS_TEXT/Share с внешним получателем, Resume/Retry после перезапуска, profile/model/settings UI. Batch20 fixtures не равны20 платным quality tests; emulator ARM bridge не равен physical ARM.
- Физические ARM64/OEM/API26+ устройства: GGUF/native engines, многочасовой auto/lock/Doze, память/температура/**батарея**, protected windows, revoke в активном запросе, rotation+revocation, process death/reboot без самозапуска.
- Реальный upgrade1.8.2→новая версия с исходным signing key/production Keystore и копией настоящих данных не выполнен: история/профили/словарь/settings/aliases/keys требуют проверки. [Credential-перенос](ANDROID_LEGACY_CREDENTIAL_PLAN.md) не покрывает global credentials и все прежние сервисы; чужие key slots не взаимозаменяемы.
- QA package/certificate и unsigned production binary сами по себе не доказывают upgrade или готовность к публикации. Новые production keys, публикация и удаление прежних релизов этим журналом не разрешаются.

Следующий этап — разбор OCR-группировки этого примера, завершение отсутствующих адаптеров и оставшихся проверок. Полный scope и исторические P1 остаются незавершёнными.
