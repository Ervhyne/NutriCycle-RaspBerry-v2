# Manual NCNN Setup (Step-by-Step)

If the automated script keeps failing, follow these manual steps to build NCNN.

---

## Step 1: Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y build-essential git cmake
sudo apt-get install -y libprotobuf-dev protobuf-compiler
sudo apt-get install -y python3-dev python3-pip

# Verify installations
gcc --version
cmake --version
protoc --version
```

**Wait for each command to complete before continuing to the next.**

---

## Step 2: Clone NCNN Repository

```bash
cd ~
git clone https://github.com/Tencent/ncnn.git
cd ncnn
git submodule update --init --recursive
```

This downloads NCNN source code (~100MB).

---

## Step 3: Build NCNN (Method 1 - Simple)

```bash
cd ~/ncnn
mkdir -p build
cd build

# Configure
cmake -DCMAKE_BUILD_TYPE=Release \
      -DNCNN_VULKAN=OFF \
      -DNCNN_BUILD_EXAMPLES=OFF \
      -DNCNN_BUILD_TOOLS=ON \c
      -DNCNN_PYTHON=ON \
      ..

# Build (takes 10-20 minutes)
make -j4
```

**If you see warnings about uninitialized variables**, that's okay - it will still build.

**If build stops with errors**, try Method 2 below.

---

## Step 3: Build NCNN (Method 2 - Ignore Warnings)

If Method 1 failed, try this:

```bash
cd ~/ncnn/build
rm -rf *  # Clean previous build

cmake -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_CXX_FLAGS="-Wno-error" \
      -DNCNN_VULKAN=OFF \
      -DNCNN_BUILD_EXAMPLES=OFF \
      -DNCNN_BUILD_TOOLS=ON \
      -DNCNN_PYTHON=OFF \
      ..

make -j4
```

Note: This disables Python bindings to simplify the build.

---

## Step 4: Verify Build Success

```bash
# Check if onnx2ncnn was built
ls -lh ~/ncnn/build/tools/onnx/onnx2ncnn

# Should show something like:
# -rwxr-xr-x 1 nutricycle nutricycle 2.1M ... onnx2ncnn
```

If you see the file, **success!** ✅

If not, check for error messages:
```bash
cd ~/ncnn/build
make 2>&1 | grep -i error
```

---

## Step 5: Convert ONNX to NCNN

**Note**: NCNN now recommends using `pnnx` (the new converter) instead of `onnx2ncnn` (legacy). Both methods are shown below.

### Method A: Using pnnx (Recommended - New Tool)

```bash
# Install pnnx
pip3 install pnnx

# Convert your model
cd ~/NutriCycle-RaspBerry-v2/deploy/models
pnnx best.onnx

# This creates best.ncnn.param and best.ncnn.bin
```

### Method B: Using onnx2ncnn (Legacy - Located in tools/onnx)

```bash
# Navigate to the onnx2ncnn location
cd ~/ncnn/build/tools/onnx

# Or if built in different location:
cd /home/nutricycle/ncnn/tools/onnx

# Convert your model
./onnx2ncnn \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.onnx \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.param \
  ~/NutriCycle-RaspBerry-v2/deploy/models/best.bin

# Verify output
ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/
```

You should see:
- `best.onnx` (original, ~5.8MB)
- `best.param` (new, ~12KB)
- `best.bin` (new, ~5.6MB)

---

## Step 6: Test the Model

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Install Python dependencies
pip3 install opencv-python numpy ultralytics

# Test with ONNX first (to verify it works)
python3 -c "from ultralytics import YOLO; model = YOLO('models/best.onnx'); print('ONNX loaded OK')"

# Test NCNN (if you have pyncnn)
# pip3 install pyncnn
# python3 test_video_ncnn.py --source 0
```

---

## Common Issues

### Issue: "cpuinfo failed prctl pr_sve_get_vl failed"
**This is harmless!** It's just a warning about SVE (Scalable Vector Extension) not being available on Raspberry Pi ARM processors. You can safely ignore it - the conversion will still work. This is not a folder location issue.

### Issue: "cmake not found"
```bash
sudo apt-get install -y cmake
```

### Issue: "protoc not found" 
```bash
sudo apt-get install -y protobuf-compiler libprotobuf-dev
protoc --version
```

### Issue: "Out of memory" during build
```bash
# Use fewer cores
cd ~/ncnn/build
make -j2  # or make -j1 for single core
```

### Issue: Build stops at 99% or hangs
```bash
# Kill and rebuild with verbose output
cd ~/ncnn/build
make clean
make VERBOSE=1
```

### Issue: "undefined reference to onnx::"
```bash
# Protobuf version mismatch - reinstall
sudo apt-get remove libprotobuf-dev protobuf-compiler
sudo apt-get install -y libprotobuf-dev protobuf-compiler
cd ~/ncnn/build
rm -rf *
# Re-run cmake and make from Step 3
```

---

## Skip NCNN Entirely (Alternative)

If NCNN continues to fail, **just use ONNX directly** - it works fine:

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy

# Install ONNX runtime
pip3 install onnxruntime

# Use the ONNX model directly
python3 test_video.py --model models/best.onnx --source 0 --conf 0.5
```

ONNX will be slower than NCNN but it will work reliably.

---
### Option 1: Using pnnx (Recommended)
```bash
# Install pnnx
pip3 install pnnx

# Convert
cd ~/NutriCycle-RaspBerry-v2/deploy/models
pnnx best.onnx

# Verify
ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/
```

### Option 2: Using onnx2ncnn (Legacy)
```bash
# 1. Dependencies
sudo apt-get update && sudo apt-get install -y build-essential git cmake libprotobuf-dev protobuf-compiler python3-dev python3-pip

# 2. Clone
cd ~ && git clone https://github.com/Tencent/ncnn.git && cd ncnn && git submodule update --init --recursive

# 3. Build
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-Wno-error" -DNCNN_VULKAN=OFF -DNCNN_BUILD_TOOLS=ON -DNCNN_PYTHON=OFF ..
make -j4

# 4. Convert (check both locations)
cd ~/ncnn/build/tools/onnx || cd /home/nutricycle/ncnn

# 4. Convert
cd ~/ncnn/build/tools/onnx
./onnx2ncnn ~/NutriCycle-RaspBerry-v2/deploy/models/best.onnx ~/NutriCycle-RaspBerry-v2/deploy/models/best.param ~/NutriCycle-RaspBerry-v2/deploy/models/best.bin

# 5. Verify
ls -lh ~/NutriCycle-RaspBerry-v2/deploy/models/
```

---

**Pro Tip**: Copy and paste ONE command at a time, wait for it to finish, then move to the next. This way you'll see exactly where any problem occurs.
