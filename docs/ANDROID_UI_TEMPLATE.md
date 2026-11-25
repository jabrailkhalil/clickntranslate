# Android UI reference and lightweight application

Reviewed official Android templates and samples on 2026-10-25. The selected UI reference is the
Material 3 adaptive navigation pattern demonstrated by **Reply**. Click’n’Translate implements that
pattern independently with its existing Compose dependencies. No sample screen, application package,
email data, image, signing configuration, navigation framework or build configuration was imported.

## Comparison

| Official source | Useful characteristics | Fit for this application |
| --- | --- | --- |
| [Architecture starter, single-module base](https://github.com/android/architecture-templates/tree/5467a8dcca30a81b4e31fda5863dd6c65836de0d) | Compose Material 3, Room, Flow, ViewModel and a small list/write UI; its current build declares minSdk24. | Suitable architecture reference, but provides little finished product interaction. Its Hilt/Navigation3 setup is not needed by the existing application graph. |
| [Reply](https://github.com/android/compose-samples/tree/25631e8f544a9a1e3f01e296eaf1b4c28428196c/Reply) | Material 3, stable top-level destinations, compact navigation bar and wider-window navigation rail, adaptive content. | Selected for the UI shell. Four existing destinations remain directly accessible. The implementation uses existing Material 3 components without adding the sample's adaptive, Window or navigation dependencies. |
| [Jetnews](https://github.com/android/compose-samples/tree/25631e8f544a9a1e3f01e296eaf1b4c28428196c/JetNews) | Reader/list-detail layouts, state-driven navigation and Material typography. | Useful for reading translated text/history, but the article feed, interest selection, drawer and widget features would add unrelated concepts. |
| [Jetsnack](https://github.com/android/compose-samples/tree/25631e8f544a9a1e3f01e296eaf1b4c28428196c/Jetsnack) | Custom visual identity, layouts and animation. Its README explicitly identifies unfinished screens. | Its custom color system, food photography and shopping navigation do not fit a small translation tool. No assets or custom layout engine are included. |
| [Now in Android](https://github.com/android/nowinandroid/tree/2982e63cb691ad49cd009aab43dc206fee6699c2) | Full offline-first architecture, adaptive UI and broad testing, with a multi-module graph. | Useful reference for state ownership. Its news features, synchronization, build plugins and module structure are unnecessary for this application's one-module implementation. Its current convention sets minSdk24. |

The reviewed Compose samples catalog declares minSdk24. This application's minimum remains
Android8/API26. Current sample/base branches use compileSdk37 and independent Gradle/Kotlin versions;
their demo build settings are not a production migration plan. Click’n’Translate keeps its verified
application ID, signing handling, SDK/build versions and external dependency pins.

## Applied interaction changes

- `AppNavigation.kt` chooses a bottom bar in compact windows and a rail at width600dp or more with
  height480dp or more. A wide but short phone retains bottom navigation. The same selected destination
  stays in `AppShell`; resizing does not fire a navigation callback or cancel the current work.
- The four destinations remain Screen, Text, History and Settings. The first-run screen has no
  background primary-navigation controls. Existing capture preparation, permission ownership,
  credential changes, cancellation and lifecycle handling stay at their existing boundaries.
- A new glossary rule initially shows its term, category and translation. Language/app scope,
  case sensitivity and enabled state appear under Additional rules. Editing a rule with matching
  restrictions expands that section automatically. Collapsing it retains its draft and shows a
  compact summary of configured restrictions. Draft/expanded state participates in saved-state restore.
- Text entry uses less empty height, retains its existing full input limit and hides the keyboard
  when translation starts. The shorter automatic-source label retains a full accessible description
  on the actual clickable language button. Local translation explains on-device processing; a
  selected network service shows its destination. Model-management instructions remain in the model
  tools rather than appearing as a permanent download requirement below a successful text translation.

These changes add no dependency, network request, downloaded visual asset or background worker.
The application's existing owned brand, colors and characters remain its visual identity.

## Source and attribution

Primary UI references:

- [Reply navigation source at the reviewed revision](https://github.com/android/compose-samples/blob/25631e8f544a9a1e3f01e296eaf1b4c28428196c/Reply/app/src/main/java/com/example/reply/ui/navigation/ReplyNavigationComponents.kt).
- [Official adaptive navigation guidance](https://developer.android.com/develop/ui/compose/layouts/adaptive/build-adaptive-navigation).
- [Official screen-size UI testing](https://developer.android.com/training/testing/different-screens/tools).

The official samples/templates are published under [Apache2.0](https://www.apache.org/licenses/LICENSE-2.0).
The implementation here is newly authored from the interaction pattern and platform APIs; no sample
source file or code fragment was copied. If sample source is incorporated later, preserve its relevant
copyright/attribution, distribute the license and identify modifications as required by that license.
Reference names are documentation/provenance, not application branding.

## Verification boundary

`AdaptiveUiIntegrationTest` exercises real Material navigation at compact, wide and short window sizes
through Compose's `DeviceConfigurationOverride.ForcedSize`, checks state/callback preservation and
uses the accessible automatic-source selector. `ProgressiveRulesUiIntegrationTest` uses real Room to
check basic defaults and collapsed advanced draft restoration. The existing editor tests still check
scoped, case-sensitive, disabled and unavailable-application records after opening the new section.

The adaptive navigation and progressive rule fixtures passed in the central API26/API36 runs.
Pinned first-start actions also passed small-window, enlarged-font and six-language checks. The
selected app theme now controls system-bar icon contrast and the Android8 navigation surface,
including AMOLED when the OS uses a light theme. Final source/APK identities and execution evidence
belong in the [project QA report](REWRITE_STATUS.ru.md); the presence of a fixture alone is not a pass.
