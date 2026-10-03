# Ходьба v8 по отдельным кадрам исходного GIF

Режим: встроенный imagegen, precise-object-edit. Каждый из десяти кадров обрабатывается отдельным запросом. В одном результате — четыре героя в одной и той же фазе (2 × 2: Блинчик, Моти, Момо, Орбит). Бубу остаётся безногой ползающей желешкой.

## Источник и воспроизведение

- Исходник: `docs/mascots/reference/original.gif`, восстановленный из прежней версии проекта; ранее локально находился в `.tmp/kirby-reference/original.gif`.
- [Метаданные источника](sources-v8/timeline.json): SHA-256, размер, границы и длительность каждого кадра.
- 10 кадров по 110 мс, полный цикл 1100 мс; дополнительные промежуточные кадры убраны.
- Прежний код использовал `QMovie` без изменения скорости. Текущий `PetMotion` повторяет независимый от размера и скорости перемещения тайминг.
- `tools/prepare_reference_walk.py` извлекает рисунки из прозрачных промежутков, использует один масштаб на весь цикл каждого героя и выравнивает регистрацию по метаданным исходника. Отдельные части тела не анимируются программно.
- `tools/compare_reference_walk.py` показывает исходник и четырёх героев синхронно. Есть пауза, шаг по кадрам и замедление. Оригинал остаётся материалом для локального сравнения; ресурсы приложения содержат новых героев.

[Синхронное сравнение](reference-comparison-v8.gif) · [Все кадры рядом](reference-poses-v8.png) · [Движение в приложении](motion-v8.gif)

## Кадр 00

[Итоговый атлас](sources-v8/frame-00.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame character replacement for a game walk cycle.
Image 1 is the ONLY POSE TEMPLATE: original animation frame 00. Image 2 is a 2x2 CHARACTER IDENTITY sheet, not a pose guide.
Create a transparent 2x2 sprite sheet, same cell order as image 2: upper-left golden pancake; upper-right charcoal kitten; lower-left pink peach; lower-right ivory baby robot.
All FOUR characters must exactly reproduce the ONE pose of image 1. This is one time instant, not four different animation phases.
POSE 00: three-quarter facing right; weight lowered, near mitten arm hanging low at the left side of body; large NEAR foot is a nearly horizontal oval planted directly below the lower-left/middle of body, tip pointing right. FAR foot is entirely hidden behind the body and near foot — do not invent a second visible shoe. Opposite arm mostly hidden on right edge. Body leans as in template; no raised foot.
Trace the pose geometry, hand location, sole angle, which limb overlaps which, and body yaw directly from image 1. Adapt only the body silhouette to each character: pancake stays squat/fluffy with butter; cat has ears/tail and charcoal paws with no pink pads; peach has leaves/stem; robot has antenna, navy face screen, cyan eyes and teal feet.
Keep the cute soft painted style, face designs, colors and details of image 2. Do not use the pink template character's face, skin, colors, pixel-art style.
Every cell must be equally sized with fixed registration: body center at x=50 percent of its cell; soles at y=90 percent. Same character sizes as image 2 relative to each cell. Full character, generous transparent gutters, no cropping. Genuine transparent alpha. No background, no grid lines, no labels, no text, no shadow, no motion lines. Exactly FOUR figures in a 2x2 grid.
This output is FRAME 00 of 10; no improvisation of motion.
```
## Кадр 01

[Итоговый атлас](sources-v8/frame-01.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 01 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: NEAR foot planted broad and low under LEFT/middle body, slightly angled down toward the right; FAR foot has just become visible low on the RIGHT behind the belly, partly occluded. Near hand hangs down at lower-left/front, slightly forward from frame 00. Face turns a little more right.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```
## Кадр 02

[Итоговый атлас](sources-v8/frame-02.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 02 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: NEAR foot sweeps backward to the LEFT and tilts diagonally downward toward RIGHT; FAR foot extends forward to the RIGHT but stays behind the belly, pointing upper-right. Near arm swings FORWARD across the belly; hand center approximately horizontal center of torso and below cheek. Body rises and turns closer to RIGHT PROFILE. Eyes clustered narrowly along RIGHT edge.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```
## Кадр 03

[Итоговый атлас](sources-v8/frame-03.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 03 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: Extreme RIGHT PROFILE and highest passing pose. Near/back foot is at far LEFT under rear of body, tilted about 50 degrees DOWN toward right; FAR/front foot projects out to RIGHT behind body, tilted UP toward right. Opposing legs make the exact open stride silhouette in template. Near mitten arm is raised FORWARD, curled across the belly at midheight, almost horizontal, hand tip to right. Face near full profile: one dominant eye plus only a narrow sliver of farther eye at right silhouette. Copy this yaw!
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```
## Кадр 04

[Итоговый атлас](sources-v8/frame-04.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 04 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: FAR/front foot lands out ahead to screen RIGHT, horizontal on floor; NEAR/back foot remains at LEFT, steep and almost vertical, toes pushing off behind. Feet widely separated exactly as template. Near hand is still forward across lower-front belly but begins dropping. Body in strong right-facing three-quarter view with eyes close to right edge.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```
## Кадр 05

[Итоговый атлас](sources-v8/frame-05.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 05 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: NEAR foot lifts from rear and begins passing forward, visible at lower LEFT/middle IN FRONT of the belly, slightly airborne and tilted UP toward RIGHT. FAR support foot stays low at RIGHT partly hidden behind body. This is NOT a copy of frame 00: near sole is above far sole. Near arm returns downward at LEFT side; body turns toward viewer while still facing right.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```
## Кадр 06

[Итоговый атлас](sources-v8/frame-06.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 06 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: NEAR foot passes beneath body lifted clear of the ground IN FRONT of belly: a broad horizontal oval at lower MIDDLE, slightly forward. FAR planted foot sits underneath and behind it, lower and slightly right, partly occluded. Near arm swings BACK toward screen LEFT and out from side, hand down. Face turns toward viewer/right three-quarter. No duplicated shoe: precisely template overlap.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```
## Кадр 07

[Итоговый атлас](sources-v8/frame-07.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 07 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: NEAR foot swings forward to screen RIGHT, raised IN FRONT of lower belly and angled upward toward right about 25 degrees. FAR supporting foot is lower/back LEFT, partly hidden under belly. Near arm extends BACK to screen LEFT slightly raised. Face is more toward viewer than frames 2-4. Exact overlap and silhouette from template.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```

### Уточнение

```text
Use case: precise-object-edit. Image 1 is the edit target (frame 07, four mascots in a 2x2 transparent atlas). Image 2 is pose reference only. Edit ONLY the charcoal kitten in the TOP-RIGHT cell. It accidentally has TWO near-side arms: one extending backward at the upper-left side, and a second hanging over the lower-front belly. REMOVE the lower-front hanging duplicate arm completely, restoring uninterrupted charcoal body texture there. KEEP the upper-left/backward extending arm, tail, far arm if visible, and both feet. The desired pose is image 2: near arm extending back left, near foot raised forward right. All three other characters stay exactly unchanged. No new appendages. Keep all figure sizes, grid cell positions, color, texture, face, body shape, top accessories and feet exactly unchanged. Change only specified duplicate arms. Preserve alpha transparency. No background, text or shadows.
```

### Уточнение

```text
Use case: precise-object-edit. Image 1 is the target: one animation frame, four mascots in a 2x2 transparent grid. Image 2 is the exact original pose guide for the same frame. Correct the NEAR ARM in ALL FOUR cells to match image 2 exactly. The near arm should be a full-size soft mitten extending diagonally DOWN-LEFT from the left side of the torso, at roughly 45 degrees downward from horizontal left. Its rounded hand tip is below the shoulder, around two thirds of the way down the torso. It is NOT a tiny round knob held straight sideways beside the eye. Pancake, cat and peach currently have that tiny high round knob: replace it with the proper down-left mitten swing. For the robot, swing its existing hand backward LEFT below the ear, instead of hanging in front of its belly. Replace the old arm, do NOT add a second arm. Cat's tail behind its arm remains intact. Keep the forward raised RIGHT foot and both feet exactly unchanged. Do not change anything except specified arms. Keep body shape and rotation, face, feet, camera, scale, cell layout, registration, colors and texture. Same dimensions and transparent alpha background. No extra limbs, no shadows, no text.
```
## Кадр 08

[Итоговый атлас](sources-v8/frame-08.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 08 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: Largest forward lift. NEAR foot is on RIGHT in front of belly, steeply raised about 50 degrees UP toward RIGHT; FAR support foot remains on floor at lower LEFT behind body. Near arm stretches BACK LEFT almost horizontally; opposite arm at right side is visible. Body faces three-quarter right but nearly frontal, eyes spaced wider than profile frames. Copy original foot angles exactly.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```

### Уточнение

```text
Use case: precise-object-edit. Image 1 is the target: one animation frame, four mascots in a 2x2 transparent grid. Image 2 is the exact original pose guide for the same frame. Edit ONLY the ROBOT in the LOWER-RIGHT cell: its NEAR ARM is missing. Add exactly one short ivory mitten arm extending BACK toward screen LEFT, attached just below the left cyan ear, extending leftward and slightly down, exactly like image 2's near arm. The rounded hand must be visibly left of the robot body silhouette. Keep the existing far arm on RIGHT edge, so robot has exactly two arms. Preserve ALL other characters exactly unchanged. Preserve robot antenna, ear, face screen, body, raised near RIGHT foot, planted back LEFT foot and their positions exactly. Do not change anything except specified arms. Keep body shape and rotation, face, feet, camera, scale, cell layout, registration, colors and texture. Same dimensions and transparent alpha background. No extra limbs, no shadows, no text.
```
## Кадр 09

[Итоговый атлас](sources-v8/frame-09.png)

```text
Use case: precise-object-edit.
Task: exact frame-by-frame replacement, animation FRAME 09 of 10.
Image 1 is the SINGLE EXACT POSE TEMPLATE for this frame. Image 2 is CHARACTER IDENTITY / STYLE / SCALE ONLY, four characters in a 2x2 grid in their frame 00 pose. Do NOT copy the pose of image 2. Replace its pose with image 1 for ALL four characters.
Output exactly FOUR figures in a transparent TWO BY TWO sheet: top-left pancake, top-right charcoal cat, bottom-left pink peach, bottom-right ivory robot, matching image 2 exactly in identity/colors/proportions/art style.
Every figure must take the SAME one pose of image 1, at the SAME time instant. Exactly reproduce body yaw, hand gesture and location, front/back foot identity, which sole is planted, foot angles, and occlusion from this single source frame. No invented walk.
Pose specifics: NEAR/front foot has JUST LANDED far forward on screen RIGHT, broad horizontal oval on the floor, fully visible IN FRONT of lower-right belly. FAR/back foot is at lower LEFT behind body, slightly lifted/tilted and partly hidden. Do NOT put near/front foot at lower-left as in identity frame 00. Near hand is descending at LEFT side, body preparing return to frame 00. This foot swap is essential.
NEAR means the limb on the viewer's side, which may move left or right during the step. FAR means behind the body. Large rounded feet follow the exact template. Keep any feet hidden exactly where they are hidden in the template. No pink sole pads for the cat; all paws/feet retain character colors.
Retain body shape: pancake squat with butter; cat round with ears/tail; peach round with stem/leaves; robot round with antenna and screen. Reproduce small vertical body rise of the template without changing body volume. Facial features rotate WITH body to the template yaw. Do not keep a static three-quarter face if the template is in profile.
Same rendering and scale as image 2; same 2x2 grid layout. Each cell's center x=50%, planted sole baseline y=90%, clear gutters and complete uncut figure. Transparent alpha background. No labels, numbers, grid borders, shadows, floor or motion lines. No pink template mascot in output. This is one frame, not a four-frame sequence.
```

### Уточнение

```text
Use case: precise-object-edit. Image 1 is the edit target (frame 09, four mascots in a 2x2 transparent atlas). Image 2 is pose reference only. Remove only DUPLICATE ARMS in three characters. Pancake (top-left): keep its main hanging near arm and the far arm on RIGHT edge; remove the extra tiny arm behind the main near arm on LEFT edge. Peach (bottom-left): keep the main hanging near arm and far arm on RIGHT edge; remove the extra little arm behind it on LEFT edge. Robot (bottom-right): keep the main round hanging near hand below the ear and the far right hand if visible; remove the second small ivory hand behind the near hand at the LEFT edge. Kitten stays exactly unchanged — its back tail is correct. Preserve the important foot pose: large NEAR foot planted on the RIGHT, smaller FAR foot behind at lower LEFT. Do not move ANY feet or faces. Keep all figure sizes, grid cell positions, color, texture, face, body shape, top accessories and feet exactly unchanged. Change only specified duplicate arms. Preserve alpha transparency. No background, text or shadows.
```
