# 1.8.1 release evidence — 25 September 2026

This report applies to the exact files below. It does not guarantee behavior on
every machine, antivirus, display server or filesystem. Detailed mechanisms and
remaining limitations: [update audit](UPDATE_AUDIT_2026-09-25.md).

The final candidate was promoted to stable after the checks below. GitHub
`/releases/latest` returns `v1.8.1`, with `draft=false`, `prerelease=false` and
eight assets. The existing 1.8.0 remains a prerelease.

## Packages

| File suffix (`Click-n-Translate-1.8.1-`) | SHA-256 |
| --- | --- |
| `windows-portable-x64.zip` | `e55dfd9121a971232d1322ddf0314933ee88695b0b5b2308895b3ad07d0ee56f` |
| `windows-x64-installer.exe` | `da586a00bc16088fdf056f3a66abfd55f2efb5799ddc2c51a6c237382ad72330` |
| `linux-x86_64.AppImage` | `7127af8d1c571c81a09e0b1961ea18caa33685e42764277596ec53451f080673` |
| `macos-arm64.dmg` | `a3b688a35df689a13adfc85d9d906fdbfb7dcdcf4b39a9eebcdac3a0ff5492e0` |
| `macos-x86_64.dmg` | `dbbad18330f300d2dddf28707dadb7413201237c700a48652b3601c29e0bfd97` |

The release tag is `v1.8.1` at `60490b5`. Windows final helper sources are from
`8a74258`. Mac ARM and Linux runtime sources are from `5e0dba9`; Linux was
repackaged with the version metadata correction from `e9e7b9a`. Intel was built
at `56470dc`. The runtime Python sources are identical across those commits;
subsequent changes affected Windows C#, packaging, QA tools and tests.

## Checks completed

| Area | Result |
| --- | --- |
| Source regression suites | [Windows and Linux CI passed](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36161837203), with unchanged user data reported by every test shard. |
| Final updater focused suite | 38 checks passed, including GUI crash with surviving OCR worker, checksum validation and receipt validation. These include fixtures and do not replace actual binary migrations. |
| Original Windows clients | Six local transitions passed: 1.6.0/1.6.1 ZIP; 1.7.0/1.8.0 ZIP and installer. Original helpers, exact package contents, preferences, data/model markers and second GUI startup checked. |
| Public Windows downloads | All six Windows jobs [passed on clean runners](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36164307117). The Linux fixture in that same run failed and was corrected separately. GitHub digests and compatibility checksum sidecars matched. |
| Live stable feed | After promotion, an unauthenticated request with the 1.7 User-Agent returned 1.8.1. The original 1.7 selector chose the correct portable and installer assets, and both public SHA256 sidecars downloaded and matched. |
| Original Windows GUI | Untouched 1.7 prompted for 1.8.1, downloaded ZIP and SHA256 from a localhost mirror, installed through its original helper and restarted. All 3,956 candidate files and preserved markers were verified; second startup reported 1.8.1. |
| Windows signatures | Six EXE signatures, including installer and updater, independently verified with osslsigncode using the published certificate and timestamp CA chain. A modified file was rejected. Windows reports the certificate as untrusted/self-signed; no SmartScreen approval is claimed. |
| OpenPGP | All five application packages and SHA256SUMS were signed and verified with fingerprint `22873EED9E329E51D7D3EAE09A508E7BEF2D4205`. |
| Linux native runtime | Final AppImage and portable directory started on Ubuntu 22.04.5 under Xvfb, acknowledged 1.8.1, accepted show/quit commands and exited cleanly. Final AppImage contains 1.8.1 AppStream metadata. |
| Linux data transition | [Public AppImage transition passed on Ubuntu 24.04](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36165244387). Actual 1.7 startup, retained settings/model markers, 1.8.1 startup and second launch checked. The old GUI was stopped with SIGTERM because its IPC has no quit command and Xvfb has no tray Exit menu; no graceful 1.7 shutdown is claimed. Both new-version launches exited normally. |
| Mac ARM | Signed native bundle passed Cocoa GUI/settings, Vision OCR, Carbon registration, RapidOCR and Argos helper checks on macOS 14.3. |
| Mac Intel | [Native Intel CI passed](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36161533482). Final re-signed app passed extended GUI/OCR/helper checks under Rosetta on macOS 14.3; signing did not change embedded Python archives. |
| Mac data transition | Both architectures passed manual 1.8.0 → 1.8.1 and second launch with isolated HOME, retained preferences and three data/model markers. Both retained the same designated requirement and `jabrailkhalil` signer. |
| Future Mac signing | Repository pins and encrypted Actions secrets now use the same published identity. [Native ARM and Intel probes passed](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36165874223): modified code retained its requirement, while an ad-hoc replacement was rejected. No signing key was regenerated. |

The initial local full-suite runs had one stale AppStream version assertion each
(Windows: 1,737 passed, 60 skipped; Linux: 1,696 passed, 101 skipped; Mac:
1,665 passed, 132 skipped). The metadata was corrected, targeted checks passed
on all three hosts, Linux was repackaged, and the final Windows/Linux CI suites
passed. These historical failures are not silently counted as green full runs.

## Evidence locations

- Final packages: `releases/1.8.1-final/`.
- Local migration receipts: `build/update-audit/verified-*-to-181/`.
- Complete Windows GUI route: `build/update-audit/1.7.0-final-ui/gui-result.json`.
- Public download receipts: `.tmp/update-audit/published-transitions-36164307117/`.
- Linux public transition receipt: `.tmp/update-audit/published-linux-36165244387/`.
- Hash-bound gates: `.tmp/update-audit/final-transition-gate.json` and
  `.tmp/update-audit/published-transition-gate.json`.
- Native/signature logs: `.tmp/update-audit/`, including `mac-migration-181.log`,
  `mac-final-signature.log`, `openpgp-final-181.log`, `linux-final-metadata.log`.

The original local Python application was restored after the Windows tests.
Disposable fixture installations were uninstalled; the user's original Mac
application and data were not replaced by test copies.

## Updates and limits

Windows 1.6+ retains in-app updates through recognizable ZIP/installer assets,
the two legacy SHA256 sidecars, the installed old helper and the existing
readiness protocol. A prerelease is absent from the normal stable update feed.

Mac and Linux currently open the release download page. Their replacement is
manual; these checks must not be described as automatic updates. Linux 1.7
requires a newer glibc than the local Ubuntu 22.04 test machine, so its real
transition requires Ubuntu 24.04. macOS had no binary in release 1.7.

The new helper supports longer paths, but cannot change the helper already in
1.7 before that helper runs. The old version correctly rolled back in a
deliberately deep TEMP test and when a package was missing Python. Recovery
after a power cut, every antivirus product, Wayland compositor and automatic
Mac/Linux replacement are not established by these checks. Local Defender was
unavailable; no local malware-scan pass is claimed.
