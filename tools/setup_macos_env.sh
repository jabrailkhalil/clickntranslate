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
"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r requirements-macos.txt 'pyinstaller>=6.16,<7' pytest
"$VENV/bin/python" -m pip install --no-deps 'argostranslate~=1.11.0'
echo "Ready. Start with: $VENV/bin/python main.py"
