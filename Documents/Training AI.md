# Training a YOLO Model on Your Laptop (NutriCycle Reference)

This document covers **only the YOLO training workflow**, based strictly on what we discussed earlier. It is designed as a **practical, step-by-step reference** that you can follow and later reuse for Raspberry Pi deployment.

---

This section explains **exactly how to train your own YOLO object detection model on your laptop**, in a way that is **easy to follow** and **easy to migrate to Raspberry Pi later**.

---

## What You Are Training

You are training **object detection**, not tracking.

* ✔️ Train: object classes + bounding boxes
* ❌ Do NOT train: tracking, IDs, motion

Tracking will be added later using **ByteTrack** with no extra training.

---

## Prerequisites

* Laptop (Windows / Linux / macOS)
* Python 3.9 – 3.11
* Webcam, phone camera, or recorded video
* Internet access (for labeling tool)

---

## Step 1 — Collect Training Images

Collect images that closely match your real deployment setup.

### Option A: Capture images from webcam

```python
import cv2, os

os.makedirs("dataset/raw", exist_ok=True)
cap = cv2.VideoCapture(0)
i = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("capture", frame)
    key = cv2.waitKey(1)

    if key == ord("c"):
        cv2.imwrite(f"dataset/raw/img_{i}.jpg", frame)
        print("saved", i)
        i += 1

    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()
```

### Capture Guidelines

* Different lighting conditions
* Different object positions
* Some motion blur
* Clean and cluttered scenes

**Target:** 300–800 images total

---

## Step 2 — Label the Images

### Recommended Tool: Roboflow

1. Create a **new Object Detection project**
2. Upload all images
3. Draw tight bounding boxes
4. Assign class names (example: `plastic`, `leaf`, `metal`, `paper`)
5. Apply default augmentations
6. Export dataset in **YOLOv8 format**

After export, you will get:

```
dataset/
├── images/
├── labels/
└── data.yaml
```

---

## Step 3 — Set Up Training Environment (Laptop)

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install ultralytics opencv-python
```

Verify installation:

```bash
yolo version
```

---

## Step 4 — Train YOLO Model

Run training using YOLOv8 nano (recommended to start):

```bash
yolo detect train \
  model=yolov8n.pt \
  data=dataset/data.yaml \
  epochs=50 \
  imgsz=640
```

### Training Output

YOLO automatically creates:

```
runs/detect/train/
├── weights/
│   ├── best.pt   ← USE THIS MODEL
│   └── last.pt
├── results.png
└── confusion_matrix.png
```

---

## Step 5 — Test the Trained Model

Test using webcam:

```bash
yolo detect predict \
  model=runs/detect/train/weights/best.pt \
  source=0
```

Or test with an image:

```bash
yolo detect predict \
  model=best.pt \
  source=test.jpg
```

If detections look correct, training is successful.

---

## Step 6 — Improve Accuracy (Optional)

If accuracy is low:

* Add more images
* Fix incorrect labels
* Increase training epochs

```bash
epochs=80
```

You may also try a larger model:

```bash
model=yolov8s.pt
```

⚠️ Do this only on a laptop or desktop, not Raspberry Pi.

---

## Step 7 — Add Object Tracking (No Training Required)

```python
from ultralytics import YOLO

model = YOLO("best.pt")
model.track(
    source=0,
    tracker="bytetrack.yaml",
    persist=True
)
```

Tracking works immediately without retraining.

---

## Step 8 — Prepare for Raspberry Pi Deployment

Copy trained model to Raspberry Pi:

```bash
scp best.pt pi@raspberrypi.local:/home/pi/models/
```

Use the same inference code on Raspberry Pi with reduced FPS.

---

## Common Mistakes to Avoid

* Do NOT train on Raspberry Pi
* Do NOT train tracking
* Do NOT mix Anaconda with venv
* Do NOT use poorly labeled boxes

---

## Final Checklist

* [ ] Images collected
* [ ] Images labeled correctly
* [ ] YOLO trained on laptop
* [ ] `best.pt` generated
* [ ] Model tested
* [ ] Ready for Raspberry Pi
