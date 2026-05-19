#!/usr/bin/env bash
# Exit immediately if any command exits with a non-zero status
set -o errexit

echo "--- Starting Build Phase ---"

# 1. Upgrade pip to ensure smooth package compilation
pip install --upgrade pip

# 2. Install your required dependencies
pip install -r requirements.txt

# 3. Collect all static files for production (handled by WhiteNoise)
python manage.py collectstatic --no-input

echo "--- Build Phase Completed Successfully ---"