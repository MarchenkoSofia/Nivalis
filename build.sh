#!/usr/bin/env bash
# Сборка AppImage. Готовит окружение в build/venv и вызывает packaging/linux/build-appimage.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV="$ROOT/build/venv"

if [ ! -x "$VENV/bin/python" ]; then
    echo "Создаю окружение для сборки..."
    python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q --disable-pip-version-check -r "$ROOT/requirements.txt" pyinstaller

PYTHON="$VENV/bin/python" exec bash "$ROOT/packaging/linux/build-appimage.sh"
