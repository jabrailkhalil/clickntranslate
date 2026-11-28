#!/usr/bin/env bash
# Runs only on the dedicated Android emulator passed by CI.
set -euo pipefail

serial=${1:?Pass the disposable emulator serial}
if [[ ! "$serial" =~ ^emulator-[0-9]+$ ]] || [[ "$(adb -s "$serial" shell getprop ro.kernel.qemu | tr -d '\r')" != 1 ]]; then
  echo "Device acceptance requires an emulator" >&2
  exit 2
fi
mode=${2:-full}
report=build/device-acceptance
case "$mode" in
  full) ;;
  native-16k) report="$report/native-16k" ;;
  *) echo "Unknown acceptance mode: $mode" >&2; exit 2 ;;
esac
mkdir -p "$report"
page_size=$(adb -s "$serial" shell getconf PAGE_SIZE | tr -d '\r')
sdk=$(adb -s "$serial" shell getprop ro.build.version.sdk | tr -d '\r')
printf 'page_size=%s\nsdk=%s\n' "$page_size" "$sdk" > "$report/memory-pages.txt"
if [[ "$mode" == native-16k && "$page_size" != 16384 ]]; then
  echo "The native acceptance device reported $page_size bytes per page" >&2
  exit 1
fi
sha256sum app/build/outputs/apk/debug/app-debug.apk > "$report/apk.sha256"
adb -s "$serial" shell getprop ro.build.fingerprint > "$report/system.txt"
adb -s "$serial" shell getprop ro.product.cpu.abilist >> "$report/system.txt"
adb -s "$serial" shell wm size >> "$report/system.txt"
adb -s "$serial" shell wm density >> "$report/system.txt"
cat "$report/system.txt"
adb -s "$serial" install -r app/build/outputs/apk/debug/app-debug.apk
adb -s "$serial" install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk

run_tests() {
  local name=$1
  local started_at=$SECONDS
  shift
  adb -s "$serial" shell am instrument -w -r "$@" \
    dev.clickn.translate.debug.test/androidx.test.runner.AndroidJUnitRunner > "$report/$name.log"
  printf '\nQA_WALL_SECONDS=%d\n' "$((SECONDS - started_at))" >> "$report/$name.log"
  python3 - "$name" "$report" <<'PY'
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "tools")
from collect_validation import instrumentation

name, directory = sys.argv[1], Path(sys.argv[2])
log = directory / (name + ".log")
try:
    result = instrumentation(log)
except ValueError:
    print(log.read_text(errors="replace")[-12000:], file=sys.stderr)
    raise
(directory / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n")
print(f"{name}: {result['passed']} passed, {result['skipped']} skipped")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        print(f"- {name}: {result['passed']} passed, {result['skipped']} skipped.", file=summary)
if result["passed"] == 0 or (name != "device-suite" and result["skipped"]):
    raise SystemExit(f"No complete result for {name}")
PY
}

run_native_ocr() {
  local ocr paddle_checks device_files file
  run_tests arabic-ocr -e class dev.clickn.translate.ocr.TesseractArabicOcrIntegrationTest -e downloadModels true -e stageOwnedProbe true || failure=1
  run_tests native-page -e class dev.clickn.translate.ocr.TesseractOwnedScreenProbeTest -e tessProbe true || failure=1
  ocr=dev.clickn.translate.ocr
  paddle_checks="$ocr.PaddleArabicParagraphIntegrationTest,$ocr.DBPostprocessorIntegrationTest"
  paddle_checks+=",$ocr.ArabicMarksIntegrationTest#aSecondDetachedMarkBelowAFathaPreventsShaddaRemoval"
  run_tests paddle-arabic -e class "$paddle_checks" -e paddleArabic true -e downloadModels true || failure=1
  device_files=/sdcard/Android/data/dev.clickn.translate.debug/files
  for file in "qa/arabic-english-ocr-result-api${sdk}.json" tess-probe-result/result.json paddle-arabic-qa/result.json; do
    adb -s "$serial" pull "$device_files/$file" "$report/${file%/*}-blocks.json" || echo "OCR diagnostic unavailable: $file" >&2
  done
}

run_apk_upgrade() {
  local package=dev.clickn.translate.debug
  local test_class=dev.clickn.translate.update.ApkInstallerContinuityIntegrationTest
  local current=app/build/outputs/apk/debug/app-debug.apk fixtures=build/qa-apk-upgrade
  python3 tools/prepare_update_apks.py "$current" "$fixtures" || return 1
  adb -s "$serial" shell run-as "$package" mkdir -p files/qa-apk-upgrade || return 1
  adb -s "$serial" shell -T "run-as $package sh -c 'cat > files/qa-apk-upgrade/newer.apk'" < "$fixtures/newer.apk" || return 1
  adb -s "$serial" shell cmd appops set "$package" REQUEST_INSTALL_PACKAGES allow || return 1
  run_tests apk-installer-handoff -e class "$test_class#sameSignedApkOpensAndroidInstallerAndCorruptCopyCannotStartIt" -e apkUpgradePhase inspect || return 1
  adb -s "$serial" exec-out run-as "$package" cat files/qa-apk-upgrade/installer.png > "$report/apk-installer.png" || return 1
  # Stage a lower, same-signed app in place, then install the untouched current APK as a normal upgrade.
  adb -s "$serial" install -r -d "$fixtures/older.apk" || return 1
  adb -s "$serial" shell dumpsys package "$package" > "$fixtures/prior-package.txt" || return 1
  grep -m 1 -E 'versionCode=[0-9]+' "$fixtures/prior-package.txt" > "$report/apk-prior-version.txt" || return 1
  grep -Eq "versionCode=$(cat "$fixtures/older-code.txt")([^0-9]|$)" "$report/apk-prior-version.txt" || return 1
  adb -s "$serial" install -r "$current" || return 1
  run_tests apk-in-place-update -e class "$test_class#anInPlaceUpgradePreservesSettingsAndQueuedModelAndLaunchesTheRealApplication" -e apkUpgradePhase recover
}

# Retain independent results even if one scenario fails.
failure=0
if [[ "$mode" == native-16k ]]; then
  run_tests onnx-identity -e class dev.clickn.translate.ocr.OnnxRuntimeIdentityIntegrationTest || failure=1
  run_native_ocr
  exit "$failure"
fi
python3 tools/mobile_onboarding_smoke.py --serial "$serial" --output "$report/onboarding" || failure=1
run_tests update-dialog -e class dev.clickn.translate.ui.UpdateDialogSurfaceIntegrationTest -e updateSurface true || failure=1
if adb -s "$serial" shell run-as dev.clickn.translate.debug test -f files/qa-update-320dp-large-rtl.png; then
  adb -s "$serial" exec-out run-as dev.clickn.translate.debug cat files/qa-update-320dp-large-rtl.png > "$report/update-320dp-large-rtl.png"
fi
run_tests provider-rotation -e class dev.clickn.translate.ui.ProviderEditorRotationIntegrationTest -e providerRotation true || failure=1
for orientation in portrait landscape landscape-ime; do
  if adb -s "$serial" shell run-as dev.clickn.translate.debug test -f "files/qa-provider-rotation/$orientation.png"; then
    adb -s "$serial" exec-out run-as dev.clickn.translate.debug cat "files/qa-provider-rotation/$orientation.png" > "$report/provider-$orientation.png"
  fi
done
run_tests home-overlay-denial -e class dev.clickn.translate.ui.HomeOverlayPermissionIntegrationTest -e homeOverlayDenial true || failure=1
run_tests offline-download-recovery -e class dev.clickn.translate.ui.OfflineDownloadRecoveryIntegrationTest -e offlineRecovery true || failure=1
if adb -s "$serial" shell run-as dev.clickn.translate.debug test -f files/qa-offline-queued-pair.png; then
  adb -s "$serial" exec-out run-as dev.clickn.translate.debug cat files/qa-offline-queued-pair.png > "$report/offline-queued-pair.png"
fi
cold_queue=dev.clickn.translate.update.ColdDownloadQueueIntegrationTest
run_tests cold-queue-stage -e class "$cold_queue#stagePersistentWorkAndCloseSettings" -e coldQueuePhase stage || failure=1
adb -s "$serial" shell am force-stop dev.clickn.translate.debug
run_tests cold-queue-recover -e class "$cold_queue#sameQueueSurvivesProcessDeathAndCancellingAnApkKeepsBothModels" -e coldQueuePhase recover || failure=1
run_tests shared-preview -e class dev.clickn.translate.ui.SharedPhotoPreviewIntegrationTest -e sharedPreview true || failure=1
for frame in shared-preview-landscape gallery-review-recreated gallery-preparing-recreated gallery-import-cancelled; do
  if adb -s "$serial" shell run-as dev.clickn.translate.debug test -f "files/qa-$frame.png"; then
    adb -s "$serial" exec-out run-as dev.clickn.translate.debug cat "files/qa-$frame.png" > "$report/$frame.png"
  fi
done
# These tests exercise the enabled features, including Android's contextual action toolbar.
# The fresh-install journey above runs with the normal initial permissions.
adb -s "$serial" shell cmd appops set dev.clickn.translate.debug SYSTEM_ALERT_WINDOW allow
adb -s "$serial" shell cmd appops set dev.clickn.translate.debug GET_USAGE_STATS allow
run_tests device-suite || failure=1
adb -s "$serial" shell cmd appops set dev.clickn.translate.debug SYSTEM_ALERT_WINDOW default
adb -s "$serial" shell cmd appops set dev.clickn.translate.debug GET_USAGE_STATS default
if ! run_tests screen-consent -e class dev.clickn.translate.capture.MediaProjectionConsentIntegrationTest -e projectionConsent true; then
  failure=1
  for file in activities windows logcat failure; do
    adb -s "$serial" exec-out run-as dev.clickn.translate.debug cat "files/qa-projection-failure/$file.txt" > "$report/consent-$file.txt" || true
  done
fi
adb -s "$serial" logcat -d -s ProjectionConsentTest:I > "$report/consent-timing.log"
if [[ -f "$report/screen-consent.json" ]]; then
  adb -s "$serial" exec-out run-as dev.clickn.translate.debug cat files/qa-projection-restart.png > "$report/projection-restart.png"
fi
run_native_ocr
run_apk_upgrade || failure=1
adb -s "$serial" shell cmd appops set dev.clickn.translate.debug REQUEST_INSTALL_PACKAGES default
exit "$failure"
