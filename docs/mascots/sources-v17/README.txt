Doc v17 (formerly Orbit) — saved 20 October 2026

CURRENT RESULT
reference-geometry.json records exact source contours and provenance.
src/icons/desktop-assistant/orbit/walk-geometry.json contains runtime paths.
src/assistant_traced_walk.py paints the paths with custom Orbit materials.
src/icons/desktop-assistant/orbit/walk-traced-frames/00.png..09.png and
walk-traced.gif are exports from that renderer. The constant viewport preserves
all ten original poses; only the antenna extends the original silhouette.
The user approved the walk and then the revised short, rounded cyan eyes.
Current exported frames use those eyes. docs/mascots/orbit-v17-eyes/ contains
the before/after comparison and a before/ backup of the earlier face and code.
The earlier docs/mascots/orbit-v17/ comparison preserves the pre-revision face.
Character names are now Doc (orbit), Chester (mochi), Blinchik (pancake),
Raf (bubu), and Lola (momo); stable internal IDs are unchanged.

REJECTED IMAGEGEN STUDIES
orbit-00.png..09.png were generated separately with built-in imagegen.
orbit-XX-fixed.png and orbit-XX-body-study.png are attempted corrections.
rejected-atlas.png is the earlier failed whole-sheet attempt.
ORBIT-PROMPT.txt, CEL-PROMPTS.txt and CORRECTION-PROMPTS.txt preserve all prompts.
registration.json, registration-contact-first.png and generated-study/ show
the failed generated sequence. These images are NOT used by the application.
tools/prepare_orbit_matched.py only recreates that rejected study under docs.

FRAME-AUDIT.txt is the three-agent diagnosis of v16 and initial v17 attempts.
Final independent review confirmed body/hand/foot geometry and original
occlusion in the native renderer, especially05->06 and08->09->00.
Review was visual and source-code inspection, not automated tests or a build.

Other mascots remain on v16. Their outstanding pose deviations are in the audit.
