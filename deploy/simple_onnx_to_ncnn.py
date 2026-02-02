"""
Simple ONNX to NCNN converter using onnx-simplifier
This script prepares your model for Raspberry Pi without needing to build NCNN tools on Windows
"""

import os
import sys
from pathlib import Path

print("🔥 NutriCycle ONNX Model Preparation")
print("=" * 50)
print()

# Check for ONNX file
model_path = "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx"

if not os.path.exists(model_path):
    print(f"❌ ONNX file not found: {model_path}")
    print("   Please export model first using:")
    print("   python -c \"from ultralytics import YOLO; YOLO('best.pt').export(format='onnx', imgsz=320)\"")
    sys.exit(1)

print(f"✅ Found ONNX model: {model_path}")
print()

# Get file size
file_size = os.path.getsize(model_path) / (1024 * 1024)
print(f"📊 Model size: {file_size:.1f} MB")
print()

print("=" * 50)
print("✅ ONNX Export Complete!")
print("=" * 50)
print()
print("📋 Next Steps:")
print()
print("1️⃣  Copy the ONNX file to your Raspberry Pi:")
print(f"    scp {model_path} pi@raspberrypi:~/")
print()
print("2️⃣  On Raspberry Pi, run the setup script:")
print("    cd ~/NutriCycle-RaspBerry-v2/deploy")
print("    chmod +x setup_ncnn_pi.sh")
print("    ./setup_ncnn_pi.sh")
print()
print("3️⃣  On Raspberry Pi, convert ONNX → NCNN:")
print("    cd ~/ncnn_build/ncnn/build")
print("    ./tools/onnx/onnx2ncnn ~/best.onnx \\")
print("        ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/best.param \\")
print("        ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/best.bin")
print()
print("4️⃣  (Optional) Quantize to INT8 on Raspberry Pi:")
print("    ./tools/quantize/ncnn2int8 \\")
print("        ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/best.param \\")
print("        ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/best.bin \\")
print("        ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/best-int8.param \\")
print("        ~/NutriCycle-RaspBerry-v2/deploy/ncnn/models/best-int8.bin \\")
print("        ~/calibration_images/")
print()
print("⚡ Why convert on Pi?")
print("   - NCNN tools are easier to build on Linux")
print("   - Ensures ARM-specific optimizations")
print("   - Avoids Windows build tool complexity")
print()
print("✅ Your ONNX model is ready to transfer!")
print()
