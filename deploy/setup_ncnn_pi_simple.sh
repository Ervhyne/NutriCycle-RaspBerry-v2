#!/bin/bash
# Simple NCNN Setup - Just builds NCNN tools (no custom C++ binary)
# Works with Python wrapper calling pyncnn directly

set -e

echo "🔥 NutriCycle NCNN Setup (Simplified)"
echo "=========================================="

# Check if running on ARM
if [[ $(uname -m) != "aarch64" ]]; then
    echo "⚠️  Warning: This script is designed for Raspberry Pi (aarch64)"
fi

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    git \
    cmake \
    libprotobuf-dev \
    protobuf-compiler \
    libopencv-dev \
    python3-opencv \
    python3-pip \
    python3-dev

# Create working directory
WORK_DIR="$HOME/ncnn_build"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Clone NCNN
echo "📥 Cloning NCNN repository..."
if [ ! -d "ncnn" ]; then
    git clone --depth=1 https://github.com/Tencent/ncnn
else
    echo "NCNN already cloned"
fi

cd ncnn

# Build NCNN
echo "🔨 Building NCNN (10-15 minutes)..."
mkdir -p build
cd build

cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DNCNN_VULKAN=OFF \
    -DNCNN_BUILD_EXAMPLES=OFF \
    -DNCNN_BUILD_TOOLS=ON \
    -DNCNN_PYTHON=ON \
    -DCMAKE_INSTALL_PREFIX="$WORK_DIR/ncnn/install" \
    ..

make -j$(nproc)
make install

echo "✅ NCNN built successfully"

# Install Python ncnn
echo "📦 Installing pyncnn (Python bindings)..."
cd "$WORK_DIR/ncnn/python"
pip3 install --upgrade pip
pip3 install .

echo ""
echo "✅ NCNN Setup Complete!"
echo "======================================"
echo "Tools location: $WORK_DIR/ncnn/build/tools"
echo ""
echo "📋 Next steps:"
echo "1. Convert ONNX → NCNN:"
echo "   cd $WORK_DIR/ncnn/build"
echo "   ./tools/onnx/onnx2ncnn ~/best.onnx best.param best.bin"
echo ""
echo "2. (Optional) INT8 quantization:"
echo "   ./tools/quantize/ncnn2int8 best.param best.bin best-int8.param best-int8.bin ~/calibration_images/"
echo ""
echo "3. Test with Python:"
echo "   python3 -c 'import ncnn; print(\"pyncnn version:\", ncnn.__version__)'"
echo ""
