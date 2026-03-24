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

# Runtime configuration (defaults are safe for existing setup)
MODEL_PATH="${MODEL_PATH:-models/best.onnx}"
VIDEO_SOURCE="${VIDEO_SOURCE:-0}"
CONFIDENCE="${CONFIDENCE:-0.5}"
FLIP_MODE="${FLIP_MODE:-vertical}"
WEBRTC_HOST="${WEBRTC_HOST:-0.0.0.0}"
WEBRTC_PORT="${WEBRTC_PORT:-8080}"
INFERENCE_IMGSZ="${INFERENCE_IMGSZ:-320}"
AUTO_CAMERA_PROBE="${AUTO_CAMERA_PROBE:-true}"
CAMERA_PROBE_MAX_INDEX="${CAMERA_PROBE_MAX_INDEX:-4}"
NGROK_REQUIRED="${NGROK_REQUIRED:-true}"
NGROK_READY_TIMEOUT="${NGROK_READY_TIMEOUT:-20}"

# Resolve camera source robustly on boot. Prefer configured source first, then probe indices.
CAMERA_SOURCE="$VIDEO_SOURCE"
if [[ "$VIDEO_SOURCE" =~ ^[0-9]+$ ]] && [[ "${AUTO_CAMERA_PROBE,,}" == "true" ]]; then
    echo "🔎 Probing camera source (preferred: $VIDEO_SOURCE)..."
    if PROBED_SOURCE=$(python3 - "$VIDEO_SOURCE" "$CAMERA_PROBE_MAX_INDEX" <<'PY'
import sys
import time
import cv2

preferred = int(sys.argv[1])
max_index = int(sys.argv[2])

order = [preferred] + [i for i in range(max_index + 1) if i != preferred]
for idx in order:
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap.release()
        continue

    ok = False
    for _ in range(8):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            ok = True
            break
        time.sleep(0.08)

    cap.release()
    if ok:
        print(idx)
        raise SystemExit(0)

raise SystemExit(1)
PY
); then
        CAMERA_SOURCE="$PROBED_SOURCE"
        echo "✅ Camera source selected: $CAMERA_SOURCE"
    else
        echo "⚠️  Camera probe failed. Falling back to configured source: $VIDEO_SOURCE"
    fi
else
    echo "ℹ️  Camera source fixed from config: $CAMERA_SOURCE"
fi

# Start WebRTC server with status update configuration
echo "📹 Starting WebRTC server on port $WEBRTC_PORT..."
echo "   Camera source: $CAMERA_SOURCE"
echo "   Machine ID: $MACHINE_ID"
if [ -n "$API_BASE_URL" ] && [ -n "$MACHINE_SECRET" ]; then
    echo "   API: $API_BASE_URL"
    echo "   Status Updates: Enabled (every ${STATUS_UPDATE_INTERVAL:-60}s)"
else
    echo "   Status Updates: Disabled (missing API_BASE_URL or MACHINE_SECRET)"
fi
echo ""

python3 webrtc_server.py \
    --model "$MODEL_PATH" \
    --source "$CAMERA_SOURCE" \
    --conf "$CONFIDENCE" \
    --flip "$FLIP_MODE" \
    --port "$WEBRTC_PORT" \
    --host "$WEBRTC_HOST" \
    --imgsz "$INFERENCE_IMGSZ" \
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
echo "📱 Local access: http://raspberrypi.local:$WEBRTC_PORT"
echo "   or: http://$(hostname -I | awk '{print $1}'):$WEBRTC_PORT"
echo ""

# Optional: Start ngrok tunnel for internet access
if command -v ngrok &> /dev/null; then
    echo "🌐 Starting ngrok tunnel..."
    ngrok http "$WEBRTC_PORT" --log=stdout &
    NGROK_PID=$!
    echo "   Waiting for ngrok public URL (timeout: ${NGROK_READY_TIMEOUT}s)..."

    NGROK_PUBLIC_URL=""
    for ((i=1; i<=NGROK_READY_TIMEOUT; i++)); do
        if ! kill -0 "$NGROK_PID" 2>/dev/null; then
            echo "❌ ngrok process exited during startup."
            break
        fi

        if command -v curl &> /dev/null; then
            NGROK_PUBLIC_URL=$(curl -fsS http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(next((t.get('public_url','') for t in d.get('tunnels',[]) if str(t.get('public_url','')).startswith('https://')), ''))" 2>/dev/null || true)
            if [ -n "$NGROK_PUBLIC_URL" ]; then
                break
            fi
        fi

        sleep 1
    done

    if [ -n "$NGROK_PUBLIC_URL" ]; then
        echo "✅ ngrok public URL: $NGROK_PUBLIC_URL"
    else
        echo "⚠️  ngrok started but no public URL detected yet."
        if [ "${NGROK_REQUIRED,,}" = "true" ]; then
            echo "❌ NGROK_REQUIRED=true, exiting so systemd can retry after network is ready."
            kill "$WEBRTC_PID" 2>/dev/null || true
            wait "$WEBRTC_PID" 2>/dev/null || true
            exit 1
        fi
    fi
else
    echo "ℹ️  ngrok not found - public access disabled"
    echo "   To enable: curl -fsSL https://ngrok-agent.s3.amazonaws.com/ngrok.sh | bash"
    if [ "${NGROK_REQUIRED,,}" = "true" ]; then
        echo "❌ NGROK_REQUIRED=true but ngrok is not installed."
        kill "$WEBRTC_PID" 2>/dev/null || true
        wait "$WEBRTC_PID" 2>/dev/null || true
        exit 1
    fi
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
