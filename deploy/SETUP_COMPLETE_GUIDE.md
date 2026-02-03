# 🚀 Complete ONNX → NCNN Setup Guide for Raspberry Pi

## Overview
This guide sets up NutriCycle object detection using the **ONNX → NCNN** workflow instead of the broken direct PT → NCNN conversion.

---

## 📋 Pre-Flight Checklist

### On Windows Laptop ✅
- [x] Model trained: `AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt`
- [x] ONNX exported: `deploy/models/best.onnx` (imgsz=512)
- [x] Raspberry Pi accessible via SSH

### On Raspberry Pi (To Do)
- [ ] Clean up old NCNN files
- [ ] Transfer fresh ONNX model
- [ ] Build NCNN tools
- [ ] Convert ONNX → NCNN
- [ ] Test inference

---

## 🎯 Step-by-Step Instructions

### Step 1: Connect to Raspberry Pi

From Windows PowerShell or terminal:

```powershell
ssh nutricycle@raspberrypi
```

Enter password when prompted.

---

### Step 2: Navigate and Clean Up

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Make cleanup script executable
chmod +x cleanup_ncnn_files.sh

# Run cleanup
./cleanup_ncnn_files.sh
```

This removes:
- Old `models/*.param` and `models/*.bin` files
- Any old `ncnn/` directories

---

### Step 3: Transfer ONNX Model

**Open a NEW PowerShell window on your laptop** (don't close SSH):

```powershell
# Navigate to your repo
cd "C:\Users\Daniella Xyrene\Documents\Github\NutriCycle-RaspBerry-v2"

# Copy ONNX model to Pi
scp deploy/models/best.onnx nutricycle@raspberrypi:~/NutriCycle-RaspBerry-v2/deploy/models/
```

---

### Step 4: Build NCNN Tools (On Pi)

Back in your SSH session:

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Make setup script executable
chmod +x setup_ncnn_pi_simple.sh

# Run setup (takes 10-15 minutes)
./setup_ncnn_pi_simple.sh
```

This will:
- Install build dependencies
- Clone NCNN from GitHub
- Build NCNN tools including `onnx2ncnn`
- Install pyncnn Python bindings

**☕ Take a coffee break - this takes time!**

---

### Step 5: Convert ONNX → NCNN

After setup completes successfully:

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Make conversion script executable
chmod +x convert_onnx_to_ncnn.sh

# Run conversion
./convert_onnx_to_ncnn.sh
```

This will:
- Verify prerequisites
- Clean up old NCNN files
- Convert ONNX → NCNN format
- Verify output files

You should see:
```
✅ Conversion successful!
📊 Model files:
-rw-r--r-- 1 nutricycle nutricycle 5.8M best.onnx
-rw-r--r-- 1 nutricycle nutricycle 5.6M best.bin
-rw-r--r-- 1 nutricycle nutricycle  12K best.param
```

---

### Step 6: Test NCNN Model

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Activate virtual environment (if you have one)
source venv/bin/activate

# Install dependencies if needed
pip install opencv-python numpy

# Test with webcam
python test_video_ncnn.py --source 0 --conf 0.5

# Or test with video file
python test_video_ncnn.py --source /path/to/video.mp4
```

Press `q` to quit the video window.

---

## 🔧 Important Configuration Notes

### Image Size: 512×512

Your model was trained with **imgsz=512**. This must be consistent everywhere:

**In Python:**
```python
# For NCNN
detector = NCNNInferencePython(
    param_path="models/best.param",
    bin_path="models/best.bin",
    target_size=512  # Match training size
)

# For ONNX (if testing)
from ultralytics import YOLO
model = YOLO("models/best.onnx")
results = model.predict(source=0, imgsz=512)
```

**Command line:**
```bash
yolo predict model=models/best.onnx source=0 imgsz=512
```

---

## 📁 File Structure After Setup

```
~/NutriCycle-RaspBerry-v2/deploy/
├── models/
│   ├── best.onnx          # Original ONNX model
│   ├── best.param         # NCNN parameter file ✨ NEW
│   └── best.bin           # NCNN weights ✨ NEW
├── test_video_ncnn.py     # Test script
├── ncnn_wrapper_pyncnn.py # Python inference wrapper
├── cleanup_ncnn_files.sh  # Cleanup script
├── setup_ncnn_pi_simple.sh # NCNN build script
└── convert_onnx_to_ncnn.sh # Conversion script

~/ncnn/                     # NCNN source and build ✨ NEW
├── build/
│   └── tools/
│       ├── onnx/
│       │   └── onnx2ncnn   # Conversion tool
│       └── quantize/
│           └── ncnn2int8   # Quantization tool (optional)
└── python/                 # pyncnn bindings
```

---

## 🐛 Troubleshooting

### Error: "NCNN tools not found" or "protobuf" errors
```bash
# First, manually install dependencies
sudo apt-get update
sudo apt-get install -y build-essential git cmake libprotobuf-dev protobuf-compiler

# Verify protobuf is installed
protoc --version

# Clean up and rebuild
rm -rf ~/ncnn
cd ~/NutriCycle-RaspBerry-v2/deploy
./setup_ncnn_pi_simple.sh
```

### Error: Build warnings about uninitialized variables
```bash
# Rebuild with warnings disabled
cd ~/ncnn/build
cmake -DCMAKE_CXX_FLAGS="-Wno-error=maybe-uninitialized" ..
make -j4

# Verify onnx2ncnn was built
ls -l tools/onnx/onnx2ncnn
```

### Error: "ONNX model not found"
```bash
# Check model exists
ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/best.onnx

# If missing, transfer again from laptop
# (In PowerShell on laptop)
scp deploy/models/best.onnx nutricycle@raspberrypi:~/NutriCycle-RaspBerry-v2/deploy/models/
```

### Error: "Wrong input dimensions"
Make sure all scripts use `target_size=512` or `imgsz=512`.

### Low FPS / Slow Inference
Consider INT8 quantization (advanced):
```bash
cd ~/ncnn/build
./tools/quantize/ncnn2int8 \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.param \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.bin \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best-int8.param \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best-int8.bin \
  /path/to/calibration/images/
```

---

## 🎉 Success Criteria

You'll know it's working when:
- ✅ Conversion completes without errors
- ✅ `.param` and `.bin` files are created
- ✅ Test script runs without crashes
- ✅ Video window shows detections with reasonable confidence (not all 1.0)
- ✅ FPS is acceptable for your use case

---

## 📞 Quick Command Reference

```bash
# SSH to Pi
ssh nutricycle@raspberrypi

# Go to deploy folder
cd ~/NutriCycle-RaspBerry-v2/deploy

# Clean up
./cleanup_ncnn_files.sh

# Setup NCNN
./setup_ncnn_pi_simple.sh

# Convert model
./convert_onnx_to_ncnn.sh

# Test inference
python test_video_ncnn.py --source 0 --conf 0.5
```

---

## 📚 Additional Resources

- [ONNX_TO_NCNN_WORKFLOW.md](ONNX_TO_NCNN_WORKFLOW.md) - Detailed technical workflow
- [NCNN_MIGRATION_GUIDE.md](NCNN_MIGRATION_GUIDE.md) - Migration from PyTorch
- [RASPBERRY_PI_INTEGRATION.md](RASPBERRY_PI_INTEGRATION.md) - Full Pi setup

---

**Need help?** Check error messages carefully - they usually point to the exact issue!
