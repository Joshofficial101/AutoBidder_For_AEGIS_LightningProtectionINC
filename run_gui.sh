#!/bin/bash

# --- Ensure we are in the script's directory (the project root) ---
cd "$(dirname "$0")"

# --- Launching LightningBid GUI using the ABSOLUTE venv Python ---
# This path points directly to the Python executable where bcrypt is installed (Python 3.13).
if [ -f ".venv/bin/python" ]; then
    echo "--- Launching LightningBid GUI with venv Python ---"
    ./.venv/bin/python -m src.gui.run_gui
else
    echo "ERROR: Virtual environment not found at .venv/bin/python. Please run ./setup.sh first."
    exit 1
fi