# Android Preview APK

Проверочная сборка UI от 3 октября 2026 года. Готовый APK хранится непосредственно в ветке `android`. GitHub Release и тег не создавались.

[Скачать ClicknTranslate-0.3.1-ui-preview-arm64.apk](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.1-ui-preview-arm64.apk)

| Параметр | Значение |
| --- | --- |
| Пакет | `dev.clickn.translate.preview` |
| Название при установке | Click’n’Translate Preview |
| Версия / versionCode | 0.3.1 / 4 |
| Android | 8.0 и новее (API 26); локальный LLM доступен с API 33 |
| Архитектура | ARM64 (`arm64-v8a`) |
| Размер | 85 917 782 байта |
| Подпись | APK Signature Scheme v2, Android Debug |
| SHA-256 APK | `63893ef843ea09baf1966b7b1afbfd1e6f0f977cc1add995c66055f8a179b24a` |
| SHA-256 сертификата | `fdd0fd2a5a35bed21bdf187d7838fc53df5abfb48040b54bf1a3444be5d0686a` |

Исходники: `604aa245d7421ee6c6d07c0b7e90e67a36446790`. В [CI](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37138360249) успешно выполнены сборка со всеми нативными библиотеками, lint и 1638 модульных тестов. Preview-пакет собран локально с `-PpreviewBuild`; восемь нативных библиотек локального перевода взяты из этого CI и побайтно сверены с итоговым APK.

Проверены ZIP CRC, ELF64 ARM64 у всех 15 библиотек, комплект CPU/Vulkan, наличие семи новых изображений UI, подпись и отсутствие Robolectric/Paparazzi/Byte Buddy в APK. На физическом телефоне сборка пока не проверена. [Подробный отчёт UI](../../docs/android-ui-polish.md).

Для сборки из исходников на Linux:

```bash
./gradlew --no-daemon -PpreviewBuild :app:assembleDebug
```

Прямая ссылка выше скачивает готовый APK без клонирования репозитория.
