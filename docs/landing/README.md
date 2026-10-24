# Previous website source

## Current public sites

- **Click’n’Translate:** [translate.clickn.dev](https://translate.clickn.dev/).
- **Author and other projects:** [clickn.dev](https://clickn.dev/).
- **Android:** [mobile overview and APK](https://translate.clickn.dev/en/#android),
  [installation guide](../ANDROID.md), [Android source](https://github.com/jabrailkhalil/clickntranslate/tree/android).
- **Current application downloads:** [GitHub Releases](https://github.com/jabrailkhalil/clickntranslate/releases/latest).

The old `xynapse.online` and `xynapse.online/clickntranslate/` addresses redirect
visitors to the new domains. Use the new addresses for links, product metadata
and documentation.

## Source snapshot

This directory preserves the **September 2026** static website: six locales,
recordings, styles, font licenses, generators and the former nginx configuration.
The live site has since changed its branding, navigation, Android section and
downloads. Treat these files as historical source and design references, rather
than the current deployment bundle. The old `/var/www/xynapse.online/` paths
record the former host layout.

For current product information use the [main README](../../README.md),
[Android guide](../ANDROID.md), [Linux guide](../LINUX.md),
[Mac guide](../MACOS.md) and the public site above. Current website privacy
information is maintained at [clickn.dev](https://clickn.dev/en/privacy/).

## Reproducing the historical snapshot

The former build uses `npm run build` and writes public files into `dist/`.
Its locale generator also rewrites `../guides/setup.*.md` from
`tools/setup-content.mjs`. Reproduce it in an isolated checkout to preserve
current documentation. The generated snapshot is for historical preview;
maintaining the live site requires its current source and hosting configuration.

[Historical design record and font license](DESIGN.md).
