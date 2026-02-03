#!/usr/bin/env python3
"""
Quick camera test script
Tests if the camera can be accessed before starting the WebRTC server
"""

import cv2
import sys

print("🔍 Testing camera access...")
print("")

# Test different camera indices
for i in range(4):
    print(f"Testing camera index {i}...", end=" ")
    
    # Try V4L2 backend (Linux)
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    
    if cap.isOpened():
        # Try to read a frame
        ret, frame = cap.read()
        if ret and frame is not None:
            height, width = frame.shape[:2]
            print(f"✅ SUCCESS! Resolution: {width}x{height}")
            
            # Show camera properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            backend = cap.getBackendName()
            print(f"   FPS: {fps}, Backend: {backend}")
            
            # This camera works!
            if i == 0:
                print("")
                print("🎉 Camera 0 works! You can use: --source 0")
            cap.release()
        else:
            print("⚠️  Camera opened but cannot read frames")
            cap.release()
    else:
        print("❌ Cannot open")

print("")
print("💡 Recommendations:")
print("   - Use the camera index that shows ✅ SUCCESS")
print("   - Update start_stream.sh with: --source <index>")
print("   - If none work, run: ./deploy/fix_camera.sh")
print("")

# Check user groups
import subprocess
try:
    groups = subprocess.check_output(['groups'], text=True)
    if 'video' in groups:
        print("✅ User is in 'video' group")
    else:
        print("⚠️  User NOT in 'video' group!")
        print("   Run: sudo usermod -a -G video $USER")
        print("   Then logout and login")
except:
    pass

print("")
print("🧪 To test with YOLO, run:")
print("   python3 deploy/webrtc_server.py --source 0")
