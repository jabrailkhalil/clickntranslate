# Pets v18 mascot integration

The six companions use complete image-generated poses in the Pets v2 format.
Doc, Chester, Blinchik, Raf and Lola were regenerated from their identity cues;
Click uses the previously accepted original robot atlas, with new matching sleep
and emotion strips. Generation used OpenAI's built-in imagegen through Pets
create-pet v0.1.6. Actual generation prompts are preserved in `PROMPTS.md`.

![Six companion designs](preview.png)

All six atlases are transparent 1536×2288 PNGs with 192×208 cells. The nine
animation rows contain 6, 8, 8, 4, 5, 8, 6, 6 and 6 frames; the last two rows
contain sixteen clockwise gaze directions. Sleep has four additional poses and
the emotion strip has eight. One shared registration transform per source row
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

Both companion views cache whole PNGs and select cells. Screen-right and
screen-left walks are separate generated sequences. Processing stays planted;
success plays a jump followed by a review pose, and errors play the failure
sequence. Main text translation, document translation, area OCR, fullscreen OCR
and both live translation modes report activity on the GUI thread. Concurrent
jobs hold the working state; cancellation clears only its own job, and stale
results are ignored by the existing session guards. Pausing travel retains idle
animation and reactions. Hovering selects gaze using local cursor coordinates.

Existing character IDs, saved poses, position, custom images and capture
ownership remain compatible. Click and the animated appearance are the defaults
for new configurations; travel starts paused. Static choices stay still. The
existing Windows, Linux and macOS packaging specifications include the complete
icons folder. No plugin connection is required for playback.

Review with `python tools/preview_mascots.py` or open the actual application using
`python tools/run_mascot_app.py`, which uses its own profile. Production-rendered
motion and 66 static choices can be exported with
`python tools/qa_mascot_motion.py OUTPUT_DIRECTORY`.
