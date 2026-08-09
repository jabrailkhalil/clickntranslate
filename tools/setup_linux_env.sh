#!/usr/bin/env bash
# Creates the Linux development/build virtualenv for Click'n'Translate.
#
# Usage: tools/setup_linux_env.sh [venv-path]
#
# argostranslate is installed with --no-deps on purpose: its dependency tree
# pulls stanza (and therefore torch, ~2 GB) only for sentence boundary
# detection, which translater.py replaces with its own splitter. The runtime
# pieces Argos actually needs — ctranslate2 and sentencepiece — come from
# requirements-linux.txt.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${1:-$HOME/.venvs/clickntranslate}"

# Qt's xcb platform plugin links these, and PyInstaller does not follow a
# plugin's own dependencies. Without them on the build machine there is nothing
# to bundle, and the app cannot open a window: "Could not load the Qt platform
# plugin xcb". The spec fails the build if they are missing.
X11_PACKAGES="libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
libxcb-shape0 libxcb-xinerama0 libxcb-util1 libxkbcommon-x11-0"
if command -v apt-get > /dev/null; then
    echo "Installing the Qt X11 runtime libraries..."
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update -qq && apt-get install -y -qq $X11_PACKAGES
    elif command -v sudo > /dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq $X11_PACKAGES
    else
        echo "  skipped: no root and no sudo. Install manually:" >&2
        echo "    apt-get install -y $X11_PACKAGES" >&2
    fi
else
    echo "Not a Debian-based system; make sure these are installed: $X11_PACKAGES"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel >/dev/null

"$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements-linux.txt"
"$VENV_DIR/bin/python" -m pip install --no-deps argostranslate
"$VENV_DIR/bin/python" -m pip install pytest pyinstaller

echo
echo "Virtualenv ready: $VENV_DIR"
echo "Run the tests with:"
echo "  $VENV_DIR/bin/python -m pytest tests -q"
