#!/usr/bin/env bash
set -euo pipefail
python -m pytest -q
historyforgeai run --topic "Ashoka and the Kalinga War" --provider mock --no-audio
historyforgeai list
