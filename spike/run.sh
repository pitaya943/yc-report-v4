#!/usr/bin/env bash
# One command from a clean checkout: install, run every test, write the samples.
# Needs Python 3.11+ and PostgreSQL binaries (initdb, pg_ctl); no running database.
#   ./run.sh           tests + samples
#   ./run.sh prove     also break each behaviour and show its test fail (about 2 minutes)
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
.venv/bin/python -m pytest -v
.venv/bin/python -m spike_exports.make_samples out
if [ "${1:-}" = "prove" ]; then
    .venv/bin/python prove_fail.py
fi
