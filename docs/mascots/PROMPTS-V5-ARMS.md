# Переходы рук v5

Встроенный imagegen, режим precise-object-edit. Добавлены две полные промежуточные позы между кадрами 04–05 и 08–09. Десять исходных кадров v5 сохранены; промежутки по 110 мс разделены на 60 и 50 мс, полный цикл остаётся 1,1 секунды. Ресурсы упаковывает `tools/prepare_walk_cycles.py`.

Референсы — кадры 4, 5, 8, 9 из соответствующего атласа [sources-v5](sources-v5/), собранные в сетку 2 × 2. Новые атласы: [sources-v5-arms](sources-v5-arms/).

## pancake

[Итоговый атлас](sources-v5-arms/pancake-inbetweens.png)

### Первый промпт

```text
Use case: precise-object-edit.
Asset: two missing in-between frames for an existing ten-frame desktop mascot walk.
Reference image is a TWO BY TWO grid of FOUR EXISTING POSES of the single thick golden pancake with cream side, butter square, brown feet, small golden mitten arms. Top row is frames 4 and 5. Bottom row is frames 8 and 9. Read each row left to right.
Generate exactly TWO NEW COMPLETE POSES in ONE HORIZONTAL ROW with TWO equal square cells and transparent background.
LEFT output cell: the precise halfway in-between of the TWO TOP reference poses. RIGHT output cell: halfway in-between of the TWO BOTTOM reference poses.
Primary correction: the NEAR ARM (left side of the screen) snaps between those reference poses. Draw its hand halfway between the reference hand positions, with a natural attached shoulder and intermediate angle/gesture. Both feet should also be a single coherent halfway walking pose, one foot supporting weight; NEVER duplicate or overlay feet. Each new pose has exactly two feet and two arms.
Preserve the reference character identity, compact body volume, palette, face, proportions and soft shaded illustration style extremely closely. The new poses will be inserted between UNCHANGED reference frames, so they must match. Eyes, cheeks, markings and top accessories must stay stable. Facing three-quarter screen RIGHT, same as reference. Very small body bob halfway between endpoints. No redesign.
Keep character at the same uniform scale in both cells, baseline at 92 percent cell height, centered horizontally, generous transparent gutters. Show the entire character. Genuine transparent alpha. No ground shadow, no background, no outlines around cells, no text, no labels, no trails, no extra poses. Exactly TWO cells in a single row.
```

## mochi

[Итоговый атлас](sources-v5-arms/mochi-inbetweens.png)

### Первый промпт

```text
Use case: precise-object-edit.
Asset: two missing in-between frames for an existing ten-frame desktop mascot walk.
Reference image is a TWO BY TWO grid of FOUR EXISTING POSES of the compact charcoal kitten with pink inner ears, tail, dark paws, charcoal mitten arms and no visible pink foot pads. Top row is frames 4 and 5. Bottom row is frames 8 and 9. Read each row left to right.
Generate exactly TWO NEW COMPLETE POSES in ONE HORIZONTAL ROW with TWO equal square cells and transparent background.
LEFT output cell: the precise halfway in-between of the TWO TOP reference poses. RIGHT output cell: halfway in-between of the TWO BOTTOM reference poses.
Primary correction: the NEAR ARM (left side of the screen) snaps between those reference poses. Draw its hand halfway between the reference hand positions, with a natural attached shoulder and intermediate angle/gesture. Both feet should also be a single coherent halfway walking pose, one foot supporting weight; NEVER duplicate or overlay feet. Each new pose has exactly two feet and two arms.
Preserve the reference character identity, compact body volume, palette, face, proportions and soft shaded illustration style extremely closely. The new poses will be inserted between UNCHANGED reference frames, so they must match. Eyes, cheeks, markings and top accessories must stay stable. Facing three-quarter screen RIGHT, same as reference. Very small body bob halfway between endpoints. No redesign.
Keep character at the same uniform scale in both cells, baseline at 92 percent cell height, centered horizontally, generous transparent gutters. Show the entire character. Genuine transparent alpha. No ground shadow, no background, no outlines around cells, no text, no labels, no trails, no extra poses. Exactly TWO cells in a single row.
```

### Точная поправка руки

```text
Use case: precise-object-edit.
Input image 1 is the EDIT TARGET: a two-cell transparent sprite strip. Input image 2 is reference only, four original walk poses.
In the LEFT cell ONLY, move the near hand LEFT by roughly half its own width from the current position, with a slightly more downward hand angle. It must be halfway between the hand positions of the two TOP poses in image 2. The palm center should be approximately 30 percent of body width from left body edge. Current left pose hand is still too far forward/right, almost identical to the top-left endpoint. Preserve the RIGHT output cell exactly.
Change ONLY that one arm's position and the tiny exposed patch of body behind its old position. Keep the body, eyes, cheeks, mouth, feet, top accessories, scale, cell registration, colors, texture and every other part exactly the same. The two cells must stay aligned exactly as image 1. Do not add or move feet. Exactly two complete characters in one row on transparent alpha. No background, no shadow, no labels.
```

## momo

[Итоговый атлас](sources-v5-arms/momo-inbetweens.png)

### Первый промпт

```text
Use case: precise-object-edit.
Asset: two missing in-between frames for an existing ten-frame desktop mascot walk.
Reference image is a TWO BY TWO grid of FOUR EXISTING POSES of the round pink peach with two leaves, a stem, rose feet and pale pink mitten arms. Top row is frames 4 and 5. Bottom row is frames 8 and 9. Read each row left to right.
Generate exactly TWO NEW COMPLETE POSES in ONE HORIZONTAL ROW with TWO equal square cells and transparent background.
LEFT output cell: the precise halfway in-between of the TWO TOP reference poses. RIGHT output cell: halfway in-between of the TWO BOTTOM reference poses.
Primary correction: the NEAR ARM (left side of the screen) snaps between those reference poses. Draw its hand halfway between the reference hand positions, with a natural attached shoulder and intermediate angle/gesture. Both feet should also be a single coherent halfway walking pose, one foot supporting weight; NEVER duplicate or overlay feet. Each new pose has exactly two feet and two arms.
Preserve the reference character identity, compact body volume, palette, face, proportions and soft shaded illustration style extremely closely. The new poses will be inserted between UNCHANGED reference frames, so they must match. Eyes, cheeks, markings and top accessories must stay stable. Facing three-quarter screen RIGHT, same as reference. Very small body bob halfway between endpoints. No redesign.
Keep character at the same uniform scale in both cells, baseline at 92 percent cell height, centered horizontally, generous transparent gutters. Show the entire character. Genuine transparent alpha. No ground shadow, no background, no outlines around cells, no text, no labels, no trails, no extra poses. Exactly TWO cells in a single row.
```

### Точная поправка руки

```text
Use case: precise-object-edit.
Input image 1 is the EDIT TARGET: a two-cell transparent sprite strip. Input image 2 is reference only, four original walk poses.
In the LEFT cell ONLY, move the near arm/hand from the outer LEFT silhouette onto the LOWER FRONT belly, closer to the rosy cheek. It must be halfway between the hand positions of the two TOP poses in image 2. The palm center needs to sit at approximately 38 percent of the peach body width measured from the left body edge, below the left rosy cheek, with the rounded hand hanging diagonally down. Current left arm sticks out sideways much too far left. Right output cell is already correct: preserve it exactly.
Change ONLY that one arm's position and the tiny exposed patch of body behind its old position. Keep the body, eyes, cheeks, mouth, feet, top accessories, scale, cell registration, colors, texture and every other part exactly the same. The two cells must stay aligned exactly as image 1. Do not add or move feet. Exactly two complete characters in one row on transparent alpha. No background, no shadow, no labels.
```

## orbit

[Итоговый атлас](sources-v5-arms/orbit-inbetweens.png)

### Первый промпт

```text
Use case: precise-object-edit.
Asset: two missing in-between frames for an existing ten-frame desktop mascot walk.
Reference image is a TWO BY TWO grid of FOUR EXISTING POSES of the ivory round baby robot with navy face screen, cyan eyes, cyan antenna, blue feet and ivory mitten arms. Top row is frames 4 and 5. Bottom row is frames 8 and 9. Read each row left to right.
Generate exactly TWO NEW COMPLETE POSES in ONE HORIZONTAL ROW with TWO equal square cells and transparent background.
LEFT output cell: the precise halfway in-between of the TWO TOP reference poses. RIGHT output cell: halfway in-between of the TWO BOTTOM reference poses.
Primary correction: the NEAR ARM (left side of the screen) snaps between those reference poses. Draw its hand halfway between the reference hand positions, with a natural attached shoulder and intermediate angle/gesture. Both feet should also be a single coherent halfway walking pose, one foot supporting weight; NEVER duplicate or overlay feet. Each new pose has exactly two feet and two arms.
Preserve the reference character identity, compact body volume, palette, face, proportions and soft shaded illustration style extremely closely. The new poses will be inserted between UNCHANGED reference frames, so they must match. Eyes, cheeks, markings and top accessories must stay stable. Facing three-quarter screen RIGHT, same as reference. Very small body bob halfway between endpoints. No redesign.
Keep character at the same uniform scale in both cells, baseline at 92 percent cell height, centered horizontally, generous transparent gutters. Show the entire character. Genuine transparent alpha. No ground shadow, no background, no outlines around cells, no text, no labels, no trails, no extra poses. Exactly TWO cells in a single row.
```
