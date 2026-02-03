# YOLO on Raspberry Pi - Complete Deployment Guide

Based on the [EJTech Tutorial](https://www.ejtech.io/learn/yolo-on-raspberry-pi)

## Overview

This guide shows how to deploy YOLO models on Raspberry Pi using NCNN format for optimal ARM CPU performance.

## ⚠️ CRITICAL BUG FIX (Raspberry Pi 4)

**If you're using Raspberry Pi 4**, there's a known Ultralytics bug that causes NCNN export errors. 

### The Fix:
```bash
pip install ultralytics==8.3.70 torch==2.5.1 torchvision==0.20
```

**Reference**: [Ultralytics Issue #19091](https://github.com/ultralytics/ultralytics/issues/19091)

This downgrade is REQUIRED before exporting to NCNN format on Pi 4. The issue should be fixed in future releases.

---

## Part 1: Raspberry Pi Setup

### Prerequisites
- Raspberry Pi 4 or 5
- 64-bit Raspberry Pi OS Bookworm
- USB camera or Pi Camera Module

### Step 1: Update System
```bash
sudo apt update
sudo apt upgrade
```

### Step 2: Create Working Directory
```bash
mkdir ~/yolo
cd ~/yolo
```

### Step 3: Create Virtual Environment
```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
```

**Note**: You'll need to reactivate this environment after reboots:
```bash
cd ~/yolo
source venv/bin/activate
```

### Step 4: Install Dependencies

**For Pi 4 (with bug fix):**
```bash
pip install ultralytics==8.3.70 torch==2.5.1 torchvision==0.20 ncnn
```
so
**For Pi 5 (latest versions):**
```bash
pip install ultralytics ncnn
```

**Important**: Installation can take 15+ minutes. If it stalls, press Ctrl+C and re-run.

### Step 5: Camera Setup
- Plug in USB camera or Pi Camera Module 3
- For Pi Camera, power off before connecting ribbon cable

---

## Part 2: Model Setup and NCNN Export

### Option A: Use Pre-trained Model

Download a YOLO11n model:
```bash
yolo detect predict model=yolo11n.pt
```

This downloads `yolo11n.pt` and runs a test.

### Option B: Use Custom Model

Transfer your custom `.pt` model file to the Pi using:
- USB drive
- SCP: `scp best.pt pi@raspberrypi:~/yolo/`
- Cloud storage

### Export to NCNN Format

**Critical step** - convert PyTorch model to NCNN:

```bash
yolo export model=your_model.pt format=ncnn
```

Replace `your_model.pt` with your actual model name (e.g., `yolo11n.pt` or `best.pt`).

This creates a folder like `your_model_ncnn_model` containing:
- `.param` file (model architecture)
- `.bin` file (model weights)

**Why NCNN?** 
- Optimized for ARM CPUs
- 2-3× faster than PyTorch on Raspberry Pi
- Lowest inference time compared to TensorFlow Lite, OpenVINO, etc.

---

## Part 3: Running Inference

### Download Test Script
```bash
wget https://ejtech.io/code/yolo_detect.py
```

### Run on USB Camera
```bash
python yolo_detect.py --model=yolo11n_ncnn_model --source=usb0 --resolution=640x480
```

### Run on Video File
```bash
python yolo_detect.py --model=yolo11n_ncnn_model --source=test_video.mp4
```

### Run on Image Folder
```bash
python yolo_detect.py --model=custom_ncnn_model --source=img_dir
```

### Script Arguments:
- `--model`: Path to NCNN model folder
- `--source`: 
  - `usb0` for USB camera
  - `video.mp4` for video file
  - `image.jpg` for single image
  - `img_dir/` for image folder
- `--resolution`: Display resolution (e.g., `640x480`)

### Expected Performance:
- **Pi 5**: ~8 FPS with YOLO11n NCNN
- **Pi 4**: ~5 FPS with YOLO11n NCNN

Press **`q`** to stop the script.

---

## Part 4: NutriCycle Specific Workflow

### Key Differences from Generic Tutorial:

**NutriCycle has:**
- ✅ Custom-trained model already in repo: `deploy/models/best.pt`
- ✅ Existing test scripts: `test_video_ncnn.py` (not the generic `yolo_detect.py`)
- ⚠️ Camera orientation: Needs `--flip vertical` flag
- 🎯 Specific classes: Foreign objects detection (not COCO 80 classes)

### Fresh Start Setup (Following EJTech + NutriCycle):

### On Raspberry Pi:

1. **Clone NutriCycle repo**:
   ```bash
   cd ~
   git clone https://github.com/Ervhyne/NutriCycle-RaspBerry-v2.git
   cd NutriCycle-RaspBerry-v2/deploy
   ```

2. **Create virtual environment**:
   ```bash
   cd ~
   mkdir -p yolo
   cd yolo
   python3 -m venv --system-site-packages venv
   source venv/bin/activate
   ```

3. **Install dependencies with bug fix** (Pi 4):
   ```bash
   pip install ultralytics==8.3.70 torch==2.5.1 torchvision==0.20 ncnn opencv-python
   ```

4. **Export your model to NCNN**:
   ```bash
   cd ~/NutriCycle-RaspBerry-v2/deploy
   source ~/yolo/venv/bin/activate  # Always activate first!
   yolo export model=models/best.pt format=ncnn imgsz=320
   ```

   This creates: `models/best_ncnn_model/`

5. **Modify test_video_ncnn.py** (if needed):
   
   Your existing script should already be configured, but verify it:
   - Uses NCNN model loading
   - Handles your custom class names
   - Has camera flip logic
   - Works with your hardware setup

6. **Run inference**:
   ```bash
   python test_video_ncnn.py --model=models/best_ncnn_model --source=1 --flip=vertical
   ```

   Note: `--source=1` if camera is on `/dev/video1`, adjust based on your setup

---

## What Files Need Modification?

### ✅ Already Done (in your repo):
- `test_video_ncnn.py` - Your custom inference script
- `models/best.pt` - Your trained model
- Project structure already set up

### ⚠️ May Need Updates:

**1. test_video_ncnn.py**
   - Verify it loads NCNN models correctly
   - Check class names match your training
   - Confirm camera source handling

**2. requirements.txt / requirements-ncnn.txt**
   - Should include: `ultralytics==8.3.70`, `torch==2.5.1`, `torchvision==0.20`, `ncnn`
   - Add Pi 4 bug fix versions

**3. setup scripts (setup_ncnn_pi_simple.sh, etc.)**
   - Update to create virtual environment
   - Add bug fix version pins
   - Automate NCNN export

### 🆕 Compare with Generic Tutorial:

| EJTech Tutorial | NutriCycle Project |
|----------------|-------------------|
| `yolo_detect.py` (generic) | `test_video_ncnn.py` (custom) |
| Downloads `yolo11n.pt` | Uses `models/best.pt` (in repo) |
| COCO 80 classes | Foreign object classes |
| No camera flip | Requires `--flip vertical` |
| Manual setup | Can automate with shell scripts |

---

## Troubleshooting

### "Unable to receive frames from camera"
- Unplug and replug camera
- Try different USB port
- Test with: `v4l2-ctl --list-devices`

### NCNN Export Fails on Pi 4
- **Apply the version downgrade fix** (see Critical Bug Fix section)
- Make sure you're in the virtual environment
- Check `pip list | grep ultralytics` shows version 8.3.70

### Slow Performance
- Reduce resolution: `--resolution=320x240`
- Use smaller model (YOLO11n instead of YOLO11s)
- Consider INT8 quantization (see NCNN tools)

### Import Errors
- Ensure virtual environment is activated: `source ~/yolo/venv/bin/activate`
- Reinstall packages: `pip install --force-reinstall ultralytics ncnn`

---

## Advanced: INT8 Quantization

For even faster inference (2× speedup on Pi 4), quantize your model to INT8:

1. Build NCNN tools on your desktop
2. Create calibration image set (100-300 images)
3. Run `ncnn2int8` tool
4. Transfer quantized model to Pi

See `convert_to_ncnn.ps1` for desktop automation.

---

## Resources

- **Original Tutorial**: https://www.ejtech.io/learn/yolo-on-raspberry-pi
- **Video Tutorial**: https://youtu.be/z70ZrSZNi-8
- **Ultralytics Docs**: https://docs.ultralytics.com/
- **NCNN GitHub**: https://github.com/Tencent/ncnn
- **Pi 4 Bug Report**: https://github.com/ultralytics/ultralytics/issues/19091

---

## Quick Reference Commands

### Setup (One Time)
```bash
mkdir ~/yolo && cd ~/yolo
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install ultralytics==8.3.70 torch==2.5.1 torchvision==0.20 ncnn  # Pi 4 only
```

### Export Model
```bash
yolo export model=your_model.pt format=ncnn imgsz=320
```

### Run Inference
```bash
python yolo_detect.py --model=model_ncnn_model --source=usb0 --resolution=640x480
```

### Reactivate Environment (After Reboot)
```bash
cd ~/yolo
source venv/bin/activate
```
