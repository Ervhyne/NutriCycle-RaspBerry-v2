# 🚀 Quick Start: Raspberry Pi Setup

**TL;DR:** All models are included in the repo. Just clone, run setup, and start the server.

---

## Prerequisites
- Raspberry Pi 4/5 (4GB+ recommended) running Raspberry Pi OS or Ubuntu 64-bit
- Python 3.10 or 3.11
- Internet connection (initial setup only)
- USB camera connected

---

## Setup (5 minutes)

### 1. Clone the repo
```bash
cd ~
git clone https://github.com/<your-org>/NutriCycle-RaspBerry-v2.git nutricycle
cd nutricycle
```

### 2. Run the automated setup
```bash
./deploy/pi_setup.sh
```

This will:
- ✓ Create a Python virtual environment
- ✓ Install all dependencies (OpenCV, Ultralytics, aiortc, PyAV, MQTT)
- ✓ Copy trained models from `AI-Model/` to `deploy/models/`

### 3. Activate the environment
```bash
source venv/bin/activate
```

### 4. Configure environment (optional)
```bash
cp deploy/.env.example deploy/.env
nano deploy/.env
```

Edit values:
- `MACHINE_ID` — unique ID for this device (e.g., RPI-001)
- `ANNOUNCE_SERVER` — your Node.js server URL for device registration
- `MQTT_BROKER` — MQTT broker for detection alerts and ESP32 integration

### 5. Test the camera
```bash
python deploy/test_video.py --model deploy/models/best.pt --source 0 --conf 0.25
```

Press `q` to quit.

### 6. Start the WebRTC server
```bash
python deploy/webrtc_server.py \
  --model deploy/models/best.pt \
  --source 0 \
  --machine-id RPI-001 \
  --conf 0.25 \
  --host 0.0.0.0 \
  --port 8080
```

Open `http://<raspberry-pi-ip>:8080` in your browser to see live detection.

---

## Internet Access (ngrok)

For remote access, use ngrok:

```bash
# Install ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz
tar -xvzf ngrok-v3-stable-linux-arm64.tgz
sudo mv ngrok /usr/local/bin/

# Run ngrok (in a separate terminal)
ngrok http 8080
```

The server auto-detects ngrok and announces the public URL.

---

## Run as a Service (Auto-start)

### 1. Create systemd service
```bash
sudo nano /etc/systemd/system/nutricycle.service
```

Paste this configuration:

```ini
[Unit]
Description=NutriCycle WebRTC Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/nutricycle
EnvironmentFile=/home/pi/nutricycle/deploy/.env
ExecStart=/home/pi/nutricycle/venv/bin/python \
  /home/pi/nutricycle/deploy/webrtc_server.py \
  --model "deploy/models/best.pt" --source 0 --machine-id "$MACHINE_ID" \
  --announce-server "$ANNOUNCE_SERVER" --announce-interval "$ANNOUNCE_INTERVAL" \
  --mqtt-broker "$MQTT_BROKER" --mqtt-port "$MQTT_PORT" \
  --mqtt-topic "$MQTT_TOPIC" --mqtt-esp-topic "$MQTT_ESP_TOPIC" \
  --control-token "$CONTROL_TOKEN" --conf 0.25
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2. Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable nutricycle.service
sudo systemctl start nutricycle.service
```

### 3. Check status and logs
```bash
sudo systemctl status nutricycle.service
sudo journalctl -u nutricycle.service -f
```

---

## Models

✅ **Models are included in the repo** at:
- `AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt` (PyTorch)
- `AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx` (ONNX)

The setup script automatically copies them to `deploy/models/` for easy access.

**Recommendation:** Use `best.pt` (PyTorch) for best performance with Ultralytics. ONNX is optional.

---

## Features

✅ **WebRTC live streaming** — View detection in any browser
✅ **MQTT integration** — Publish detections to MQTT broker for ESP32 alerts
✅ **Device announcement** — Auto-register with your Node.js server
✅ **Remote control** — Accept start/stop commands from your backend
✅ **Automatic public URL detection** — Works with ngrok out of the box
✅ **Foreign object detection** — Trained model included

---

## Troubleshooting

**Camera not working?**
- Try different camera index: `--source 1` or `--source 2`
- Check camera permissions: `ls -l /dev/video*`
- Test with: `raspistill -o test.jpg` (Pi Camera) or `v4l2-ctl --list-devices` (USB)

**Dependencies failed?**
- Make sure you're using Python 3.10 or 3.11: `python3 --version`
- Try installing system libs: `sudo apt install build-essential libatlas-base-dev`

**ONNX runtime not installed?**
- Use the PyTorch model instead: `--model deploy/models/best.pt`
- Or install via conda: `conda install -c conda-forge onnxruntime`

**Server won't start?**
- Check port 8080 is not in use: `sudo lsof -i :8080`
- Try a different port: `--port 8081`

---

## Next Steps

📖 Read [RASPBERRY_PI_INTEGRATION.md](RASPBERRY_PI_INTEGRATION.md) for advanced setup
📖 Read [INTERNET_ACCESS.md](INTERNET_ACCESS.md) for Cloudflare Tunnel and Tailscale options
📖 Check [README.md](README.md) for development and testing guides

---

**Ready to detect foreign objects!** 🎯
