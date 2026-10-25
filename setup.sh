#!/usr/bin/env bash
# macOS/Linux source setup. Run from a trusted OpenLUFS source download.
set -euo pipefail
cd -- "$(dirname -- "$0")"
mode=venv
if [[ "${1:-}" == "--no-venv" ]]; then mode=target
elif [[ -n "${1:-}" ]]; then echo "Usage: bash setup.sh [--no-venv]"; exit 2; fi
python_bin=""
for candidate in "${OPENLUFS_PYTHON:-}" python3.12 python3.13 python3.11 python3.14 python3; do
    [[ -n "$candidate" ]] || continue
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(not ((3,11) <= sys.version_info[:2] <= (3,14)))'; then
        python_bin="$("$candidate" -c 'import sys; print(sys.executable)')"; break
    fi
done
if [[ -z "$python_bin" ]]; then echo "Install Python 3.12, then run this command again."; exit 1; fi
if ! command -v ffmpeg >/dev/null 2>&1; then echo "Install FFmpeg first; see README.md."; exit 1; fi
if [[ "$mode" == venv ]]; then
    "$python_bin" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python tools/fetch_mp3rgain.py
    printf '%s\n' venv > .openlufs-source-mode
else
    "$python_bin" -m pip install --upgrade --target .python-deps -r requirements.txt
    "$python_bin" tools/fetch_mp3rgain.py
    printf '%s\n' "$python_bin" > .openlufs-python
    printf '%s\n' target > .openlufs-source-mode
fi
echo "Setup finished. Start OpenLUFS with: bash run.sh"
