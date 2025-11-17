#!/bin/bash
set -e

echo "--- Build Script Started (Prepare Only) ---"

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install rclone (Download Only)
if [ ! -f "./rclone" ]; then
    echo "Downloading rclone..."
    curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip
    unzip -o rclone-current-linux-amd64.zip
    cd rclone-*-linux-amd64
    cp rclone ../rclone
    cd ..
    rm -rf rclone-*-linux-amd64 rclone-current-linux-amd64.zip
    chmod +x rclone
    echo "rclone binary ready."
else
    echo "rclone already exists."
fi

echo "--- Build Script Finished ---"