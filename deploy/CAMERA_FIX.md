# Camera Access Error - Fixed! 🎥

## Problem
When a mobile device connects to the WebRTC stream, you get these errors:
```
ERROR: Failed to open camera/video source: 0
VIDEOIO(V4L2:/dev/video0): can't open camera by index
Not a video capture device
```

## Root Causes
1. **Multiple camera instances** - Old code opened a new camera for each WebRTC connection
2. **Permission issues** - User not in the `video` group
3. **Wrong video device** - Using wrong `/dev/videoX` index

## Solutions Applied

### 1. Code Fix ✅
Updated `webrtc_server.py` to use a **shared camera singleton**:
- Only opens the camera ONCE
- All client connections share the same camera stream
- Proper reference counting prevents camera conflicts

### 2. Camera Permissions Fix

**On Raspberry Pi, run these commands:**

```bash
# Make the scripts executable
chmod +x deploy/fix_camera.sh
chmod +x deploy/start_stream.sh

# Run the camera troubleshooting script
cd ~/NutriCycle-RaspBerry-v2
./deploy/fix_camera.sh
```

This will:
- Add your user to the `video` group
- Check available cameras
- Test camera access
- Show helpful diagnostics

**Important:** After running the fix script, you must:
- **Logout and login again**, OR
- Run: `newgrp video`, OR
- **Reboot**: `sudo reboot`

### 3. Manual Permission Fix (Alternative)

If the script doesn't work, try manually:

```bash
# Add user to video group
sudo usermod -a -G video $USER

# Check video devices
ls -la /dev/video*

# Fix permissions if needed
sudo chmod 666 /dev/video0

# Check available cameras
v4l2-ctl --list-devices

# Test camera in Python
python3 -c "import cv2; cap=cv2.VideoCapture(0, cv2.CAP_V4L2); print('✅ Success!' if cap.isOpened() else '❌ Failed')"
```

## Testing the Fix

1. **Stop any running instances:**
   ```bash
   pkill -f webrtc_server.py
   pkill -f ngrok
   ```

2. **Start the server:**
   ```bash
   cd ~/NutriCycle-RaspBerry-v2/deploy
   ./start_stream.sh
   ```

3. **Connect from mobile:**
   - Open the ngrok URL in your mobile browser
   - You should see the camera stream without errors!

## Troubleshooting

### Still getting errors?

**1. Check which camera index to use:**
```bash
v4l2-ctl --list-devices
```

**2. Try different camera indices:**
Edit `start_stream.sh` and change `--source 0` to `--source 1` or `--source 2`

**3. Check if camera is in use:**
```bash
# Kill all Python processes
pkill -f python

# Check what's using the camera
sudo lsof /dev/video0
```

**4. Check logs:**
```bash
# The server will show detailed error messages
# Look for lines starting with ❌ or ERROR
```

**5. Reboot (often fixes everything):**
```bash
sudo reboot
```

## What Changed in the Code?

### Before (Problem):
```python
class YOLOVideoTrack:
    def __init__(self, source, ...):
        self.cap = cv2.VideoCapture(source)  # ❌ Opens new camera each time!
```

Each WebRTC connection tried to open the camera again → **FAILS!**

### After (Fixed):
```python
class SharedCamera:
    _instance = None  # ✅ Singleton pattern
    
    @classmethod
    async def get_instance(cls, source):
        if cls._instance is None:
            cls._instance = SharedCamera(source)  # Open once
        return cls._instance
```

Camera opens only ONCE, all connections share it → **WORKS!**

## Additional Features Added

1. **Camera test at startup** - Server checks camera before starting
2. **Better error messages** - Shows exact troubleshooting steps
3. **Reference counting** - Properly manages camera lifecycle
4. **Improved Linux support** - Uses `CAP_V4L2` backend for better compatibility

## Files Modified

- ✅ [webrtc_server.py](webrtc_server.py) - Shared camera implementation
- ✅ [start_stream.sh](start_stream.sh) - Added camera checks
- ✅ [fix_camera.sh](fix_camera.sh) - New troubleshooting script (NEW)

## Quick Command Reference

```bash
# Fix camera permissions
./deploy/fix_camera.sh

# Start the stream
./deploy/start_stream.sh

# Check camera status
v4l2-ctl --list-devices

# Test camera in Python
python3 -c "import cv2; print(cv2.VideoCapture(0, cv2.CAP_V4L2).isOpened())"

# Kill all streams
pkill -f webrtc_server.py; pkill -f ngrok
```

## Need More Help?

Check the server logs for specific error messages. The updated code now shows:
- ✅ Success messages with green checkmarks
- ❌ Error messages with troubleshooting steps
- 📹 Camera status and resolution info

---

**Your camera should now work perfectly with multiple mobile connections!** 🎉
