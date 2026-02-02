#!/bin/bash
# NCNN Setup Script for Raspberry Pi 4
# Builds NCNN and YOLOv8 inference binary

set -e

echo "🔥 NutriCycle NCNN Setup for Raspberry Pi"
echo "=========================================="

# Check if running on ARM
if [[ $(uname -m) != "aarch64" ]]; then
    echo "⚠️  Warning: This script is designed for Raspberry Pi (aarch64)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install dependencies
echo "📦 Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    git \
    cmake \
    libprotobuf-dev \
    protobuf-compiler \
    libopencv-dev \
    python3-opencv

# Create working directory
WORK_DIR="$HOME/ncnn_build"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Clone NCNN
echo "📥 Cloning NCNN repository..."
if [ ! -d "ncnn" ]; then
    git clone --depth=1 https://github.com/Tencent/ncnn
else
    echo "NCNN already cloned, skipping..."
fi

cd ncnn

# Build NCNN
echo "🔨 Building NCNN (this may take 10-15 minutes)..."
mkdir -p build
cd build

cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DNCNN_VULKAN=OFF \
    -DNCNN_BUILD_EXAMPLES=ON \
    -DNCNN_BUILD_TOOLS=ON \
    -DNCNN_DISABLE_RTTI=OFF \
    -DNCNN_DISABLE_EXCEPTION=OFF \
    ..

make -j$(nproc)

echo "✅ NCNN built successfully"

# Create inference directory structure
DEPLOY_DIR="$(dirname "$(dirname "$(realpath "$0")")")/deploy"
NCNN_DIR="$DEPLOY_DIR/ncnn"

mkdir -p "$NCNN_DIR/bin"
mkdir -p "$NCNN_DIR/models"
mkdir -p "$NCNN_DIR/src"

echo "📝 Creating YOLOv8 inference wrapper..."

# Create C++ YOLOv8 inference code
cat > "$NCNN_DIR/src/yolo_ncnn.cpp" << 'EOF'
// YOLOv8 NCNN Inference for NutriCycle
// Simplified inference with JSON output

#include <opencv2/opencv.hpp>
#include <net.h>
#include <iostream>
#include <vector>
#include <algorithm>

struct Detection {
    float x, y, w, h;
    float conf;
    int cls;
};

int main(int argc, char** argv) {
    if (argc < 4) {
        std::cerr << "Usage: " << argv[0] << " <param> <bin> <image> [conf=0.5]" << std::endl;
        return 1;
    }

    const char* param_path = argv[1];
    const char* bin_path = argv[2];
    const char* image_path = argv[3];
    float conf_threshold = (argc > 4) ? std::atof(argv[4]) : 0.5f;

    // Load model
    ncnn::Net net;
    net.opt.use_vulkan_compute = false;
    net.opt.num_threads = 4;

    if (net.load_param(param_path) != 0 || net.load_model(bin_path) != 0) {
        std::cerr << "ERROR: Failed to load model" << std::endl;
        return 1;
    }

    // Load image
    cv::Mat bgr = cv::imread(image_path);
    if (bgr.empty()) {
        std::cerr << "ERROR: Failed to load image: " << image_path << std::endl;
        return 1;
    }

    // Preprocess (letterbox + normalize)
    int target_size = 320;
    int img_w = bgr.cols;
    int img_h = bgr.rows;
    
    float scale = std::min(target_size / (float)img_w, target_size / (float)img_h);
    int new_w = (int)(img_w * scale);
    int new_h = (int)(img_h * scale);

    cv::Mat resized;
    cv::resize(bgr, resized, cv::Size(new_w, new_h));

    // Letterbox
    cv::Mat padded = cv::Mat::zeros(target_size, target_size, CV_8UC3);
    int pad_x = (target_size - new_w) / 2;
    int pad_y = (target_size - new_h) / 2;
    resized.copyTo(padded(cv::Rect(pad_x, pad_y, new_w, new_h)));

    // Convert to ncnn Mat
    ncnn::Mat in = ncnn::Mat::from_pixels(padded.data, ncnn::Mat::PIXEL_BGR, target_size, target_size);
    const float norm_vals[3] = {1/255.f, 1/255.f, 1/255.f};
    in.substract_mean_normalize(0, norm_vals);

    // Inference
    ncnn::Extractor ex = net.create_extractor();
    ex.input("images", in);

    ncnn::Mat out;
    ex.extract("output0", out);

    // Parse detections (YOLOv8 format: [1, 84, 8400] or similar)
    std::vector<Detection> detections;
    
    int num_proposals = out.w;  // e.g., 8400
    int num_values = out.h;     // e.g., 84 (4 bbox + 80 classes) or 5 for single class

    for (int i = 0; i < num_proposals; i++) {
        const float* values = out.row(0) + i * num_values;
        
        // YOLOv8: [x, y, w, h, class_scores...]
        float cx = values[0];
        float cy = values[1];
        float w = values[2];
        float h = values[3];

        // Find max class score
        float max_score = 0.0f;
        int max_cls = 0;
        for (int c = 4; c < num_values; c++) {
            if (values[c] > max_score) {
                max_score = values[c];
                max_cls = c - 4;
            }
        }

        if (max_score > conf_threshold) {
            Detection det;
            // Convert from normalized coords back to original image
            det.x = (cx - pad_x) / scale;
            det.y = (cy - pad_y) / scale;
            det.w = w / scale;
            det.h = h / scale;
            det.conf = max_score;
            det.cls = max_cls;
            detections.push_back(det);
        }
    }

    // Output JSON
    std::cout << "{\"detections\": [";
    for (size_t i = 0; i < detections.size(); i++) {
        const auto& det = detections[i];
        std::cout << "{\"cls\": " << det.cls 
                  << ", \"conf\": " << det.conf
                  << ", \"x\": " << det.x
                  << ", \"y\": " << det.y
                  << ", \"w\": " << det.w
                  << ", \"h\": " << det.h
                  << "}";
        if (i < detections.size() - 1) std::cout << ", ";
    }
    std::cout << "]}" << std::endl;

    return 0;
}
EOF

# Create CMakeLists.txt for yolo_ncnn
cat > "$NCNN_DIR/src/CMakeLists.txt" << 'EOF'
cmake_minimum_required(VERSION 3.10)
project(yolo_ncnn)

set(CMAKE_CXX_STANDARD 11)

find_package(OpenCV REQUIRED)
find_package(ncnn REQUIRED)

add_executable(yolo_ncnn yolo_ncnn.cpp)
target_link_libraries(yolo_ncnn ncnn ${OpenCV_LIBS})
EOF

# Build yolo_ncnn
echo "🔨 Building YOLOv8 inference binary..."
cd "$NCNN_DIR/src"
mkdir -p build
cd build

cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -Dncnn_DIR="$WORK_DIR/ncnn/build/install/lib/cmake/ncnn" \
    ..

make -j$(nproc)

# Copy binary to bin directory
cp yolo_ncnn "$NCNN_DIR/bin/"

echo "✅ YOLOv8 NCNN binary built successfully"

# Create simple test script
cat > "$NCNN_DIR/test_inference.sh" << 'EOF'
#!/bin/bash
# Quick test script for NCNN inference

if [ ! -f "models/best-int8.param" ]; then
    echo "❌ Model files not found in models/"
    echo "Please copy best-int8.param and best-int8.bin to deploy/ncnn/models/"
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: ./test_inference.sh <image.jpg>"
    exit 1
fi

./bin/yolo_ncnn models/best-int8.param models/best-int8.bin "$1" 0.5
EOF

chmod +x "$NCNN_DIR/test_inference.sh"

echo ""
echo "✅ NCNN Setup Complete!"
echo "======================================"
echo "Binary location: $NCNN_DIR/bin/yolo_ncnn"
echo "Models directory: $NCNN_DIR/models/"
echo ""
echo "📋 Next steps:"
echo "1. Copy your NCNN model files:"
echo "   cp best-int8.param best-int8.bin $NCNN_DIR/models/"
echo ""
echo "2. Test inference:"
echo "   cd $NCNN_DIR"
echo "   ./test_inference.sh your_test_image.jpg"
echo ""
echo "3. Update Python scripts to use NCNN wrapper"
echo ""
