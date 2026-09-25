# Click'n'Translate

Бесплатный экранный переводчик с открытым исходным кодом для **Windows, Linux и macOS**. Распознавайте текст в приложениях, изображениях и играх, переводите выделенное или следите за меняющимся текстом в нескольких областях экрана.

[English](../../README.md) · **Русский** · [简体中文](README.zh-CN.md) · [Español](README.es.md) · [Français](README.fr.md)

## Скачать 1.8.0

| Система | Скачать | Для чего |
| --- | --- | --- |
| Windows x64 | [Установщик (.exe)](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-x64-installer.exe) | Обычная установка на Windows 10/11, x64. |
| Windows x64 | [Portable ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-windows-portable-x64.zip) | Запуск без установки; распакуйте архив целиком. |
| Linux x86_64 | [AppImage](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.AppImage) | Один исполняемый файл для Linux x86_64; перед запуском разрешите его выполнение. |
| Linux x86_64 | [tar.gz](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-linux-x86_64.tar.gz) | Папка приложения для Linux x86_64; распакуйте перед запуском. |
| macOS arm64 | [DMG](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.dmg) | Установка на Apple Silicon (M1 и новее), macOS 13.4 или новее. |
| macOS arm64 | [ZIP](https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.0/Click-n-Translate-1.8.0-macos-arm64.zip) | То же приложение для Apple Silicon в ZIP-архиве. |

[Все файлы, контрольные суммы SHA-256 и подписи](https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.0).

В сборках Windows и macOS пока используется **самоподписанный сертификат `jabrailkhalil`**. Windows может показать предупреждение SmartScreen. У Mac-версии пока нет Apple Developer ID и нотариализации, поэтому Gatekeeper может заблокировать первый запуск. Для Linux доступны отдельные подписи OpenPGP. Сборки для Intel Mac в этом выпуске нет.

## Возможности

- OCR с экрана, перевод выделенного текста, полноэкранное наложение и динамический перевод нескольких областей.
- Онлайн-перевод и локальное распознавание; офлайн-перевод после загрузки языковых моделей.
- Перевод документов, настраиваемые сочетания клавиш и компаньон на рабочем столе.
- Светлая и тёмная темы, шесть языков интерфейса и отдельные параметры окон для каждого режима.
- **В 1.8.0:** единое приветственное окно, аккуратный выбор языков, исправления динамического наложения, помощь с разрешениями macOS и тонкие полосы прокрутки во всём приложении.

## Начало работы

1. Скачайте вариант для своей системы и откройте приложение. Python уже включён в сборку.
2. Выберите движок OCR, переводчик и языки в настройках. Для офлайн-перевода загрузите языковые модели.
3. Выберите захват или перевод. На Mac приложение поможет открыть разрешения **«Запись экрана»** и **«Универсальный доступ»**. На Linux настройте сочетания клавиш через окружение рабочего стола: [инструкция](../../docs/LINUX.md).

Распознавание выполняется локально. Онлайн-перевод отправляет текст выбранному провайдеру; для локального перевода используйте офлайн-движок. Подробнее: [конфиденциальность](../../PRIVACY.md).

## Помощь и разработка

[Linux](../../docs/LINUX.md) · [macOS и сборка](../../docs/MACOS.md) · [Сообщить об ошибке](https://github.com/jabrailkhalil/clickntranslate/issues) · [Лицензия GPL-3.0](../../LICENSE)

Click’n’Translate бесплатный. Будем признательны, если вы [поставите звезду проекту на GitHub](https://github.com/jabrailkhalil/clickntranslate) и [присоединитесь к Telegram](https://t.me/jabrail_digital).
