Live detection + tracking helper (NutriCycle)

Files
- `live_track.py` — small CLI for live detection + tracking (webcam or video)
- `live_track.bat` — Windows wrapper that runs the script using `.venv311`'s python
- `requirements.txt` — packages used by the script

Quick start (PowerShell):

1. From repo root, optionally activate the venv (recommended on Windows):
   & ".\.venv311\Scripts\Activate.ps1"

2. Install Python dependencies (from repo root):
   & ".\.venv311\Scripts\python.exe" -m pip install --upgrade pip
   & ".\.venv311\Scripts\python.exe" -m pip install -r deploy/requirements.txt
   # Note: `onnxruntime` may not have Pip wheels for newer Python versions on Windows; see Notes below.

2.5 For Raspberry Pi deployment (copy trained model to deploy folder):
   ```bash
   # On Raspberry Pi (or Linux):
   ./deploy/setup_model.sh
   
   # On Windows PowerShell:
   Copy-Item "AI-Model\runs\detect\nutricycle_foreign_only\weights\best.pt" "deploy\models\best.pt"
   ```
   - Copy `.env.example` to `.env` and update values (MQTT broker, announce server, MACHINE_ID etc.)
     ```bash
     cp deploy/.env.example .env
     ```


3. Quick tests (no code):
   - Single image (fast check):
     & ".\.venv311\Scripts\yolo.exe" predict model="AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" source="NutriCycle-Objects-Detection-v1.v1-v1-baseline.yolov8/test/images/img_0002.jpg" imgsz=512 conf=0.25 save=True project="AI-Model/runs" name=quick_test

   - Quick webcam detection (no script):
     & ".\.venv311\Scripts\yolo.exe" detect predict model="AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" source=0 show=True

4. Use the helper script (`deploy/test_video.py`) — more control (flip, save, video file):
   - Upside-down webcam (example you asked to save):
     ```powershell
     python deploy/test_video.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" --source 1 --flip vertical
     ```
   - Record output:
     ```powershell
     python deploy/test_video.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" --source 1 --flip vertical --output out.mp4 --conf 0.5
     ```
   - Test a local video file:
     ```powershell
     python deploy/test_video.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" --source "C:\path\to\video.mp4" --output out.mp4
     ```
   - Press `q` in the window to quit at any time.

5. Not sure which camera index is your external webcam? Run this quick scan (Windows: uses DirectShow):
   ```powershell
   python - <<'PY'
   import cv2
   for i in range(8):
       cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
       ok, _ = cap.read()
       print(i, 'OK' if ok else 'no')
       cap.release()
   PY
   ```
   Use the index that prints `OK` (0/1/2...). On Windows, `cv2.CAP_DSHOW` is more reliable for USB cameras.

6. Run webcam tracking with a tracker (optional):
   & ".\\.venv311\\Scripts\\yolo.exe" track model="AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" source=0 tracker=bytetrack.yaml imgsz=512 conf=0.1 save=True project="AI-Model/runs" name=live_track

If you need persistent tracker registration (stable IDs), use the Python helper:
   & ".\\.venv311\\Scripts\\python.exe" deploy\\live_track.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx" --source 0 --persist --save --name live_track

Or use the bundled batch wrapper on Windows:
  deploy\live_track.bat --source 0 --save --name my_run

If you need persistent tracker registration (stable IDs), use the Python helper:
   & ".\\.venv311\\Scripts\\python.exe" deploy\\live_track.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx" --source 0 --persist --save --name live_track

Or use the bundled batch wrapper on Windows:
  deploy\live_track.bat --source 0 --save --name my_run

Notes:
- Use ONNX for CPU-only deployment (Raspberry Pi). We exported `best.onnx` for that purpose. On desktop, `.pt` is usually faster and easier (no `onnxruntime` dependency).

- ONNX runtime on Windows: if `pip install onnxruntime` fails, it is often due to using a Python version with no prebuilt wheels (e.g., Python 3.14). Options:
  - Use the provided `.venv311` (Python 3.11) or install Python 3.10/3.11; then run:
    ```powershell
    & ".\.venv311\Scripts\python.exe" -m pip install onnxruntime
    ```
  - Or use Conda (recommended if you use Anaconda/Miniconda):
    ```powershell
    conda install -c conda-forge onnxruntime
    ```

- If you prefer to avoid runtime dependency issues, run inference with the `.pt` model on desktop (example above uses `best.pt`).

- Tracker note (Windows): some trackers (ByteTrack/BotSort) require the `lap` package which may need to compile C extensions. If `pip install lap` fails with "Microsoft Visual C++ 14.0 or greater is required", you have two options:
  1. Install the Visual C++ Build Tools and then run:
     ```powershell
     & ".\.venv311\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
     & ".\.venv311\Scripts\python.exe" -m pip install numpy
     & ".\.venv311\Scripts\python.exe" -m pip install lap
     ```
  2. Use a prebuilt wheel or conda (recommended):
     - `conda install -c conda-forge lap`
     - or download a matching wheel and `pip install <wheel-file>`.

  If you prefer to avoid compiled extensions, run tracking without a tracker (detection-only) — the CLI still works but without ID tracking.

- Windows camera tip: for more reliable USB camera access, prefer DirectShow (OpenCV backend `cv2.CAP_DSHOW`) and try different USB ports if a camera index doesn't work.

- **Models are included in the repo** at `AI-Model/runs/detect/nutricycle_foreign_only/weights/` (best.pt, best.onnx). Use `setup_model.sh` to copy them to `deploy/models/` for Raspberry Pi deployment.

---

## WebRTC streaming (live detection in browser) 🌐📹

Stream live camera + YOLO detection to any browser using WebRTC. Tested on Windows; Pi-compatible with notes below.

**Files**
- `deploy/webrtc_server.py` — WebRTC server with YOLO inference
- `deploy/webrtc_client.html` — browser client (auto-served by server)

**Quick start (Windows)**

1. Install WebRTC dependencies (Python 3.11 recommended):
   ```powershell
   & ".\.venv311\Scripts\python.exe" -m pip install aiortc aiohttp av
   ```
   
   If `av` (PyAV) installation fails on Windows:
   - Option A (Conda — easiest):
     ```powershell
     conda install -c conda-forge av aiortc aiohttp
     ```
   - Option B: Download a prebuilt wheel for your Python version from [PyAV releases](https://github.com/PyAV-Org/PyAV/releases) and `pip install <wheel-file>`.

2. Run the WebRTC server (example with external webcam index 1, flipped vertically):
   ```powershell
   python deploy/webrtc_server.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" --source 1 --flip vertical --conf 0.5
   ```
   
   Options:
   - `--model`: path to `.pt` or `.onnx` model (use `.pt` on Windows for simplicity)
   - `--source`: camera index (`0`, `1`, etc.) or video file path
   - `--flip`: `none`, `vertical`, `horizontal`, or `180`
   - `--conf`: confidence threshold (default 0.5)
   - `--host`: server host (default `0.0.0.0`)
   - `--port`: server port (default `8080`)

3. Open browser and navigate to:
   ```
   http://localhost:8080
   ```
   You should see live camera feed with YOLO detections streaming in your browser. Press **Reconnect** if the stream drops.

**Raspberry Pi WebRTC deployment**

1. Install system dependencies for PyAV on Pi:
   ```bash
   sudo apt update
   sudo apt install -y libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libavresample-dev libavfilter-dev pkg-config
   ```

2. Install Python WebRTC packages:
   ```bash
   source venv/bin/activate
   python -m pip install aiortc aiohttp av
   ```
   
   If `av` fails on Pi, use Conda or build from source (see PyAV docs).

3. Run the server on Pi (use `.onnx` model for CPU inference):
   ```bash
   python deploy/webrtc_server.py --model deploy/models/best.onnx --source 0 --conf 0.25 --host 0.0.0.0 --port 8080
   ```

4. Access the stream from another device on the same network:
   ```
   http://<pi-ip-address>:8080
   ```

**Troubleshooting**
- **PyAV install fails**: Use Conda (`conda install -c conda-forge av`) or download matching wheel.
- **Camera not opening**: Check camera index with the scan command in the Quick Start section above.
- **Stream not appearing**: Check browser console (F12) for WebRTC errors; ensure firewall allows port 8080.
- **Low FPS on Pi**: Lower resolution or use a smaller YOLO model (yolov8n). Consider hardware acceleration (e.g., Coral TPU).
- **ONNX model fails**: Ensure `onnxruntime` is installed or use `.pt` on desktop.

**Notes**
- WebRTC provides low-latency streaming compared to RTSP/HTTP.
- On Windows prefer `.pt` models; on Pi prefer `.onnx` (CPU optimized).
- For production, consider SSL (HTTPS) for secure WebRTC signaling.
- Multiple clients can connect simultaneously to view the same stream.

---

## Raspberry Pi deployment (CPU / ONNX) 🐧🔧

This project supports deploying the exported `best.onnx` to a Raspberry Pi (CPU-only inference). Below are tested, practical steps and troubleshooting tips so nothing is left out.

**Prerequisites**
- Raspberry Pi OS 64-bit (or Ubuntu 64-bit) recommended
- Raspberry Pi 4/5 with 4GB+ RAM recommended
- Python 3.10/3.11 (use `pyenv` or the `.venv311` approach in this repo)

**Quick deploy steps**
1. Copy the model and repo to the Pi (example from your laptop):
   ```bash
   scp AI-Model/runs/detect/nutricycle_foreign_only/weights/best.onnx pi@raspberrypi:/home/pi/nutricycle/deploy/models/best.onnx
   # or git clone this repo directly on the Pi
   ```

2. Prepare a Python virtual environment on the Pi:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install numpy
   ```

3. Install OpenCV (headless recommended for Pi):
   ```bash
   python -m pip install opencv-python-headless
   ```
   If `pip` binary wheels are unavailable, first install system libs:
   ```bash
   sudo apt update && sudo apt install -y build-essential libatlas-base-dev libjpeg-dev libopenjp2-7-dev libtiff5-dev libavcodec-dev libavformat-dev libswscale-dev libv4l-dev
   ```

4. Install ONNX Runtime (recommended for `.onnx` CPU inference):
   ```bash
   python -m pip install onnxruntime
   ```
   - If `pip` cannot find a wheel for your Pi/Python, use Conda (if available) or find a matching prebuilt wheel at the ONNX Runtime releases page: https://github.com/microsoft/onnxruntime/releases
   - Building ONNX Runtime from source is an option but more advanced (see ONNX Runtime docs).

5. Install Ultralytics and other Python deps:
   ```bash
   python -m pip install ultralytics
   # optional tracker deps: lap (use conda if pip wheel not available)
   ```

6. Run detection with the ONNX model (example):
   ```bash
   python deploy/test_video.py --model deploy/models/best.onnx --source 0 --conf 0.25
   ```

**Troubleshooting & tips**
- If `onnxruntime` is not installable on your Pi's Python version: use a supported Python (3.10/3.11) or use Conda/mamba to install the package. 
- If `opencv-python-headless` fails to install, ensure system libs listed above are present; as a fallback install OpenCV via apt or build from source.
- For very constrained devices, consider using a smaller model (yolov8n) or hardware accelerators (Coral Edge TPU / NPU) — those require additional runtime steps.

**Notes**
- On desktop (Windows/macOS) prefer the `.pt` model for development — `.onnx` is primarily targeted at CPU-only deployments like Raspberry Pi.
- For Jetson/Coral/other accelerators, follow the device-specific runtime and conversion instructions instead of the steps above.

---


