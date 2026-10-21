# Android Preview APK

Проверочная сборка от 22 октября 2026 года с новой пятёркой статичных маскотов. Готовый APK хранится непосредственно в ветке `android`. GitHub Release и тег не создавались.

[Скачать ClicknTranslate-0.3.3-ui-preview-arm64.apk](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.3-ui-preview-arm64.apk)

| Параметр | Значение |
| --- | --- |
| Пакет | `dev.clickn.translate.preview` |
| Название при установке и под значком | Clickn |
| Версия / versionCode | 0.3.3 / 6 |
| Android | 8.0 и новее (API 26); локальный LLM доступен с API 33 |
| Архитектура | ARM64 (`arm64-v8a`) |
| Размер | 86 231 462 байта |
| Подпись | APK Signature Scheme v2, Android Debug |
| SHA-256 APK | `92a842e5b97d9c62c9c0e9c2307355f9d47f90623073ba3c1426b2ff51fea730` |
| SHA-256 сертификата | `fdd0fd2a5a35bed21bdf187d7838fc53df5abfb48040b54bf1a3444be5d0686a` |

Исходники APK: `d86d93db10f23d32e66810818cf53a3d4d49e429`. Пакет собран локально с `-PpreviewBuild`. Финальный прогон этой конфигурации: 1660 тестов в 447 классах, без ошибок и пропусков; сборка и lint успешны — 0 ошибок, 958 предупреждений, 42 информационных сообщения. Отдельно проверены 20 снимков интерфейса, включая новую пятёрку на светлом и чёрном фоне. Подпись совпадает с 0.3.2 и предыдущими UI preview, поэтому приложение можно обновить с сохранением настроек.

Проверки исходников 0.3.3 на GitHub: [полная сборка и тесты](https://github.com/jabrailkhalil/clickntranslate/actions/runs/39682399225) · [CodeQL](https://github.com/jabrailkhalil/clickntranslate/actions/runs/39682399261).

Восемь нативных библиотек локального перевода взяты из [ранее проверенного CI](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37138360249) и побайтно сверены с итоговым APK; исходники нативного движка не менялись. Проверены ZIP CRC, ELF64 ARM64 у всех 15 библиотек, комплект CPU/Vulkan, девять изображений UI, подпись и отсутствие Robolectric/Paparazzi/Byte Buddy в APK. Пиксели всех пяти новых маскотов совпадают с ресурсами проекта; старые PNG Моти/Бубу/Момо отсутствуют. На физическом телефоне сборка пока не проверена. [Маскоты, PNG и точные промпты встроенного ImageGen](../../docs/android-mascots-2026-10-22.md) · [Режимы и ограничения Telegram](../../docs/android-preview-v2.md).

[Предыдущий UI preview 0.3.2](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.2-ui-preview-arm64.apk) сохранён для сравнения; SHA-256: `6021035c442015b3ec3913b2459b6664c711499d3b0d954ac979036b995e0d2b`.

[Предыдущий UI preview 0.3.1](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.1-ui-preview-arm64.apk) сохранён для сравнения; SHA-256: `63893ef843ea09baf1966b7b1afbfd1e6f0f977cc1add995c66055f8a179b24a`.

Для сборки из исходников на Linux:

```bash
./gradlew --no-daemon -PpreviewBuild :app:assembleDebug
```

Прямая ссылка выше скачивает готовый APK без клонирования репозитория.
