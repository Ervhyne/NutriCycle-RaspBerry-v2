# ONNX to NCNN Conversion Workflow

## Why ONNX → NCNN Instead of Direct PT → NCNN?

The direct `best.pt` → NCNN conversion produces broken results:
- ❌ All predictions have confidence 1.0
- ❌ Detection quality is very different from best.pt or ONNX
- ✅ **Solution**: Use best.pt → ONNX → NCNN workflow

## Prerequisites

### On Your Laptop (Windows)
You already have:
- ✅ `AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx` (trained with imgsz=512)
- ✅ Copy in `deploy/models/best.onnx`

### On Raspberry Pi
Need to install NCNN tools for conversion.

---

## Step-by-Step Conversion Process

### 1. Clean Up Old Files (On Raspberry Pi)

SSH into your Pi and remove any broken NCNN files:

```bash
ssh nutricycle@raspberrypi

# Navigate to deploy directory
cd ~/NutriCycle-RaspBerry-v2/deploy

# Remove old NCNN models if they exist
rm -f models/*.param models/*.bin
rm -rf ncnn/models/*

# Clean up any old NCNN build directories (optional)
# rm -rf ~/ncnn_build
```

---

### 2. Transfer ONNX Model to Pi

From your laptop (in this repo folder):

```powershell
# Copy ONNX model to Pi
scp deploy/models/best.onnx nutricycle@raspberrypi:~/NutriCycle-RaspBerry-v2/deploy/models/
```

---

### 3. Setup NCNN Tools on Raspberry Pi

Run the provided setup script:

```bash
ssh nutricycle@raspberrypi
cd ~/NutriCycle-RaspBerry-v2/deploy

# Make script executable
chmod +x setup_ncnn_pi_simple.sh

# Run setup (this will install NCNN tools)
./setup_ncnn_pi_simple.sh
```

This script will:
- Install dependencies (cmake, protobuf, etc.)
- Clone and build NCNN from source
- Create the `onnx2ncnn` conversion tool

---

### 4. Convert ONNX → NCNN (On Raspberry Pi)

After NCNN tools are built:

```bash
cd ~/ncnn/build/tools/onnx

# Convert ONNX to NCNN format
./onnx2ncnn \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.onnx \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.param \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.bin

# Verify files were created
ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/
```

You should see:
- `best.onnx` (original)
- `best.param` (NCNN parameter file)
- `best.bin` (NCNN weight file)

---

### 5. Test NCNN Model (On Raspberry Pi)

Test the converted model:

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Activate virtual environment
source venv/bin/activate

# Test with video
python test_video_ncnn.py
```

---

## Important Configuration Notes

### Image Size Consistency
Your model was trained with **imgsz=512**, so all inference must use 512:

**In Python code:**
```python
# For ONNX models
model = YOLO("models/best.onnx")
results = model.predict(source=0, imgsz=512)

# For NCNN wrapper
detector = NCNNObjectDetector(
    param_path="models/best.param",
    bin_path="models/best.bin",
    target_size=512  # Must match training size
)
```

**Command line:**
```bash
yolo predict model=models/best.onnx source=0 imgsz=512
```

---

## Troubleshooting

### If NCNN Build Fails
```bash
# Install missing dependencies
sudo apt-get update
sudo apt-get install -y build-essential cmake git libprotobuf-dev protobuf-compiler

# Try building again
cd ~/ncnn/build
cmake ..
make -j4
```

### If Conversion Fails
Check ONNX model is valid:
```bash
# On laptop with ultralytics installed
python -c "from ultralytics import YOLO; model = YOLO('deploy/models/best.onnx'); print('ONNX model loaded successfully')"
```

### If Predictions Are Still Wrong
- Verify you're using imgsz=512 everywhere
- Check that the NCNN files are in the correct location
- Compare ONNX predictions vs NCNN predictions side-by-side

---

## File Structure After Conversion

```
NutriCycle-RaspBerry-v2/
└── deploy/
    ├── models/
    │   ├── best.onnx     # Original ONNX model
    │   ├── best.pt       # Original PyTorch model
    │   ├── best.param    # NCNN parameter file (converted)
    │   └── best.bin      # NCNN weight file (converted)
    ├── test_video_ncnn.py
    ├── ncnn_wrapper_pyncnn.py
    └── setup_ncnn_pi_simple.sh
```

---

## Quick Reference Commands

**Cleanup:**
```bash
rm -f ~/NutriCycle-RaspBerry-v2/deploy/models/*.param ~/NutriCycle-RaspBerry-v2/deploy/models/*.bin
```

**Convert:**
```bash
~/ncnn/build/tools/onnx/onnx2ncnn \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.onnx \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.param \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.bin
```

**Test:**
```bash
cd ~/NutriCycle-RaspBerry-v2/deploy && source venv/bin/activate && python test_video_ncnn.py
```
