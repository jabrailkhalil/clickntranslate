# Блинчик v14 — объёмные руки и ботинки

Сгенерировано встроенным imagegen с прозрачным фоном. Один общий лист, четыре детали; корпус и лицо из v9 сохранены.

В следующей пробе v15 используются только руки с этого листа. Ботинки возвращены к прежним деталям из `walk-layers`; новые сохранены для варианта v14.

## Файлы

- Исходный лист: [sources-v14/pancake-limbs.png](sources-v14/pancake-limbs.png).
- Детали для Python-просмотра: `src/icons/desktop-assistant/pancake/volume-layers/`: `foot-near.png`, `foot-far.png`, `arm-near.png`, `arm-far.png`.
- Разделение листа: `python tools/prepare_pancake_cycle.py --volume`.
- Просмотр: `python tools/preview_pancake_cycle.py`.

## Промпт

```text
Use case: precise-object-edit. Create a production animation parts sheet for the SAME cute pancake mascot in image 1. Image 2 is its current shoe, image 3 its current arm. Redesign ONLY these detachable limbs to read as plump rounded volumes, preserving the warm golden pancake illustration style and fine chocolate outline. Do not draw a whole mascot or change the body.
Output a strict 2 by 2 sheet on genuinely transparent RGBA background, four equal square cells separated by generous completely empty transparent gutters. No text, grids, labels, frame borders, cast shadows or scenery.
TOP LEFT: one near-side shoe/foot. A large plump caramel-brown rounded oval, like a soft stuffed cartoon boot without laces or opening. Horizontal with toe pointing right. Width to height about 1.9 to 1. A gently domed, broad visible TOP surface, rounded toe, a clearly shaded darker curved LOWER SIDE surface so it has thickness and volume, and a warm light softly reflected across the upper-left dome. This is NOT a thin flat pancake, disk, flipper or outline oval. No separate black sole line, no toes, no shin. Fine brown contour, watercolor microtexture. Root will hide under the body in the animation.
TOP RIGHT: the SAME rounded shoe shape, same horizontal pose, for the far side. Slightly deeper caramel shading, same lighting direction and proportions. Entire shoe included.
BOTTOM LEFT: one near-side hand/arm as a single short chubby fingerless mitten. It hangs down from a short broad shoulder attachment at TOP CENTRE, palm at bottom. Width to height about 0.92 to 1. Broad soft rounded root (NOT a pointed triangular or leaf tip), rounded bulbous palm, no fingers, no wrist crease, no joints or dark seam across its top attachment. Creamy pale buttery yellow as on image 1, a softly shaded golden underside/right side, soft warm white highlight on upper left to show rounded volume, subtle watercolor texture. Fine brown contour ONLY around the left side, right side and bottom; the upper central attachment blends softly into creamy body skin. The shape must be round and plush, not a flat leaf, teardrop or human hand.
BOTTOM RIGHT: the SAME short rounded hand/arm for the far side, with slightly warmer/deeper shading, same shape and top-centre attachment. No mirrored pointed shape.
Keep all four parts separate and centered, facing the same way. Preserve attractive hand-painted cartoon identity. Plenty of transparency around each object. No glossy plastic 3D render, no realistic human anatomy. Each part is fully visible, with solid colour inside and clean soft antialiased alpha edges.
```
