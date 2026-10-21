# Pets v18 mascot integration

The six companions use complete image-generated poses in the Pets v2 format.
Doc, Chester, Blinchik, Raf and Lola were regenerated from their identity cues;
Click uses the previously accepted original robot atlas. Extra sleep and emotion
strips are retained as generation provenance; the app does not load them. Generation used OpenAI's built-in imagegen through Pets
create-pet v0.1.6. Actual generation prompts are preserved in `PROMPTS.md`.

![Six companion designs](preview.png)

All six atlases are transparent 1536×2288 PNGs with 192×208 cells. The nine
animation rows contain 6, 8, 8, 4, 5, 8, 6, 6 and 6 frames; the last two rows
contain sixteen clockwise gaze directions. Playback uses only the seven stationary
native states and gaze; the two gait rows are never selected. One shared registration transform per source row
preserves the generated motion, and a common cell viewport keeps the body
anchored. A final chroma-edge pass is applied once to each encoded artifact.

| Companion | Stable settings key | Measured jump lift | Atlas SHA-256 |
| --- | --- | --- | --- |
| Click | `click` | 47 px | `4003554f70c1956e32e6365dc0952f0c984be0d3865a44704cb7ea57a03e28e7` |
| Doc | `orbit` | 26 px | `dc53e5aa3fdd2f816d5a23364d6acffb5bec8aedc0def2971230a6649aa8b6c6` |
| Chester | `mochi` | 50 px | `892d085420eadab8910947a507df6a01b8f04c005c49366638facab10099ac08` |
| Blinchik | `pancake` | 63 px | `52ed7ad5667e3487f150c44f1c9b5bb09450af62c5adffde41787265c9e579e7` |
| Raf | `bubu` | 76 px | `99129426d8fe6069dbb2356e6e5ccc6a07218f1102fdf65d275e2b8323c74a6e` |
| Lola | `momo` | 34 px | `6db968c1e8977364f3afed4d2ffa1e628f5b30d516cc2f3384998ef18e1ea57a` |

`validation.json` records the exact encoded hashes, structural gates, visible
jump displacement, quality gates and the result of three independent blind
direction reviews. All cardinals passed without ambiguity. Small differences
between neighboring diagonal angles and local pixel-difference outliers were
visually reviewed and retained as warnings. The Pets MCP preflight accepted
every final atlas. Full decoded source strips, canonical references, rejected
revisions, assembly scripts and detailed QA are preserved in the separate local
source archive.

Both companion views stay at a fixed position and render complete v2 frames.
There is no automatic walking, crawling, synthetic limb motion, sleep or extra
emotion strip in the app. `running` means active work in the Pets contract;
it uses row 7, never either directional gait row. The native state mapping is:

| Native animation | ClicknTranslate scenario |
| --- | --- |
| idle | Quiet, stationary breathing between interactions |
| waving | Greeting on click; opens actions beneath the pet |
| jumping | Translation completed successfully |
| running | Text/document/OCR/live translation is processing |
| waiting | Waiting for input or choosing an action in the open menu |
| review | Checking the finished result after the success jump |
| failed | Translation failed; the user can retry |
| sixteen look directions | Follow the local pointer while calm |

The compact popup offers screen, region, text, OCR copy, live and document
translation, companion settings, hide and a seven-state reaction picker. A
selected reaction plays one cycle. Real work takes priority. Click reactions
also play once from a static built-in pose, then restore that pose. Custom
images remain static. Hovering and the open menu keep playback running. Manual
dragging still places the pet; capture hides the companion before screenshots.
The in-window companion uses the same popup and stays beside its label.

![Stationary companion and its action popup](interaction-preview.png)

Main text translation, document translation, area OCR, fullscreen OCR and both
live translation modes report activity on the GUI thread. Concurrent jobs hold
the working state; cancellation clears only its own job, and stale results are
ignored by existing session guards. Explicit reactions work with automatic
translation reactions disabled, without masking an active job.

Existing character IDs, positions, custom images and capture ownership remain
compatible. Old walking profiles migrate to stationary animation. Old custom
emotion/sleep choices map to their nearest native pose. Walking speed and pause
controls have been removed. Settings offer seven native static poses, animated
playback, character, size, opacity, visibility and event reactions. Click and
stationary animation are the defaults for new configurations.

Picker thumbnails retain only one 192×208 cell; the original PNG is decoded
once when animation first needs it and shared by both companion views. The
Windows, Linux and macOS packaging specifications include the icons folder.
No plugin connection is required for playback.

Review with `python tools/preview_mascots.py` or open the actual application using
`python tools/run_mascot_app.py`, which uses its own profile. Production-rendered
stationary animation and 42 native static choices can be exported with
`python tools/qa_mascot_motion.py OUTPUT_DIRECTORY`.
