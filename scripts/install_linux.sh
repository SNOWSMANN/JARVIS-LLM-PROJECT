#!/usr/bin/env bash
# Jarvis — Linux / WSL setup. Primary target is Windows; this is for CI/dev boxes.
set -euo pipefail

echo "--- Jarvis Linux installer ---"

if ! command -v python3 >/dev/null; then
    echo "python3 not found. Install Python 3.11 first." >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null; then
    echo "Installing ffmpeg..."
    sudo apt-get update && sudo apt-get install -y ffmpeg portaudio19-dev
fi

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip wheel
pip install -e ".[dev]"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ".env created. Fill in OPENAI_API_KEY and ELEVENLABS_API_KEY before running."
fi

echo
echo "Done. To start:"
echo "  source .venv/bin/activate"
echo "  python -m jarvis text        # text REPL, no mic needed"
echo "  python -m jarvis             # voice loop ('hey jarvis')"
