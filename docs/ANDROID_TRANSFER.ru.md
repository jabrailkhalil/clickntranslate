# Передача Android-разработки на другой ПК

Исходный снимок передачи `acf17c589595b868b491440dc48bdba59ed3b5d8` соответствует Android-коду `e32ed513d3785ef877461577b4addc8652c243f0` из полной рабочей ветки. Большие APK и архив проверок передаются отдельно. Работа над code46 продолжена в `android-release-updater`. [Проверка на Android 15](qa/android46/README.ru.md) · [Проверка на OnePlus 15](qa/android46/oneplus15/README.ru.md)

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

1. На Android 15 и на OnePlus подтверждены отмена и повторный запрос согласия MediaProjection. На телефоне при закрытии выбранного приложения во время HTTP-запроса проекция завершилась, поздний ответ не показал плашку. Новый сеанс показал перевод за 1,583 с. В режиме захвата всего экрана приложение распознало фразу из выделенной области и показало результат за 1,144 с. [Эмулятор](qa/android46/README.ru.md) · [Проверка на OnePlus 15](qa/android46/oneplus15/README.ru.md)
2. На OnePlus в отдельном профиле проверен переход code7→46 с общей тестовой подписью. После отмены осталась старая версия, после установки сохранились история и тема. Для подтверждения производственного обновления взять подписанный APK 1.8.2 из коммита `05493e63c6c07d206547182db6828a4dd73ca0ca` по пути `artifacts/android/ClicknTranslate-1.8.2-arm64.apk` и подписать проверяемый APK code46 прежним ключом. Отдельно проверить обновление с code45. [Подписанный code44 на эмуляторе](qa/archive-restoration/gallery44/original-upgrade/result.json)
3. На CPU OnePlus Hy-MT2 перевёл английский и арабский текст на русский, Sakura перевела две японские фразы на китайский. Проверены выгрузка Sakura, английский офлайн-синтез и арабский OCR. Для Shizuku 13.6.0 нужен менеджер в профиле владельца телефона. [Shizuku на эмуляторе](qa/archive-restoration/ocr42/shizuku.json) · [Проверка на OnePlus 15](qa/android46/oneplus15/README.ru.md)
4. Открыты качество распознавания на более широком наборе смешанных и многоколоночных страниц, слышимость TTS, работа всех провайдеров и совместимость Android 8 на ARM64. [Матрица функций](ANDROID_FEATURE_STATUS_183.ru.md)

Локальные папки `.tmp`, SDK, диски эмуляторов, Gradle-кэш и настройки компьютера не нужны для клонирования. В этой ветке есть свежие отчёты. Проверенный APK code44 и полный архив относятся к полной ветке.
