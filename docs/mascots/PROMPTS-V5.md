# Ходьба v5: промпты и исходники

Встроенный imagegen, 2026-09-27. Режим: редактирование по двум референсам — последовательность поз прежней анимации и внешний вид нового героя. Из старого GIF взяты 10 фаз по 110 мс. Новые прозрачные атласы находятся в `sources-v5/`; каждая картинка содержит 5 × 2 полных позы. Старый персонаж не входит в ресурсы приложения. Для желешки сохраняется ползание без ног.

## mochi

[Исходный атлас](sources-v5/mochi-walk.png)

Use case: precise-object-edit.
Asset: transparent sprite atlas for a desktop pet, exactly FIVE columns by TWO rows, exactly TEN walking poses.
Input image 1 is the POSE AND MOTION TEMPLATE: ten numbered frames of a previous mascot, read left to right on the first row, then left to right on the second row. Copy its sequence of body directions, planted and lifted feet, front/back overlap, arm swing and gentle body bounce. It walks FORWARD toward screen RIGHT; it is NOT strafing or shuffling sideways.
Input image 2 is the CHARACTER IDENTITY AND RENDERING STYLE reference: replace the pink template character with this extremely cute compact charcoal kitten. Preserve the kitten's charcoal fur, tiny triangular pink-inner ears, huge dark shiny eyes, tiny pink mouth, round blushing cheeks, short tail, soft plush shading and warm thin outlines.
Generate the complete kitten in every cell, including large soft charcoal paws and short mitten arms. The body is a compact round bean, no human torso. Face and body aimed three-quarter RIGHT, eyes clustered toward the right/front side; tail at the LEFT/back. Legs move in ONE front/back lane under the body, each foot takes its turn ahead of the other. The near paw crosses IN FRONT of the belly in its forward swing, the far paw passes behind. Do NOT keep one foot permanently on the left and the other on the right of the body. No lateral side-steps. Use fairly large paws about one third the body's width, clear even at small sizes.
Match the TEN template phases exactly, including their order and which foot is planted or lifted. Keep kitten identity, body volume, head size, colors and lighting IDENTICAL across all ten frames. Paw SOLES FACE DOWN or away during walking: no pink paw-pad patterns shown to the viewer. Soft rounded paws, no shoes, no heels.
Each of the 10 cells is the SAME size with equal spacing and generous transparent gutters. Use the SAME ground baseline and body center registration in all cells; preserve only the intentional small body bob from the template. Feet and tail fit entirely inside their cells. Transparent alpha background. No ground shadow, no white backdrop, no boxes, no text, no labels, no numbers, no motion lines. Retain the kitten's soft illustrated rendering, NOT pixel art. No pink sphere/template character anywhere in output.

## pancake

[Исходный атлас](sources-v5/pancake-walk.png)

Use case: precise-object-edit.
Asset: transparent sprite atlas for a desktop pet, exactly FIVE columns by TWO rows, exactly TEN walking poses.
Input image 1 is the POSE AND MOTION TEMPLATE: ten numbered frames of a previous mascot, read left to right on the first row then left to right on the second row. Copy its sequence of body directions, planted and lifted feet, front/back overlap, arm swing and gentle body bounce. This is forward walking toward screen RIGHT, never lateral strafing or side-stepping.
Input image 2 is the CHARACTER IDENTITY AND SOFT ILLUSTRATED RENDERING reference. Replace the pink template character with this extremely cute single thick fluffy PANCAKE. Preserve the warm golden toasted top, pale cream side, little butter square, bead eyes, tiny w smile and rosy cheeks from image 2. A squat pancake, NOT a spherical bread roll. Use big rounded warm-brown feet and small golden mitten arms. Keep the butter and pancake thickness identical across all ten frames.
Generate the complete character in each cell. Face and body are three-quarter RIGHT, eyes clustered toward the right/front side. Legs move in ONE front/back lane beneath the body. Each foot takes its turn ahead of the other, the near foot swings IN FRONT of the belly while the far foot passes behind. Do NOT fix one foot permanently to the left and the other to the right of the body. Use feet about one third the body width, visible and expressive like the pose template. No skinny floating legs.
Match the TEN template poses and their order precisely, including the lifted forward foot in frame 8. Keep identity, body size and lighting consistent. The first and final frames must join into one coherent repeated cycle.
Every cell has the SAME dimensions and equal spacing, generous clear transparent gutters. The SAME ground baseline and body center registration across cells, except for the intentional small body bounce in the pose template. The ENTIRE figure including feet and antenna/leaves/butter fits within its cell.
Genuine transparent alpha, no shadows or floor, no labels, no grid, no numbers, no text, no motion lines. Keep the soft shaded cute illustration style of image 2, NOT pixel art. No pink template sphere character.

## momo

[Исходный атлас](sources-v5/momo-walk.png)

Use case: precise-object-edit.
Asset: transparent sprite atlas for a desktop pet, exactly FIVE columns by TWO rows, exactly TEN walking poses.
Input image 1 is the POSE AND MOTION TEMPLATE: ten numbered frames of a previous mascot, read left to right on the first row then left to right on the second row. Copy its sequence of body directions, planted and lifted feet, front/back overlap, arm swing and gentle body bounce. This is forward walking toward screen RIGHT, never lateral strafing or side-stepping.
Input image 2 is the CHARACTER IDENTITY AND SOFT ILLUSTRATED RENDERING reference. Replace the pink template character with this extremely cute blushing PINK PEACH. Preserve the pale blush pink center, rose-pink edges, subtle peach crease, short stem, two mint-green leaves, bead eyes, tiny w smile and rosy cheeks from image 2. It remains a peach, NOT an orange or yellow ball. Use big rounded dark-rose feet and small pale-pink mitten arms. Keep peach volume, stem and leaf design identical across all ten frames.
Generate the complete character in each cell. Face and body are three-quarter RIGHT, eyes clustered toward the right/front side. Legs move in ONE front/back lane beneath the body. Each foot takes its turn ahead of the other, the near foot swings IN FRONT of the belly while the far foot passes behind. Do NOT fix one foot permanently to the left and the other to the right of the body. Use feet about one third the body width, visible and expressive like the pose template. No skinny floating legs.
Match the TEN template poses and their order precisely, including the lifted forward foot in frame 8. Keep identity, body size and lighting consistent. The first and final frames must join into one coherent repeated cycle.
Every cell has the SAME dimensions and equal spacing, generous clear transparent gutters. The SAME ground baseline and body center registration across cells, except for the intentional small body bounce in the pose template. The ENTIRE figure including feet and antenna/leaves/butter fits within its cell.
Genuine transparent alpha, no shadows or floor, no labels, no grid, no numbers, no text, no motion lines. Keep the soft shaded cute illustration style of image 2, NOT pixel art. No pink template sphere character.

## orbit

[Исходный атлас](sources-v5/orbit-walk.png)

Use case: precise-object-edit.
Asset: transparent sprite atlas for a desktop pet, exactly FIVE columns by TWO rows, exactly TEN walking poses.
Input image 1 is the POSE AND MOTION TEMPLATE: ten numbered frames of a previous mascot, read left to right on the first row then left to right on the second row. Copy its sequence of body directions, planted and lifted feet, front/back overlap, arm swing and gentle body bounce. This is forward walking toward screen RIGHT, never lateral strafing or side-stepping.
Input image 2 is the CHARACTER IDENTITY AND SOFT ILLUSTRATED RENDERING reference. Replace the pink template character with this extremely cute ivory BABY ROBOT. Preserve the oversized ivory round helmet/body, wide glossy navy face screen, kind bright cyan eyes and smile, cyan side ear disks, short antenna and cyan antenna tip from image 2. Simple compact toy, no complex machinery. Use big rounded dark-teal feet and short ivory mitten arms. Keep all robot panels, proportions, antenna and colors identical across all ten frames.
Generate the complete character in each cell. Face and body are three-quarter RIGHT, eyes clustered toward the right/front side. Legs move in ONE front/back lane beneath the body. Each foot takes its turn ahead of the other, the near foot swings IN FRONT of the belly while the far foot passes behind. Do NOT fix one foot permanently to the left and the other to the right of the body. Use feet about one third the body width, visible and expressive like the pose template. No skinny floating legs.
Match the TEN template poses and their order precisely, including the lifted forward foot in frame 8. Keep identity, body size and lighting consistent. The first and final frames must join into one coherent repeated cycle.
Every cell has the SAME dimensions and equal spacing, generous clear transparent gutters. The SAME ground baseline and body center registration across cells, except for the intentional small body bounce in the pose template. The ENTIRE figure including feet and antenna/leaves/butter fits within its cell.
Genuine transparent alpha, no shadows or floor, no labels, no grid, no numbers, no text, no motion lines. Keep the soft shaded cute illustration style of image 2, NOT pixel art. No pink template sphere character.
