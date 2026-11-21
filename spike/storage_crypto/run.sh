#!/usr/bin/env bash
# One command from a clean checkout: creates a virtual environment, installs
# the pinned packages and runs every test. Needs Python 3.13 and access to PyPI.
set -euo pipefail
cd "$(dirname "$0")"
VENV="${SPIKE_VENV:-.venv}"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --disable-pip-version-check -r requirements.txt
exec "$VENV/bin/python" -m pytest -p no:cacheprovider "$@"
