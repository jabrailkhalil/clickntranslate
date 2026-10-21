# Click’n’Translate companions — Pets v18

Six original companions use OpenAI image generation: Blinchik (`pancake`),
Chester (`mochi`), Raf (`bubu`), Lola (`momo`), Doc (`orbit`) and Click (`click`).
Character IDs and saved preferences are preserved; Click is the default.

Each companion contains its transparent Pets v2 atlas (`pets-v2.png`), metadata
(`sprites.json`), tiny home shortcut (`preview.png`) and retained native export
strips (`expressions.png`, `sleep.png`, `walk.gif`). The application plays seven
stationary states and sixteen gaze directions from the atlas. Gait rows are
not selected. Desktop and settings share decoded whole frames; the home page
uses a static cached PNG and no animation timer.

`assistant_sprites.py` selects complete cells. `assistant_motion.py` provides
native timing and automatic work/success/failure reactions. Captures hide the
desktop companion; hidden previews stop their timers. Doc's rejected idle
ankle cells map to the accepted resting frame without modifying the atlas.

The assets are bundled locally. Playback requires no plugin connection.
Generation prompts, exact artwork hashes, UI behavior and validation results
are documented in `docs/mascots/pets-v18/`.

Use `python tools/preview_mascots.py` for the workshop, or
`python tools/run_mascot_app.py` for the application with a separate profile.
`python tools/qa_mascot_motion.py OUTPUT_DIRECTORY` exports native motion and
42 static poses for review.
