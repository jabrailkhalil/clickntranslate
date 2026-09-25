# Click'n'Translate landing page

Static landing page for the Click'n'Translate section on xynapse.online.

## Local preview

From this directory, generate the six locales and assemble public files:

```powershell
npm run build
python -m http.server 4287 --bind 127.0.0.1 --directory dist
```

## Public URL

`https://xynapse.online/clickntranslate/`

Canonical links, Open Graph URLs, `robots.txt`, and `sitemap.xml` use that
address. The landing page is available in English, Russian, Spanish, German,
French, and Simplified Chinese. The root page selects a language from the
browser locale until the visitor makes a manual choice.

## Editing

- Text and translations: `tools/content.mjs`.
- Shared HTML: `tools/generate-locales.mjs` (the six HTML files are generated).
- Styling: `styles.css`; interactions and current GitHub downloads: `app.js`.
- Design references, attribution and licenses: [DESIGN.md](DESIGN.md).
- Real app recordings and owner-supplied screenshots: `assets/`.

Run `npm run build` after editing. `dist/` includes only public files; it omits
source tools, private configuration and the old unused generated social card.
The site is static and does not require Node.js on the host.

## Hosting

The existing host serves the site from `/var/www/xynapse.online/clickntranslate/`.
Deploy the contents of `dist/` only. Preserve the previous version outside the
public document root before switching versions. Other paths on xynapse.online
and the application release assets are independent of this site.

Download buttons resolve the latest stable GitHub release at page load. Windows
has installer/portable choices, Mac has Apple Silicon/Intel choices, and Linux
uses AppImage. API failures fall back to the latest release page.
