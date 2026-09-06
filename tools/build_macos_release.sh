#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Darwin ]]; then
  echo "macOS builds require a Mac or the macOS GitHub Actions workflow." >&2
  exit 1
fi
cd "$(dirname "$0")/.."
PYTHON="${VENV:-.venv-macos}/bin/python"
VERSION="$("$PYTHON" -c 'from app_version import APP_VERSION; print(APP_VERSION)')"
ARCH="$("$PYTHON" -c 'import platform; print(platform.machine())')"
mkdir -p build/macos releases
"$PYTHON" -c "from PIL import Image; Image.open('icons/icon.png').convert('RGBA').save('build/macos/icon.icns')"
"$PYTHON" -m PyInstaller --noconfirm --clean --workpath build/macos/pyinstaller ClicknTranslate-macos.spec
APP="dist/ClicknTranslate.app"
codesign --verify --deep --strict --verbose=2 "$APP"
"$PYTHON" tools/smoke_macos_bundle.py "$APP"

# Notarize only with an explicitly configured Developer ID and keychain profile.
# The profile is provisioned separately via `xcrun notarytool store-credentials`.
if [[ -n "${MACOS_NOTARY_PROFILE:-}" ]]; then
  if [[ -z "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
    echo "Notarization requires MACOS_CODESIGN_IDENTITY." >&2
    exit 1
  fi
  ditto -c -k --keepParent "$APP" build/macos/notarize.zip
  xcrun notarytool submit build/macos/notarize.zip --keychain-profile "$MACOS_NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose "$APP"
fi

# Unique staging directory; never delete an arbitrary caller-supplied folder.
STAGE="$(mktemp -d "$(pwd)/build/macos/dmg.XXXXXX")"
ditto "$APP" "$STAGE/ClicknTranslate.app"
ln -s /Applications "$STAGE/Applications"
OUTPUT="releases/Click-n-Translate-${VERSION}-macos-${ARCH}"
hdiutil create -ov -volname "Click’n’Translate" -srcfolder "$STAGE" -format UDZO "$OUTPUT.dmg"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$OUTPUT.zip"
shasum -a 256 "$OUTPUT.dmg" "$OUTPUT.zip" > "$OUTPUT.sha256"
echo "Created $OUTPUT.dmg and .zip"
if [[ -z "${MACOS_NOTARY_PROFILE:-}" ]]; then
  echo "Development build: not notarized. This is not yet a trusted public Mac release."
fi
