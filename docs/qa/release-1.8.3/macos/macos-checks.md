# Проверка Click’n’Translate 1.8.3 для macOS

## Финальный кандидат 7cd32e5

Обе подписанные сборки ветки `release-1.8.3-qa` проверены из коммита `7cd32e563c917e33cabfbdd104dfd7069b4c2e0f`. Скачаны четыре файла дистрибутива и проверены их SHA-256, подписи вложенного приложения на обоих нативных Mac и архитектуры трёх исполняемых файлов в каждом ZIP. [Сборка](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46008969175) · [Проверка установленных DMG](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46009103028)

| Проверка установленного приложения | Apple Silicon | Intel |
| --- | --- | --- |
| Система | macOS 15.8.2 | macOS 15.7.9 |
| Тесты платформы | 260 прошли, 17 дополнительных случаев, 35 пропущены, 17,44 с | 260 прошли, 17 дополнительных случаев, 35 пропущены, 40,70 с |
| Проверено Mach-O для macOS 13.4 | 260 | 261 |
| Точные результаты вложенного OcrWorker | 8/8 | 8/8 |
| Китайские символы в каждом из двух комплектных OTF | 780 | 780 |
| TIFF без сжатия, с LZW и Adobe Deflate | 36/36 через загрузчик из проверенного коммита | 36/36 через загрузчик из проверенного коммита |
| Длина пути сокета до и после выбора приватного каталога | 193 → 68 байт | 193 → 71 байт |
| Восстановленная тема из повреждённого профиля | Светлая | Светлая |
| Готовность главного окна в этом пробном профиле | 2,47 с | 3,64 с |
| Второй реальный вызов приложения | код 0, первый процесс подтвердил show | код 0, первый процесс подтвердил show |
| Screen Recording / Accessibility | false / false | false / false |
| Gatekeeper | rejected, код 3 | rejected, код 3 |

42 отдельных теста IPC прошли на каждой из трёх машин с macOS arm64, macOS Intel и Ubuntu 24.04. Один клиент отправлял команду по настоящему Unix-сокету владельцу, два длинных каталога одного пользователя сохраняли разные сеансы, символическая ссылка обслуживалась в том же сеансе. [Нативные тесты IPC](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46009099029)

В артефакте каждой архитектуры находятся DMG и ZIP. Контрольные суммы в таблице относятся к отдельным файлам внутри артефакта.

| Файл финальной сборки | SHA-256 |
| --- | --- |
| [Click-n-Translate-1.8.3-macos-arm64.dmg](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46008969175/artifacts/15203276513) | `98876b72232536a5562d341f31e8d446485d8100c738c90c19a80e2fec50d600` |
| [Click-n-Translate-1.8.3-macos-arm64.zip](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46008969175/artifacts/15203276513) | `9ffc631a90e2bd03bfc133cc8818e4034d33c4d0a716a1339d5c746de445cf0d` |
| [Click-n-Translate-1.8.3-macos-x86_64.dmg](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46008969175/artifacts/15203287391) | `c237a860c92e63f0259f37bd9cf03c8a6cf3c7c7e1438cef8aa943269c4b86c1` |
| [Click-n-Translate-1.8.3-macos-x86_64.zip](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46008969175/artifacts/15203287391) | `e6265373d4fc59ae8692e8093586d3146eccac50ffd1d1af05850d74155c9fe0` |

На Apple Silicon текущие Настройки через локальный HTTP-сервер заменили настоящую публичную 1.8.2 точным финальным ZIP. Новое GUI подтвердило готовность. В отдельном прогоне после аварии восстановилась прежняя программа и ответила по IPC. Настройки, контрольные файлы и модели сохранились в обоих случаях. В контроллере стенда моделировались версия исходной установки и определение её местоположения. [Обновление и откат финального ZIP](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46009996195)

На чистом Apple Silicon копия из отдельного DMG унаследовала quarantine в формате Safari. Первая попытка LaunchServices за 35,01 с не создала отчёт приложения. Gatekeeper вернул код 3. Пользовательского подтверждения не было. Ручная выдача Screen Recording и Accessibility, сохранение выданных прав, работа нижней границы Ventura 13.4 и реальные несколько мониторов остаются отдельными сценариями. [Наблюдение Gatekeeper](46009103028/macos-quarantined-first-open/quarantine.json)

[Повреждённый профиль на Apple Silicon](46009103028/macos-arm64-installed/invalid-theme-main.png) · [Профиль на Intel](46009103028/macos-x86_64-installed/invalid-theme-main.png) · [Отрисовка комплектного китайского шрифта](46009103028/macos-arm64-installed/final-chinese-fonts.png)

## Устранённые сбои

Исходный коммит `fafcbb87ae12618d24884c668cb02ab80c7e6307` на обоих Mac открывал список языков при 80 % сначала шириной 640, затем 306. Исправление учитывает отложенную раскладку и измеряет уже оформленное поле поиска. В нативном Cocoa проверены 90 сочетаний и 180 открытий, доступность последней строки, 48 положений окна, темы, Carbon, Apple Vision и временная запись в Keychain. [Два первоначальных сбоя](https://github.com/jabrailkhalil/clickntranslate/actions/runs/45963672074) · [Трасса и снимки](https://github.com/jabrailkhalil/clickntranslate/actions/runs/45965112027) · [Нативные сценарии](https://github.com/jabrailkhalil/clickntranslate/actions/runs/45967679601)

Промежуточный OcrWorker на обоих Mac читал `CLICK TRANSLATE` как `C √ ICK TRANSL`. Для коротких горизонтальных фрагментов с английской или кириллической моделью был скорректирован масштаб детектора. На 20 английских и 13 русских размеченных кадрах текст стал точным. Глобальное изменение масштаба теряло слово «Французский» на плотном интерфейсе, поэтому оставлено условие по геометрии. На трёх настоящих изображениях Cocoa итог полностью совпал с прежним выводом. [Прежняя ошибка упакованного OcrWorker](https://github.com/jabrailkhalil/clickntranslate/actions/runs/45968074075) · [Сравнение на готовых изображениях](ocr-evidence/adaptive-product-screens.json)

В кандидате `05c30f30` настоящий сокетный путь длиной 104 байта вызывал ошибку IPC на Darwin до чтения профиля. При допустимом 52-байтовом пути обе программы восстанавливали повреждённую тему. Финальное исправление `fc64beaf` ограничивает длину в байтах и проверяет принадлежность и права резервного каталога. Исходный runtime-каталог определяет отдельный сеанс по устройству и inode. [Воспроизведение](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46006916728) · [Прежний кандидат с коротким путём](https://github.com/jabrailkhalil/clickntranslate/actions/runs/46008241336) · [Патч IPC](https://github.com/jabrailkhalil/clickntranslate/commit/7cd32e563c917e33cabfbdd104dfd7069b4c2e0f)

## Разрешения, TextEdit и сеть

На выделенном Apple Silicon процесс Python имел Screen Recording и Accessibility. ScreenCaptureKit снял реальное окно TextEdit 625×686, Apple Vision прочитала `LANTERN COCOA TEXT`. AXSelectedText вернул выделение, Cmd+C и Cmd+V заменили текст в настоящем документе, прежний буфер обмена восстановился. После перехода во второе окно того же приложения защита отменила вставку. В этом запуске этап TextEdit завершился успешно, следующий отдельный этап ожидал ещё не готовый пакет. Установленные финальные .app имели оба права выключенными. [Отчёт TextEdit](45968462652/macos-external-textedit/external-textedit.json) · [Снимок окна](45968462652/macos-external-textedit/textedit-region.png)

У обоих DMG постоянная самоподпись с отпечатком `FC6752F0026D34E5B63433544AF788B8FC1899EF`, нотарификация отсутствует. Копия из артефакта Actions не имела quarantine и запустилась через LaunchServices. Отдельная копия унаследовала смоделированный атрибут Safari, автоматического допуска за 35 с не последовало. Для ручной выдачи разрешений и проверки их сохранения после обновления достаточно одного графического Mac. Для нижней границы нужен именно Ventura 13.4, где используется Core Graphics, а разные DPI требуют двух экранов. [Инструкция проекта](https://github.com/jabrailkhalil/clickntranslate/blob/7cd32e563c917e33cabfbdd104dfd7069b4c2e0f/docs/guides/setup.ru.md#macos)

На GitHub macos-15 продуктовый `translate_text` с пустой конфигурацией и без ключей перевёл `Good morning. Thank you very much.` в «Доброе утро. Большое спасибо.» через Google за 0,34 с и MyMemory за 1,13 с. Последние публичные узлы Lingva и LibreTranslate вернули HTTP 502 за 1,92 с и 2,06 с соответственно. Проверка была на `eec0ed79`, код `src/translater.py` до финального кандидата не менялся. [Исходные ответы](46004127718/macos-public-translations/online-providers.json)

## Протоколы финальной проверки

Подробные протоколы установленных приложений содержат распознанный текст, результаты проверки подписи и выданные разрешения. [Apple Silicon](46009103028/macos-arm64-installed/installed-package.json) · [Intel](46009103028/macos-x86_64-installed/installed-package.json)

Для каждой архитектуры зафиксированы длина пути сокета, время до открытия окна, отрисованные символы и декодированные изображения. [Apple Silicon](46009103028/macos-arm64-installed/final-resources.json) · [Intel](46009103028/macos-x86_64-installed/final-resources.json)

Установленные программы записали состояние системных разрешений при запуске. [Apple Silicon](46009103028/macos-arm64-installed/frozen-permissions.json) · [Intel](46009103028/macos-x86_64-installed/frozen-permissions.json)

Отдельный прогон на Apple Silicon использовал ZIP финального кандидата для установки и отката. [Установка](46009996195/macos-native-upgrade/success-report.json) · [Откат](46009996195/macos-native-upgrade/rollback-report.json)
