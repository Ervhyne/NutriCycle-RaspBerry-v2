#!/bin/bash
# Cleanup script to remove broken NCNN files before proper conversion

echo "🧹 Cleaning up old NCNN files..."
echo "================================"
echo ""

# Remove NCNN model files
if [ -f "models/best.param" ] || [ -f "models/best.bin" ]; then
    echo "🗑️  Removing old NCNN models..."
    rm -f models/*.param models/*.bin
    echo "   ✅ Removed models/*.param and models/*.bin"
else
    echo "   ℹ️  No NCNN model files found in models/"
fi

# Remove NCNN directory if it exists
if [ -d "ncnn" ]; then
    echo "🗑️  Removing ncnn/ directory..."
    rm -rf ncnn/
    echo "   ✅ Removed ncnn/"
else
    echo "   ℹ️  No ncnn/ directory found"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Transfer fresh ONNX model from laptop"
echo "   2. Run setup_ncnn_pi_simple.sh to build NCNN tools"
echo "   3. Convert ONNX → NCNN using onnx2ncnn"
echo ""
echo "See ONNX_TO_NCNN_WORKFLOW.md for detailed instructions"
