# Разработка Click'n'Translate для Android

## Структура

- `app/src/main/java/dev/clickn/translate` — Kotlin-код приложения.
- `app/src/main/res` — строки, темы, системные XML и иконки.
- `app/src/test/java/dev/clickn/translate` — модульные тесты.
- `app/src/androidTest/java/dev/clickn/translate` — проверки на Android-устройстве.
- `llama-android` — локальная интеграция нативного LLM-движка.
- `third_party/llama.cpp` — закреплённая нативная зависимость.

## Проверки

```bash
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
python3 -m unittest discover -s tools/dictionary_packs/tests
```

При наличии Android-устройства с отладкой USB:

```bash
./gradlew :app:connectedDebugAndroidTest
```

Проверяй короткие и длинные названия языков, светлую и тёмную темы, разрешения, плавающую кнопку, экспорт и повторный запуск приложения. Не добавляй API-ключи, пароли и сертификаты в исходники.

## Фирменные материалы

Идентичность продукта задаётся в `AppBrand.kt`. Название в ресурсах Android должно совпадать в каждой локали. Адаптивная иконка содержит CT внутри безопасной области маски. Основной логотип находится в `drawable-nodpi/brand_logo.png`.

Изменения пакета должны учитывать Android Manifest, импорты, ProGuard, JNI-символы, сценарии диагностики и тесты. Пакет библиотеки нативного движка имеет собственную идентичность и не является идентификатором приложения.

Для новой локали добавь файл `values-TAG/strings.xml`, запись в `xml/locales_config.xml` и вариант в `APP_LANGUAGE_OPTIONS` в `SettingsScreen.kt`. Сохраняй placeholders и Android-экранирование.
