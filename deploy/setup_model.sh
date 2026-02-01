#!/usr/bin/env bash
set -euo pipefail

# NutriCycle - Setup model for Raspberry Pi deployment
# This script copies the trained model from AI-Model/ to deploy/models/
# Run from repo root: ./deploy/setup_model.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Source model location
SOURCE_MODEL="AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt"
SOURCE_ONNX="AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx"

# Destination
DEST_DIR="deploy/models"
mkdir -p "$DEST_DIR"

echo "=== NutriCycle Model Setup ==="

# Copy best.pt (PyTorch model - recommended)
if [ -f "$SOURCE_MODEL" ]; then
  echo "Copying $SOURCE_MODEL -> $DEST_DIR/best.pt"
  cp "$SOURCE_MODEL" "$DEST_DIR/best.pt"
  echo "✓ best.pt ready"
else
  echo "⚠ Warning: $SOURCE_MODEL not found"
fi

# Copy best.onnx if available (optional, for ONNX runtime)
if [ -f "$SOURCE_ONNX" ]; then
  echo "Copying $SOURCE_ONNX -> $DEST_DIR/best.onnx"
  cp "$SOURCE_ONNX" "$DEST_DIR/best.onnx"
  echo "✓ best.onnx ready"
else
  echo "ℹ Info: ONNX model not found (optional)"
fi

echo ""
echo "=== Model files ready in $DEST_DIR/ ==="
ls -lh "$DEST_DIR/"

echo ""
echo "Next steps:"
echo "1. Run: source venv/bin/activate"
echo "2. Test: python deploy/test_video.py --model deploy/models/best.pt --source 0"
echo "3. Start server: python deploy/webrtc_server.py --model deploy/models/best.pt --source 0"
