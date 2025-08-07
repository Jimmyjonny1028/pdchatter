#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies for OCR
apt-get update && apt-get install -y tesseract-ocr

# Install Python dependencies
pip install -r requirements.txt