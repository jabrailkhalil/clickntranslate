# Landing page design

Updated September 2026 for the Windows, macOS and Linux releases.

## References and attribution

- **Astroship, Web3Templates / Surjith S M**:
  <https://github.com/surjithctly/astroship>
  and <https://astroship.web3templates.com/>.
  The two-column hero, compact navigation, primary/secondary action grouping
  and contrasting final call to action are adapted from the public
  `hero.astro`, `navbar/navbar.astro` and `cta.astro` components. This adaptation
  uses static HTML and CSS, with project-specific layout, content and media.
  The upstream GPL-3.0 license is retained in
  `licenses/ASTROSHIP-GPL-3.0.txt`; source is in this public GPL-3.0 repository.
- **Screen Studio**: <https://screen.studio/>. Visual reference for emphasizing
  the actual desktop product and keeping the download action clear. No code or
  media copied from this site.
- **Onest**: <https://github.com/google/fonts/tree/main/ofl/onest>.
  Fonts are hosted locally; the SIL Open Font License is in
  `licenses/ONEST-OFL.txt`.

## Decisions

Near-black background, light text, restrained purple accents and a dark olive
community section. Actual application recordings and the owner's
screenshots explain the product. A tabbed demo replaces the old grid of
simultaneously moving images. Visitors can hide animations; the system's
reduced-motion preference is respected until the visitor explicitly chooses
playback. Companion previews switch between the supplied light/dark captures.

The six localized pages share one renderer and structured content. Font files,
images and scripts are served by this site. The browser contacts GitHub's public
API to resolve downloads; no new analytics or cookie service is included.

The header uses the parent site's Xynapse logo and wordmark and links to
`https://xynapse.online/`. The product keeps its own icon in the page favicon
and footer.
The companion preview starts with the dark screenshot and can switch to light.
CSS and JavaScript filenames include content hashes; language links include a
shared build revision. The HTML cache policy is defined in
`hosting/nginx-cache.conf` to prevent old localized pages from staying cached.

## Downloads

Each platform has an explicit choice. Mac architecture is never inferred from
the browser user agent. The GitHub `/releases/latest` API resolves the versioned
asset names for Windows installer/portable, Mac arm64/x86_64 and Linux AppImage.
Only assets from a stable published release on the project's official download
path are used. Buttons retain the latest-release page as their fallback if the
API is unavailable or the requested asset is missing. No published application
package is created or replaced by this website build.
