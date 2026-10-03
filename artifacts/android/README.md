# Android Preview APK

Проверочная сборка UI от 3 октября 2026 года. Готовый APK хранится непосредственно в ветке `android`. GitHub Release и тег не создавались.

[Скачать ClicknTranslate-0.3.2-ui-preview-arm64.apk](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.2-ui-preview-arm64.apk)

| Параметр | Значение |
| --- | --- |
| Пакет | `dev.clickn.translate.preview` |
| Название при установке и под значком | Clickn |
| Версия / versionCode | 0.3.2 / 5 |
| Android | 8.0 и новее (API 26); локальный LLM доступен с API 33 |
| Архитектура | ARM64 (`arm64-v8a`) |
| Размер | 86 586 278 байт |
| Подпись | APK Signature Scheme v2, Android Debug |
| SHA-256 APK | `6021035c442015b3ec3913b2459b6664c711499d3b0d954ac979036b995e0d2b` |
| SHA-256 сертификата | `fdd0fd2a5a35bed21bdf187d7838fc53df5abfb48040b54bf1a3444be5d0686a` |

Исходники APK: `e094ffca6fff65be9fab40752b73019e50c1b9f9`. Пакет собран локально с `-PpreviewBuild`. Финальный прогон этой конфигурации: 1659 тестов в 447 классах, без ошибок и пропусков; lint — 0 ошибок, 964 предупреждения, 42 информационных сообщения. Отдельно проверены 19 снимков интерфейса. Подпись совпадает с предыдущим UI preview, поэтому приложение можно обновить с сохранением настроек.

В [CI для 06f92eb](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37149825319) успешно выполнены полная сборка со всеми нативными библиотеками, lint и модульные тесты. [CodeQL для того же коммита](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37149825350) также завершился успешно. Последующие изменения исходников APK касаются закрепления карточки, подписей и фона значков и проверены локально указанным финальным прогоном.

Восемь нативных библиотек локального перевода взяты из [ранее проверенного CI](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37138360249) и побайтно сверены с итоговым APK; исходники нативного движка не менялись. Проверены ZIP CRC, ELF64 ARM64 у всех 15 библиотек, комплект CPU/Vulkan, наличие десяти изображений UI, подпись и отсутствие Robolectric/Paparazzi/Byte Buddy в APK. На физическом телефоне сборка пока не проверена. [Изменения, поведение и ограничения Telegram](../../docs/android-preview-v2.md) · [Картинки и точные промпты ImageGen](../../docs/android-preview-v2-artwork.md).

[Предыдущий UI preview 0.3.1](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.1-ui-preview-arm64.apk) сохранён для сравнения; SHA-256: `63893ef843ea09baf1966b7b1afbfd1e6f0f977cc1add995c66055f8a179b24a`.

Для сборки из исходников на Linux:

```bash
./gradlew --no-daemon -PpreviewBuild :app:assembleDebug
```

Прямая ссылка выше скачивает готовый APK без клонирования репозитория.
