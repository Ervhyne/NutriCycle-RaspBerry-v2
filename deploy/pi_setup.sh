#!/usr/bin/env bash
set -euo pipefail

# NutriCycle Raspberry Pi setup helper
# Usage: run on the Pi from the repo root: ./deploy/pi_setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== NutriCycle Pi setup ==="

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10/3.11 before running this script." >&2
  exit 1
fi

python3 --version

# Create virtual environment
if [ ! -d "venv" ]; then
  echo "Creating venv (venv)..."
  python3 -m venv venv
else
  echo "Using existing venv/"
fi

# Activate venv
# shellcheck disable=SC1091
. venv/bin/activate

echo "Upgrading pip and installing base packages..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install numpy

# Install system libs helpful for OpenCV (only if apt is available)
if command -v apt-get >/dev/null 2>&1; then
  echo "Installing recommended system packages for OpenCV (requires sudo)..."
  sudo apt-get update
  sudo apt-get install -y build-essential libatlas-base-dev libjpeg-dev libopenjp2-7-dev libtiff5-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev || true
fi

# Install OpenCV headless (recommended for Pi headless environments)
echo "Installing OpenCV (headless recommended)"
python -m pip install opencv-python-headless || echo "opencv-python-headless install may fall back to building from source if wheels are unavailable"

# Try installing ONNX Runtime (recommended for ONNX CPU inference)
echo "Installing ONNX Runtime (optional but recommended for .onnx models)"
if python -m pip install onnxruntime; then
  echo "onnxruntime installed"
else
  echo "onnxruntime install failed with pip. Try using conda/mamba: 'conda install -c conda-forge onnxruntime' or find a matching wheel at https://github.com/microsoft/onnxruntime/releases" >&2
fi

# Install Ultralytics and extras
echo "Installing ultralytics and recommended Python packages"
python -m pip install ultralytics || echo "ultralytics install failed"

# Optional tracker deps note
echo "If you plan to use tracker packages (ByteTrack/BotSort) and need 'lap', consider: 'conda install -c conda-forge lap' or use a prebuilt wheel on Windows/other platforms."

# Create models dir
mkdir -p models

cat <<'EOF'

=== Next steps ===
- Copy your ONNX model into deploy/models/best.onnx (example):
  scp AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx pi@raspberrypi:/home/pi/nutricycle/deploy/models/best.onnx
  # or transfer however you prefer

- Quick run (camera):
  python deploy/test_video.py --model deploy/models/best.onnx --source 0 --conf 0.25

- If onnxruntime failed above and you need it, try using conda/mamba or find a prebuilt wheel for your Pi's Python and CPU architecture.

EOF

echo "Setup complete. Activate the venv with: source venv/bin/activate"

echo "Note: the script is intended to be run on the Raspberry Pi itself. If you prefer, you can adapt steps to your provisioning system (Ansible, cloud-init, etc.)"
