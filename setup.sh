#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "--- 1. Creating Virtual Environment (.venv) ---"
# Use python3 on Mac/Linux systems where 'python' might be aliased to Python 2
python3 -m venv .venv

echo "--- 2. Activating and Installing Dependencies ---"
# Activate the environment and run the install command
source .venv/bin/activate
pip install -r requirements.txt

echo "--- 3. Making run_gui.sh executable ---"
# Ensure the run script has execute permissions
chmod +x run_gui.sh

echo "===================================="
echo "✅ SETUP COMPLETE!"
echo "Run the application next time with: ./run_gui.sh"
echo "===================================="

# Deactivate the environment after setup
deactivate