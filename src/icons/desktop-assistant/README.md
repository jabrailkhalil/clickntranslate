# Click'n'Translate companions — Pets v18

Six original companions use OpenAI image generation through the Pets create-pet
workflow: Blinchik (`pancake`), Chester (`mochi`), Raf (`bubu`), Lola (`momo`),
Doc (`orbit`) and Click (`click`). Existing character IDs and saved preferences
are preserved. Click is the default for new configurations.

Each character's runtime artwork consists of:

- `pets-v2.png`: transparent 1536×2288 atlas, 192×208 cells, nine animation states
  and sixteen clockwise look directions, starting upward.
- `sleep.png`: four breathing poses in a transparent 768×208 strip.
- `expressions.png`: eight full poses: neutral, happy, curious, thinking,
  surprised, sad, sleepy and proud.
- `sprites.json`: layout, frame durations, generation provenance and atlas hash.
- `walk.gif`: transparent eight-frame export for external preview tools.

`assistant_sprites.py` caches the PNGs and selects whole cells.
`assistant_motion.py` shares timing and event state between the desktop companion
and the small main-window companion. Translation, documents, OCR and live
translation trigger working, success and failure reactions. Concurrent jobs keep
the companion busy until all jobs finish. Idle breathing continues when travel
is paused; hover, menus, dragging and capture pause the applicable timer. Static
poses remain still. Cursor movement over an idle animated companion selects its
look direction. Hidden views stop their timers; minimizing the main window also
stops its small companion's timer.

Blinchik stays a broad, thin pancake with attached butter. Raf crawls and has a
single jelly body. Chester retains his cat ears and tail, Lola her two leaves,
and Doc his spherical ivory shell, cyan screen eyes and single antenna.

The assets are bundled locally by the existing PyInstaller specifications.
Runtime playback requires no plugin connection or image-generation service.
Earlier source and rig experiments remain available for development history;
the active renderer reads the files listed above.

Use `python tools/preview_mascots.py` for the six-character workshop, or
`python tools/run_mascot_app.py` for the real application with a separate profile.
`python tools/qa_mascot_motion.py OUTPUT_DIRECTORY` exports production-rendered
motion and all 66 static choices for review.
