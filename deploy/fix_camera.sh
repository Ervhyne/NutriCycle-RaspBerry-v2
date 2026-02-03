#!/bin/bash
# Camera troubleshooting script for Raspberry Pi
# Run this if you get camera access errors

echo "🔍 NutriCycle Camera Troubleshooting"
echo "===================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "⚠️  Don't run this script as root (sudo)"
   echo "   Run as: ./fix_camera.sh"
   exit 1
fi

# 1. Check video devices
echo "1️⃣ Checking video devices..."
if ls /dev/video* 1> /dev/null 2>&1; then
    echo "✅ Found video devices:"
    ls -la /dev/video*
else
    echo "❌ No video devices found!"
    echo "   Make sure your camera is connected"
    exit 1
fi
echo ""

# 2. Check user groups
echo "2️⃣ Checking user groups..."
if groups | grep -q video; then
    echo "✅ User is in 'video' group"
else
    echo "⚠️  User is NOT in 'video' group"
    echo "   Adding $USER to video group..."
    sudo usermod -a -G video $USER
    echo "✅ Added to video group"
    echo "⚠️  You must LOGOUT and LOGIN again for this to take effect!"
    echo "   Or run: newgrp video"
fi
echo ""

# 3. Check v4l-utils
echo "3️⃣ Checking v4l-utils..."
if command -v v4l2-ctl &> /dev/null; then
    echo "✅ v4l-utils installed"
    echo ""
    echo "📹 Available cameras:"
    v4l2-ctl --list-devices
else
    echo "⚠️  v4l-utils not installed"
    echo "   Installing..."
    sudo apt-get update
    sudo apt-get install -y v4l-utils
    echo "✅ v4l-utils installed"
fi
echo ""

# 4. Test camera access
echo "4️⃣ Testing camera access..."
python3 << 'PYTHON_TEST'
import cv2
import sys

for i in range(5):
    print(f"  Testing /dev/video{i}...", end=" ")
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"✅ Works! Resolution: {frame.shape[1]}x{frame.shape[0]}")
            cap.release()
        else:
            print("❌ Opened but can't read frames")
            cap.release()
    else:
        print("❌ Cannot open")
        
PYTHON_TEST

echo ""
echo "5️⃣ Checking camera permissions..."
for dev in /dev/video*; do
    if [ -e "$dev" ]; then
        perm=$(ls -la "$dev" | awk '{print $1, $3, $4}')
        echo "  $dev: $perm"
    fi
done
echo ""

# Final recommendations
echo "✅ Troubleshooting complete!"
echo ""
echo "📋 Common solutions:"
echo "   1. If NOT in video group → logout and login again"
echo "   2. If permission denied → run: sudo chmod 666 /dev/video0"
echo "   3. If camera in use → kill other processes: pkill -f python"
echo "   4. Try different camera index in start_stream.sh (--source 0, 1, or 2)"
echo "   5. Reboot if nothing works: sudo reboot"
echo ""
echo "🧪 Test the fixed camera:"
echo "   python3 -c 'import cv2; cap=cv2.VideoCapture(0, cv2.CAP_V4L2); print(\"Success!\" if cap.isOpened() else \"Failed\")'"
