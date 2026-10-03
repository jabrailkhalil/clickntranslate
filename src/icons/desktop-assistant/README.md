# Click'n'Translate companions

Five characters based on the project owner's concepts: Blinchik (pancake), Mochi
(cat), Bubu (legless jelly), Momo (pink peach), and Orbit (baby robot).

The transparent atlases were generated with built-in imagegen. Sources and full
prompts are in `docs/mascots/PROMPTS-V2.md` for emotions and activities, and
`docs/mascots/PROMPTS-V8.md` for the current complete walking poses.
Each of the ten source GIF frames was processed separately for all four walkers.

Current runtime assets:

- `<character>/rig/`: eight expressions, four special poses and four limb layers.
- Four walkers use `walk-reference-frames/`: ten complete poses from v8.
- `walk.gif`: ten frames at 110 ms per walker; 20 frames for the jelly crawl.
- `walk-frames/` retains v5 as a complete-sequence fallback. Extra in-betweens,
  `walk-layers/` and `assistant_walk.py` are unused experiments kept for comparison.

`python tools/prepare_reference_walk.py` packs the current sequence using the
source timing and bounds recorded in `docs/mascots/sources-v8/timeline.json`.
`python tools/prepare_mascots.py` prepares all artwork and GIF samples. Neither
command packages the application or runs automated tests.

The cycle lasts 1.1 seconds independently of sprite size and screen speed,
matching the original QMovie behavior. No added or interpolated frames. Body,
arms and feet are drawn together. Screen movement retains subpixel positioning
and 16 ms updates. Jelly extends and contracts on the ground.
The desktop, main-window companion and Python workshop share the renderer.

Static emotions stay still. Translation activity triggers cooking, reading,
bubbles, gardening or scanning, followed by success/error reactions. Idle walking
stays walking. Sleep is selected manually. Hover, click, menus and dragging freeze
the same pose without changing scale.

`run-mascot-app.cmd` opens the full source app using a separate local profile.
`preview-mascots.cmd` opens the animation workshop. See `docs/mascots/PREVIEW.md`.
`compare-mascots.cmd` opens a local frame-synchronized source comparison with
pause, step buttons and a frame slider. The source GIF is not a runtime asset.
Packaging and automated tests are deferred until the visual revision is settled.
All three PyInstaller specifications already include this artwork folder.
The former mascot's artwork is absent from runtime assets.
