#!/bin/bash
# Example startup script for NutriCycle WebRTC server with status updates
# Save as: ~/NutriCycle-RaspBerry-v2/deploy/start_stream_with_status.sh
# Usage: ./start_stream_with_status.sh

set -e

echo "🚀 Starting NutriCycle WebRTC Stream with Status Updates..."

# Configuration
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"
VENV_DIR="${HOME}/yolo/venv"

# Load environment variables from .env
if [ -f "$DEPLOY_DIR/.env" ]; then
    echo "📋 Loading configuration from .env..."
    set -a
    source "$DEPLOY_DIR/.env"
    set +a
else
    echo "⚠️  .env file not found in $DEPLOY_DIR"
    echo "   Copy from .env.example and configure:"
    echo "   cp $DEPLOY_DIR/.env.example $DEPLOY_DIR/.env"
    exit 1
fi

# Validate required variables
if [ -z "$MACHINE_ID" ]; then
    echo "❌ Error: MACHINE_ID not set in .env"
    exit 1
fi

if [ -z "$API_BASE_URL" ]; then
    echo "⚠️  Warning: API_BASE_URL not set - status updates disabled"
fi

if [ -z "$MACHINE_SECRET" ]; then
    echo "⚠️  Warning: MACHINE_SECRET not set - status updates disabled"
fi

# Activate venv
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Error: Virtual environment not found at $VENV_DIR"
    echo "   Run: bash $DEPLOY_DIR/pi_setup.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Kill any existing processes
echo "🧹 Cleaning up old processes..."
pkill -f webrtc_server.py || true
pkill -f ngrok || true
sleep 1

# Check camera access (retry on boot because camera device can appear late)
echo "📹 Checking camera access..."
CAMERA_WAIT_SECONDS="${CAMERA_WAIT_SECONDS:-25}"
camera_ready=0
for ((i=1; i<=CAMERA_WAIT_SECONDS; i++)); do
    if ls /dev/video* 1> /dev/null 2>&1; then
        camera_ready=1
        break
    fi
    echo "   Waiting for camera device... (${i}/${CAMERA_WAIT_SECONDS})"
    sleep 1
done

if [ "$camera_ready" -ne 1 ]; then
    echo "❌ No camera found after ${CAMERA_WAIT_SECONDS}s. Connect camera and reboot or restart service."
    exit 1
fi

echo "✅ Camera devices found: $(ls /dev/video* | tr '\n' ' ')"

# Verify user is in video group
if ! groups | grep -q video; then
    echo "⚠️  Warning: User not in 'video' group!"
    echo "   Run: sudo usermod -a -G video $USER"
    echo "   Then logout and login again"
    echo ""
fi

cd "$DEPLOY_DIR"

# Start WebRTC server with status update configuration
echo "📹 Starting WebRTC server on port 8080..."
echo "   Machine ID: $MACHINE_ID"
if [ -n "$API_BASE_URL" ] && [ -n "$MACHINE_SECRET" ]; then
    echo "   API: $API_BASE_URL"
    echo "   Status Updates: Enabled (every ${STATUS_UPDATE_INTERVAL:-60}s)"
else
    echo "   Status Updates: Disabled (missing API_BASE_URL or MACHINE_SECRET)"
fi
echo ""

python3 webrtc_server.py \
  --model models/best.onnx \
  --source 0 \
  --conf 0.5 \
  --flip vertical \
  --port 8080 \
  --host 0.0.0.0 \
  --machine-id "$MACHINE_ID" \
  --api-base-url "$API_BASE_URL" \
  --machine-secret "$MACHINE_SECRET" \
  --status-update-interval "${STATUS_UPDATE_INTERVAL:-60}" \
  --announce-server "$ANNOUNCE_SERVER" \
  --announce-interval "${ANNOUNCE_INTERVAL:-60}" \
  $ADDITIONAL_ARGS &

WEBRTC_PID=$!

# Ensure WebRTC really started; fail fast so systemd can restart the service.
sleep 3
if ! kill -0 "$WEBRTC_PID" 2>/dev/null; then
    echo "❌ WebRTC process exited right after startup."
    echo "   Check service logs: sudo journalctl -u nutricycle.service -n 200 --no-pager"
    exit 1
fi

echo ""
echo "✅ WebRTC server started (PID: $WEBRTC_PID)"
echo ""
echo "📱 Local access: http://raspberrypi.local:8080"
echo "   or: http://$(hostname -I | awk '{print $1}'):8080"
echo ""

# Optional: Start ngrok tunnel for internet access
if command -v ngrok &> /dev/null; then
    echo "🌐 Starting ngrok tunnel..."
    ngrok http 8080 --log=stdout &
    NGROK_PID=$!
    echo "   Check ngrok output above for public https URL"
    sleep 2
else
    echo "ℹ️  ngrok not found - public access disabled"
    echo "   To enable: curl -fsSL https://ngrok-agent.s3.amazonaws.com/ngrok.sh | bash"
fi

echo ""
echo "================================================"
echo "NutriCycle WebRTC Stream is Running"
echo "================================================"
echo ""
echo "✅ Status Updates: Server will send machine status every ${STATUS_UPDATE_INTERVAL:-60} seconds"
echo "   Check logs below for confirmation:"
echo "   - 'Machine status updated to online'"
echo "   - 'Machine status heartbeat sent'"
echo ""
echo "To stop: killall python3 ngrok (or Ctrl+C)"
echo "To view logs: journalctl -f (if running as systemd service)"
echo ""

# Keep service tied to the WebRTC process. If it exits, systemd will restart.
wait "$WEBRTC_PID"
