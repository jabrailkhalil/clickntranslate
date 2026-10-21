# Статичные маскоты Clickn — 22 октября 2026

Пять картинок созданы встроенным ImageGen по актуальным персонажам настольного приложения из коммита `959175f` ветки `codex/custom-mascots`: Док v17 с одобренными глазами; остальные — v16. На Android используются статичные изображения без ходьбы, таймеров анимации и смены кадров. Изменения относятся к preview 0.3.3, без GitHub Release или тега.

Идентичность сохранена: Честер — тёмный кот, Док — кремовый робот, Блинчик — золотистый блинчик, Раф — голубое желе без ног, Лола — розовый персик. Честеру дана светлая подложка с тонкой обводкой в превью и на плавающей кнопке. Логотип CT и название Clickn не менялись.

Оригиналы PNG сохранены без изменений. Для APK применены только обрезка прозрачных полей, равномерное уменьшение и центрирование: 512 × 512 px, видимая область до 464 px, исходная прозрачность сохранена. Рисунок и альфа-канал не перекрашивались. Все пути, SHA-256, границы кадрирования и точные промпты находятся в [manifest.json](mascots/android-2026-10-22/manifest.json).

| Герой | Мастер ImageGen | PNG для Android | Референс |
| --- | --- | --- | --- |
| chester | [chester.png](../output/imagegen/android-mascots-2026-10-22/companion_chester.png) | [chester.png](../app/src/main/res/drawable-nodpi/companion_chester.png) | [chester.png](../docs/mascots/android-2026-10-22/references/chester.png) |
| doc | [doc.png](../output/imagegen/android-mascots-2026-10-22/companion_doc.png) | [doc.png](../app/src/main/res/drawable-nodpi/companion_doc.png) | [doc.png](../docs/mascots/android-2026-10-22/references/doc.png) |
| pancake | [pancake.png](../output/imagegen/android-mascots-2026-10-22/companion_pancake.png) | [pancake.png](../app/src/main/res/drawable-nodpi/companion_pancake.png) | [pancake.png](../docs/mascots/android-2026-10-22/references/pancake.png) |
| raf | [raf.png](../output/imagegen/android-mascots-2026-10-22/companion_raf.png) | [raf.png](../app/src/main/res/drawable-nodpi/companion_raf.png) | [raf.png](../docs/mascots/android-2026-10-22/references/raf.png) |
| lola | [lola.png](../output/imagegen/android-mascots-2026-10-22/companion_lola.png) | [lola.png](../app/src/main/res/drawable-nodpi/companion_lola.png) | [lola.png](../docs/mascots/android-2026-10-22/references/lola.png) |

Внутренние ключи `doc`, `pancake`, `bubu` и `momo` остаются совместимыми с предыдущим preview. Старый ключ `mochi` читается как Честер (`chester`); в интерфейсе больше нет отдельного Моти или старого лиса. Своя картинка, действие кнопки и постоянная видимость сохраняются.

Повторная упаковка из сохранённых мастеров с Python и Pillow:

```bash
python tools/pack_android_mascots.py docs/mascots/android-2026-10-22/manifest.json --output docs/mascots/android-2026-10-22/manifest.json
```

## Точные промпты ImageGen

### chester

```text
Use case: stylized-concept. Asset type: final STATIC transparent mascot illustration for the Android Clickn floating button, readable at 40–64 dp. Image 1 is the IDENTITY REFERENCE of the owner's current mascot, not a style to discard. Polish this same character into a richer, colorful, coherent premium 2.5D app sticker: plump simple forms, clean smooth contours, soft volumetric shading, bright tasteful highlights, warm friendly expression, controlled saturated accents. Keep the defining silhouette, species, body proportions, facial design and original palette. Complete character, calm standing/sitting three-quarter pose as in reference, centered square composition, character occupies about 82% of canvas, ears/antenna/leaves/feet fully visible. Strong readable contour and a restrained pale rim for contrast on dark and light screens. True transparent RGBA outside the character. No floor or cast shadow, no circular badge, no scenery, no text, no watermark, no extra props, no extra characters, no cropped anatomy, no animation sheet. Refine material and lighting; retain the approved character identity.
Subject and identity constraints: Chester is the charcoal brown CAT in the reference (not the older fox). Keep rounded seated body, triangular ears with warm pink interiors, dark cocoa charcoal fur, curled short tail, large glossy eyes and small cute mouth, pink cheeks. Make highlights warm and clear enough for tiny sizes, with a subtle cream rim. Do not turn the fur white, orange, or add clothing.
```

### doc

```text
Use case: stylized-concept. Asset type: final STATIC transparent mascot illustration for the Android Clickn floating button, readable at 40–64 dp. Image 1 is the IDENTITY REFERENCE of the owner's current mascot, not a style to discard. Polish this same character into a richer, colorful, coherent premium 2.5D app sticker: plump simple forms, clean smooth contours, soft volumetric shading, bright tasteful highlights, warm friendly expression, controlled saturated accents. Keep the defining silhouette, species, body proportions, facial design and original palette. Complete character, calm standing/sitting three-quarter pose as in reference, centered square composition, character occupies about 82% of canvas, ears/antenna/leaves/feet fully visible. Strong readable contour and a restrained pale rim for contrast on dark and light screens. True transparent RGBA outside the character. No floor or cast shadow, no circular badge, no scenery, no text, no watermark, no extra props, no extra characters, no cropped anatomy, no animation sheet. Refine material and lighting; retain the approved character identity.
Subject and identity constraints: Doc is this small rounded ivory cream ROBOT, egg-like body, tiny ivory rounded arms, squat teal boots, short antenna with cyan round tip, compact dark navy visor with TWO SMALL ROUND CYAN EYES with white glints and a tiny cyan smile. Preserve the approved smaller rounded eyes and compact visor. Smooth away raster stair-stepping but preserve body shape and colors. No huge eyes, no tall eye outlines, no new robot parts or props.
```

### pancake

```text
Use case: stylized-concept. Asset type: final STATIC transparent mascot illustration for the Android Clickn floating button, readable at 40–64 dp. Image 1 is the IDENTITY REFERENCE of the owner's current mascot, not a style to discard. Polish this same character into a richer, colorful, coherent premium 2.5D app sticker: plump simple forms, clean smooth contours, soft volumetric shading, bright tasteful highlights, warm friendly expression, controlled saturated accents. Keep the defining silhouette, species, body proportions, facial design and original palette. Complete character, calm standing/sitting three-quarter pose as in reference, centered square composition, character occupies about 82% of canvas, ears/antenna/leaves/feet fully visible. Strong readable contour and a restrained pale rim for contrast on dark and light screens. True transparent RGBA outside the character. No floor or cast shadow, no circular badge, no scenery, no text, no watermark, no extra props, no extra characters, no cropped anatomy, no animation sheet. Refine material and lighting; retain the approved character identity.
Subject and identity constraints: Blinchik/Pancake is this thick golden pancake buddy, warm toasted golden top, pale creamy side, butter square on top, small rounded side arms, plump caramel brown oval feet, dark glossy eyes, small happy mouth and pink cheeks. Rich golden maple highlights and buttery glow. It must remain a pancake, not a bread roll or a pancake stack.
```

### raf

```text
Use case: stylized-concept. Asset type: final STATIC transparent mascot illustration for the Android Clickn floating button, readable at 40–64 dp. Image 1 is the IDENTITY REFERENCE of the owner's current mascot, not a style to discard. Polish this same character into a richer, colorful, coherent premium 2.5D app sticker: plump simple forms, clean smooth contours, soft volumetric shading, bright tasteful highlights, warm friendly expression, controlled saturated accents. Keep the defining silhouette, species, body proportions, facial design and original palette. Complete character, calm standing/sitting three-quarter pose as in reference, centered square composition, character occupies about 82% of canvas, ears/antenna/leaves/feet fully visible. Strong readable contour and a restrained pale rim for contrast on dark and light screens. True transparent RGBA outside the character. No floor or cast shadow, no circular badge, no scenery, no text, no watermark, no extra props, no extra characters, no cropped anatomy, no animation sheet. Refine material and lighting; retain the approved character identity.
Subject and identity constraints: Raf is this legless blue JELLY, a low round translucent droplet with curved little tip, sky blue body, soft darker blue rim, glossy dark round eyes, tiny smile and pink cheeks. Colorful aqua highlights and convincing soft gel volume. Absolutely NO legs, feet, shoes, hands, tail, bubble props, puddle, or external shadow. Keep compact original silhouette.
```

### lola

```text
Use case: stylized-concept. Asset type: final STATIC transparent mascot illustration for the Android Clickn floating button, readable at 40–64 dp. Image 1 is the IDENTITY REFERENCE of the owner's current mascot, not a style to discard. Polish this same character into a richer, colorful, coherent premium 2.5D app sticker: plump simple forms, clean smooth contours, soft volumetric shading, bright tasteful highlights, warm friendly expression, controlled saturated accents. Keep the defining silhouette, species, body proportions, facial design and original palette. Complete character, calm standing/sitting three-quarter pose as in reference, centered square composition, character occupies about 82% of canvas, ears/antenna/leaves/feet fully visible. Strong readable contour and a restrained pale rim for contrast on dark and light screens. True transparent RGBA outside the character. No floor or cast shadow, no circular badge, no scenery, no text, no watermark, no extra props, no extra characters, no cropped anatomy, no animation sheet. Refine material and lighting; retain the approved character identity.
Subject and identity constraints: Lola is this pink PEACH buddy with two green leaves and a tiny brown stem on top, plump soft peach body, small rounded arms and rose pink feet, large glossy dark eyes, little smile and warm pink cheeks. Preserve peach character silhouette and leaf arrangement. Rich coral pink to rosy blush shading and fresh green highlights. No hair, clothing, fruit basket, or props.
```

