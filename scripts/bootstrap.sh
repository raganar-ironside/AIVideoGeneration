#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg espeak-ng git fonts-dejavu-core
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp -n .env.example .env || true
printf '\nReady. Run: source .venv/bin/activate && historyforgeai run --topic "Ashoka and the Kalinga War" --provider mock\n'
