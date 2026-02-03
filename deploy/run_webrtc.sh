#!/bin/bash
# Quick launch script for WebRTC streaming server

set -e

# Activate virtual environment
if [ -d ~/yolo/venv ]; then
    source ~/yolo/venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  Virtual environment not found at ~/yolo/venv"
    echo "   Creating it now..."
    python3 -m venv ~/yolo/venv
    source ~/yolo/venv/bin/activate
fi

# Install dependencies if needed
echo "Checking dependencies..."
pip3 install --quiet aiohttp aiortc av opencv-python numpy ultralytics onnxruntime

cd ~/NutriCycle-RaspBerry-v2/deploy

echo ""
echo "🚀 Starting WebRTC Server..."
echo "   Model: models/best.onnx"
echo "   Camera: /dev/video0 (index 0)"
echo "   Port: 8080"
echo ""
echo "📱 Access locally at: http://raspberrypi.local:8080"
echo "🌐 For internet access, run: ngrok http 8080"
echo ""

# Run with default settings
python3 webrtc_server.py \
  --model models/best.onnx \
  --source 0 \
  --conf 0.5 \
  --flip vertical \
  --port 8080 \
  --host 0.0.0.0
