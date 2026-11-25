# Physical Android screen-capture fixture

This standalone debug APK gives the Android task picker a second application with a known label, **CT QA card**, and two possible phrases. The card requests no permissions and does no file or network I/O. A long press closes its task, which causes Android to revoke a projection scoped to that task.

## Build

From the Android repository root, with the project's JDK and Android SDK configured, run the following. On Windows use `gradlew.bat`.

```sh
./gradlew -p tools/projection-fixture assembleDebug
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest
```

The source-only fixture has its own settings and uses the repository's Android Gradle Plugin version. It is independent of the normal application build, instrumentation discovery and API 35 emulator workflow.

## Run on a physical device

Use an unlocked disposable Android user named `ClicknTranslateQA-46` on Android 14 or later. Switch that user to the primary screen, check its ID with `adb shell am get-current-user`, and substitute it for `USER_ID` below. Grant ClicknTranslate its standard overlay permission in that user, leave its Accessibility service disabled and stop any existing recording before running the test. When multiple devices are connected, select the intended one with `ANDROID_SERIAL` or `adb -s SERIAL`.

```sh
adb install --user USER_ID -r tools/projection-fixture/build/outputs/apk/debug/projection-fixture-debug.apk
adb install --user USER_ID -r app/build/outputs/apk/debug/app-debug.apk
adb install --user USER_ID -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument --user USER_ID -w -r \
  -e class 'dev.clickn.translate.capture.PhysicalProjectionConsentIntegrationTest#taskOnlyDenyGrantRevokeWhileTranslatingAndRestart' \
  -e physicalProjectionConsent true -e qaUser USER_ID \
  dev.clickn.translate.debug.test/androidx.test.runner.AndroidJUnitRunner
```

The test uses the system consent dialog to deny once, then share **one application** and choose **CT QA card**. It exercises ClicknTranslate's real foreground service, virtual display, bundled ML Kit and translation client. A loopback server withholds the first response while the selected task closes. The test checks resource cleanup and that the delayed response cannot reopen the result. A second grant must capture the green card and display the known Russian translation. The command reports timing and the two virtual display IDs. It saves no screenshot, system log or UI hierarchy.

To exercise the normal whole-screen permission on that same foreground QA user, select `dev.clickn.translate.capture.PhysicalProjectionConsentIntegrationTest#defaultDisplayTranslatesTheOwnedCardAndStops` and pass `-e physicalDefaultProjectionConsent true -e qaUser USER_ID`. It confirms the Android dialog, limits recognition to the centre of the synthetic card, verifies the foreground user and fixture immediately before triggering OCR, and requires exactly one known request and a rendered result before stopping. This test needs exclusive use of the QA screen.

For a soak that can also run with the disposable user in the background, replace the test class with `dev.clickn.translate.capture.OwnedSurfaceCaptureSoakIntegrationTest#repeatedOwnedPagesPassTheRealOcrAndTranslationAdapter` and pass `-e ownedCaptureSoak true -e ownedSeconds 120`. This checks the Android buffer queue, page-change policy, OCR and loopback translation with self-generated pixels. The same class has `authorizedShizukuTransportDecodesOnlySyntheticPixels` with `-e shizukuTransport true` for devices with Shizuku already running and authorized for the QA user. Its remote shell processes emit fixed bytes and never read the display.

[Android task-only screen sharing](https://developer.android.com/about/versions/14/features/app-screen-sharing) · [Testing specific Android users](https://source.android.com/docs/devices/admin/multi-user-testing)
