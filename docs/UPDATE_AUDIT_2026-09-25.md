# Update audit — 25 September 2026

## Release decision

**1.8.1 was promoted after the final package checks passed.** The stable GitHub
feed now returns 1.8.1, so clients that downloaded 1.8.0 also see a higher version.
The published 1.8.0 prerelease and its assets remain unchanged.
Results below identify the exact candidate they cover. They are not approval
of subsequently rebuilt binaries.

## What the installed clients actually do

| Client | Current behavior | Compatibility requirement |
| --- | --- | --- |
| Windows portable 1.6–1.7 | GitHub latest release → matching ZIP and adjacent SHA256 → **installed old helper** → backup, replace, start, acknowledge, rollback on failure | Preserve the launcher/app layout, recognizable Windows ZIP name, sidecar checksum and readiness protocol |
| Windows installer 1.7 | Detects its Inno registration, prefers full installer, invokes the **old helper** in setup mode | Preserve AppId, install directory, userdata exclusions, installer name and readiness protocol |
| Windows Store | Package manager owns updates | Do not use the portable helper |
| Linux 1.7 / current macOS source | Announces a release and opens its download page | Existing clients cannot acquire a new automatic updater merely from changing GitHub release metadata |

`platform_support.supports_in_app_update()` enables replacement only on Windows.
The platform guard returns before download/apply on Mac and Linux. They do not
execute the Windows helper. macOS had no published binary in release 1.7.0.

The stable feed is `/releases/latest`. A prerelease is not an update offered to
ordinary 1.7 clients through that feed. Never remove a legacy checksum merely to
make the download list shorter. The two Windows sidecars are machine inputs.

## Reproduced problems and changes

1. **The historical E2E script took its helper from the new build.** That did not
   prove that installed clients could reach it. Its default now uses the old
   build. `tools/qa_update_transition.py` additionally tests original published
   binaries, records both helper hashes, and checks real application readiness.
2. **Old helper path limit.** The GUI test with an isolated, deeply nested TEMP
   produced a 269-character extraction path and `PathTooLongException`. Standard
   TEMP on this machine would produce 215 characters. The old helper restored
   1.7. The fixed helper declares a .NET 4.6.2 target as well as the existing
   Win32 long-path manifest, and uses a shorter extraction directory. This fixes
   the new helper; it does not retrospectively change the one in 1.7.
3. **Preparation happened after moving the working installation away.** The
   new helper extracts and verifies ZIP contents before backing up/replacing
   the program. Preparation failures therefore leave program files in place.
4. **Missing/malformed checksum silently skipped verification.** New downloads
   require a checksum and exactly match its filename. A checksum for another
   file, ambiguous entries, or a missing checksum blocks application.
5. **Asset scoring could accept Mac/Linux or verification/source ZIPs when the
   Windows package was missing.** The new selector excludes these explicitly.
6. **Failure UI always blamed other running copies.** New helper diagnostics
   distinguish long paths, access errors, invalid packages and startup timeout.
7. **Published 1.7 installer and portable ZIP inventories differ.** In particular
   the installer omits a nested `cv2/data/__init__.py` shipped in the ZIP. A test
   must use the actual installed helper and actual installed files, not assume
   every dependency is identical between those distribution formats.
8. **An orphan OCR process could satisfy the startup health check.** The helper
   now requires the exact main GUI executable to remain running. Added tests
   cover both ZIP and installer updates where the GUI acknowledges readiness,
   starts an OCR child, then crashes; those updates must roll back.

## Final 1.8.1 candidate

The final files are in `releases/1.8.1-final`, with eight public assets: five
application downloads, two Windows compatibility checksums and one optional
verification archive. The package hashes and final evidence are summarized in
[the 1.8.1 QA report](QA_1.8.1_2026-09-25.md).

All six real Windows transitions passed twice against the final bytes: locally
and on clean Windows Server 2022 GitHub runners. The originals were 1.6.0 ZIP,
1.6.1 ZIP, 1.7.0 ZIP/installer and 1.8.0 ZIP/installer. Each run invoked the
helper shipped in the old release, checked all 3,956 candidate files, retained
synthetic preferences and three data/model markers, and verified a second GUI
startup. The clean-run receipts also confirm fixture cleanup completed.

An additional untouched 1.7 GUI test passed the complete startup prompt,
download, checksum, old-helper replacement and restart path with normal TEMP.
It used a localhost mirror of the final bytes, not the live stable feed.
The clean-run tests separately downloaded the public GitHub files. Their helper
invocation is automated through the helper CLI, not by clicking the download UI.

`tools/verify_update_evidence.py` checks that all six receipts match the exact
final ZIP/installer hashes. Both local and public-download gates passed; receipts
from the superseded candidate were rejected. Rebuilding a package invalidates
these results until the new bytes pass again.

Mac ARM and Intel manual 1.8.0 → 1.8.1 transitions passed with isolated HOME
directories, retained preferences/model markers and a second startup. Both
architectures retain the published 1.8.0 designated requirement and signer
`FC6752F0026D34E5B63433544AF788B8FC1899EF`. This is a self-signed identity,
not Apple Developer ID or notarization. CI initially stored a different older
Mac certificate. The final packages use the existing local published identity;
repository certificate pins and encrypted Actions signing secrets were then
synchronized to that same identity. No replacement signing key was generated.
The signing continuity probe passed on both native Mac architectures in
[CI run 36165874223](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36165874223):
changed code kept the same designated requirement, and an ad-hoc replacement
was rejected.

The original 1.7 Linux AppImage requires glibc 2.38 and cannot start on the local
Ubuntu 22.04 host. The final 1.8.1 AppImage runs there; the original-to-new
transition is tested separately on Ubuntu 24.04. Early harness runs failed on
an overlong test socket path and an extra welcome window. Those were fixture
issues, not successful product migrations, and their failed receipts are kept.
The final public-file transition passed in run `36165244387`. The original
1.7 process was explicitly stopped with SIGTERM before manual replacement;
its IPC has no quit operation and the headless test environment has no tray
Exit menu. This is not proof of graceful old-version shutdown. Both 1.8.1
launches acknowledged readiness, retained preferences/markers and quit normally.

Known limits remain: an already-installed old Windows helper still has its
original long-path limitation; current Mac/Linux clients open the download page
instead of replacing the app automatically; power-loss recovery is not proven.
Local Microsoft Defender was unavailable, so no local Defender pass is claimed.

## Executed migration evidence

These tests ran on the local Windows machine in disposable directories with
spaces and Cyrillic characters. Settings/model markers were synthetic. They
do not establish behavior on every Windows build, antivirus or disk condition.

| Scenario | Candidate | Result and evidence directory under `build/update-audit/` |
| --- | --- | --- |
| Original 1.7 GUI → local HTTP mirror → original helper, deep TEMP | Published 1.8.0 | Path-length failure, 1.7 restored; `1.7.0-portable-ui` |
| Original 1.7 helper, normal TEMP | Published 1.8.0 ZIP | Passed; all 3,956 package files match, preferences and three userdata/model markers retained, real GUI ready and second launch ready; `170-normal-01` |
| Original 1.6 helper, normal TEMP | Published 1.8.0 ZIP | Passed with the same checks; `160-normal-01` |
| Original 1.6.1 helper, normal TEMP | Published 1.8.0 ZIP | Passed with the same checks; `161-normal-01` |
| Original 1.7 installer and its helper → original 1.8 installer | Published 1.8.0 EXE | Passed; all 3,956 archive files match, preferences/markers retained, GUI and second launch ready; `170-installer-02` |
| Original 1.7 helper, deliberately long TEMP | Published 1.8.0 ZIP | Expected failure; all 4,004 original program files restored, markers/preferences retained, 1.7 restarted; `170-long-rollback-01` |
| Fixed candidate helper, deliberately long TEMP | Published 1.8.0 ZIP | Passed; `candidate-long-path-01`. This is explicitly a **helper override**, not proof of an old-client transition |
| Original 1.7 helper, candidate missing `python312.dll` | Deliberately damaged 1.8.0 ZIP | Startup failure; all 4,004 old files restored, data/preferences retained, real 1.7 restarted; `170-broken-rollback-01` |

The helper-level migration harness does not automate the download button and
does not pretend that local files prove live GitHub connectivity. The GUI test
used a local mirror of verified published bytes. Successful CLI migration is
separate evidence from the download UI/network path.

Published 1.8.0 package hashes used above:

```
8e9fbd60fc026849d7714d65825ce192e455c12e3ab6d59b032d55b7a7aa97e1  Windows ZIP
84402785d727c1e8d5e1f6763d614a3470ee6f8c28e2bfbd48f0d4c973d39e9f  Windows EXE
```

The 46 helper/manifest/installer/archive tests passed after the preparation and
long-path changes. Download/checksum/selection tests also passed. These include
fixtures and source-level checks; they do not replace migration of the rebuilt
candidate. Preserve each JSON receipt and its artifact/helper hashes.

## Practices from established projects

| Project | Verified practice | Application here |
| --- | --- | --- |
| [OBS Windows updater](https://github.com/obsproject/obs-studio/blob/master/frontend/utility/AutoUpdateThread.cpp) | Separate stable manifest/channel metadata; retrieves and verifies the updater module before launch | Future protocol should support updating the helper independently, with authenticated metadata |
| [Telegram Desktop updater](https://github.com/telegramdesktop/tdesktop/blob/dev/Telegram/SourceFiles/core/update_checker.cpp) | Authenticates update packages and stages an updater from the downloaded update | Authenticate packages before executing any replacement helper; keep a trusted public key in the client |
| [VS Code Windows](https://code.visualstudio.com/docs/setup/windows) | User installer avoids routine elevation; ZIP distribution uses manual updates | Treat installation types as distinct contracts, and test each contract |
| [VS Code Linux](https://code.visualstudio.com/docs/setup/linux) | Repository/package-manager updates for managed packages | Keep managed installations under their package manager |
| [Sparkle](https://sparkle-project.org/documentation/) | macOS update framework with signed update archives and stable signing keys | Evaluate native Sparkle integration for future Mac automatic updates |
| [AppImage](https://docs.appimage.org/packaging-guide/optional/updates.html) | Embedded update information and AppImageUpdate; zsync for efficient transfer | Evaluate AppImageUpdate for the AppImage distribution, preserving the previous working image |

The .NET correction follows Microsoft's [long-path migration guidance](https://learn.microsoft.com/en-us/dotnet/framework/migration-guide/retargeting/4.6.x).

## Future update contract

This is a design proposal, not a claim that these parts are implemented:

- Signed, versioned manifest with explicit OS, CPU architecture, package format,
  channel, version, URL, byte length, digest, minimum client/updater version.
- Stable embedded verification key and an explicit key-rotation procedure.
  Existing detached GPG/OS signatures are not currently consumed automatically
  by the app's update downloader; SHA256 over HTTPS is not the same mechanism.
- Independently replaceable, authenticated helper. Keep the existing Windows
  asset names and sidecars for every supported old client during migration.
- Stage and verify before replacement; keep a durable transaction record and
  previous working version until the new GUI confirms the expected build.
  Exception rollback exists today; recovery after power loss is not proven.
- Preserve user data outside program replacement; back up before any future
  incompatible settings/database migration.
- Use platform-native update mechanisms for Mac and managed Linux packages.
  A one-time manual transition remains necessary for already installed Linux
  clients whose only update operation is opening the browser.

## Required checks before promoting a rebuilt candidate

- Record its source commit, signatures, hashes and actual package inventory.
- Repeat real 1.7 ZIP and installer migrations against those exact bytes.
- Repeat 1.6/1.6.1 compatibility and 1.8.0 prerelease → fixed candidate.
- Test invalid package, failed startup, retained data and second launch.
- Verify GitHub asset selection/checksums using old code and the final file list.
- Verify public downloads and all native platform builds separately.
- Keep the release preliminary if any required result is missing or failed.
- A successful test of a helper override must never satisfy the old-client gate.
