# Click’n’Translate

**Читайте текст с экрана на своём языке.**

Переводите игры, копируйте текст с картинок, читайте документы и заменяйте сообщения переводом. Бесплатное приложение с открытым кодом для **Windows, macOS и Linux**. Для **Android** есть отдельная мобильная версия.

[![Downloads](https://img.shields.io/github/downloads/jabrailkhalil/clickntranslate/total?style=for-the-badge&color=8b6bb1)](https://github.com/jabrailkhalil/clickntranslate/releases)

[English](../../README.md) · [Русский](README.ru.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [简体中文](README.zh-CN.md) · [Português](README.pt.md) · [Italiano](README.it.md)

![Click’n’Translate 1.8.2](../images/desktop-1.8.2.png)

## Скачать 1.8.2

| OS | Download |
| --- | --- |
| Windows 10/11 x64 | [Installer](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe) · [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-portable-x64.zip) |
| macOS 13.4+, Apple Silicon | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-arm64.dmg) |
| macOS 13.4+, Intel | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-macos-x86_64.dmg) |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.AppImage) · [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-linux-x86_64.tar.gz) |
| Android 8.0+, ARM64 | [APK](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/ClicknTranslate-1.8.2-arm64.apk) |

[Checksums / signatures](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2) · [Signing identities](../SIGNING_IDENTITIES.md)

## Под задачу, а не под одно окно

| Что нужно сделать | Как это работает |
| --- | --- |
| Прочитать текст, который нельзя выделить | Выделите область экрана: приложение распознает и переведёт текст |
| Скопировать текст с изображения | OCR перенесёт распознанный текст в буфер обмена |
| Перевести выделение в другом приложении | Нажмите своё сочетание клавиш; для режима хранится отдельная пара языков |
| Написать сообщение на другом языке | Замените выделение переводом; при желании включите выделение всего поля перед заменой |
| Следить за меняющимся текстом | Динамический перевод наблюдает за одной или несколькими областями |
| Прочитать документ | Откройте исходник и перевод рядом, редактируйте результат и скрывайте исходник |

![Настоящий перевод в версии 1.8.2](../images/translate-text-1.8.2.gif)

Поддерживаются TXT, Markdown, DOCX, PDF с текстовым слоем, HTML и RTF. Для сканов нужен OCR. Можно печатать прямо в главном окне, раскрыть результат в отдельное рабочее окно или скопировать его.

## Онлайн, офлайн или свой API

- **Онлайн:** Google, MyMemory, Lingva, LibreTranslate.
- **Офлайн:** Argos Translate и Hy-MT после установки нужных моделей.
- **Локальный OCR:** Windows OCR, Apple Vision, Tesseract, RapidOCR, EasyOCR. Нативные движки зависят от ОС.
- **Свои ключи:** OpenAI, Gemini, Claude, DeepL, LibreTranslate и совместимые Custom API. Для vision-модели можно явно включить изображения и получить распознавание с переводом у одного провайдера.

Откройте **Настройки → Перевод и OCR → Языковые пакеты**. Во вкладках OCR и переводчиков устанавливаются локальные компоненты, во вкладке **API** — подключения. Если движка или направления нет, приложение предложит перейти к установке либо выбрать доступный сервис.

![Настройки и API в 1.8.2](../images/settings-api-1.8.2.gif)

Локальный OCR обрабатывает изображения на устройстве. Онлайн-перевод отправляет текст выбранному сервису; включённый vision API получает и выбранное изображение. После загрузки моделей офлайн-перевод работает локально. У API-провайдера могут быть свои тарифы и лимиты. [Приватность](../../PRIVACY.md).

## Удобно каждый день

Восемь языков интерфейса: русский, английский, испанский, немецкий, французский, китайский, португальский и итальянский — с подсказками и встроенным гайдом. Есть светлая и тёмная темы, масштаб интерфейса, отдельный размер текста результата с примером, импорт/экспорт настроек и необязательные локальные истории.

![Новые маскоты и их настройки](../images/companion-1.8.2.gif)

Маскот открывает меню действий по нажатию и реагирует на события. Персонажа, размер и прозрачность можно настроить; самого маскота — скрыть.

| Горячая клавиша Windows | Действие |
| --- | --- |
| Ctrl + Alt + T | Перевести область |
| Ctrl + Alt + C | Скопировать текст из области |
| Ctrl + Alt + F | Перевести экран |
| Ctrl + Alt + Q | Перевести выделение |
| Ctrl + Shift + Q | Заменить переводом |
| Ctrl + Alt + G | Динамический перевод |
| Ctrl + Shift + Space | Показать или скрыть приложение |

Сочетания меняются в настройках горячих клавиш. На Mac используйте Command вместо Ctrl, Option вместо Alt. На Linux назначьте команды в своей среде рабочего стола: [инструкция](../LINUX.md).

## Первый запуск и обновления

Python уже включён в настольные сборки. Распакуйте ZIP целиком или используйте установщик. На Mac для соответствующих функций нужны «Запись экрана» и «Универсальный доступ». На Android разрешения на захват и показ поверх других приложений запрашиваются при включении перевода экрана.

В Windows и Mac используется прежний самоподписанный сертификат **jabrailkhalil**: возможен SmartScreen; у Mac нет Apple-нотаризации. [Первый запуск по шагам](../guides/setup.ru.md).

Настольная версия 1.8.2 скачивает обновления из GitHub Releases внутри приложения, показывает прогресс и перезапускается после замены файлов. Mac/Linux 1.8.1 и старше сначала нужно обновить вручную до этой версии. Защищённое расположение установки может требовать ручной замены; Store-сборки обновляются через Microsoft Store. [Как устроено обновление](../UPDATES_1.8.2_DEVELOPMENT.md).

Android — отдельный интерфейс с переводом экрана, текста и фото, а также историей: [мобильная версия](https://github.com/jabrailkhalil/clickntranslate/tree/android#readme). Счётчик GitHub показывает скачивания файлов релизов, а не число уникальных пользователей.

Нашли ошибку? Создайте **Баг-репорт** в настройках и приложите ZIP к [issue](https://github.com/jabrailkhalil/clickntranslate/issues). Содержимое буфера, документов, историй и ключи в отчёт не включаются.

[Сайт](https://translate.clickn.dev/) · [Telegram](https://t.me/jabrail_digital) · [Исходный код](../REPOSITORY_LAYOUT.md) · [GPL-3.0](../../LICENSE)
