# Desktop companion asset

`purple-orb.png` is the original round purple companion generated for this
project using the built-in imagegen tool on 2026-09-19. The generated PNG is
copied unchanged, including its transparent alpha background. Its prompt is
recorded in `docs/MASCOT_PURPLE_ORB_PROMPT.md`. It is separate from Kirby.

`kirby.gif` is the unchanged `images/Y3il.gif` from
https://github.com/sueun-dev/coding-with-kirby/tree/2bc61e77eb0e3c8d249509d0b4734796bad81b59.

Upstream author: sueun-dev. The repository's MIT license is preserved in
`LICENSE.txt` alongside the image. Kirby is a third-party character, not an
original Click'n'Translate character or a claim of affiliation.

SHA-256: `9f75f8b9fcd49f424bbda18b94e579f72afadab7c41a9e1b73638ffdccbbc2550`.

The companion controller and translation menu are implemented locally. The
upstream macOS application, background monitoring and game systems are not
imported. All three PyInstaller specs already include the complete `icons`
directory, including this asset and its license.

## Artwork for this private test build

The following original PNG files were retrieved unchanged on 2026-09-19:

- `kirby-stand.png`: https://kirby.nintendo.com/assets/img/home/kirby-pink_2x.png
- `kirby-star.png` (Kirby riding a star): https://kirby.nintendo.com/assets/img/intro/kirby-star2.png
- `kirby-sleep.png`: https://www.nintendo.com/jp/switch/a2jya/assets/img/common/chara_kirby_sleep.png

Sources: [official Kirby site](https://kirby.nintendo.com/) and
[Nintendo's Return to Dream Land Deluxe ability page](https://www.nintendo.com/jp/switch/a2jya/copy/index.html).
These Nintendo / HAL Laboratory artworks are NOT covered by the adjacent
MIT license. Their inclusion is limited to the user's local, unpublished test
build; no redistribution permission or affiliation is asserted. Review or
replace them before a public release. Qt fits them at runtime; the downloaded
files have not been cropped, retouched or re-encoded.
