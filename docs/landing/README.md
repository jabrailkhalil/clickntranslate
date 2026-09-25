# Click'n'Translate landing page

Static landing page for the Click'n'Translate section on xynapse.online.

## Local preview

From this directory, run a local static server and open the reported URL:

```powershell
python -m http.server 4173
```

## Public URL

`https://xynapse.online/clickntranslate/`

Canonical links, Open Graph URLs, `robots.txt`, and `sitemap.xml` use that
address. The landing page is available in English, Russian, Spanish, German,
French, and Simplified Chinese. The root page selects a language from the
browser locale until the visitor makes a manual choice.

## Pre-publication checklist

- Open Graph and page media use the real application recording at
  `assets/translation-demo.gif`. Do not publish `social-card.png`; it is an
  unused generated draft.
- Confirm the versioned Windows installer URL and all footer links.
- Test English and Russian at desktop, tablet, and phone widths.
- Verify keyboard navigation, reduced-motion mode, contrast, and image alt text.
- Enable GitHub Pages only after the owner approves the complete public page.
