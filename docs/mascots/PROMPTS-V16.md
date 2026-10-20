# Покадровая перерисовка v16

12 октября 2026. Режим: встроенный imagegen, прозрачные PNG. Исходный GIF задаёт десять поз, порядок и длительность кадров (110 мс). Каждый герой нарисован полными кадрами на общем листе; проблемные кадры дополнительно отредактированы отдельно. Это художественная перерисовка по позам, а не пиксельная копия исходника.

## Итоги и файлы

- `sources-v16/reference-atlas.png` и `reference-00.png` … `reference-09.png`: шаблоны из исходного GIF.
- `sources-v16/pancake-sheet-yaw.png`, `mochi-sheet.png`, `momo-sheet.png`, `orbit-sheet.png`: четыре шагающих героя.
- `sources-v16/bubu-sheet-spaced.png`: отдельный цикл ползания без ног и прыжков.
- `sources-v16/last-cel-fixed.png`: исправление руки Блинчика и Момо в кадре 09; клетки Моти и Орбита из этой правки не применяются.
- `sources-v16/feet-correction-fixed.png`: исправление стоп Орбита в кадре 06 и дальнего ботинка Блинчика в кадре 07.
- `sources-v16/orbit-ground-fixed.png`: дополнительная правка опоры Орбита в кадре 06.
- `src/icons/desktop-assistant/<герой>/walk-redrawn-frames/00.png` … `09.png`: итоговые кадры приложения с полным альфа-каналом.
- `src/icons/desktop-assistant/<герой>/walk-redrawn.gif`: отдельный GIF для просмотра.
- [Сравнение с оригиналом](redrawn-v16/comparison.gif), [все позы](redrawn-v16/poses.png), [движение всех пяти героев](motion-v16.gif).

Для подготовки ресурсов: `python tools/prepare_redrawn_walk.py --apply-corrections --pack pancake mochi bubu momo orbit`. Рисунки не генерируются повторно: скрипт разделяет листы и использует сохранённые правки. Масштаб один на весь цикл каждого героя, позиция целого кадра выравнивается по опоре. Параметры сохранены в `sources-v16/*-registration.json`.

## Поиск готовых инструментов

- [EbSynth](https://ebsynth.com/): перенос перерисованных ключевых кадров по движению видео. По официальной странице PNG с прозрачностью доступен в Pro; Free экспортирует MP4. Не подключался и не покупался.
- [Aseprite](https://www.aseprite.org/docs/animation/): покадровая работа, слои, настройка длительности и onion skin (полупрозрачный предыдущий кадр). Для текущего просмотра эти нужные функции добавлены в наш Qt-инструмент сравнения.
- В каталоге плагинов найдены Runway и Higgsfield, но подключения к ним нет. Для этого варианта использован встроенный imagegen; перенос точных спрайтов через видеогенераторы не выполнялся.

## Общий промпт для четырёх шагающих героев

```text
Use case: precise-object-edit.
Task: frame-by-frame rotoscoped replacement of an existing TEN-FRAME walk-cycle sprite sheet.
Image 1 is the exact POSE AND REGISTRATION TEMPLATE, a 5-column by 2-row sprite sheet with ten sequential walk poses. Image 2 is the CHARACTER IDENTITY reference only.
Replace the pink template character in EVERY ONE of the ten cells with the character from image 2. Draw the entire complete character in each cel, with organic overlap of limbs and body. Match image 1's individual pose geometry extremely closely: body yaw, body rise, torso lean, which foot is planted, direction and tilt of each shoe, exact hand swing, and which limb portions are hidden by the belly.
Do not invent or rearrange the walk. Do not output a turnaround or a row of similar standing poses. It must be the ten DIFFERENT sequential poses in the same cell order as image 1.
The NEAR limb always keeps its identity: it is on the viewer's side whether it swings forward/right or backward/left. Do not swap the feet between frames.
Top row poses 0–4: near shoe starts planted underneath the left/middle, slides BACKWARD on the ground toward the left as the body advances; by cell 2 it is diagonal, by cells 3 and 4 it is the rear shoe at the LEFT partially BEHIND the belly. Meanwhile far shoe swings forward to the RIGHT behind the torso and lands in cell 4. Near arm swings forward across belly, highest in cell 3.
Bottom row poses 5–9: near shoe lifts, swings FORWARD from left to right across the front of the belly, diagonal upward-right in cells 7/8, then plants low at the RIGHT in cell 9. Far foot is planted behind and moves backward from right to left. Near arm swings backward toward left. Cell 9 must lead naturally into cell 0: same character dimensions and a continuous step, no end pose.
Preserve the TEMPLATE foot silhouettes and silhouette overlaps: plump large oval feet with a domed top and visible rounded lower side; no thin disks, no sticks for legs, no wedge cutouts through the middle of a boot. Arms are short soft rounded volumes attached organically to the torso.
CRITICAL REGISTRATION: exact 5 columns x 2 rows, TEN complete sprites total, all square cells of equal size, wide landscape 5:2 canvas (ideally 2560 by 1024). Same shared ground baseline and same shared fixed scale across ALL ten cells. The character may bob/turn only as in the pose template. Preserve head size, limb volume, line weight, face size, palette and lighting across all ten poses. Do not individually center or auto-fit each pose. Keep ample clear transparent gutters, no sprite touching the neighboring cell.
Use the appealing illustrated character style of image 2: clean readable contours, softly shaded volume, consistent warm light from upper-left. This is a finished hand-drawn sprite sequence, not a 3D rig or cutout puppet.
TRUE transparent RGBA background. No floor, cast shadow, labels, numbers, frame borders, grid lines or text. No pink template character left anywhere. Draw each frame deliberately; the body and feet must NOT randomly grow or shrink.
```

## Блинчик

```text
К общему промпту добавлено:
Character: our cute golden fluffy PANCAKE with a small consistent pat of butter on top, creamy sides and golden brown cooked top, tiny black shiny eyes, pink cheeks and a tiny cute mouth. Keep its body thick, round and plump in profile, not a thin plate. Creamy short rounded mitten arms. Two LARGE caramel-brown oval feet matching the template's volume and posing. Preserve the identity of image 2, while allowing the torso to be a little rounder to retain the pose template's weight and foot connections. No Kirby face or pink skin.
```

## Моти

```text
К общему промпту добавлено:
Character: our cute chubby charcoal-gray CAT MOCHI in image 2. Soft round charcoal body, small triangular cat ears with pale pink inner fur, large shiny black eyes, pink cheeks and a tiny pink cat mouth, small round tail at back/left. Short plump charcoal mitten forepaws and large oval CHARCOAL back paws follow the exact arms and feet of the pose template. No pink paw pads or human feet, no white belly, no long thin legs. Keep ears and tail consistent and attached while following the body's turning perspective. The background must remain fully transparent.
STRICT TURN: top-row columns 3 and 4 are almost RIGHT PROFILE, eyes cluster very close to the right contour; top-row column 5 begins turning back. Bottom row shows the return to three-quarter. Follow this difference visibly, do not keep every face in the same three-quarter view.
```

## Момо

```text
К общему промпту добавлено:
Character: our cute peach MOMO from image 2, plump pale pink peach body, stronger rosy pink along the sides and limbs, small consistent brown stem and two green leaves on top, glossy black eyes, tiny mouth and pink cheeks. Short rounded rosy mitten arms, large oval deep rosy feet. Preserve the peach cleft and leaf proportions, with a stable face and body size. No butter, cat ears, robot parts or template pink character. Match every exact source pose.
STRICT TURN: top-row columns 3 and 4 are almost RIGHT PROFILE, eyes cluster very close to the right contour; top-row column 5 begins turning back. Bottom row shows the return to three-quarter. Follow this difference visibly, do not keep every face in the same three-quarter view.
```

## Орбит

```text
К общему промпту добавлено:
Character: our cute ivory round ROBOT ORBIT from image 2. Creamy round shell, dark navy oval face screen, two cyan glowing round eyes and tiny cyan smile, small consistent top antenna with cyan tip, one round side ear port. Short stubby ivory mittens and big rounded teal-blue feet; no long thin mechanical rods. The face screen must turn in perspective WITH the torso, becoming narrow and near the right silhouette in top-row cells 2–4 as the source template turns toward profile. Keep antenna and screen shape and material consistent; no random accessories or extra limbs.
STRICT TURN: top-row columns 3 and 4 are almost RIGHT PROFILE, eyes cluster very close to the right contour; top-row column 5 begins turning back. Bottom row shows the return to three-quarter. Follow this difference visibly, do not keep every face in the same three-quarter view.
```

## Поворот Блинчика

```text
Use case: precise-object-edit. Image 1 is the EDIT TARGET: a 5-column x 2-row ten-frame pancake walk cycle. Image 2 is the EXACT POSE template from the original walk.
Preserve all ten cells, all foot shapes and foot positions, hand drawing, identity, butter, size, transparent background and overall clean style of image 1. Only correct the insufficient TORSO/HEAD TURN in top-row columns 3, 4 and 5 (animation frames 02,03,04), using corresponding cells in image 2.
In top row column 3 the pancake turns significantly to the RIGHT, and in column 4 it is almost right profile: eyes are clustered along the rightmost contour, the far eye is foreshortened into a narrow oval, cheek and mouth rotate with the torso; the visible cooked top and butter also change perspective naturally with this yaw. In column 5 the face begins returning to three-quarter. Keep the pancake thick and plump in profile. All other seven cells retain the exact same artwork.
Do not redraw or move feet, do not change ground registration, scale, body height, hand silhouettes, number of cells, or crop the canvas. Preserve continuity of the 10-frame cycle. No new shadows, no labels, no background, no pixel template character. True RGBA transparency.
```

## Ползание Бубу

```text
Use case: precise-object-edit.
Create a complete TEN-FRAME hand-drawn sprite sheet for the SAME cute blue JELLY BUBU as the attached identity reference. Preserve its pale translucent blue soft jelly material, darker blue rim, large glossy black eyes, tiny cute mouth, pink cheeks, curved top tip and sparse broad soft highlights.
Animation: a smooth low CRAWL toward the right. The jelly has NO legs, feet, arms or shoes. It NEVER jumps, hops, floats or leaves the floor. The broad lower skirt stays in contact with one common baseline in ALL ten cels.
Lay out EXACTLY TEN sprites in FIVE columns and TWO rows on a wide 5:2 canvas, equal SQUARE cells, chronological left-to-right in each row. Fixed camera, fixed overall scale, same body volume, palette, face size, contour weight and lighting.
The cycle goes from a compact droplet through a gentle forward stretch to a rear catch-up. Top row 0: compact rounded rest-between-crawls, 1: right/front edge begins extending, 2: visibly wider/lower, 3: front extends farther right while rear stays planted, 4: widest/lowest pose (only 12% wider than frame 0). Bottom row 5: rear/left skirt begins sliding forward while right/front remains planted, 6: rounded body catches up with a small wave flowing through the upper tip, 7: nearly compact, 8: compact and very slightly taller, 9: settles toward the same shape as frame 0 so the loop is seamless. No blink or sudden facial expression during this locomotion.
Illustrate the differences as small natural volume-preserving deformations in a single coherent animation; NOT ten duplicate standing blobs. Do not shift the entire body up or down. Do not make the legs from another mascot, or a long slug tail. No expanding puddle trail, floor, ground shadow, motion marks or text.
All ten sprites fully visible, ample empty transparent gutters between cells. Genuine transparent RGBA outside each jelly. Clean antialiased edges; no checkerboard background. The design must remain cute, clearly legless and grounded.
```

## Поля и прозрачность Бубу

```text
Use case: precise-object-edit. Edit the attached 5-column x 2-row TEN-FRAME jelly crawl sprite sheet.
Keep the EXACT SAME jelly character and the SAME ten poses in the SAME cell order, facial expression, material and color. Fix only the cramped layout and dirty transparency.
Each of the 10 cells must have generous completely clear gutters, with at least 12 percent of each cell width as empty transparent margin on BOTH left and right. Uniformly scale ALL TEN jelly drawings to 75 percent of their current size without changing any individual shape or the size relationships between poses. No jelly can touch or cross a cell boundary. Retain one consistent baseline at 88 percent of each cell height in BOTH rows, with feet-free lower skirts resting on that line. This is a 5-by-2 grid of equal square cells on a 5:2 landscape canvas.
Remove ALL detached blue speckles, smoke, stray particles and ghost patches between the sprites. Outside the silhouette of each jelly, the image must have exactly empty alpha. Inside the jelly retain its soft light-blue material and gentle painted shading.
No legs, feet, arms, shoes, jumps, motion blur, background, labels, grid, shadows or drawn floor. Keep the 10-frame crawl and loop identical; only make space around the intact drawings and provide clean transparent gutters.
```

## Руки в кадре 09

```text
Use case: precise-object-edit.
Image 1 is the EDIT TARGET, a 2x2 sheet: pancake at top left, cat at top right, peach at bottom left, robot at bottom right. These are animation frame 09. Image 2 shows the same heroes in animation frame 00 and is an ARM-POSE reference. Image 3 is the precise original frame 09 pose template.
Change ONLY the near/viewer's-side LEFT ARM of the pancake (top-left cell) and the peach (bottom-left cell) in image 1. Their arm currently sticks backward and sideways too much, causing a jerk at the loop. Make it hang DOWN alongside the left belly, a rounded soft mitten descending from the same shoulder, just slightly angled backward. Use the arm pose and silhouette of the corresponding hero in image 2 and the arm position from image 3. It should be almost in the rest/down position when the loop returns to frame 00.
The cat and robot cells remain EXACTLY untouched. Every other part of pancake and peach remains EXACTLY untouched: especially their body outline, face, butter/leaves, feet and feet positions, colors, size, floor level, image registration, far arm and transparent surroundings.
Do not move or resize any character. Do not copy the FEET or BODY PLACEMENT from image 2; image 2 only guides the two near arms. Keep the 2x2 800x800 composition. Preserve full transparency and style. No extra objects, no background.
```

## Стопы в кадрах 06 и 07

```text
Use case: precise-object-edit.
Image 1 is the EDIT TARGET: TWO equal square cells side by side, robot on left and pancake on right. Preserve this exact composition, each body/face/arm position and all style/scale details.
Images 2 and 3 are precise pose templates for the LEFT and RIGHT cells respectively.
LEFT ROBOT = walk frame 06, template image 2. Correct ONLY the two teal feet. The NEAR foot is currently too far to the right and too steep: place it under the LEFT/MIDDLE of the belly, a broad oval nearly horizontal, very slightly tilted up toward the right, lifted just a little above the other foot. The FAR foot stays behind, planted lower and slightly to the RIGHT, partly hidden by the near shoe. Match the relative centers, silhouettes, layering, angles and lift from image 2. These are plump short attached feet, no shins or floating parts. Keep the robot BODY, ARMS, FACE, EAR PORT and ANTENNA completely unchanged.
RIGHT PANCAKE = walk frame 07, template image 3. Correct ONLY the far/back brown foot. It currently reads as a duplicate concentric outline wrapped around the near foot. Make it a distinct flatter oval peeking out BELOW AND TO THE LEFT of the raised near shoe, directly beneath the belly, planted on the same baseline. Use image 3's foot overlap: front shoe angled upward-right, back shoe mostly horizontal beneath-left. Keep the existing NEAR foot outline, position and size intact except eliminating the redundant duplicate crescent line. Do not change the pancake BODY, ARMS, BUTTER, FACE or cell placement.
No other edits. Preserve the exact 2x1 layout and fixed scale. True transparent RGBA background, no new shadows, marks, limbs or text. Draw the two corrected foot pairs as clean coherent forms with correct occlusion.
```

## Опора Орбита

```text
Use case: precise-object-edit.
This is ONE animation cel of our robot. Preserve the exact square canvas, all transparent margins, robot size, head, antenna, face, body outline, ears, arms, colors and ALL pixels above the lower belly.
Only adjust the vertical placement of the TWO blue feet to correct ground contact. Move BOTH feet downward by 4 percent of canvas height (16 pixels in this 396x397 reference), without changing their horizontal positions, rotation, size, shape, material, outline or overlap with one another. The lower far foot should reach a baseline at 90 percent of canvas height. The higher near foot remains about 4 percent of canvas height above that baseline.
Keep each foot attached under the belly by preserving its root behind the body; no visible skinny legs. Fill the tiny exposed old foot area with the continuing cream belly or transparency as appropriate. The head/body/arms MUST stay exactly at their current coordinates, unchanged in size. Do not reframe, recenter, crop, zoom, recolor or redraw the rest of the character. One transparent RGBA sprite, no background or shadow.
```
