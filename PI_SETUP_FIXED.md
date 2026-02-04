# 🔥 Fixed: Raspberry Pi ONNX Setup (Python Native)

**Problem:** Inference on Raspberry Pi had compatibility issues  
**Solution:** Use ONNX Runtime or Ultralytics ONNX targets — no C++ compilation needed!

---

## ✅ Steps on Raspberry Pi (After Git Clone)

### 1️⃣ Run the simplified setup script

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy
# No native builds required. Create/activate a venv and install dependencies:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This uses ONNX Runtime for model inference (no native builds required).

---

### 2️⃣ Using the ONNX model

If you're using the ONNX model (recommended for our ONNX-focused workflow), keep `deploy/models/best.onnx` or export from your `.pt` model to ONNX. Test inference locally with the provided `deploy/test_video.py` script which supports ONNX (uses `onnxruntime`) or use the Ultralytics runtime.

---

### 4️⃣ Install Python dependencies

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy
pip3 install opencv-python numpy
```

---

### 5️⃣ Test inference

```bash
# Test with an image using the ONNX model (or .pt fallback)
python3 test_video.py --model=models/best.onnx --source=test_image.jpg
```

---

### 6️⃣ Run video test

```bash
python3 test_video.py --model=models/best.onnx --source=1 --flip vertical
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
