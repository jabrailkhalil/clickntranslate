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

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel >/dev/null

"$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements-linux.txt"
"$VENV_DIR/bin/python" -m pip install --no-deps argostranslate
"$VENV_DIR/bin/python" -m pip install pytest pyinstaller

echo
echo "Virtualenv ready: $VENV_DIR"
echo "Run the tests with:"
echo "  $VENV_DIR/bin/python -m pytest tests -q"
