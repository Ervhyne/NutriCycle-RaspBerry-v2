# Laptop → Raspberry Pi AI Workflow (NutriCycle Reference)

## Core Principle

Both a **laptop** and a **Raspberry Pi 4** are full computers. If you build your AI pipeline correctly, **90% of the code is identical** on both.

> **Best practice:** Develop and test everything on the laptop first, then migrate to Raspberry Pi.

---

## Recommended Development Flow

1. Develop & test on **Laptop**
2. Freeze dependencies
3. Copy project to **Raspberry Pi**
4. Adjust camera input & performance
5. Run as production service

---

## Standard Project Structure (Migration-Safe)

```
nutricycle-vision/
├── venv/
├── models/
│   └── best.pt
├── data/
├── src/
│   ├── camera.py
│   ├── detector.py
│   ├── tracker.py
│   ├── api.py
│   └── main.py
├── requirements.txt
└── README.md
```

---

## Laptop Setup

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
```

### Install Dependencies

```bash
pip install ultralytics opencv-python flask fastapi
pip freeze > requirements.txt
```

`requirements.txt` is the key file used for migration.

---

## Run YOLO + Tracking on Laptop

Example `main.py`:

```python
from ultralytics import YOLO
import cv2

model = YOLO("models/best.pt")
cap = cv2.VideoCapture(0)  # laptop webcam

for r in model.track(
    source=cap,
    tracker="bytetrack.yaml",
    stream=True
):
    frame = r.plot()
    cv2.imshow("NutriCycle", frame)
    if cv2.waitKey(1) == 27:
        break
```

If this works on the laptop, it will work on Raspberry Pi.

---

## API Layer (Optional)

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/detections")
def detections():
    return jsonify(latest_detections)
```

---

## Migration to Raspberry Pi

### Copy Project

```bash
scp -r nutricycle-vision pi@raspberrypi.local:/home/pi/
```

### Recreate Environment on Pi

```bash
ssh pi@raspberrypi.local
cd nutricycle-vision
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

No Anaconda on Raspberry Pi.

---

## Camera Source Change (Usually the ONLY code change)

Laptop:

```python
cv2.VideoCapture(0)
```

Raspberry Pi USB webcam:

```python
cv2.VideoCapture("/dev/video0")
```

IP Camera:

```python
cv2.VideoCapture("rtsp://camera_ip/stream")
```

---

## Raspberry Pi Performance Tuning

* Use `yolov8n.pt` only
* Reduce image size
* Limit FPS

```python
model = YOLO("yolov8n.pt")
imgsz = 416
cap.set(cv2.CAP_PROP_FPS, 10)
```

---

## What NOT to Do

* Do NOT train YOLO on Raspberry Pi
* Do NOT use Anaconda on Pi
* Do NOT hardcode paths
* Do NOT stream annotated video to mobile

---

## Final Summary

* Laptop = development + training
* Raspberry Pi = deployment runtime
* Same codebase
* Same dependencies
* Minimal changes

This workflow is the recommended reference architecture for NutriCycle AI agents.
