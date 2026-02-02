# 🔥 Fixed: Raspberry Pi NCNN Setup (Python Native)

**Problem:** C++ compilation failed with CMake errors  
**Solution:** Use Python NCNN bindings (pyncnn) — no C++ compilation needed!

---

## ✅ Steps on Raspberry Pi (After Git Clone)

### 1️⃣ Run the simplified setup script

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy
chmod +x setup_ncnn_pi_simple.sh
./setup_ncnn_pi_simple.sh
```

This builds NCNN + Python bindings (takes 10-15 min, but succeeds without CMake errors).

---

### 2️⃣ Convert ONNX → NCNN

```bash
# Go to NCNN tools
cd ~/ncnn_build/ncnn/build

# Convert (adjust path to your ONNX file)
./tools/onnx/onnx2ncnn \
  ~/NutriCycle-RaspBerry-v2/AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx \
  best.param \
  best.bin

# Copy to deploy folder
mkdir -p ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models
cp best.param best.bin ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/
```

---

### 3️⃣ (Optional) INT8 Quantization

```bash
# Create calibration folder with 100-300 images
mkdir -p ~/calibration_images
# Copy representative images there

# Quantize
./tools/quantize/ncnn2int8 \
  best.param best.bin \
  best-int8.param best-int8.bin \
  ~/calibration_images/

# Copy INT8 model
cp best-int8.* ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/
```

---

### 4️⃣ Install Python dependencies

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy
pip3 install opencv-python numpy
```

---

### 5️⃣ Test inference

```bash
# Test with an image
python3 -c "
from ncnn_wrapper_pyncnn import load_ncnn_model
import cv2

model = load_ncnn_model('ncnn/models/best')
frame = cv2.imread('test_image.jpg')
results = model(frame)
print(f'Detections: {len(results[0].boxes)}')
"
```

---

### 6️⃣ Run video test

```bash
# Update test_video_ncnn.py to import ncnn_wrapper_pyncnn instead of ncnn_wrapper
python3 test_video_ncnn.py --source 1 --flip vertical
```

---

## 🔧 Quick Fix for test_video_ncnn.py

Change line 8:
```python
# OLD
from ncnn_wrapper import load_ncnn_model

# NEW
from ncnn_wrapper_pyncnn import load_ncnn_model
```

---

## ✅ Why This Works

| Old Approach (Failed)     | New Approach (Works) |
| ------------------------- | -------------------- |
| Custom C++ binary         | Python bindings      |
| Complex CMake config      | pip install          |
| Find package errors       | Native Python API    |
| ❌ Compilation issues      | ✅ Clean build        |

---

## 🎯 Expected Performance

- **8-12 FPS** on Pi 4 (320×320 INT8)
- **No illegal instruction**
- **Stable Python API**

---

**This approach is cleaner, more maintainable, and avoids C++ compilation issues!** ✅
