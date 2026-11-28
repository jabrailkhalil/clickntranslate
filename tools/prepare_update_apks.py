"""Build two package-manager fixtures using only the CI debug application's identity."""

import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def prepare(current, output):
    sdk = Path(os.environ["ANDROID_HOME"])
    tools = sdk / "build-tools" / "35.0.0"
    android = sdk / "platforms" / "android-35" / "android.jar"
    keystore = Path.home() / ".android" / "debug.keystore"
    badging = subprocess.check_output([tools / "aapt", "dump", "badging", current], text=True)
    identity = re.search(r"^package: name='dev\.clickn\.translate\.debug' versionCode='(\d+)' versionName='(\d+\.\d+\.\d+)'", badging, re.M)
    if not identity or int(identity[1]) < 2:
        raise ValueError("Expected the disposable ClicknTranslate debug application")
    code, version = int(identity[1]), identity[2]
    output.mkdir(parents=True, exist_ok=True)

    def fingerprint(file):
        details = subprocess.check_output([tools / "apksigner", "verify", "--print-certs", file], text=True)
        match = re.search(r"^Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})$", details, re.M)
        if not match:
            raise ValueError("No APK signing certificate")
        return match[1]

    expected_certificate = fingerprint(current)
    with zipfile.ZipFile(current) as archive:
        # The Google APIs x86_64 AVD also reports arm64-v8a through its native bridge.
        # Carry the architecture that this build actually ships.
        libraries = [info for info in archive.infolist()
                     if info.filename.startswith(("lib/arm64-v8a/", "lib/x86_64/")) and info.filename.endswith(".so")]
        if not libraries:
            raise ValueError("The debug APK has no supported native library for the acceptance device")
        lib = min(libraries, key=lambda info: info.file_size)
        content = archive.read(lib)
        if not content.startswith(b"\x7fELF"):
            raise ValueError("Expected a native ELF library from the current APK")

    for name, fixture_code in (("older", code - 1), ("newer", code + 1)):
        with tempfile.TemporaryDirectory(dir=output) as tmp:
            stage = Path(tmp)
            manifest = stage / "AndroidManifest.xml"
            manifest.write_text(f"""<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="dev.clickn.translate.debug" android:versionCode="{fixture_code}" android:versionName="{version}">
    <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35" />
    <application android:label="ClicknTranslate" android:debuggable="true" android:hasCode="false"
        android:extractNativeLibs="true" />
</manifest>""", encoding="utf-8")
            raw, aligned, signed = stage / "raw.apk", stage / "aligned.apk", output / f"{name}.apk"
            subprocess.run([tools / "aapt2", "link", "-I", android, "--manifest", manifest, "-o", raw], check=True)
            with zipfile.ZipFile(raw, "a") as archive:
                archive.writestr(lib.filename, content, compress_type=zipfile.ZIP_STORED)
            subprocess.run([tools / "zipalign", "-P", "16", "-f", "4", raw, aligned], check=True)
            # The SDK debug keystore uses the Android tooling's public default password.
            env = dict(os.environ, APK_QA_DEBUG_PASSWORD="android")
            subprocess.run([tools / "apksigner", "sign", "--ks", keystore, "--ks-key-alias", "androiddebugkey",
                            "--ks-pass", "env:APK_QA_DEBUG_PASSWORD", "--key-pass", "env:APK_QA_DEBUG_PASSWORD",
                            "--out", signed, aligned], env=env, check=True)
            if fingerprint(signed) != expected_certificate:
                raise ValueError(f"{name} fixture is not signed by this runner's debug certificate")
    (output / "older-code.txt").write_text(str(code - 1), encoding="ascii")
    print(f"Prepared same-signature debug fixtures for {version}, version codes {code - 1} / {code} / {code + 1}")


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
