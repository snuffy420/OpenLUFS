#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
mode="$(cat .openlufs-source-mode 2>/dev/null || true)"
if [[ "$mode" == target ]]; then
    python_bin="$(cat .openlufs-python)"
    if [[ ! -x "$python_bin" || ! -d .python-deps ]]; then echo "Run bash setup.sh --no-venv again."; exit 1; fi
    export PYTHONPATH="$PWD/.python-deps${PYTHONPATH:+:$PYTHONPATH}"
    export PYTHONNOUSERSITE=1
    exec "$python_bin" norm.py "$@"
elif [[ -x .venv/bin/python ]]; then
    exec .venv/bin/python norm.py "$@"
else
    echo "Run bash setup.sh or bash setup.sh --no-venv first. See README.md."
    exit 1
fi
