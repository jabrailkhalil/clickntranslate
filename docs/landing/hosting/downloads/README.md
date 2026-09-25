# Homepage download statistics

The collector uses GitHub's public releases API for `jabrailkhalil/clickntranslate`
and `jabrailkhalil/xynapse`. It follows pagination, includes public prereleases,
and counts application packages from all currently available releases.
Checksums, verification bundles, OCR dependencies, source archives and unrelated
workflow packages are excluded. Legacy Xynapse extension packages are included.
Counts are file downloads, including repeated downloads and updater downloads;
they are not unique people or successful installations. Deleted release assets
cannot be counted retroactively.

goallog is listed as a web app with `total: null`. There is no install counter;
the private debug APK and activity/user metrics are not public download totals.
The chart compares accumulated totals, not a fabricated daily history.

The systemd timer refreshes every 30 minutes. `collect.py` needs only Python's
standard library and public GitHub access; no credentials are used. Run it as
`www-data`, with `/var/lib/xynapse-downloads` for private state and write access
to `/var/www/xynapse.online/statistics`. Install the script under
`/usr/local/lib/xynapse-downloads/` and the units under `/etc/systemd/system/`.
Only sanitized aggregate data is published to `statistics/downloads.json`.
Writes are atomic. Each project retains its previous value and timestamp when
its API request fails; the UI labels stale data. Unknown counts remain null.

The homepage loads a content-hashed copy of `../xynapse-downloads.js` from its
own origin; this works with the existing CSP without widening access. The
Click'n'Translate landing build does not deploy these parent-site files.

API field reference: https://docs.github.com/en/rest/releases/assets
