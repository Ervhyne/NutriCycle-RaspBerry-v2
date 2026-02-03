#!/bin/bash
# Quick commands for ONNX to NCNN conversion workflow
# Run this on Raspberry Pi after setup_ncnn_pi_simple.sh completes

echo "🚀 NutriCycle ONNX → NCNN Quick Commands"
echo "========================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if NCNN tools exist
if [ ! -f "$HOME/ncnn/build/tools/onnx/onnx2ncnn" ]; then
    echo -e "${RED}❌ NCNN tools not found!${NC}"
    echo "Run setup_ncnn_pi_simple.sh first:"
    echo "   chmod +x setup_ncnn_pi_simple.sh"
    echo "   ./setup_ncnn_pi_simple.sh"
    exit 1
fi

# Check if ONNX model exists
if [ ! -f "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.onnx" ]; then
    echo -e "${RED}❌ ONNX model not found!${NC}"
    echo "Transfer from laptop first:"
    echo "   scp deploy/models/best.onnx nutricycle@raspberrypi:~/NutriCycle-RaspBerry-v2/deploy/models/"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites met${NC}"
echo ""

# Cleanup old files
echo "🧹 Cleaning up old NCNN files..."
rm -f "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.param"
rm -f "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.bin"

# Convert
echo ""
echo "🔄 Converting ONNX → NCNN..."
cd "$HOME/ncnn/build/tools/onnx"

./onnx2ncnn \
  "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.onnx" \
  "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.param" \
  "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.bin"

# Verify
if [ -f "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.param" ] && \
   [ -f "$HOME/NutriCycle-RaspBerry-v2/deploy/models/best.bin" ]; then
    echo ""
    echo -e "${GREEN}✅ Conversion successful!${NC}"
    echo ""
    echo "📊 Model files:"
    ls -lh "$HOME/NutriCycle-RaspBerry-v2/deploy/models/"
    echo ""
    echo "🧪 Test the model:"
    echo "   cd ~/NutriCycle-RaspBerry-v2/deploy"
    echo "   source venv/bin/activate"
    echo "   python test_video_ncnn.py"
else
    echo ""
    echo -e "${RED}❌ Conversion failed!${NC}"
    echo "Check error messages above"
    exit 1
fi
