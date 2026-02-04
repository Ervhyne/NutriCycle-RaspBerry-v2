# NutriCycle WebRTC Server — Full Setup & Test Guide ✅

This document describes a full fresh-start setup to run the WebRTC streaming + ONNX inference server from the `deploy/` folder, expose it with ngrok (optional), and test MQTT and control endpoints.

> Assumptions
> - Repo checkout is at: `NutriCycle-RaspBerry-v2/` and you use `deploy/` on the Raspberry Pi.
> - Virtualenv path: `~/yolo/venv` (activate before installing).
> - You have a camera attached or a video device available (e.g., `/dev/video0`).

---

## 1) Prerequisites 🔧

- OS: Raspberry Pi OS (or Debian-based) for Raspberry; commands below target Linux. If using Windows, adapt virtualenv activation and apt steps.
- Python: 3.10+ recommended
- Camera: USB webcam or Pi camera

System packages (install on Raspberry Pi):

```bash
sudo apt update && sudo apt install -y python3-venv python3-dev build-essential ffmpeg pkg-config \
    libavcodec-dev libavformat-dev libavdevice-dev libavfilter-dev libavutil-dev libswscale-dev \
    libssl-dev libffi-dev libopus-dev libvpx-dev libx264-dev
# Optional: mosquitto for local MQTT broker
sudo apt install -y mosquitto mosquitto-clients
```

---

## 2) Virtualenv & Python packages (venv: `~/yolo/venv`) 🐍

Activate your venv then install requirements:

Linux / macOS:
```bash
source ~/yolo/venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r deploy/requirements.txt
```

PowerShell (Windows):
```powershell
~\yolo\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r deploy/requirements.txt
```

What `deploy/requirements.txt` should provide (high level):
- onnxruntime (or matching ARM wheel on Pi)
- ultralytics
- opencv-python
- numpy
- paho-mqtt
- aiortc, aiohttp
- av (PyAV; system deps above)

Notes:
- On Raspberry Pi you might need a platform-specific `onnxruntime` wheel. If `pip install onnxruntime` fails, check ONNX Runtime ARM instructions.
- If `aiortc` or `av` pip installs fail, ensure the system libs above are present and try again.

---

## 3) Prepare model files 🧠

If you already have an ONNX model (recommended), place it under `AI-Model/...` e.g.:
```
AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx
```

If you only have a `.pt` file, export ONNX (recommended imgsz=320 for Pi performance):
```bash
# run from your YOLO working dir with Ultralytics CLI
yolo export model=models/best.pt format=onnx imgsz=320
```

Verify ONNX runtime availability:
```bash
python -c "import onnxruntime; print('onnxruntime:', onnxruntime.__version__)"
```

---

## 4) Quick smoke tests 🔍

1) Test camera + model locally (non-WebRTC):
```bash
python deploy/test_video.py --model AI-Model/runs/detect/.../best.onnx --source 0 --imgsz 320
```
- You should see an OpenCV window with annotations and FPS.

2) If camera cannot be opened:
- Check `v4l2-ctl --list-devices`
- Add user to video group: `sudo usermod -a -G video $USER`

---

## 5) Start the WebRTC server 🚀

Recommended command (host accessible on LAN):
```bash
python deploy/webrtc_server.py \
  --model AI-Model/runs/detect/.../best.onnx \
  --source 0 \
  --imgsz 320 \
  --conf 0.5 \
  --host 0.0.0.0 --port 8080 \
  --mqtt-broker <MQTT_HOST> --mqtt-port 1883 --mqtt-topic nutricycle/detections --mqtt-esp-topic nutricycle/esp32
```

Server logs to watch:
- `✅ Shared camera opened: 320x320 ...`
- `Streaming at X.X FPS, inference: Y ms`
- `Connected to MQTT broker: <host>` (if MQTT provided)
- `Detection event: N objects from <machine_id>` when detections happen

---

## 6) Open the Web Client (WebRTC) 🌐

- Open a browser and visit `http://<raspberry_ip>:8080/` (or `http://localhost:8080` if local)
- Client should request camera stream; you should see live annotated video and FPS overlay.

Notes: if you expose via ngrok or Cloudflare, see next section.

---

## 7) Expose server via ngrok (optional) 🔗

1. Install ngrok: https://ngrok.com/download and login to get your auth token
2. Run:
```bash
ngrok http 8080
```
3. The forwarding https URL is printed by ngrok. You can provide `--public-url` to the server when starting or let the server auto-detect ngrok (it queries `http://127.0.0.1:4040/api/tunnels`).

---

## 8) Test MQTT end-to-end 🛰️

Subscribe to detection topic from another machine (or locally):
```bash
mosquitto_sub -h <MQTT_HOST> -t nutricycle/detections -v
# compact ESP alerts
mosquitto_sub -h <MQTT_HOST> -t nutricycle/esp32 -v
```

Trigger a detection by placing a target in view. You should see JSON messages printed by `mosquitto_sub` when detections occur.

Test control endpoint to forward commands to ESP32 via MQTT:
```bash
curl -X POST http://<server>:8080/control -H 'Content-Type: application/json' \
  -d '{"machine_id":"<your_machine_id>","command":"start"}'
# If control token is required, add header: -H 'Authorization: Bearer <token>'
```
- The server will publish the command to the MQTT ESP topic if connected.

---

## 9) Verification checklist ✅

- [ ] `python -c "import onnxruntime"` succeeds
- [ ] `python deploy/test_video.py --imgsz 320` shows annotated video
- [ ] `python deploy/webrtc_server.py --imgsz 320` starts and shows camera 320x320 in logs
- [ ] Browser connects and shows annotated stream
- [ ] `mosquitto_sub` receives detection messages on `nutricycle/detections`
- [ ] `curl /control` publishes to `nutricycle/esp32` topic

---

## 10) Troubleshooting tips ⚠️

- If `aiortc` / `av` build fails: install system libs (see Section 1) and retry.
- If onnxruntime failing on Pi: search for prebuilt ARM wheel for your Pi OS release or fall back to `.pt` model for testing.
- Camera not opening: check permissions and that the correct device index is used (`--source 0` or `--source 1`).
- If MQTT messages not received, ensure broker address and port are correct and that a subscription is active.

---

## 11) Run as service (example systemd unit) ⚙️

Create `/etc/systemd/system/nutricycle-webrtc.service` (example):
```ini
[Unit]
Description=NutriCycle WebRTC server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/NutriCycle-RaspBerry-v2
Environment=PATH=/home/pi/yolo/venv/bin
ExecStart=/home/pi/yolo/venv/bin/python deploy/webrtc_server.py --model AI-Model/runs/detect/.../best.onnx --source 0 --imgsz 320 --mqtt-broker <MQTT_HOST>
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nutricycle-webrtc
sudo journalctl -u nutricycle-webrtc -f
```

---

## Final notes 💡
- Keep `--imgsz 320` on Pi for best CPU throughput with ONNX.
- If you need help installing a specific package (e.g., ONNX runtime for ARM or `aiortc` build errors), tell me the error and I can provide exact commands.

---

Good luck — let me know if you want this added to the repo as `deploy/WEBRTC_SETUP.md` (I can create the file there if you want, or update it with extra steps). ✨
