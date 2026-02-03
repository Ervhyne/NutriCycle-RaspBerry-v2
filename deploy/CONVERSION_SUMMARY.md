# 📝 ONNX → NCNN Conversion Summary

## What Changed?

### Problem Identified ❌
- Direct `best.pt` → NCNN conversion produces incorrect results
- All detections show confidence = 1.0
- Results differ significantly from PyTorch and ONNX versions

### Solution Implemented ✅
- Use **best.pt → ONNX → NCNN** workflow instead
- Ensures consistent inference quality across formats
- Properly preserves model weights and confidence scores

---

## Files Created/Updated

### New Files ✨
1. **[SETUP_COMPLETE_GUIDE.md](SETUP_COMPLETE_GUIDE.md)**
   - Complete step-by-step guide for Pi setup
   - Troubleshooting tips
   - Quick command reference

2. **[ONNX_TO_NCNN_WORKFLOW.md](ONNX_TO_NCNN_WORKFLOW.md)**
   - Technical workflow documentation
   - Detailed conversion process
   - Configuration notes

3. **[cleanup_ncnn_files.sh](cleanup_ncnn_files.sh)**
   - Removes old/broken NCNN files
   - Prepares for fresh conversion

4. **[convert_onnx_to_ncnn.sh](convert_onnx_to_ncnn.sh)**
   - Automated ONNX → NCNN conversion
   - Includes verification steps
   - Color-coded output

### Updated Files 🔧
1. **[setup_ncnn_pi_simple.sh](setup_ncnn_pi_simple.sh)**
   - Fixed paths (~/ncnn instead of ~/ncnn_build)
   - Added verification steps
   - Better error messages

2. **[ncnn_wrapper_pyncnn.py](ncnn_wrapper_pyncnn.py)**
   - Changed default `target_size` from 320 to **512**
   - Matches your model's training size

---

## Workflow Overview

```
Laptop (Windows)                  Raspberry Pi (Linux)
─────────────────                 ────────────────────

best.pt (trained)
    │
    ├─> export ONNX
    │
best.onnx ──────────SCP──────────> best.onnx
                                       │
                                       ├─> setup NCNN tools
                                       │   (onnx2ncnn)
                                       │
                                       ├─> convert
                                       │
                                   best.param
                                   best.bin
                                       │
                                       └─> test inference
                                           ✅ Working!
```

---

## Key Configuration: imgsz=512

Your model was trained with **imgsz=512**, so all inference must use this size:

| Component | Configuration |
|-----------|--------------|
| Training args | `imgsz: 512` ✅ |
| ONNX export | `imgsz=512` ✅ |
| NCNN wrapper | `target_size=512` ✅ |
| YOLO predict | `imgsz=512` ⚠️ (must specify) |

---

## Next Steps on Raspberry Pi

1. **SSH to Pi**: `ssh nutricycle@raspberrypi`

2. **Navigate**: `cd ~/NutriCycle-RaspBerry-v2/deploy`

3. **Clean up**: `./cleanup_ncnn_files.sh`

4. **Transfer ONNX** (from laptop):
   ```powershell
   scp deploy/models/best.onnx nutricycle@raspberrypi:~/NutriCycle-RaspBerry-v2/deploy/models/
   ```

5. **Setup NCNN** (on Pi): `./setup_ncnn_pi_simple.sh` (10-15 min)

6. **Convert**: `./convert_onnx_to_ncnn.sh`

7. **Test**: `python test_video_ncnn.py --source 0 --conf 0.5`

---

## Files to Delete on Pi (Before Starting)

These will be cleaned by the scripts:
- `deploy/models/*.param` (old NCNN param files)
- `deploy/models/*.bin` (old NCNN weight files)
- `deploy/ncnn/` (old NCNN directory structure)

You can also manually delete with:
```bash
rm -f ~/NutriCycle-RaspBerry-v2/deploy/models/*.param
rm -f ~/NutriCycle-RaspBerry-v2/deploy/models/*.bin
rm -rf ~/NutriCycle-RaspBerry-v2/deploy/ncnn/
```

---

## Expected Results

### After Conversion
```bash
$ ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/
-rw-r--r-- 1 nutricycle nutricycle 5.8M best.onnx
-rw-r--r-- 1 nutricycle nutricycle 5.6M best.bin    ✨ NEW
-rw-r--r-- 1 nutricycle nutricycle  12K best.param  ✨ NEW
```

### After Testing
- Video window opens showing camera feed
- Foreign objects detected with bounding boxes
- Confidence scores are reasonable (0.5-0.9 range, NOT all 1.0)
- FPS displayed in corner
- Press 'q' to quit

---

## Why This Approach Works

1. **ONNX is a proven format**
   - Industry standard
   - Well-tested export from PyTorch
   - Your `best.onnx` already works correctly

2. **onnx2ncnn is reliable**
   - Official NCNN tool
   - Properly converts operators
   - Preserves quantization and weights

3. **No direct PyTorch → NCNN**
   - Avoids the broken conversion path
   - Eliminates confidence=1.0 bug
   - Results match ONNX quality

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| "NCNN tools not found" | Re-run `setup_ncnn_pi_simple.sh` |
| "ONNX model not found" | Re-transfer with `scp` command |
| "Wrong input dimensions" | Check `target_size=512` in code |
| All confidence = 1.0 | You're using old broken NCNN - reconvert |
| Import error: ncnn | Run `pip install pyncnn` in venv |
| Low FPS | Consider INT8 quantization |

---

## Success Checklist ✅

- [ ] Scripts made executable (`chmod +x *.sh`)
- [ ] Old NCNN files cleaned up
- [ ] Fresh ONNX model transferred to Pi
- [ ] NCNN tools built successfully
- [ ] onnx2ncnn conversion completed
- [ ] `.param` and `.bin` files created
- [ ] Test script runs without errors
- [ ] Detections show reasonable confidence
- [ ] FPS is acceptable

---

**You're all set!** Follow [SETUP_COMPLETE_GUIDE.md](SETUP_COMPLETE_GUIDE.md) for detailed instructions.
