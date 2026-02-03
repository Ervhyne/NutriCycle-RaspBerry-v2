#!/bin/bash
# Start WebRTC server and ngrok tunnel together

set -e

echo "🚀 Starting NutriCycle WebRTC Stream..."

# Kill any existing processes
pkill -f webrtc_server.py || true
pkill -f ngrok || true
sleep 1

# Check if user is in video group
if ! groups | grep -q video; then
    echo "⚠️  Warning: User not in 'video' group!"
    echo "   Run: sudo usermod -a -G video \$USER"
    echo "   Then logout and login again"
    echo ""
fi

# Check camera access
echo "📹 Checking camera access..."
if ! ls /dev/video* 1> /dev/null 2>&1; then
    echo "❌ No camera found! Connect your camera and try again."
    exit 1
fi
echo "✅ Camera devices found: $(ls /dev/video* | tr '\n' ' ')"

# Activate venv
if [ -d ~/yolo/venv ]; then
    source ~/yolo/venv/bin/activate
else
    echo "❌ Virtual environment not found"
    exit 1
fi

cd ~/NutriCycle-RaspBerry-v2/deploy

# Start WebRTC server in background
echo "📹 Starting WebRTC server on port 8080..."
python3 webrtc_server.py \
  --model models/best.onnx \
  --source 0 \
  --conf 0.5 \
  --flip vertical \
  --port 8080 \
  --host 0.0.0.0 &

WEBRTC_PID=$!

# Wait for server to start
sleep 3

# Start ngrok tunnel
echo "🌐 Starting ngrok tunnel..."
ngrok http 8080 --log=stdout &

NGROK_PID=$!

echo ""
echo "✅ Services started!"
echo "   WebRTC PID: $WEBRTC_PID"
echo "   ngrok PID: $NGROK_PID"
echo ""
echo "📱 Local access: http://raspberrypi.local:8080"
echo "🌐 Internet access: Check ngrok output above for https URL"
echo ""
echo "To stop: killall python3 ngrok"
echo "To view logs: journalctl -f"

# Wait for both processes
wait
