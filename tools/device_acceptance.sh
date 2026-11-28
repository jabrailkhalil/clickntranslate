#!/usr/bin/env bash
# Runs only on the dedicated Android emulator passed by CI.
set -euo pipefail

serial=${1:?Pass the disposable emulator serial}
if [[ ! "$serial" =~ ^emulator-[0-9]+$ ]] || [[ "$(adb -s "$serial" shell getprop ro.kernel.qemu | tr -d '\r')" != 1 ]]; then
  echo "Device acceptance requires an emulator" >&2
  exit 2
fi
report=build/device-acceptance
mkdir -p "$report"
adb -s "$serial" shell getprop ro.build.fingerprint > "$report/system.txt"
adb -s "$serial" shell getprop ro.product.cpu.abilist >> "$report/system.txt"
adb -s "$serial" shell wm size >> "$report/system.txt"
adb -s "$serial" shell wm density >> "$report/system.txt"
cat "$report/system.txt"
adb -s "$serial" install -r app/build/outputs/apk/debug/app-debug.apk
adb -s "$serial" install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk

run_tests() {
  local name=$1
  shift
  adb -s "$serial" shell am instrument -w -r "$@" \
    dev.clickn.translate.debug.test/androidx.test.runner.AndroidJUnitRunner > "$report/$name.log"
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

# Retain independent results even if one scenario fails.
failure=0
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
run_tests arabic-ocr -e class dev.clickn.translate.ocr.TesseractArabicOcrIntegrationTest -e downloadModels true -e stageOwnedProbe true || failure=1
run_tests native-page -e class dev.clickn.translate.ocr.TesseractOwnedScreenProbeTest -e tessProbe true || failure=1
ocr=dev.clickn.translate.ocr
paddle_checks="$ocr.PaddleArabicParagraphIntegrationTest,$ocr.DBPostprocessorIntegrationTest"
paddle_checks+=",$ocr.ArabicMarksIntegrationTest#aSecondDetachedMarkBelowAFathaPreventsShaddaRemoval"
run_tests paddle-arabic -e class "$paddle_checks" -e paddleArabic true -e downloadModels true || failure=1
device_files=/sdcard/Android/data/dev.clickn.translate.debug/files
for file in qa/arabic-english-ocr-result-api35.json tess-probe-result/result.json paddle-arabic-qa/result.json; do
  adb -s "$serial" pull "$device_files/$file" "$report/${file%/*}-blocks.json" || echo "OCR diagnostic unavailable: $file" >&2
done
exit "$failure"
