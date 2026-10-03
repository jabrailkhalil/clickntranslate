# Плавная ходьба v7: слои и промпты

Встроенный imagegen. Режим: редактирование одобренных изображений v5 с выделением отдельных слоёв корпуса, рук и лап. Фазы движения рассчитывает общий отрисовщик приложения; рисунки не смешиваются наложением.

## pancake

[Исходный атлас](sources-v7/pancake-layers.png)

Use case: precise-object-edit.
Create a transparent animation-layer sprite sheet from the supplied approved desktop mascot. EXACT grid: TWO columns by THREE rows, six equal cells, large clear transparent gutters, no written labels or grid lines.
Preserve the approved character identity, soft shaded illustration, three-quarter-right viewing direction, proportions, colors, outlines and face exactly. This is an animation asset separation, not a redesign.
ROW 1 LEFT: only the main body/head, with face and all attached identity details, NO ARMS, NO FEET, NO LEGS. Keep the full body outline naturally filled where the limbs were, including a clean smooth underside. Face toward screen RIGHT, identical to reference. Character-specific ears/antenna/leaves/butter/tail stay attached to the body.
ROW 1 RIGHT: precisely the SAME body/head and size, only the eyes gently closed for a blink; still NO arms, feet or legs.
ROW 2 LEFT: the detached NEAR arm, a short soft rounded mitten/paw from this character, neutral hanging shape, root at top, hand at bottom. One single limb.
ROW 2 RIGHT: the matching detached FAR arm, same design and lighting, slightly darker. One single limb.
ROW 3 LEFT: the detached NEAR foot/paw, a big rounded low soft shape viewed from the SIDE, toes pointing RIGHT, sole facing DOWN. It must have a wide horizontal resting bottom. Width about 2.1 times height. No pink paw pads, no sole facing camera, no tiny legs attached. One single foot.
ROW 3 RIGHT: the matching detached FAR foot/paw, same right-facing side view, slightly darker. Same shape. One single foot.
The main body can occupy 80% of its cell. Each detached limb is enlarged within its own cell for crisp rendering; it will be scaled by the animation program. Keep all six sprites entirely separate, generous transparent margins. Genuine transparent alpha background, no ground shadow, no background, no decorative elements, no alternate full-body poses, no text.
Character: exactly this single thick golden pancake, cream edge, butter square, black glossy eyes, tiny w mouth, rosy cheeks. Main body stays squat, not a ball. Arms golden, feet warm brown.

Уточнение фона:

Use case: background-extraction. Edit this sprite sheet. Remove ALL of the brown glow, soft halos, dark backdrop and cast shadows around every sprite. Preserve the six illustrated sprites pixel-consistently in their same positions and sizes. Background must be genuine empty transparent alpha everywhere outside the crisp dark outlines. No glow, no shadow, no backdrop, no replacement color. The bodies, arms and feet themselves retain their colors and shading. Strict clean cutout.

## mochi

[Исходный атлас](sources-v7/mochi-layers.png)

Use case: precise-object-edit.
Create a transparent animation-layer sprite sheet from the supplied approved desktop mascot. EXACT grid: TWO columns by THREE rows, six equal cells, large clear transparent gutters, no written labels or grid lines.
Preserve the approved character identity, soft shaded illustration, three-quarter-right viewing direction, proportions, colors, outlines and face exactly. This is an animation asset separation, not a redesign.
ROW 1 LEFT: only the main body/head, with face and all attached identity details, NO ARMS, NO FEET, NO LEGS. Keep the full body outline naturally filled where the limbs were, including a clean smooth underside. Face toward screen RIGHT, identical to reference. Character-specific ears/antenna/leaves/butter/tail stay attached to the body.
ROW 1 RIGHT: precisely the SAME body/head and size, only the eyes gently closed for a blink; still NO arms, feet or legs.
ROW 2 LEFT: the detached NEAR arm, a short soft rounded mitten/paw from this character, neutral hanging shape, root at top, hand at bottom. One single limb.
ROW 2 RIGHT: the matching detached FAR arm, same design and lighting, slightly darker. One single limb.
ROW 3 LEFT: the detached NEAR foot/paw, a big rounded low soft shape viewed from the SIDE, toes pointing RIGHT, sole facing DOWN. It must have a wide horizontal resting bottom. Width about 2.1 times height. No pink paw pads, no sole facing camera, no tiny legs attached. One single foot.
ROW 3 RIGHT: the matching detached FAR foot/paw, same right-facing side view, slightly darker. Same shape. One single foot.
The main body can occupy 80% of its cell. Each detached limb is enlarged within its own cell for crisp rendering; it will be scaled by the animation program. Keep all six sprites entirely separate, generous transparent margins. Genuine transparent alpha background, no ground shadow, no background, no decorative elements, no alternate full-body poses, no text.
Character: exactly this charcoal kitten, same ears, cheeks, eyes, tiny mouth and tail. Main body retains ears and tail. Dark charcoal arms and paws, NO pink paw pads.
CRITICAL: clean transparent cutouts only. Zero glow, zero aura or ambient light outside the outlines. Empty alpha, no tinted shadows.

## momo

[Исходный атлас](sources-v7/momo-layers.png)

Use case: precise-object-edit.
Create a transparent animation-layer sprite sheet from the supplied approved desktop mascot. EXACT grid: TWO columns by THREE rows, six equal cells, large clear transparent gutters, no written labels or grid lines.
Preserve the approved character identity, soft shaded illustration, three-quarter-right viewing direction, proportions, colors, outlines and face exactly. This is an animation asset separation, not a redesign.
ROW 1 LEFT: only the main body/head, with face and all attached identity details, NO ARMS, NO FEET, NO LEGS. Keep the full body outline naturally filled where the limbs were, including a clean smooth underside. Face toward screen RIGHT, identical to reference. Character-specific ears/antenna/leaves/butter/tail stay attached to the body.
ROW 1 RIGHT: precisely the SAME body/head and size, only the eyes gently closed for a blink; still NO arms, feet or legs.
ROW 2 LEFT: the detached NEAR arm, a short soft rounded mitten/paw from this character, neutral hanging shape, root at top, hand at bottom. One single limb.
ROW 2 RIGHT: the matching detached FAR arm, same design and lighting, slightly darker. One single limb.
ROW 3 LEFT: the detached NEAR foot/paw, a big rounded low soft shape viewed from the SIDE, toes pointing RIGHT, sole facing DOWN. It must have a wide horizontal resting bottom. Width about 2.1 times height. No pink paw pads, no sole facing camera, no tiny legs attached. One single foot.
ROW 3 RIGHT: the matching detached FAR foot/paw, same right-facing side view, slightly darker. Same shape. One single foot.
The main body can occupy 80% of its cell. Each detached limb is enlarged within its own cell for crisp rendering; it will be scaled by the animation program. Keep all six sprites entirely separate, generous transparent margins. Genuine transparent alpha background, no ground shadow, no background, no decorative elements, no alternate full-body poses, no text.
Character: exactly this pale pink peach, same green leaves, stem, peach seam, cheeks and face. Pale-pink arms, dark-rose feet.
CRITICAL: clean transparent cutouts only. Zero glow, zero aura or ambient light outside the outlines. Empty alpha, no tinted shadows.

Уточнение корпуса:

Use case: precise-object-edit. In the supplied TWO-column THREE-row sprite sheet, change only the TWO peach bodies in the TOP ROW. Remove their attached left arms completely, leaving smooth round peach outlines and smooth pink body shading. Both top sprites must be just the peach body with its face, leaves and stem: NO arms and NO feet. Do not change their faces, size, colors, positions or leaves. Keep the FOUR separate arms and feet in the bottom two rows unchanged. Preserve genuine transparent alpha background, no new background.

## orbit

[Исходный атлас](sources-v7/orbit-layers.png)

Use case: precise-object-edit.
Create a transparent animation-layer sprite sheet from the supplied approved desktop mascot. EXACT grid: TWO columns by THREE rows, six equal cells, large clear transparent gutters, no written labels or grid lines.
Preserve the approved character identity, soft shaded illustration, three-quarter-right viewing direction, proportions, colors, outlines and face exactly. This is an animation asset separation, not a redesign.
ROW 1 LEFT: only the main body/head, with face and all attached identity details, NO ARMS, NO FEET, NO LEGS. Keep the full body outline naturally filled where the limbs were, including a clean smooth underside. Face toward screen RIGHT, identical to reference. Character-specific ears/antenna/leaves/butter/tail stay attached to the body.
ROW 1 RIGHT: precisely the SAME body/head and size, only the eyes gently closed for a blink; still NO arms, feet or legs.
ROW 2 LEFT: the detached NEAR arm, a short soft rounded mitten/paw from this character, neutral hanging shape, root at top, hand at bottom. One single limb.
ROW 2 RIGHT: the matching detached FAR arm, same design and lighting, slightly darker. One single limb.
ROW 3 LEFT: the detached NEAR foot/paw, a big rounded low soft shape viewed from the SIDE, toes pointing RIGHT, sole facing DOWN. It must have a wide horizontal resting bottom. Width about 2.1 times height. No pink paw pads, no sole facing camera, no tiny legs attached. One single foot.
ROW 3 RIGHT: the matching detached FAR foot/paw, same right-facing side view, slightly darker. Same shape. One single foot.
The main body can occupy 80% of its cell. Each detached limb is enlarged within its own cell for crisp rendering; it will be scaled by the animation program. Keep all six sprites entirely separate, generous transparent margins. Genuine transparent alpha background, no ground shadow, no background, no decorative elements, no alternate full-body poses, no text.
Character: exactly this ivory baby robot, same navy face screen and cyan eyes, cyan ear disks and antenna. Ivory arms, dark-teal feet.
CRITICAL: clean transparent cutouts only. Zero glow, zero aura or ambient light outside the outlines. Empty alpha, no tinted shadows.
