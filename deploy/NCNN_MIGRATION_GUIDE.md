# 🔥 NCNN Migration Guide for NutriCycle

**Migration from ONNX Runtime → NCNN (Rock-solid Pi 4 inference)**

---

## 📋 Overview

This guide migrates your YOLOv8n inference from unstable ONNX Runtime to **NCNN** — eliminating illegal instruction crashes permanently.

**What changes:**
- ❌ Remove: ultralytics, torch, onnxruntime
- ✅ Add: NCNN C++ inference binary
- ✅ Keep: Everything else (camera, OpenCV, ESP32 logic)

---

## 🛠️ Part 1: Convert Model to NCNN (Desktop)

### Step 1.1: Re-export clean ONNX (on your desktop)

```bash
cd AI-Model/runs/detect/nutricycle_foreign_only/weights
yolo export model=best.pt format=onnx imgsz=320 opset=12 simplify=True
```

**Result:** Fresh `best.onnx` optimized for NCNN

---

### Step 1.2: Download NCNN tools (desktop)

```bash
# Clone NCNN repository
git clone https://github.com/Tencent/ncnn
cd ncnn

# Build tools
mkdir -p build
cd build
cmake ..
make -j4
```

**Result:** `onnx2ncnn` converter in `tools/onnx/`

---

### Step 1.3: Convert ONNX → NCNN

```bash
cd ncnn/build
./tools/onnx/onnx2ncnn \
  ../../../../AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx \
  best.param \
  best.bin
```

**Result:** 
- `best.param` (model graph)
- `best.bin` (model weights)

---

### Step 1.4: Quantize to INT8 (STRONGLY RECOMMENDED)

This gives **2× speed** on Raspberry Pi 4.

```bash
# Create calibration image folder
mkdir -p calibration_images
# Copy 100-300 real images from your dataset here
cp ../../../../AI-Model/datasets/your_images/*.jpg calibration_images/

# Quantize
./tools/quantize/ncnn2int8 \
  best.param best.bin \
  best-int8.param best-int8.bin \
  calibration_images/
```

**Result:** 
- `best-int8.param`
- `best-int8.bin`

**Copy these files to your repo:**
```bash
cp best-int8.* ../../../../deploy/models/
```

---

## 🍓 Part 2: Setup NCNN on Raspberry Pi

### Step 2.1: Install NCNN

Use the provided setup script:

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy
chmod +x setup_ncnn_pi.sh
./setup_ncnn_pi.sh
```

This will:
- Install build dependencies
- Clone and compile NCNN
- Build YOLOv8 inference binary
- Install to `deploy/ncnn/`

---

### Step 2.2: Verify installation

```bash
./deploy/ncnn/yolo_ncnn --help
```

Expected output:
```
Usage: yolo_ncnn [options]
  -m <model.param>
  -w <model.bin>
  -i <image.jpg>
  -c <confidence>
```

---

## 🐍 Part 3: Update Python Code

### Step 3.1: Install new requirements

```bash
pip install -r deploy/requirements-ncnn.txt
```

This removes ultralytics/torch/onnxruntime.

---

### Step 3.2: Test basic inference

```bash
# Test with single image
python deploy/test_ncnn.py --image test_image.jpg

# Test with video
python deploy/test_video_ncnn.py --source 1 --flip vertical
```

---

### Step 3.3: Use WebRTC server (optional)

```bash
python deploy/webrtc_server_ncnn.py \
  --source 1 \
  --flip vertical \
  --conf 0.5 \
  --mqtt-broker 192.168.x.x
```

---

## 🎯 Performance Expectations

| Resolution | FPS on Pi 4 | Latency | Notes          |
| ---------- | ----------- | ------- | -------------- |
| 320×320    | 8-12 FPS    | ~100ms  | Recommended    |
| 416×416    | 5-8 FPS     | ~150ms  | Higher quality |
| 640×640    | 2-4 FPS     | ~300ms  | Too slow       |

**Recommendation:** Use 320×320 with INT8 quantization

---

## ✅ Verification Checklist

After migration:

- [ ] Model converted: `best-int8.param` and `best-int8.bin` exist
- [ ] NCNN binary built: `deploy/ncnn/yolo_ncnn` exists
- [ ] Test inference works: `test_video_ncnn.py` runs without crashes
- [ ] FPS is 6+ on Pi 4
- [ ] No "illegal instruction" errors
- [ ] ESP32 triggers still work (if applicable)

---

## 🔧 Troubleshooting

### "onnx2ncnn: command not found"

Build NCNN tools first (Part 1.2)

### "undefined reference to pthread"

Add `-lpthread` to CMakeLists when building

### Inference is too slow (<5 FPS)

1. Use INT8 quantized model
2. Reduce image size to 320×320
3. Verify 4 CPU cores available

### Wrong detections

Recalibrate INT8 quantization with more representative images

---

## 📞 Next Steps

1. ✅ Follow this guide step-by-step
2. ✅ Test on Pi 4 before deploying to production
3. ✅ Tune confidence threshold (`--conf`)
4. ✅ Integrate with ESP32 if not already done

---

**Migration complete! You now have rock-solid inference on Raspberry Pi 4. 🎉**
