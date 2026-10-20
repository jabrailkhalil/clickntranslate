# Click'n'Translate companions

Five characters based on the project owner's concepts: Blinchik (pancake), Chester
(cat), Raf (legless jelly), Lola (pink peach), and Doc (baby robot).
Their stable asset/settings keys remain `pancake`, `mochi`, `bubu`, `momo`,
and `orbit`. Display names are shared through `assistant_text.py`.

## Current Doc (formerly Orbit): v17

Doc's walk uses exact visible contours from each of the ten reference cels.
`walk-geometry.json` stores paths; `assistant_traced_walk.py` applies the ivory
shell, cyan eyes, navy visor and teal shoes. No per-frame fitting or limb rig is
used. The viewport and scale stay constant; source occlusion and 110 ms timing
are retained. The antenna follows the measured crown. Pixel edges are deliberate.
`walk-traced-frames/` and `walk-traced.gif` are exports of that same renderer.
The other four mascots retain v16. See `docs/mascots/PREVIEW.md` for the agent audit.
The user approved the walk and the revised short, rounded cyan eyes.

To refresh: `python tools/extract_walk_geometry.py`, then
`python tools/export_orbit_traced.py`. The source GIF remains a development
reference; it is not loaded at runtime. Geometry provenance is recorded in
`docs/mascots/sources-v17/reference-geometry.json` and the reference folder.

## Earlier generated artwork

The transparent atlases were generated with built-in imagegen. Sources and full
prompts are in `docs/mascots/PROMPTS-V2.md` for emotions and activities, and
`docs/mascots/PROMPTS-V16.md` for the current complete walking and crawling cels.
Each character has a coherent ten-pose sheet; targeted frame corrections preserve
the loop's arm poses and foot overlap. The original GIF supplies the walk poses
and timing. Generated drawings are adaptations rather than pixel-exact tracing.

Current runtime assets:

- `<character>/rig/`: eight expressions, four special poses and four limb layers.
- Four characters use `walk-redrawn-frames/`; Orbit's v16 is retained for comparison.
- `walk-redrawn.gif`: separate ten-frame export for each character.
- `walk-reference-frames/` and `walk.gif` retain v8 for comparison and fallback.
- `walk-frames/` retains v5 as a complete-sequence fallback. Extra in-betweens,
  `walk-layers/` and `assistant_walk.py` are unused experiments kept for comparison.

`python tools/prepare_redrawn_walk.py --apply-corrections --pack pancake mochi bubu momo orbit`
packs the current sequence from the saved sheets and corrections. Registration
uses one scale per character and sole alignment for complete cels. Metadata is
recorded in `docs/mascots/sources-v16/*-registration.json`.
`python tools/prepare_mascots.py` prepares all artwork and GIF samples. Neither
command packages the application or runs automated tests.

The cycle lasts 1.1 seconds independently of sprite size and screen speed,
matching the original QMovie behavior for the four walkers. No added or interpolated frames. Body,
arms and feet are drawn together. Screen movement retains subpixel positioning
and 16 ms updates. Jelly extends and contracts on the ground; its cel index follows
the crawl phase. A separate soft shadow is drawn underneath the complete sprite.
The desktop, main-window companion and Python workshop share the renderer.

Static emotions stay still. Translation activity triggers cooking, reading,
bubbles, gardening or scanning, followed by success/error reactions. Idle walking
stays walking. Sleep is selected manually. Hover, click, menus and dragging freeze
the same pose without changing scale.

`run-mascot-app.cmd` opens the full source app using a separate local profile.
`preview-mascots.cmd` opens the animation workshop. See `docs/mascots/PREVIEW.md`.
`compare-mascots.cmd` opens a local frame-synchronized source comparison with
pause, step buttons, a frame slider and an onion-skin option. The source GIF is not a runtime asset.
Packaging and automated tests are deferred until the visual revision is settled.
All three PyInstaller specifications already include this artwork folder.
The former mascot's artwork is absent from runtime assets.
