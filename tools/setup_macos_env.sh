#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Darwin ]]; then
  echo "Run this script on macOS (Apple Silicon or Intel)." >&2
  exit 1
fi
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3.12}"
VENV="${VENV:-.venv-macos}"
"$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12"'
ARCH="$("$PYTHON" -c 'import platform; print(platform.machine())')"
if [[ "$ARCH" != "$(uname -m)" ]]; then
  echo "Use a native Python matching this Mac, without Rosetta." >&2
  exit 1
fi
"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
# On newer hosts pip prefers newer deployment targets (for example NumPy's
# macOS 14 wheel). Resolve for our oldest supported OS, even on a newer Mac.
WHEELS="$(mktemp -d "${TMPDIR:-/tmp}/cnt-macos-wheels.XXXXXX")"
trap 'rm -rf "$WHEELS"' EXIT
"$VENV/bin/python" -m pip download --only-binary=:all: \
  --platform "macosx_13_0_$ARCH" --dest "$WHEELS" \
  -r requirements-macos.txt 'pyinstaller>=6.16,<7' pytest
"$VENV/bin/python" -m pip install --no-index --find-links "$WHEELS" --force-reinstall \
  -r requirements-macos.txt 'pyinstaller>=6.16,<7' pytest
"$VENV/bin/python" -m pip install --no-deps 'argostranslate~=1.11.0'
echo "Ready. Start with: $VENV/bin/python main.py"
