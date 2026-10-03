# Android UI assets

The default CT logo is the original desktop `src/icons/icon.png`, copied unchanged to `app/src/main/res/drawable-nodpi/ic_clickn_logo.png`. The adaptive launcher uses that same bitmap; the monochrome themed icon preserves its CT lettering.

Doc is the existing robot character. Doc, Pancake, Mochi, Bubu and Momo use complete static poses from the desktop character resources. These are deliberately static; animation can be added later without changing the button's action.

Chester is the new fox, generated on 2026-10-03 using the built-in image generation tool. The existing robot pose was supplied only as a style reference. The transparent PNG is saved at `app/src/main/res/drawable-nodpi/companion_chester.png`.

## Chester generation prompt

Use case: stylized-concept. Asset type: static character sprite for ClicknTranslate Android floating button, readable at 48–96dp. Primary request: CHESTER is an original friendly little FOX companion. Scene/backdrop: true alpha transparent background. Subject: a compact orange fox, large rounded head, two recognizable triangular ears with dark tips and cream interiors, cream muzzle and belly, dark tiny paws, fluffy curled orange tail with cream tip visible beside body, large glossy dark eyes with small white highlights, gentle smile. Style/medium: polished cute game sprite with crisp warm dark outlines and soft smooth shading, matching the proportions and illustrative finish of the provided baby robot style reference (Image 1 is only style reference, do not copy its robot anatomy). Composition: one full-body fox standing still in a calm front three-quarter pose, centered in square canvas, character fills 82% of image with transparent margins, complete paws, ears and tail visible. Constraints: original animal identity, one character, no scenery, props, clothing, lettering, labels, logos, watermark, shadow plate or checkerboard; clean alpha edge. This is a static image, not an atlas or animation.

## Design references

Theme previews render the production Material 3 palettes, with paired background and foreground roles. Paper palettes retain the existing Komi Store Apache 2.0 notices in the repository.

- [Material 3 color roles](https://developer.android.com/develop/ui/compose/designsystems/material3)
- [Compose accessibility defaults](https://developer.android.com/develop/ui/compose/accessibility/api-defaults)
- [Android overlay window type](https://developer.android.com/reference/android/view/WindowManager.LayoutParams#TYPE_APPLICATION_OVERLAY)

The floating button remains an application-owned Android overlay. Its artwork is configurable independently of capture gestures, translation mode, launcher icon and header icon.
