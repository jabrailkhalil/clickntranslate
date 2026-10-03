# Clickn Android UI preview 0.3.2

Development build on the `android` branch. No release or tag is created.

The launcher label is **Clickn**. The full product name stays inside the app. The original CT icon is the default; Ocean, Mint and Sunset are selectable CT variants. Characters and imported pictures are confined to the floating button.

## Introduction and glossary

The introduction has two steps: theme thumbnails, then languages and a brief usage guide. It does not ask for an OCR engine or translation provider. Existing service configuration is preserved; permissions are requested when screen capture is used.

The glossary opens with three independent mode cards: personal terms, corrected translations and text to leave unchanged. Each card explains its purpose and opens only its own records. The 929 Japanese manga sound effects are an optional runtime pack, off by default. They no longer populate the user database or appear as hundreds of editable rows.

Untouched records seeded by older previews are hidden and excluded from active matching. Edited, disabled and application-specific entries stay user records. The first migration remembers the legacy row IDs, so later user entries with the same words remain visible. No records are deleted during this migration.

## Floating translation

The button hides after 45 seconds of inactivity by default and can be brought back with **Show button** in the capture notification or the app home screen. The home screen offers **Stop** separately while capture is active, so denied notification permission does not prevent recovering the button. Closing a reading card also hides it. **Keep the button visible** enables persistent access. Loop mode and open gesture menus keep the button available.

A selection or shared-text card closes after 15–60 seconds of inactivity, with more time for longer results. Loading, touch interaction, speech playback and pinning prevent automatic dismissal. The **Pin** action keeps a result open. Closing a shared-text result during translation prevents the final response from reopening it. The capture notification also offers **Stop**.

All six companions were redrawn as static transparent pictures. The cat is light ivory. Production PNGs are centered and scaled consistently. See [artwork and exact prompts](android-preview-v2-artwork.md).

## Empty text in Telegram

Empty OCR results now explain selection size, OCR language and sharing a message directly. Empty-looking capture frames receive separate capture guidance. The app accepts Android `ACTION_SEND` text shares as well as `ACTION_PROCESS_TEXT`; a user can select a Telegram message and share its text to Clickn without OCR.

The current bundled recognizers are Latin, Japanese, Chinese and Korean. Russian Cyrillic needs a configured compatible OCR service or direct text sharing. No Cyrillic recognizer is silently substituted and no new cloud service is selected automatically. Android 14 full-display consent was already implemented and is retained.

Official references: [ML Kit language support](https://developers.google.com/ml-kit/vision/text-recognition/v2/languages) and [Android media projection](https://developer.android.com/media/grow/media-projection).

The Telegram report has not been reproduced on a connected phone in this workspace. Device capture permissions, protected screens and OCR language remain practical things to verify on the phone.

## Verification

Unit checks cover opt-in packs, legacy rows, overrides and bounded reading time. Android runtime checks exercise card completion, pinning, button visibility, icon switching and migration with a real Room database. UI snapshots cover the mode cards, logo chooser, companions and existing themes. Build results and APK checksum are recorded in `artifacts/android/README.md` when the preview is packaged.
