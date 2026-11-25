# Передача Android-разработки на другой ПК

Исходный снимок передачи `acf17c589595b868b491440dc48bdba59ed3b5d8` соответствует Android-коду `e32ed513d3785ef877461577b4addc8652c243f0` из полной рабочей ветки. Большие APK и архив проверок передаются отдельно. Работа над code46 продолжена в `android-release-updater`. [Что удалось воспроизвести и проверить на Android 15](qa/android46/README.ru.md)

Состояние на 25 ноября 2026. На исходном ПК разработка велась в `codex/android-rewrite`. Актуальная ветка после передачи — `android-release-updater`. Изменения относятся к Android. По разрешению владельца использованы его архивные интерфейс, персонажи и Android-модули, включая наложение.

## Исходники и APK

| Что | Состояние |
|---|---|
| Текущие исходники | **1.8.3, code46**. Обновление APK с GitHub, сохранение выбора переводчика при загрузке моделей и восстановление языковой пары после поворота экрана. [Проверка обновлений и приёмка на телефоне](ANDROID_HANDOFF_183.ru.md). |
| Снимок передачи | **1.8.3, code45**, исходный коммит `b747432a8100581252f3a54bb023e8be1b229f70`. В нём изменено владение ресурсами при старте MediaProjection. |
| Последний кандидат с производственной подписью, прошедший приёмку на эмуляторе | **1.8.3, code44**, исходники `5a578d60e68518c8891345ad62376d7c1540ca49`. Подписанный APK передаётся отдельно. [Отчёт](qa/archive-restoration/gallery44/README.md). |
| Пакет | `dev.clickn.translate`, ARM64, minSdk 26, targetSdk 35. Локальный LLM требует Android 13 или новее. |
| SHA-256 APK code44 | `a22c48e8b15c11a7f594fc46f2d47ab5d14e45195b70c4d69cd23fe45baac7cc` |
| SHA-256 прежнего сертификата | `1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85` |

Для code44 прошли 1 895 JVM-тестов и 110 инструментальных тестов на API 36. Ещё 5 инструментальных пропущены по условиям запуска. Lint сообщил 0 ошибок, 975 предупреждений и 42 информационные записи. Проверены подпись v2/v3, статическое выравнивание ZIP и ELF на 16 КБ. На Android 15 исходная 1.8.2 (code7) обновлена до code44 с сохранением времени установки, тестовой записи истории, тёмной темы и языка перевода. На API 36 code44 сохранил фотозадачу code43 и экспортировал новый PNG с непрозрачной подложкой в контрольных участках. [Результаты code44](qa/archive-restoration/gallery44/README.md) · [Матрица функций](ANDROID_FEATURE_STATUS_183.ru.md).

## Развернуть проект

```text
git clone --recurse-submodules --branch android-release-updater https://github.com/jabrailkhalil/clickntranslate.git
cd clickntranslate
git submodule update --init --recursive
git -C third_party/llama.cpp rev-parse HEAD
```

Ожидаемый коммит подмодуля — `c818263f2a5ddab028dea5f169ea2b2266421125`. Установить JDK 17 и добавить его в `JAVA_HOME`. Android SDK указать в `ANDROID_HOME` или в локальном `local.properties`. Через SDK Manager установить Platform 35, Build Tools 35.0.0, Platform Tools, NDK 28.2.13676358 и CMake 3.22.1. На Windows лучше использовать короткий путь к проекту и отдельный короткий путь для NDK staging. Gradle Wrapper устанавливает Gradle 8.10.2.

Быстрая Debug-сборка, JVM, lint и инструментальный APK на Windows. Для Linux использовать `./gradlew` с теми же задачами.

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest :app:testDebugUnitTest :app:lintDebug --console=plain "-ParchiveNdkVersion=28.2.13676358" "-ParchiveCpuDebug=true" "-PandroidTestBuildType=debug"
```

Параметр `archiveCpuDebug=true` выключает Vulkan только в Debug. Для проверяемого полного варианта использовать `-ParchiveCpuDebug=false` и добавить `:app:assembleRelease`. Vulkan требует компилятор для хоста. В прежней Windows-сборке использован LLVM-MinGW в `PATH`, локальный CMake toolchain для компилятора шейдеров и `-PnativeBuildStagingDir=C:/ct-native/archive054-vulkan`. На другом ПК передать свои абсолютные пути. [Фактическая команда code44](qa/archive-restoration/gallery44/build.json).

Для повторения Windows-конфигурации LLVM-MinGW создать локальный `llvm-mingw-toolchain.cmake` с путями этого ПК и передать `-PvulkanHostToolchain=<абсолютный путь>`. Это хостовый компилятор генератора Vulkan-шейдеров. Android-код компилирует NDK.

```cmake
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_C_COMPILER "C:/path/to/llvm-mingw/bin/x86_64-w64-mingw32-clang.exe")
set(CMAKE_CXX_COMPILER "C:/path/to/llvm-mingw/bin/x86_64-w64-mingw32-clang++.exe")
set(CMAKE_MAKE_PROGRAM "C:/path/to/Android/Sdk/cmake/3.22.1/bin/ninja.exe" CACHE FILEPATH "" FORCE)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE NEVER)
```

Без ключа задача `:app:assembleRelease` создаёт `app/build/outputs/apk/release/app-release-unsigned.apk`. Подпись для обновления пользователей возможна только прежним ключом. Закрытый ключ и пароли передаются владельцем отдельно. `docs/production-certificate.pem` содержит публичный сертификат для сверки. Перед установкой подписанного APK проверить `apksigner verify --verbose --print-certs <APK>` и сравнить отпечаток с таблицей. В рабочей ветке GitHub Actions собирает Debug и запускает сценарии на Android 15. JVM и lint для code46 проверены локально. В ветке `android` их также запускает основной процесс CI. [Проверка Android 15](../.github/workflows/android-acceptance.yml) · [Основной CI](../.github/workflows/android.yml)

## Продолжение

1. Приёмка захвата, начатая в code45, продолжена на code46. На Android 15 проверены отказ в системном диалоге, немедленный повтор, отзыв разрешения во время перевода и новый захват с выводом результата. После остановки проверены сервис, виртуальный дисплей и окна приложения. На физическом телефоне осталось повторить этот сценарий и измерить длительную сессию автоперевода. [Результаты code46](qa/android46/README.ru.md)
2. Для регрессии обновления использовать отдельный тестовый профиль или эмулятор. Исходный подписанный APK 1.8.2 лежит в истории `android` по пути `artifacts/android/ClicknTranslate-1.8.2-arm64.apk`, в коммите `05493e63c6c07d206547182db6828a4dd73ca0ca`. Для обновления использовать `adb install -r <подписанный APK>`. Начать с проверки устройства через `adb devices -l`. Историю пользователя проверять на специально созданной записи. [Прогон с code44](qa/archive-restoration/gallery44/original-upgrade/result.json).
3. На физическом ARM64 последняя подтверждённая установка — code33 поверх 1.8.2. На исходном ПК телефон не определялся через ADB. Проверить запуск, время первого и повторного экранного перевода, длительный автоперевод, отзыв разрешений, Shizuku и локальные Hy-MT2/Sakura. Shizuku проверен на API 36 с официальным менеджером 13.6.0 от shell. Локальная модель на ARM-трансляции эмулятора завершилась `SIGILL`, поэтому для неё нужен нативный ARM64. [Shizuku](qa/archive-restoration/ocr42/shizuku.json) · [Локальная модель](qa/archive-restoration/hymt183/README.md).
4. Результаты испытаний сверять с матрицей. Открыты полнота смешанного и многоколоночного OCR, слышимое TTS, реальная работа всех провайдеров и совместимость Android 8 на ARM64. Прогон базовых функций и обновления на эмуляторе покрывает только перечисленные сценарии. [Матрица и ограничения](ANDROID_FEATURE_STATUS_183.ru.md).

Локальные папки `.tmp`, SDK, диски эмуляторов, Gradle-кэш и настройки компьютера не нужны для клонирования. В этой ветке есть свежие отчёты. Проверенный APK code44 и полный архив относятся к полной ветке.
