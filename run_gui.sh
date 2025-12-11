#!/bin/bash

# --- Ensure we are in the script's directory (the project root) ---
cd "$(dirname "$0")"

echo "--- 1. Activating Virtual Environment ---"
# Check if the environment exists before trying to activate
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "ERROR: Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

echo "--- 2. Launching LightningBid GUI ---"
# Run the application as a module from the root
python -m src.gui.run_gui

# --- Deactivate environment after the app closes ---
deactivate