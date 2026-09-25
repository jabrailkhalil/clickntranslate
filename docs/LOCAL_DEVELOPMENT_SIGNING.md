# Локальная подпись jabrailkhalil

Эта инструкция относится к тестовым сборкам от 25 сентября 2026 года.
Самоподписанный сертификат подтверждает владение соответствующим закрытым
ключом; он не даёт публичного доверия Microsoft/Apple и не заменяет Developer ID,
нотариализацию или доверенный Windows code-signing certificate.

## Windows

Пять собственных EXE, установщик и встроенный деинсталлятор подписаны
Authenticode/SHA-256 с RFC 3161 timestamp. Закрытый RSA-ключ неэкспортируемый,
хранится в `Cert:\CurrentUser\My`; имя сертификата `CN=jabrailkhalil`.
SHA-1 отпечаток для выбора identity:

`A0888D5CDEF8AED02740B5AF0EE34D1A1D7A535C`

Текущий сертификат экспортирован только в публичных форматах `.cer`/`.pem`.
Доверенные корневые хранилища Windows не изменялись. `tools/sign_windows.ps1`
и `tools/build_signed_installer.ps1` по-прежнему требуют доверенный сертификат
для публичного релиза и отвергают self-signed identity. Для этого тестового
набора применён отдельный локальный сценарий прямого вызова SignTool/Inno.
Не подписываются от имени проекта сторонние DLL.

Пример независимой проверки без изменения системного доверия:

```bash
osslsigncode verify -CAfile certificates/windows-jabrailkhalil.pem \
  -TSA-CAfile /etc/ssl/certs/ca-certificates.crt \
  -in Click-n-Translate-1.8.0-windows-x64-test-installer.exe
```

## macOS

Ключ находится в отдельном каталоге
`~/Library/Application Support/ClicknTranslateBuild/signing-jabrailkhalil`.
Прежняя identity и установленное приложение сохранены. SHA-1 identity:

`FC6752F0026D34E5B63433544AF788B8FC1899EF`

Чтобы повторить сборку на этом Mac:

```bash
export CLICKNTRANSLATE_SIGNING_DIR="$HOME/Library/Application Support/ClicknTranslateBuild/signing-jabrailkhalil"
export CLICKNTRANSLATE_SIGN_ALL_CODE=1
export CLICKNTRANSLATE_EXTENDED_SMOKE=1
unset MACOS_CODESIGN_IDENTITY MACOS_NOTARY_PROFILE
bash tools/build_macos_release.sh
```

`macos_signing.py sign --all-code` подписывает вложенные Mach-O/frameworks
и `.app` в правильном порядке. Этот путь не включает hardened runtime:
у местного сертификата нет Apple Team ID. Отдельная подпись DMG была сделана
тем же ключом после его создания. Проверить приложение:

```bash
codesign --verify --deep --strict ClicknTranslate.app
codesign -dvv ClicknTranslate.app
codesign --verify --strict Click-n-Translate-1.8.0-macos-arm64.dmg
```

Новая identity требует новых разрешений Screen Recording и Accessibility.
Включённая запись старой версии может относиться к старому сертификату.

## Linux и общий набор файлов

OpenPGP ключ Ed25519 имеет имя `jabrailkhalil`, срок три года и отпечаток:

`2287 3EED 9E32 9E51 D7D3 EAE0 9A50 8E7B EF2D 4205`

Приватный ключ защищён парольной фразой и правами каталога на Linux VM;
в артефакты включён только `certificates/linux-jabrailkhalil.asc`.
Для проверки с отдельным keyring, без импорта в личную связку GPG:

```bash
gpg --dearmor --output ./jabrailkhalil-public.gpg certificates/linux-jabrailkhalil.asc
gpgv --keyring ./jabrailkhalil-public.gpg SHA256SUMS.txt.asc SHA256SUMS.txt
sha256sum -c SHA256SUMS.txt
```

Перед доверием ключу сверьте отпечаток с владельцем. Подпись манифеста охватывает
все указанные в нём файлы, включая Windows/Mac архивы, исходники и отчёты.
Сам `SHA256SUMS.txt.asc` не включён в подписываемый манифест во избежание цикла.

Публикация, загрузка сертификатов/ключей в GitHub и нотариализация не выполнялись.
