# Подготовка Android 1.8.2

Сборка хранится в ветке `android`. GitHub Release и тег не создавались: публикация выполняется владельцем проекта отдельно.

## Интерфейс и персонажи

Первый запуск начинается с выбора языка интерфейса: язык системы, English, Русский, Deutsch, Français, Español, 中文. Названия языков показаны на их собственном языке; выбор сразу переводит интерфейс и сохраняется. Далее идут тема с миниатюрами и параметры перевода. Завершённый старый мастер настройки показывается один раз заново для этой версии.

Честер, Док, Блинчик, Раф и Лола перерисованы встроенным ImageGen по предыдущим статичным картинкам. Все смотрят вперёд. Убраны белая окантовка, круглая подложка Честера и программная рамка. Android использует прозрачные статичные PNG; рисунок и альфа-канал не перекрашивались. После генерации применены только обрезка прозрачных полей, равномерное уменьшение и центрирование до 512 × 512 px (видимая область до 464 px).

[Мастера, референсы, SHA-256 и промпты](mascots/android-1.8.2/manifest.json). Мастера сохранены в `output/imagegen/android-1.8.2/`. Внутренние ключи персонажей совместимы с предыдущими сборками.

## Версии

Видимая версия продукта — **1.8.2**, как у настольного приложения. Android `versionCode = 7` — отдельный возрастающий номер сборки. Платформы могут выпускать обновления в разные даты; совпадение видимых версий удобно для общего набора функций, но не требуется системой. При следующей Android-сборке необходимо увеличивать versionCode, даже если versionName остаётся 1.8.2. [Документация Android](https://developer.android.com/studio/publish/versioning).

## Постоянная подпись

Создан первый постоянный ключ: RSA 4096, SHA256withRSA, alias `clickntranslate`, сертификат действителен до 28 сентября 2126 года. SHA-256 сертификата:

`1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85`

[Публичный сертификат](../artifacts/android/clickntranslate-release-certificate.pem) можно распространять. Закрытый ключ и локальный файл с паролем хранятся **за пределами репозитория** в `%USERPROFILE%\.android\clickntranslate-signing`, доступ разрешён владельцу и SYSTEM. Сохраните приватную резервную копию всей этой папки: будущие обновления должны подписываться тем же ключом. [Документация Android о подписи](https://developer.android.com/studio/publish/app-signing).

Сборка использует основной пакет `dev.clickn.translate`. Старые UI preview имели пакет `dev.clickn.translate.preview` и тестовую подпись: новая сборка устанавливается рядом с ними, с отдельными настройками.

Подписанная сборка с настроенным Android и нативным инструментарием:

```powershell
.\tools\android-signing.ps1
```

Сценарий читает приватную конфигурацию вне Git, передаёт подпись через переменные окружения только на время сборки и восстанавливает предыдущие значения. Для другого компьютера восстановите приватную папку и передайте `-SigningDirectory`. Не создавайте новый ключ для обновления опубликованного приложения.

На машине подготовки Windows нативные исходники не менялись, а C++-инструментарий для host shader compiler отсутствует. Поэтому использованы восемь проверенных библиотек из [CI](https://github.com/jabrailkhalil/clickntranslate/actions/runs/37138360249) через локальный, исключённый из Git `tmp/ci-native.gradle`; их SHA-256 сверяются с готовым APK. Обычная сборка из исходников требует полного нативного инструментария. Скрипт подписи не скачивает и не заменяет библиотеки сам.

## Точные промпты ImageGen

### chester

```text
Use case: precise-object-edit. Image 1 is the EDIT TARGET / exact character identity reference. Create a polished STATIC app mascot illustration of this SAME character, but turn BOTH body and head STRAIGHT TOWARD THE VIEWER, with a centered face, two visible eyes making warm eye contact with the camera, a gentle sweet smile and a relaxed cute balanced pose. Frontal view at eye level, NOT side view and NOT three-quarter. Keep original species, defining features and palette. Style: soft rounded premium 2.5D toy illustration, charming, lively colors, soft material shading and carefully placed highlights INSIDE the body, clear simple face at 40–64 dp. Complete character centered on a square transparent canvas, about 82% occupancy, all ears/feet/leaves/antenna inside the frame, natural proportions. NO STROKE OR OUTLINE around the silhouette of ANY color; especially NO WHITE OUTLINE, pale fringe, halo, outer glow, rim light, sticker edge, cutout border or white keyline. Shape is defined only by its own material colors and gentle volumetric shading. NO circular badge, disc, backdrop, ground plane, cast shadow, scenery, words, watermark, extra characters or animation frames. True transparent alpha right up to the natural body boundary.
Identity: Chester: warm charcoal brown CAT, frontal sitting pose with both front paws together, both ears visible with pink interiors, curled tail visible beside the body, expressive glossy dark eyes, tiny friendly mouth and pink cheeks. Keep him a CAT, not a fox. Use naturally illuminated warm cocoa midtones in the fur so he reads on dark screens, without adding an outline or any white rim. No clothing.
```

### doc

```text
Use case: precise-object-edit. Image 1 is the EDIT TARGET / exact character identity reference. Create a polished STATIC app mascot illustration of this SAME character, but turn BOTH body and head STRAIGHT TOWARD THE VIEWER, with a centered face, two visible eyes making warm eye contact with the camera, a gentle sweet smile and a relaxed cute balanced pose. Frontal view at eye level, NOT side view and NOT three-quarter. Keep original species, defining features and palette. Style: soft rounded premium 2.5D toy illustration, charming, lively colors, soft material shading and carefully placed highlights INSIDE the body, clear simple face at 40–64 dp. Complete character centered on a square transparent canvas, about 82% occupancy, all ears/feet/leaves/antenna inside the frame, natural proportions. NO STROKE OR OUTLINE around the silhouette of ANY color; especially NO WHITE OUTLINE, pale fringe, halo, outer glow, rim light, sticker edge, cutout border or white keyline. Shape is defined only by its own material colors and gentle volumetric shading. NO circular badge, disc, backdrop, ground plane, cast shadow, scenery, words, watermark, extra characters or animation frames. True transparent alpha right up to the natural body boundary.
Identity: Doc: ivory cream rounded baby ROBOT, full frontal pose, compact dark navy visor centered on body, two small round cyan eyes with small interior glints and a tiny cyan smile. Two matching short ivory rounded arms relaxed beside the body and TWO evenly planted teal boots visible, short centered antenna with a cyan ball. Preserve the compact visor and approved smaller rounded eyes. No large glowing eye outlines or new robot hardware.
```

### pancake

```text
Use case: precise-object-edit. Image 1 is the EDIT TARGET / exact character identity reference. Create a polished STATIC app mascot illustration of this SAME character, but turn BOTH body and head STRAIGHT TOWARD THE VIEWER, with a centered face, two visible eyes making warm eye contact with the camera, a gentle sweet smile and a relaxed cute balanced pose. Frontal view at eye level, NOT side view and NOT three-quarter. Keep original species, defining features and palette. Style: soft rounded premium 2.5D toy illustration, charming, lively colors, soft material shading and carefully placed highlights INSIDE the body, clear simple face at 40–64 dp. Complete character centered on a square transparent canvas, about 82% occupancy, all ears/feet/leaves/antenna inside the frame, natural proportions. NO STROKE OR OUTLINE around the silhouette of ANY color; especially NO WHITE OUTLINE, pale fringe, halo, outer glow, rim light, sticker edge, cutout border or white keyline. Shape is defined only by its own material colors and gentle volumetric shading. NO circular badge, disc, backdrop, ground plane, cast shadow, scenery, words, watermark, extra characters or animation frames. True transparent alpha right up to the natural body boundary.
Identity: Blinchik/Pancake: thick plump golden PANCAKE buddy, round toasted golden top with one butter square, creamy side, two small arms relaxed at the sides and two caramel oval feet equally visible in a balanced frontal pose. Two warm glossy eyes looking at viewer, tiny happy smile, pink cheeks. Must remain a single thick pancake, not bread or a stack. Soft buttery highlights, no harsh cartoon stroke.
```

### raf

```text
Use case: precise-object-edit. Image 1 is the EDIT TARGET / exact character identity reference. Create a polished STATIC app mascot illustration of this SAME character, but turn BOTH body and head STRAIGHT TOWARD THE VIEWER, with a centered face, two visible eyes making warm eye contact with the camera, a gentle sweet smile and a relaxed cute balanced pose. Frontal view at eye level, NOT side view and NOT three-quarter. Keep original species, defining features and palette. Style: soft rounded premium 2.5D toy illustration, charming, lively colors, soft material shading and carefully placed highlights INSIDE the body, clear simple face at 40–64 dp. Complete character centered on a square transparent canvas, about 82% occupancy, all ears/feet/leaves/antenna inside the frame, natural proportions. NO STROKE OR OUTLINE around the silhouette of ANY color; especially NO WHITE OUTLINE, pale fringe, halo, outer glow, rim light, sticker edge, cutout border or white keyline. Shape is defined only by its own material colors and gentle volumetric shading. NO circular badge, disc, backdrop, ground plane, cast shadow, scenery, words, watermark, extra characters or animation frames. True transparent alpha right up to the natural body boundary.
Identity: Raf: low soft translucent sky-blue JELLY, a rounded legless droplet with the small curved tip retained, full frontal face with two round dark eyes and little happy smile, pink cheeks. Gentle aqua gradients and broad soft internal reflections. NO legs, feet, shoes, arms, hands, tail, puddle, extra bubbles or strong blue outline. Keep the compact original volume and softly rounded bottom.
```

### lola

```text
Use case: precise-object-edit. Image 1 is the EDIT TARGET / exact character identity reference. Create a polished STATIC app mascot illustration of this SAME character, but turn BOTH body and head STRAIGHT TOWARD THE VIEWER, with a centered face, two visible eyes making warm eye contact with the camera, a gentle sweet smile and a relaxed cute balanced pose. Frontal view at eye level, NOT side view and NOT three-quarter. Keep original species, defining features and palette. Style: soft rounded premium 2.5D toy illustration, charming, lively colors, soft material shading and carefully placed highlights INSIDE the body, clear simple face at 40–64 dp. Complete character centered on a square transparent canvas, about 82% occupancy, all ears/feet/leaves/antenna inside the frame, natural proportions. NO STROKE OR OUTLINE around the silhouette of ANY color; especially NO WHITE OUTLINE, pale fringe, halo, outer glow, rim light, sticker edge, cutout border or white keyline. Shape is defined only by its own material colors and gentle volumetric shading. NO circular badge, disc, backdrop, ground plane, cast shadow, scenery, words, watermark, extra characters or animation frames. True transparent alpha right up to the natural body boundary.
Identity: Lola: plump rose pink PEACH buddy, two fresh green leaves and short brown stem on top, full frontal view, centered face with both eyes making eye contact, sweet small smile and pink cheeks. Two small rounded arms at sides and two rose colored feet planted evenly. Soft velvety peach material and vivid fresh colors; no heavy red contour, outline, white rim, clothing, or props.
```

## Результат подготовки

Исходники APK: 55536f25f9dd6c526b8a9fbb83515d8fd62f8519. Выполнены 1660 тестов в 447 классах без ошибок и пропусков, 21 проверка снимков, подписанная сборка и lintRelease. Lint: 0 ошибок, 936 предупреждений, 42 информационных сообщений. APK и карта R8 сохранены в ветке без GitHub Release и тега. [Скачать и проверить](../artifacts/android/README.md).
