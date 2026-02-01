# Raspberry Pi Integration Guide 🐧🔧

This guide shows how to prepare a Raspberry Pi (or similar Debian-based ARM device) to run the NutriCycle WebRTC + YOLO server, host the model locally, announce its public URL to your Node server, and publish detection events to MQTT for ESP32 alerts.

---

## Goals ✅
- Recreate the repo layout on the Pi and install runtime dependencies
- Download and place the model into `deploy/models/`
- Run the WebRTC server (`deploy/webrtc_server.py`) as a service
- Make the device announce its public video URL and MachineID to your Node server
- Publish detection events to MQTT and forward control commands from Node → ESP32

---

## Supported / Recommended Hardware & OS
- Raspberry Pi 4/5 (4GB+ recommended) or Pi Zero 2W for lightweight tasks
- OS: Raspberry Pi OS 64-bit or Ubuntu 22.04/24.04 (64-bit recommended)
- Use Python 3.10 or 3.11 for best binary wheel support

---

## Expected repo layout on the Pi (recommended)
```
~/nutricycle/                       # git clone here
  deploy/
    webrtc_server.py
    test_video.py
    get_model.sh
    get_model.ps1
    requirements.txt
    RASPBERRY_PI_INTEGRATION.md
    ANNOUNCE.md
    get_model.sh
    models/                         # place best.onnx / best.pt here
  AI-Model/                          # dataset / other stuff (ignored)
```

---

## 1) Prepare the Pi (apt + system packages)
Run (as pi or sudo):
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git wget curl pkg-config libatlas-base-dev libjpeg-dev libopenjp2-7-dev libtiff5-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev ffmpeg
```
Notes:
- `ffmpeg` helps PyAV and some inference pipelines. If you plan headless, install `opencv-python-headless` (pip). 

---

## 2) Clone repo and create a venv
```bash
cd ~
git clone https://github.com/<org>/NutriCycle-RaspBerry.git nutricycle
cd nutricycle
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

---

## 3) Install Python deps
Use the included `deploy/requirements.txt`:
```bash
source venv/bin/activate
python -m pip install -r deploy/requirements.txt
# Recommended: install opencv headless
python -m pip install opencv-python-headless
```
Notes:
- `onnxruntime` is recommended for `.onnx` models. If `pip install onnxruntime` fails on Pi, try Conda/mamba or find a prebuilt wheel for your platform (ONNX Runtime releases). 
- PyAV (`av`) may need the ffmpeg system libs (we installed them above). If pip wheel fails, build PyAV or use conda.

---

## 4) Download the model (place into `deploy/models/`)
Options:
- Use hosted model URL (recommended):
  ```bash
  ./deploy/get_model.sh https://storage.example.com/best.onnx deploy/models/best.onnx
  ```
- Or copy manually via `scp` or USB

Confirm:
```bash
ls -lh deploy/models
```

---

## 5) Configure environment (.env)
Copy template and edit values:
```bash
cp deploy/.env.example deploy/.env
# Edit the values with your MACHINE_ID, MQTT broker, ANNOUNCE_SERVER etc.
```
Important entries:
- `MACHINE_ID` — unique ID for the device
- `ANNOUNCE_SERVER` — your Node server API endpoint for announcing
- `MQTT_BROKER`, `MQTT_PORT` — MQTT broker for detection/ESP alerts
- `CONTROL_TOKEN` — if you require the Node server to authenticate control calls

---

## 6) Run manually (smoke test)
```bash
source venv/bin/activate
python deploy/webrtc_server.py --model deploy/models/best.onnx --source 0 --machine-id RPI-001 --announce-server https://your-node.example.com/api/announce --mqtt-broker mqtt.example.com
```
- Open `http://localhost:8080` or (from another device) `http://<pi-ip>:8080`
- If using ngrok, start ngrok and the server will auto-detect the public URL (ngrok exposes local API on port 4040)

---

## 7) Create a systemd service (auto-start)
Create `/etc/systemd/system/nutricycle.service` with contents:

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
  --model "deploy/models/best.onnx" --source 0 --machine-id "$MACHINE_ID" \
  --announce-server "$ANNOUNCE_SERVER" --announce-interval "$ANNOUNCE_INTERVAL" \
  --mqtt-broker "$MQTT_BROKER" --mqtt-port "$MQTT_PORT" --mqtt-topic "$MQTT_TOPIC" --mqtt-esp-topic "$MQTT_ESP_TOPIC" \
  --control-token "$CONTROL_TOKEN"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable + start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable nutricycle.service
sudo systemctl start nutricycle.service
sudo journalctl -u nutricycle.service -f
```

---

## 8) Public Access (ngrok / Cloudflare Tunnel / Tailscale)
- Quick test (ngrok): `ngrok http 8080`
- Production (recommended): use **Cloudflare Tunnel** for persistent HTTPS or **Tailscale** for secure private network.
- The server auto-detects an ngrok tunnel URL (localhost:4040) and will announce it if `--announce-server` is configured.

---

## 9) MQTT & ESP32 integration
- Make sure an MQTT broker is reachable from the Pi (local Mosquitto or cloud broker)
- Configure `deploy/.env` with `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_ESP_TOPIC`
- The server publishes full detection JSON to `MQTT_TOPIC` and compact alerts (`{"machine_id":"...","alert":true}`) to `MQTT_ESP_TOPIC` for ESP32 clients
- ESP32 subscribe and act (servo stop) on the compact alert topic

---

## 10) Control API (Node → Pi → ESP32)
- Your Node server can POST authenticated commands to the device public URL `/control`:
```http
POST https://<device-url>/control
Authorization: Bearer <token>
Content-Type: application/json

{ "machine_id": "RPI-001", "command": "stop" }
```
- The Pi validates token (if configured) and forwards the JSON to `MQTT_ESP_TOPIC` for the ESP32.
- Responses: `200 OK` = forwarded, `401/403` = auth, `404` = machine id mismatch

---

## 11) Logs, monitoring & maintenance
- Use `journalctl -u nutricycle.service -f` for logs
- Rotate logs using `logrotate` if you add file-based logging
- To update code: `git pull` (then restart service)
- To update model: replace file at `deploy/models/best.onnx` and restart service

---

## 12) Troubleshooting checklist
- Black screen / no video: check camera index (try `--source 1`, use `cv2.CAP_DSHOW` on Windows), ensure no other app holds the camera
- PyAV import errors: ensure `ffmpeg` + dev libs are installed; use conda if pip wheels fail
- onnxruntime install fail: use Python 3.10/3.11 or Conda; check Raspberry architecture wheel availability
- If announce fails: check `ngrok` is running and accessible via `http://127.0.0.1:4040/api/tunnels`

---

## Quick checklist (summary) ✅
- [ ] Clone repo and create venv
- [ ] Install apt packages + pip deps
- [ ] Download model with `deploy/get_model.sh` or copy it to `deploy/models/`
- [ ] Create `.env` from `.env.example` and fill values
- [ ] Test `python deploy/webrtc_server.py ...` manually
- [ ] Create systemd service and enable it
- [ ] Set up ngrok/Cloudflare/Tailscale and verify public URL
- [ ] Verify announce to Node server and MQTT detection/ESP alerts

---

If you want, I can:
- Add a ready-made `systemd` unit file to `deploy/` for you to customize, or
- Add a small `deploy/announce_once.sh` helper and a `deploy/node_example.js` example to show how the Node server should accept the announce and send a `/control` command.

Which would you like next? 🔧