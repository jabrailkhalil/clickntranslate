# Mac-сборки для последующего общего релиза

Сборки можно хранить в GitHub Actions, не создавая GitHub Release или тег.
В workflow **macOS** есть ручной режим `prepare_release`: он собирает Apple Silicon
(`arm64`) и Intel (`x86_64`), использует постоянный сертификат и сохраняет файлы
в артефактах `macos-arm64-prepared` и `macos-x86_64-prepared`.

## Подготовлено 9 сентября 2026 года

[Успешный запуск Actions №34401925327](https://github.com/jabrailkhalil/clickntranslate/actions/runs/34401925327),
исходники `478f0c6ec74445606116766eb3d10bcdd670ad8a`:

| Mac | Скачать |
| --- | --- |
| Apple Silicon / arm64 | [macos-arm64-prepared](https://github.com/jabrailkhalil/clickntranslate/actions/runs/34401925327/artifacts/10123887082) |
| Intel / x86_64 | [macos-x86_64-prepared](https://github.com/jabrailkhalil/clickntranslate/actions/runs/34401925327/artifacts/10124009677) |

Обе архитектуры собраны и подписаны; runtime-тесты не запускались.
Артефакты истекают **8 декабря 2026 года в 20:35 UTC**. Скачать до этой даты.

Команда для Windows:

```powershell
gh run download 34401925327 --repo jabrailkhalil/clickntranslate --pattern 'macos-*-prepared' --dir macos-prepared
```

Это отдельные CI-сборки из указанного коммита. Они не являются загрузкой байт
локальной `/Applications/ClicknTranslate.app`. Приложение и данные на Mac не меняются.
Режим подготовки пропускает pytest и runtime smoke по текущему запросу пользователя;
проверки структуры пакета, минимальной macOS и постоянной подписи выполняются.
Обычный режим сборки и сборка по тегу сохраняют свои тесты.

## Подготовить файлы

На странице **Actions → macOS → Run workflow** выбрать нужную ветку,
включить только `prepare_release`, оставить `signing_only` выключенным.
То же через GitHub CLI:

```bash
gh workflow run macos.yml --repo jabrailkhalil/clickntranslate --ref main -f prepare_release=true
```

После успешного выполнения каждого задания внизу страницы запуска появляются
артефакты для соответствующей архитектуры. Они содержат только `.dmg`, `.zip`,
`.sha256`, `BUILD.json` с коммитом/архитектурой/подписью и краткую инструкцию.
Приватного ключа, пользовательских данных, истории и установленных OCR-моделей
в этих артефактах нет. `.app` находится внутри `.dmg` и `.zip`.

## Забрать с Windows

Войти в GitHub и скачать оба артефакта со страницы запуска либо выполнить
в PowerShell, подставив номер запуска:

```powershell
$RunId = 'НОМЕР_ЗАПУСКА'
gh run download $RunId --repo jabrailkhalil/clickntranslate --pattern 'macos-*-prepared' --dir macos-prepared
```

При скачивании через браузер распаковать внешний архив Actions. Внутренний
`Click-n-Translate-1.7.1-macos-*.zip` оставить целым: он сохраняет права и симлинки
Mac-приложения. Готовые `.dmg`, `.zip` и `.sha256` можно позднее добавить
к одному релизу вместе с Windows/Linux-файлами.

Проверка контрольных сумм в PowerShell:

```powershell
Get-ChildItem macos-prepared -Filter BUILD.json -Recurse | ForEach-Object {
    $Folder = $_.DirectoryName
    $Build = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
    Write-Host "$($Build.architecture) / $($Build.source_commit)"
    foreach ($File in $Build.files) {
        $Path = Join-Path $Folder $File.name
        $Actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
        if ($Actual -ne $File.sha256) { throw "Checksum mismatch: $Path" }
    }
}
```

Сверить `source_commit` обоих `BUILD.json` и использовать тот же код для Windows
и Linux. Позднейшие изменения кода требуют новых Mac-артефактов. Итоговую
функциональную приёмку выполнить перед общим релизом; отчёт в [MACOS_QA.md](MACOS_QA.md).
Существующий workflow `release.yml` при пуше тега заново собирает Mac и Linux
и создаёт черновик релиза; он не выбирает эти подготовленные артефакты автоматически.

## Срок и подпись

Хранение — **90 дней**, после чего GitHub удалит артефакты. Скачать их на Windows
заранее; срок конкретного запуска доступен через API артефактов. Для скачивания
нужен вход в GitHub. См. [правила хранения и скачивания GitHub](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts).

Подпись одна для обеих архитектур:
`E5E6A8042F96479E560AED29881A6F06D4D374A2`. Она постоянная self-signed,
без платного Apple Developer ID и без нотариализации. Подготовка файлов
не публикует обновление для пользователей и не запускает GitHub Release.
