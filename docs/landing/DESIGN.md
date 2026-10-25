# Previous landing page: design record

Historical design record from September 2026, covering the former desktop-only
site. The current product site is [translate.clickn.dev](https://translate.clickn.dev/)
and includes Windows, macOS, Linux and Android. The parent site is
[clickn.dev](https://clickn.dev/). See [README.md](README.md) for the status of
this source snapshot.

## Implementation and font license

The landing page uses the project's static HTML, CSS and JavaScript. Its locale
generator imports Node.js standard modules and the project's own content and
asset helpers. The build requires no external site template or UI framework.

Onest fonts are hosted locally; their SIL Open Font License is retained in
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

The former header used the parent site's Xynapse logo and wordmark and linked to
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
