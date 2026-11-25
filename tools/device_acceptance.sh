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
run_tests device-suite || failure=1
run_tests screen-consent -e class dev.clickn.translate.capture.MediaProjectionConsentIntegrationTest -e projectionConsent true || failure=1
run_tests arabic-ocr -e class dev.clickn.translate.ocr.TesseractArabicOcrIntegrationTest -e downloadModels true || failure=1
exit "$failure"
