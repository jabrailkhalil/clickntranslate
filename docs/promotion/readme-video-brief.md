# README demo — superseded draft

Do not render or publish this generated-demo concept. The approved promotion
media is the real application footage in `gifs/README.md`. This file is kept
only as an unused historical draft.

## Intent

- **Goal:** make a visitor understand the product in under 12 seconds without
  reading feature lists.
- **Audience:** Windows users who encounter foreign or unselectable text in
  games, images, videos, applications, and documents.
- **Core message:** one configurable hotkey turns screen text into usable text or
  an in-context translation.
- **Destination:** GitHub README first; YouTube/Product Hunt version second.
- **Format:** silent 16:9 screen demonstration with very little text.
- **Runtime:** 12 seconds, loop-safe.

## Creative direction

Show a real action and real result. Do not animate a list of seven features.
Use the product's dark UI, violet accent, blue send-arrow motif, and rounded
overlays. Cursor movement must be deliberate and slow enough to follow at README
size.

The demo should remain understandable with audio muted and at roughly 600 px
display width.

## Storyboard

| Time | Visual | On-screen copy |
| --- | --- | --- |
| 0.0–1.5 s | Foreign-language text in a game/app; cursor pauses over it | `Text you can't select?` |
| 1.5–3.2 s | `Ctrl + Alt + G` appears briefly; cursor draws two regions | `Choose the important areas` |
| 3.2–6.5 s | Original dialogue changes; two translated overlays update without covering the whole screen | `Translations update in place` |
| 6.5–8.8 s | Cut to highlighted sentence in an editor; `Ctrl + Shift + Q`; selection becomes translated text | `Or replace selected text` |
| 8.8–12.0 s | Product window and logo; Windows + Linux marks; loop returns through a soft match cut | `Free · Open source · No account` |

## Capture requirements

- Use fabricated sample text, not a real private conversation or licensed game
  dialogue.
- Capture at 1920 x 1080 and 60 fps; final delivery may be 30 fps.
- Disable unrelated notifications, tray popups, clocks, usernames, and desktop
  files.
- Keep only two selected regions so the result reads instantly.
- Use source/target languages whose glyphs remain legible at small size.
- Record the hotkey badges as graphics in post; do not rely on a keyboard
  visualizer that changes style.
- Ensure overlays are excluded from the next OCR capture so the demo does not
  show feedback or flicker.

## Deliverables

1. `clickntranslate-readme-demo.mp4`: H.264, 1920 x 1080, 30 fps, no audio,
   visually lossless enough for YouTube/Product Hunt.
2. `clickntranslate-readme-demo.gif`: 1200 x 675 or 960 x 540, 15–20 fps,
   optimized palette, target under 10 MB if legibility permits.
3. `clickntranslate-readme-poster.png`: 1270 x 760 Product Hunt-safe poster.
4. Optional WebM for a future landing page.

## Acceptance checks

- A first-time viewer can say “it translates selected screen regions” after one
  loop.
- No frame contains private data, third-party branding that implies endorsement,
  or unsupported claims.
- Text is readable on a 600 px-wide preview.
- The selected regions and overlays do not jump or grow when the text is short.
- The loop has no black frame or hard flash.
- GIF and MP4 show the same UI behavior.
- README image alt text describes the action, not “demo GIF.”

## Suggested README placement

Place the demo directly below the one-line pitch and download buttons. Keep the
existing detailed feature GIFs farther down the page. Suggested alt text:

```markdown
![Selecting two changing screen regions and translating them in place with Click'n'Translate](docs/images/clickntranslate-readme-demo.gif)
```
