# YOLO Foreign Object Detection — Training Checklist (NutriCycle)

This document is a **simple, executable to‑do list** for training a YOLO model that detects **NON‑VEGETABLE / FOREIGN OBJECTS** on a conveyor.

Scope:

* ✅ Single‑class detection (`foreign_object`)
* ❌ No vegetable classes
* ❌ No tracking training
* ❌ No Raspberry Pi deployment details

---

## 🎯 Objective

Detect **any object that is NOT a vegetable** on the conveyor.

The model should answer only one question:

> **Is there a foreign object present?**

---

## 🏷️ Class Definition (DO NOT CHANGE LATER)

```
foreign_object
```

### What counts as `foreign_object`

* Plastic
* Metal
* Paper
* Wrappers
* Random trash
* Any non‑vegetable item

### What is BACKGROUND (never label)

* Vegetables
* Conveyor belt
* Empty belt
* Shadows
* Normal scene

---

## 📦 Dataset Targets (IMPORTANT)

### Total images

* **300–500 images TOTAL**

### Distribution

| Image Type                  | Target Count |
| --------------------------- | ------------ |
| Images with foreign objects | 150–250      |
| Images with only vegetables | 100–200      |
| Empty conveyor images       | 50–100       |

📌 Images with NO boxes are **required and correct**.

---

## 📸 Step 1 — Collect Images

### Allowed sources

* Mobile phone camera ✅ (recommended)
* Webcam capture program
* Extracted frames from video

### Capture rules

* Fixed camera angle
* Same distance as deployment
* 720p–1080p resolution
* Mix lighting conditions

### DO capture

* Different foreign object types
* Different sizes
* Partial occlusion
* Objects on top of vegetables

### DO NOT capture

* Random angles
* Portrait orientation
* Filters / HDR

---

## ✍️ Step 2 — Annotation Rules

### Tool

* **Roboflow** (Object Detection project)

### Labeling rules

✔️ Draw a box ONLY when a foreign object exists
✔️ Tight bounding boxes
✔️ Label ALL foreign objects in the image
✔️ Leave image EMPTY if no foreign object exists

❌ Do NOT label vegetables
❌ Do NOT label conveyor
❌ Do NOT label background noise

---

## 🧠 Step 3 — Prepare Training Environment (Laptop)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install ultralytics opencv-python
```

---

## 🚀 Step 4 — Train YOLO Model

Start with YOLOv8 Nano:

```bash
yolo detect train \
  model=yolov8n.pt \
  data=dataset/data.yaml \
  epochs=50 \
  imgsz=640
```

---

## 📁 Expected Output

```
runs/detect/train/
├── weights/
│   └── best.pt   ← USE THIS
├── results.png
└── confusion_matrix.png
```

---

## 🧪 Step 5 — Test the Model

Test on webcam:

```bash
yolo detect predict \
  model=runs/detect/train/weights/best.pt \
  source=0
```

Test on images:

```bash
yolo detect predict model=best.pt source=test.jpg
```

---

## 🔧 Step 6 — Improve Accuracy (If Needed)

If detection is weak:

* Add more **foreign_object** examples
* Add more **empty / veggie‑only** images
* Fix bad boxes
* Increase epochs

```bash
epochs=80
```

Optional upgrade:

```bash
model=yolov8s.pt
```

⚠️ Laptop only — never on Raspberry Pi.

---

## 🧩 Step 7 — Tracking (NO TRAINING)

Tracking is added AFTER training:

```python
from ultralytics import YOLO

model = YOLO("best.pt")
model.track(source=0, tracker="bytetrack.yaml", persist=True)
```

---

## ❌ Common Mistakes (Avoid These)

* Training on Raspberry Pi
* Labeling vegetables
* Multiple classes for foreign objects
* Drawing boxes on every image
* Too many duplicate frames

---

## ✅ Final Completion Checklist

* [ ] Single class: `foreign_object`
* [ ] 300–500 total images
* [ ] ≥150 images with foreign objects
* [ ] ≥100 images with no boxes
* [ ] YOLOv8 trained on laptop
* [ ] `best.pt` validated
* [ ] Ready for inference / deployment

---

## 🧠 One Rule to Remember

> **Label only what you want the system to stop. Everything else is background.**

This document is the **authoritative training reference** for NutriCycle foreign‑object detection.
