# Подписанный Android APK 1.8.2

Готовая сборка сохранена в ветке android. GitHub Release и тег **не создавались**; публикация выполняется владельцем проекта отдельно.

[Скачать ClicknTranslate-1.8.2-arm64.apk](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-1.8.2-arm64.apk)

| Параметр | Значение |
| --- | --- |
| Основной пакет | dev.clickn.translate |
| Название под значком | Clickn |
| Версия / versionCode | 1.8.2 / 7 |
| Android | 8.0 и новее (API 26); локальный LLM доступен с API 33 |
| Архитектура | ARM64 (arm64-v8a) |
| Вариант | Release, R8 и сокращение ресурсов, без debug-флага |
| Размер | 60 487 261 байт |
| Подпись | Постоянная ClicknTranslate, RSA 4096, APK Signature Scheme v2 |
| SHA-256 APK | 3a8d5d6ce41b368642f0b03bd1745e9764908aa9a1229660bd67b1557b114d63 |
| SHA-256 сертификата | 1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85 |
| Исходники APK | 55536f25f9dd6c526b8a9fbb83515d8fd62f8519 |

[Контрольная сумма](ClicknTranslate-1.8.2-arm64.apk.sha256) · [Публичный сертификат](clickntranslate-release-certificate.pem) · [R8 mapping для этой сборки](ClicknTranslate-1.8.2-mapping.txt.gz).

## Изменения

Пять статичных персонажей перерисованы лицом к пользователю без белой окантовки и подложки. Первый экран настройки предлагает язык интерфейса; далее идут тема и языки перевода. Исходный логотип CT и название Clickn сохранены. [Мастера, точные промпты, подпись и правила версий](../../docs/android-1.8.2.md).

Это основной пакет с первым постоянным ключом. Он устанавливается **рядом** со старыми UI preview (dev.clickn.translate.preview), с отдельными разрешениями, моделями и настройками. Будущие обновления основного пакета требуют того же ключа и большего versionCode. Закрытый ключ и пароль находятся вне репозитория; инструкция приватного резервного копирования — в документе выше.

## Проверки

- 1660 тестов в 447 классах: 0 ошибок, 0 падений, 0 пропусков; включены runtime-проверки всех шести языков, сохранения темы и персонажей.
- 21 снимок интерфейса успешно записан и проверен отдельно; новые персонажи просмотрены на светлом и чёрном фоне.
- assembleRelease и lintRelease успешны: 0 ошибок, 936 предупреждений, 42 информационных сообщений lint.
- Проверены подпись, версия, основной пакет, отсутствие debug-флага, ZIP CRC и ELF64 ARM64 всех 15 нативных библиотек.
- Восемь библиотек неизменённого нативного движка взяты из [проверенного CI](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37138360249); их SHA-256 совпадают с APK. На машине подготовки Windows использован локальный init-скрипт для этих библиотек.
- Пиксели всех пяти маскотов и четырёх вариантов CT совпадают с ресурсами проекта. Robolectric, Paparazzi и Byte Buddy в APK отсутствуют.

На физическом телефоне сборка пока не проверена. [Режимы и ограничения Telegram](../../docs/android-preview-v2.md).

## Пересборка

С полным Android/NDK/CMake-инструментарием на Windows и восстановленной приватной папкой ключа:

    .\tools\android-signing.ps1

На Linux задайте четыре переменные RELEASE_KEYSTORE_PATH, RELEASE_KEYSTORE_PASSWORD, RELEASE_KEY_ALIAS, RELEASE_KEY_PASSWORD приватно и выполните ./gradlew --no-daemon :app:assembleRelease. Не добавляйте ключ или пароль в Git.

## Прежние UI preview

Эти сборки имеют тестовую подпись и отдельный пакет dev.clickn.translate.preview.

| Версия | APK | SHA-256 |
| --- | --- | --- |
| 0.3.3 / 6 | [Скачать](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.3-ui-preview-arm64.apk) | 92a842e5b97d9c62c9c0e9c2307355f9d47f90623073ba3c1426b2ff51fea730 |
| 0.3.2 / 5 | [Скачать](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.2-ui-preview-arm64.apk) | 6021035c442015b3ec3913b2459b6664c711499d3b0d954ac979036b995e0d2b |
| 0.3.1 | [Скачать](https://raw.githubusercontent.com/jabrailkhalil/clickntranslate/android/artifacts/android/ClicknTranslate-0.3.1-ui-preview-arm64.apk) | 63893ef843ea09baf1966b7b1afbfd1e6f0f977cc1add995c66055f8a179b24a |
