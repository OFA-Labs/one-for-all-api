#!/usr/bin/env sh
set -eu
handoff_path=${1:?Pass the external developer_handoff.yaml path}
api_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$api_root"
if [ ! -x .venv-voice/bin/python ]; then
  python3.12 -m venv .venv-voice
fi
voice_python="$api_root/.venv-voice/bin/python"
"$voice_python" -m pip install -r requirements.txt -r requirements-local-execution.txt -r requirements-voice.txt
"$voice_python" scripts/handoff_check.py --handoff "$handoff_path"
"$voice_python" -m voice --fake-demo
printf '%s\n' SETUP_OK
