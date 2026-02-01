#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <MODEL_URL> <DEST_PATH>"
  exit 1
fi

MODEL_URL="$1"
DEST_PATH="$2"

mkdir -p "$(dirname "$DEST_PATH")"

if command -v curl >/dev/null 2>&1; then
  echo "Downloading $MODEL_URL -> $DEST_PATH"
  curl -L --progress-bar -o "$DEST_PATH" "$MODEL_URL"
elif command -v wget >/dev/null 2>&1; then
  echo "Downloading $MODEL_URL -> $DEST_PATH"
  wget -O "$DEST_PATH" "$MODEL_URL"
else
  echo "Error: neither curl nor wget available"
  exit 2
fi

echo "Download complete: $DEST_PATH"
