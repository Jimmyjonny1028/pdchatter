#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install --no-cache-dir -r requirements.txt

# The `build.sh` script is complete. Render will now run the `start.sh` or
# the command specified in your Render dashboard to start the server.
echo "Build complete."
