#!/usr/bin/env bash
# Builds the Linux artifacts: a portable tarball and an AppImage.
#
# Usage:
#   tools/build_linux_release.sh [--skip-pyinstaller] [--skip-appimage]
#
# Environment:
#   VENV           virtualenv to build with (default ~/.venvs/clickntranslate)
#   APPIMAGETOOL   path to an existing appimagetool binary; downloaded when unset
#
# AppImage is the primary artifact: it keeps the portable layout the Windows
# build uses, which matters because the optional OCR engines are pip-installed
# into the app's own directory at runtime — something a Flatpak sandbox blocks.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$HOME/.venvs/clickntranslate}"
PYTHON="$VENV/bin/python"

SKIP_PYINSTALLER=0
SKIP_APPIMAGE=0
for argument in "$@"; do
    case "$argument" in
        --skip-pyinstaller) SKIP_PYINSTALLER=1 ;;
        --skip-appimage) SKIP_APPIMAGE=1 ;;
        *) echo "Unknown option: $argument" >&2; exit 2 ;;
    esac
done

VERSION="$("$PYTHON" -c "import sys; sys.path.insert(0, '$REPO_DIR'); from app_version import APP_VERSION; print(APP_VERSION)")"
ARCH="$(uname -m)"
DIST_DIR="$REPO_DIR/dist/clickntranslate"
RELEASE_DIR="$REPO_DIR/releases"
APPDIR="$REPO_DIR/build/AppDir"

echo "Click'n'Translate $VERSION ($ARCH)"

# --- 1. PyInstaller ----------------------------------------------------------
if [ "$SKIP_PYINSTALLER" -eq 0 ]; then
    echo "[1/4] Building with PyInstaller..."
    (cd "$REPO_DIR" && "$PYTHON" -m PyInstaller ClicknTranslate-linux.spec --clean --noconfirm)
fi

if [ ! -x "$DIST_DIR/clickntranslate" ]; then
    echo "ERROR: $DIST_DIR/clickntranslate is missing; the build did not produce a binary." >&2
    exit 1
fi

for helper in _internal/ArgosWorker _internal/OcrWorker; do
    if [ ! -x "$DIST_DIR/$helper" ]; then
        echo "ERROR: helper $helper is missing from the build." >&2
        exit 1
    fi
done

mkdir -p "$RELEASE_DIR"

# --- 2. Icon -----------------------------------------------------------------
# The repository ships a Windows .ico; AppImage needs a PNG.
ICON_PNG="$REPO_DIR/build/clickntranslate.png"
echo "[2/4] Preparing the icon..."
"$PYTHON" - "$REPO_DIR/icons/icon.ico" "$ICON_PNG" <<'PYTHON'
import sys
from PIL import Image

source, target = sys.argv[1], sys.argv[2]
image = Image.open(source)
# .ico files hold several sizes; take the largest and normalize to 256x256.
if hasattr(image, "n_frames") and image.n_frames > 1:
    best, best_area = image, 0
    for index in range(image.n_frames):
        image.seek(index)
        area = image.width * image.height
        if area > best_area:
            best, best_area = image.copy(), area
    image = best
image.convert("RGBA").resize((256, 256), Image.LANCZOS).save(target, "PNG")
print(f"icon -> {target}")
PYTHON

# --- 3. Portable tarball -----------------------------------------------------
echo "[3/4] Packing the portable tarball..."
TARBALL="$RELEASE_DIR/Click-n-Translate-$VERSION-linux-$ARCH.tar.gz"
rm -f "$TARBALL"
tar -czf "$TARBALL" -C "$REPO_DIR/dist" clickntranslate
echo "  $TARBALL"

# --- 4. AppImage -------------------------------------------------------------
if [ "$SKIP_APPIMAGE" -eq 1 ]; then
    echo "[4/4] Skipping the AppImage."
    exit 0
fi

echo "[4/4] Building the AppImage..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/metainfo"
cp -a "$DIST_DIR/." "$APPDIR/usr/bin/"
cp "$ICON_PNG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/clickntranslate.png"
cp "$ICON_PNG" "$APPDIR/clickntranslate.png"
cp "$REPO_DIR/packaging/linux/io.github.jabrailkhalil.clickntranslate.appdata.xml" \
    "$APPDIR/usr/share/metainfo/"

"$PYTHON" - "$APPDIR" "$REPO_DIR" <<'PYTHON'
import sys, os
sys.path.insert(0, sys.argv[2])
import linux_desktop
import platform_support

appdir = sys.argv[1]
# Inside an AppImage the Exec value is resolved against usr/bin by AppRun.
text = linux_desktop.desktop_entry_text("clickntranslate")
desktop_name = platform_support.DESKTOP_ENTRY_NAME
for path in (
    os.path.join(appdir, desktop_name),
    os.path.join(appdir, "usr", "share", "applications", desktop_name),
):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
print("desktop entry written")
PYTHON

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/clickntranslate" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

APPIMAGETOOL="${APPIMAGETOOL:-$REPO_DIR/build/appimagetool-$ARCH.AppImage}"
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "  downloading appimagetool..."
    curl -fsSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

APPIMAGE="$RELEASE_DIR/Click-n-Translate-$VERSION-linux-$ARCH.AppImage"
rm -f "$APPIMAGE"
# appimagetool asks appstreamcli to resolve every <url>, so a slow Telegram or
# GitHub endpoint can make an otherwise reproducible local build fail. Validate
# the complete metadata deterministically first, then tell appimagetool not to
# repeat the same validation with network access.
if command -v appstreamcli >/dev/null 2>&1; then
    appstreamcli validate --no-net \
        "$APPDIR/usr/share/metainfo/io.github.jabrailkhalil.clickntranslate.appdata.xml"
fi
# --appimage-extract-and-run keeps this working where FUSE is unavailable
# (containers, WSL, some CI images).
ARCH="$ARCH" "$APPIMAGETOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$APPIMAGE"

echo
echo "Artifacts:"
echo "  $TARBALL"
echo "  $APPIMAGE"
( cd "$RELEASE_DIR" && sha256sum "$(basename "$TARBALL")" "$(basename "$APPIMAGE")" > "Click-n-Translate-$VERSION-linux-$ARCH.sha256" )
echo "  $RELEASE_DIR/Click-n-Translate-$VERSION-linux-$ARCH.sha256"
