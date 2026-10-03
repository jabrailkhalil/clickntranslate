# Блинчик: детали для непрерывного цикла

Режим: встроенный imagegen, прозрачный фон. Сгенерирован один лист деталей; отдельные кадры повторно не генерировались.

Входы: `src/icons/desktop-assistant/pancake/walk-reference-frames/00.png` как образ героя и `src/icons/desktop-assistant/pancake/walk-layers/body.png` как основа корпуса.

Исходный лист: [sources-v9/pancake-layers.png](sources-v9/pancake-layers.png). `tools/prepare_pancake_cycle.py` разделяет его на четыре прозрачных слоя в `src/icons/desktop-assistant/pancake/cycle-layers/`. Стопы используются из прежних `walk-layers/`. `src/assistant_reference_motion.py` рисует эти детали по замкнутым траекториям. Выход для визуального просмотра: [pancake-cycle-v9/comparison.gif](pancake-cycle-v9/comparison.gif).

## Полный промпт

```text
Edit the attached pancake mascot artwork into a precise 2 by 2 transparent animation layer sheet. Input 1 is the full mascot identity reference. Input 2 is the exact isolated torso edit target. These are animation parts for this same cute pancake, NOT new characters and NOT animation poses.
Transparent RGBA background, generous EMPTY transparent gutters dividing four equally sized square cells. No text, no grid lines, no shadows outside parts.
TOP LEFT: the exact wide squat pancake torso from image 2, golden toasted top, creamy pale side, two thin horizontal golden pancake rim bands, chocolate brown fine outline, watercolor texture, butter cube on top. REMOVE ALL face features and blush from this torso, leaving matching clean creamy surface. No arms, feet or face. Preserve its 1.45:1 squat silhouette and texture, shape of butter and overall design faithfully. No invented syrup drips.
TOP RIGHT: only the isolated FACE from image 2: two glossy warm dark brown oval eyes with little white highlights, tiny happy w-shaped mouth, two pink blush dots. Full coherent face in a friendly three-quarter forward right view. Preserve the exact familiar cute eyes and expression. No pancake, no backing shape or skin rectangle, no contour enclosing face; transparent everywhere between features. Eye whites are only small highlights, no large white eyeballs.
BOTTOM LEFT: one isolated short chubby pancake ARM/HAND, pale buttery cream with warm golden shading, a soft ROUND mitten without digits. A short soft nub narrowing at upper attachment, rounded palm below. There is NO dark line across the upper attachment, so it can blend into the torso. Not a long pointed leaf or triangular tip, no sharp corners. Similar to the hand in image 1, with delicate brown outline ONLY around side and bottom edges. Upper attachment blends smoothly with creamy torso when layered. No torso or other parts.
BOTTOM RIGHT: another version of the same hand for the far side, matching shape, a little warmer shaded.
Each cell contains only its requested complete isolated layer, centred in cell. Four cells. Keep the original charming golden pancake illustration style and subtle grain. Not 3D, not vector flat clipart, no extra characters. Crisp usable transparent sprite assets.
```
