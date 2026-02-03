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
WORK_DIR="$HOME"
cd "$WORK_DIR"

# Clone NCNN
echo "📥 Cloning NCNN repository..."
if [ ! -d "ncnn" ]; then
    git clone --depth=1 https://github.com/Tencent/ncnn.git
else
    echo "ℹ️  NCNN already cloned, pulling latest changes..."
    cd ncnn
    git pull
    cd ..
fi

cd ncnn

# Initialize and update submodules
echo "📥 Updating git submodules..."
git submodule update --init --recursive

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
    ..

make -j$(nproc)

echo "✅ NCNN built successfully"
echo "Verifying onnx2ncnn tool..."
if [ -f "tools/onnx/onnx2ncnn" ]; then
    echo "✅ onnx2ncnn found at: $(pwd)/tools/onnx/onnx2ncnn"
else
    echo "❌ onnx2ncnn not found! Build may have failed."
    exit 1
fi

# Install Python ncnn
echo "📦 Installing pyncnn (Python bindings)..."
cd "$HOME/ncnn/python"
pip3 install --upgrade pip
pip3 install .

# Verify pyncnn installation
echo "Verifying pyncnn installation..."
python3 -c "import ncnn; print('✅ pyncnn installed successfully, version:', ncnn.__version__)" || echo "⚠️  pyncnn installation may have issues"

echo ""
echo "✅ NCNN Setup Complete!"
echo "======================================"
echo "Tools location: $HOME/ncnn/build/tools"
echo ""
echo "📋 Next steps:"
echo "1. Convert ONNX → NCNN:"
echo "   cd ~/ncnn/build/tools/onnx"
echo "   ./onnx2ncnn ~/NutriCycle-RaspBerry-v2/deploy/models/best.onnx \\"
echo "              ~/NutriCycle-RaspBerry-v2/deploy/models/best.param \\"
echo "              ~/NutriCycle-RaspBerry-v2/deploy/models/best.bin"
echo ""
echo "2. Verify conversion:"
echo "   ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/"
echo ""
echo "3. Test NCNN model:"
echo "   cd ~/NutriCycle-RaspBerry-v2/deploy"
echo "   source venv/bin/activate"
echo "   python test_video_ncnn.py"
echo ""
