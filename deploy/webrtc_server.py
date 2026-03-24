#!/usr/bin/env python3
"""
WebRTC server for NutriCycle live detection streaming.
Streams camera + YOLO inference to browser clients via WebRTC.

Usage:
  python deploy/webrtc_server.py --model AI-Model/runs/detect/.../best.pt --source 1 --flip vertical --conf 0.5
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from aiohttp import web, ClientSession
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaBlackhole
from av import VideoFrame
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global args
args = None
model = None
shared_camera = None  # Singleton camera instance
model_is_onnx = False
model_is_ncnn = False

# Event queue for detection events
from asyncio import Queue
event_queue: Queue = Queue(maxsize=32)  # non-blocking if full

# Global detection state gate to avoid per-frame spam.
# False means currently clear/no trigger, True means trigger active.
last_has_detection = False
detection_state_lock = asyncio.Lock()
detection_on_streak = 0
detection_off_streak = 0

# In-memory latest annotated frame (JPEG bytes) for instant preview
latest_frame_jpeg = None
latest_frame_lock = asyncio.Lock()


# Persist the latest known batchNumber locally so we don't need to call
# protected endpoints like GET /batches?machineId=... just to resolve "latest".
STATE_FILE = Path(__file__).with_name("device_state.json")
_last_batch_cache = {}


def _parse_simple_env_file(env_file: Path) -> dict[str, str]:
    """Parse a minimal .env file format (KEY=VALUE, optional quotes/comments)."""
    parsed: dict[str, str] = {}
    try:
        raw = env_file.read_text(encoding="utf-8")
    except Exception:
        return parsed

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        parsed[key] = value

    return parsed


def _load_env_file_into_environ(env_file: Path) -> bool:
    """Load env file values without overriding already-exported environment vars."""
    if not env_file.exists():
        return False

    loaded = _parse_simple_env_file(env_file)
    for key, value in loaded.items():
        os.environ.setdefault(key, value)
    return True


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _env_optional_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _env_optional_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_ice_servers_for_json() -> list[dict]:
    servers: list[dict] = []

    for url in getattr(args, "ice_stun_urls", []):
        servers.append({"urls": [url]})

    turn_url = getattr(args, "ice_turn_url", None)
    turn_username = getattr(args, "ice_turn_username", None)
    turn_password = getattr(args, "ice_turn_password", None)
    if turn_url and turn_username and turn_password:
        servers.append(
            {
                "urls": [turn_url],
                "username": turn_username,
                "credential": turn_password,
            }
        )

    return servers


def _build_ice_servers_for_aiortc() -> list[RTCIceServer]:
    servers: list[RTCIceServer] = []

    for url in getattr(args, "ice_stun_urls", []):
        servers.append(RTCIceServer(urls=[url]))

    turn_url = getattr(args, "ice_turn_url", None)
    turn_username = getattr(args, "ice_turn_username", None)
    turn_password = getattr(args, "ice_turn_password", None)
    if turn_url and turn_username and turn_password:
        servers.append(
            RTCIceServer(
                urls=[turn_url],
                username=turn_username,
                credential=turn_password,
            )
        )

    return servers


def _load_device_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_device_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        # best-effort only
        pass


def _get_last_batch_number(machine_id: str | None) -> str | None:
    if not machine_id:
        return None
    cached = _last_batch_cache.get(machine_id)
    if cached:
        return cached
    state = _load_device_state()
    batch_number = state.get("machines", {}).get(machine_id, {}).get("last_batch_number")
    if batch_number:
        _last_batch_cache[machine_id] = batch_number
    return batch_number


def _set_last_batch_number(machine_id: str | None, batch_number: str | None) -> None:
    if not machine_id or not batch_number:
        return
    _last_batch_cache[machine_id] = batch_number
    state = _load_device_state()
    machines = state.setdefault("machines", {})
    mstate = machines.setdefault(machine_id, {})
    mstate["last_batch_number"] = batch_number
    mstate["updated_at"] = time.time()
    _save_device_state(state)


def _url_variants(server_url: str, path: str) -> list[str]:
    """Try both root and /api-mounted variants for a given path."""
    base = (server_url or "").rstrip("/")
    p = "/" + path.lstrip("/")
    # If caller already includes /api, don't duplicate it.
    if base.endswith("/api"):
        return [f"{base}{p}", f"{base[:-4]}{p}"]
    return [f"{base}{p}", f"{base}/api{p}"]


async def _enqueue_detection_state_if_changed(
    dets: list,
    width: int,
    height: int,
    frame_id: int | None,
    queue: Queue | None,
) -> None:
    """Emit one event only when trigger state changes (0->1 or 1->0)."""
    global last_has_detection, detection_on_streak, detection_off_streak

    if queue is None:
        return

    trigger_dets = _filter_trigger_detections(dets, width, height)
    has_detection = bool(trigger_dets)
    stable_frames = (
        max(1, int(getattr(args, 'trigger_stable_frames', 3)))
        if getattr(args, 'line_trigger_enabled', False)
        else 1
    )

    async with detection_state_lock:
        if has_detection:
            detection_on_streak += 1
            detection_off_streak = 0
        else:
            detection_off_streak += 1
            detection_on_streak = 0

        if not last_has_detection and has_detection and detection_on_streak >= stable_frames:
            last_has_detection = True
        elif last_has_detection and (not has_detection) and detection_off_streak >= stable_frames:
            last_has_detection = False
        else:
            return

        state_now = last_has_detection

    event = {
        'timestamp': time.time(),
        'frame_id': frame_id,
        'width': width,
        'height': height,
        'detections': trigger_dets if state_now else [],
        'count': len(trigger_dets) if state_now else 0,
        'has_detection': state_now,
        'line_trigger_enabled': bool(getattr(args, 'line_trigger_enabled', False)),
        'machine_id': getattr(args, 'machine_id', None)
    }
    try:
        queue.put_nowait(event)
    except Exception:
        # queue full, drop event to avoid blocking
        pass


def _run_model_inference(frame, conf_threshold: float, imgsz: int):
    """Run inference with safe sizing behavior for fixed-shape ONNX exports."""
    if model_is_onnx:
        # Many ONNX exports are fixed-size (commonly 640x640).
        # Let Ultralytics use model-native sizing instead of forcing --imgsz.
        return model(frame, conf=conf_threshold, verbose=False)
    return model(frame, conf=conf_threshold, imgsz=imgsz, verbose=False)


def _is_ncnn_export_path(path: str) -> bool:
    """Return True when path points to an Ultralytics NCNN export directory."""
    p = Path(path)
    return p.is_dir() and (p / "model.ncnn.param").exists() and (p / "model.ncnn.bin").exists()


def _normalize_xyxy(xyxy) -> list[float] | None:
    """Normalize YOLO bbox output into [x1, y1, x2, y2]."""
    try:
        if xyxy is None:
            return None
        # Common Ultralytics shape is [[x1, y1, x2, y2]]
        if isinstance(xyxy, list) and len(xyxy) == 1 and isinstance(xyxy[0], list):
            xyxy = xyxy[0]
        if not isinstance(xyxy, list) or len(xyxy) < 4:
            return None
        return [float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])]
    except Exception:
        return None


def _filter_trigger_detections(dets: list, width: int, height: int) -> list:
    """Return detections that are considered trigger-active under current mode."""
    if not getattr(args, 'line_trigger_enabled', False):
        return dets

    if width <= 0 or height <= 0:
        return []

    trigger_line_y = float(getattr(args, 'trigger_line_y', 0.55))
    trigger_line_y = max(0.0, min(1.0, trigger_line_y))
    line_y_px = trigger_line_y * float(height)
    side = getattr(args, 'after_line_side', 'top')
    cls_filter = getattr(args, 'trigger_class', None)
    min_conf = getattr(args, 'trigger_min_conf', None)
    if min_conf is None:
        min_conf = float(getattr(args, 'conf', 0.5))

    filtered = []
    for d in dets:
        try:
            conf = float(d.get('conf', 0.0))
            cls_id = int(d.get('cls', -1))
            xyxy = _normalize_xyxy(d.get('xyxy'))
            if conf < min_conf:
                continue
            if cls_filter is not None and cls_id != int(cls_filter):
                continue
            if xyxy is None:
                continue
            y_center = (float(xyxy[1]) + float(xyxy[3])) / 2.0
            in_after_line = y_center <= line_y_px if side == 'top' else y_center >= line_y_px
            if in_after_line:
                filtered.append(d)
        except Exception:
            continue

    return filtered


def _draw_trigger_overlay(frame_bgr, dets: list | None = None) -> None:
    """Draw horizontal trigger line and status label on the annotated frame."""
    if not getattr(args, 'line_trigger_enabled', False):
        return
    if frame_bgr is None or not hasattr(frame_bgr, 'shape'):
        return

    h, w = frame_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return

    trigger_line_y = float(getattr(args, 'trigger_line_y', 0.55))
    trigger_line_y = max(0.0, min(1.0, trigger_line_y))
    y = int(trigger_line_y * h)

    active = False
    if dets is not None:
        try:
            active = bool(_filter_trigger_detections(dets, w, h))
        except Exception:
            active = False

    # Green when clear, red when trigger zone occupied.
    color = (0, 0, 255) if active else (0, 255, 0)
    cv2.line(frame_bgr, (0, y), (w - 1, y), color, 2)

    side = getattr(args, 'after_line_side', 'top')
    label = f"TRIGGER LINE y={trigger_line_y:.2f} side={side} {'ACTIVE' if active else 'CLEAR'}"
    label_y = y - 8 if y > 24 else y + 20
    cv2.putText(
        frame_bgr,
        label,
        (10, label_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )


class SharedCamera:
    """Singleton camera instance shared across all video tracks."""
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self, source):
        self.source = source
        # Open camera with DirectShow on Windows, V4L2 on Linux for better USB camera support
        if isinstance(source, int):
            backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_V4L2
            self.cap = cv2.VideoCapture(source, backend)
        else:
            self.cap = cv2.VideoCapture(source)
        
        if not self.cap.isOpened():
            logger.error(f"Failed to open camera/video source: {source}")
            raise RuntimeError(f"Cannot open camera: {source}")
        
        # Capture resolution is independent from inference imgsz.
        # Keep this low on Raspberry Pi to reduce end-to-end pipeline load.
        desired_width = int(getattr(args, 'capture_width', 640))
        desired_height = int(getattr(args, 'capture_height', 480))
        self.desired_width = max(1, desired_width)
        self.desired_height = max(1, desired_height)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, desired_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, desired_height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Get actual camera properties
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0

        # Some USB cameras ignore requested CAP_PROP resolution.
        # If that happens, force a software resize on every frame read.
        self.force_resize = (
            actual_width != self.desired_width or actual_height != self.desired_height
        )
        self.width = self.desired_width if self.force_resize else actual_width
        self.height = self.desired_height if self.force_resize else actual_height
        if self.force_resize:
            logger.warning(
                "Camera returned %sx%s instead of requested %sx%s; applying software resize fallback",
                actual_width,
                actual_height,
                self.desired_width,
                self.desired_height,
            )
        
        logger.info(f"✅ Shared camera opened: {self.width}x{self.height} @ {self.fps}fps")
        self.ref_count = 0
    
    @classmethod
    async def get_instance(cls, source):
        """Get or create the singleton camera instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = SharedCamera(source)
            cls._instance.ref_count += 1
            logger.info(f"Camera reference count: {cls._instance.ref_count}")
            return cls._instance
    
    @classmethod
    async def release_instance(cls):
        """Decrease reference count and release if no more users."""
        async with cls._lock:
            if cls._instance:
                cls._instance.ref_count -= 1
                logger.info(f"Camera reference count: {cls._instance.ref_count}")
                if cls._instance.ref_count <= 0:
                    cls._instance.cap.release()
                    logger.info("📹 Shared camera released")
                    cls._instance = None
    
    def read(self):
        """Thread-safe camera read."""
        ret, frame = self.cap.read()
        if not ret:
            return ret, frame
        if self.force_resize and frame is not None:
            frame = cv2.resize(
                frame,
                (self.desired_width, self.desired_height),
                interpolation=cv2.INTER_AREA,
            )
        return ret, frame


class YOLOVideoTrack(VideoStreamTrack):
    """Video track that captures from shared camera and applies YOLO inference."""
    
    def __init__(self, camera, flip_mode, model_instance, conf_threshold, event_queue=None, imgsz=320):
        super().__init__()
        self.camera = camera
        self.flip_mode = flip_mode
        self.model = model_instance
        self.conf = conf_threshold
        self.event_queue = event_queue
        self.imgsz = imgsz
        
        self.width = camera.width
        self.height = camera.height
        self.fps = camera.fps
        self.measured_fps = camera.fps
        
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps_counter = 0
        
        logger.info(f"🎬 Video track created for client")
    
    def stop(self):
        """Release camera reference when track stops."""
        super().stop()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(SharedCamera.release_instance())
        except RuntimeError:
            # No running loop; release synchronously as best effort.
            asyncio.run(SharedCamera.release_instance())
        
    async def recv(self):
        """Receive the next frame (with YOLO inference applied)."""
        try:
            pts, time_base = await self.next_timestamp()
            
            # Run blocking I/O in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            ret, frame = await loop.run_in_executor(None, self.camera.read)
            
            if not ret:
                logger.warning("Failed to read frame from camera")
                # Return black frame on failure
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            
            # Apply flip if requested
            if self.flip_mode != 'none':
                if self.flip_mode == 'vertical':
                    frame = cv2.flip(frame, 0)
                elif self.flip_mode == 'horizontal':
                    frame = cv2.flip(frame, 1)
                elif self.flip_mode == '180':
                    frame = cv2.flip(frame, -1)
            
            # Run YOLO inference
            t0 = time.time()
            results = _run_model_inference(frame, conf_threshold=self.conf, imgsz=self.imgsz)
            annotated = results[0].plot()
            inference_time = time.time() - t0

            # Update latest annotated frame for instant preview (non-blocking)
            try:
                ret, buf = cv2.imencode('.jpg', annotated)
                if ret:
                    async with latest_frame_lock:
                        globals()['latest_frame_jpeg'] = buf.tobytes()
            except Exception:
                pass

            # Build detection list
            dets = []
            for b in results[0].boxes:
                try:
                    xyxy = _normalize_xyxy(b.xyxy.tolist() if hasattr(b, 'xyxy') else None)
                    dets.append({
                        'cls': int(b.cls),
                        'name': self.model.names[int(b.cls)] if hasattr(self.model, 'names') else str(int(b.cls)),
                        'conf': float(b.conf),
                        'xyxy': xyxy,
                    })
                except Exception:
                    continue

            _draw_trigger_overlay(annotated, dets)

            # Emit detection updates only on state transitions (no spam per frame).
            await _enqueue_detection_state_if_changed(
                dets=dets,
                width=self.width,
                height=self.height,
                frame_id=self.frame_count,
                queue=self.event_queue,
            )
            
            # Add FPS overlay
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                fps = self.fps_counter / (current_time - self.last_fps_time)
                self.last_fps_time = current_time
                self.fps_counter = 0
                self.measured_fps = fps
                logger.info(f"Streaming at {fps:.1f} FPS, inference: {inference_time*1000:.0f}ms")
            else:
                fps = self.measured_fps
            
            cv2.putText(
                annotated,
                f"FPS: {fps:.1f} | Inference: {inference_time*1000:.0f}ms",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            # Convert BGR to RGB for WebRTC
            frame_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            
            # Create VideoFrame
            new_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
            new_frame.pts = pts
            new_frame.time_base = time_base
            
            self.frame_count += 1
            
            if self.frame_count == 1:
                logger.info(f"First frame sent: {self.width}x{self.height}")
            
            return new_frame
        except Exception as e:
            logger.error(f"Error in recv(): {e}", exc_info=True)
            raise


# Track active peer connections
pcs = set()

async def index(request):
    """Serve the HTML client."""
    content = Path(__file__).parent / "webrtc_client.html"
    if not content.exists():
        return web.Response(text="webrtc_client.html not found", status=404)
    return web.FileResponse(content)


async def offer(request):
    """Handle WebRTC offer from client."""
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    ice_servers = _build_ice_servers_for_aiortc()
    configuration = RTCConfiguration(iceServers=ice_servers)
    pc = RTCPeerConnection(configuration=configuration)
    pcs.add(pc)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
    
    # Get shared camera instance
    try:
        camera = await SharedCamera.get_instance(args.source)
    except RuntimeError as e:
        logger.error(f"Failed to get camera: {e}")
        return web.Response(status=503, text="Camera unavailable")
    
    # Create video track with shared camera
    video_track = YOLOVideoTrack(
        camera=camera,
        flip_mode=args.flip,
        model_instance=model,
        conf_threshold=args.conf,
        event_queue=event_queue,
        imgsz=args.imgsz
    )
    
    pc.addTrack(video_track)
    
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    )


async def on_shutdown(app):
    """Close all peer connections on shutdown."""
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

    # Set last-known batch to idle when machine/server goes offline
    try:
        machine_id = getattr(args, 'machine_id', None)
        server_url = getattr(args, 'server_url', 'http://localhost:4000')
        batch_num = _get_last_batch_number(machine_id)
        if machine_id and batch_num:
            patch_data = {"status": "idle"}
            headers = {"x-machine-id": machine_id}
            async with ClientSession() as session:
                logger.info(f"[Shutdown] Patching last batch {batch_num} to 'idle' ...")
                for patch_url in _url_variants(server_url, f"batches/{batch_num}"):
                    async with session.patch(patch_url, json=patch_data, headers=headers, timeout=10) as patch_resp:
                        logger.info(f"[Shutdown] PATCH {patch_url} status: {patch_resp.status}")
                        if patch_resp.status < 400:
                            break
                        text = await patch_resp.text()
                        logger.warning(f"[Shutdown] Failed PATCH {patch_url}: {text}")
        else:
            logger.info("[Shutdown] No cached batch to set idle on shutdown.")
    except Exception as e:
        logger.error(f"[Shutdown] Failed to set cached batch to idle on shutdown: {e}", exc_info=True)


def main():
    global args, model, model_is_onnx, model_is_ncnn

    # MQTT client (optional)
    mqtt_client = None

    async def announce_task(app):
        """Announce machine_id and public URL to central node server periodically, and update status to online."""
        announce_server = getattr(args, 'announce_server', None)
        interval = getattr(args, 'announce_interval', 60)
        machine_id = getattr(args, 'machine_id', None)
        public_url = getattr(args, 'public_url', None)
        
        # Status update configuration
        api_base_url = getattr(args, 'api_base_url', None)
        machine_secret = getattr(args, 'machine_secret', None)
        status_update_interval = getattr(args, 'status_update_interval', 60)
        
        # Track if we've sent initial status
        status_sent = False

        async with ClientSession() as session:
            while True:
                try:
                    # Try to auto-detect ngrok public URL if none provided
                    if not public_url:
                        try:
                            r = await session.get('http://127.0.0.1:4040/api/tunnels', timeout=2)
                            if r.status == 200:
                                j = await r.json()
                                for t in j.get('tunnels', []):
                                    if t.get('public_url', '').startswith('https'):
                                        public_url = t['public_url']
                                        break
                        except Exception:
                            pass

                    if announce_server and machine_id and public_url:
                        payload = {
                            'machine_id': machine_id,
                            'video_url': public_url,
                            'timestamp': time.time()
                        }
                        try:
                            await session.post(announce_server, json=payload, timeout=5)
                            logger.info(f"Announced to server: {announce_server}")
                        except Exception as e:
                            logger.warning(f"Failed to announce: {e}")
                    
                    # Send status update to NutriCycle API
                    if api_base_url and machine_id and machine_secret:
                        status_endpoint = f"{api_base_url}/api/machines/{machine_id}/device/status"
                        status_payload = {
                            'secret': machine_secret,
                            'status': 'online',
                            'meta': {
                                'video_url': public_url,
                                'timestamp': time.time()
                            }
                        }
                        try:
                            await session.post(status_endpoint, json=status_payload, timeout=5)
                            if not status_sent:
                                logger.info(f"✅ Machine status updated to 'online': {status_endpoint}")
                                status_sent = True
                            else:
                                logger.debug(f"Machine status heartbeat sent")
                        except Exception as e:
                            logger.warning(f"Failed to update machine status: {e}")
                    elif machine_id and not (api_base_url and machine_secret) and not status_sent:
                        logger.warning(f"⚠️  No API configuration for status updates. Set API_BASE_URL and MACHINE_SECRET to enable status updates.")
                        status_sent = True  # Only warn once
                        
                except Exception as e:
                    logger.error(f"Error in announce_task: {e}")
                await asyncio.sleep(interval)

    async def event_broadcaster(app):
        """Consume detection events and publish via MQTT (if configured) and optionally log."""
        nonlocal mqtt_client
        mqtt_broker = getattr(args, 'mqtt_broker', None)
        mqtt_topic = getattr(args, 'mqtt_topic', 'nutricycle/detections')
        mqtt_esp_topic = getattr(args, 'mqtt_esp_topic', 'nutricycle/esp32')
        mqtt_control_topic = getattr(args, 'mqtt_control_topic', 'nutricycle/rpi/control/+')
        mqtt_esp_command_topic = getattr(args, 'mqtt_esp_command_topic', 'nutricycle/esp32/{machineId}/command')
        mqtt_port = getattr(args, 'mqtt_port', 1883)
        mqtt_qos = getattr(args, 'mqtt_qos', 1)
        server_url = getattr(args, 'server_url', 'http://localhost:4000')
        machine_id = getattr(args, 'machine_id', None)

        # Get reference to the running event loop so MQTT thread can schedule async tasks
        loop = asyncio.get_event_loop()


        # Resume or create a specific batch by batch_number
        async def resume_or_create_batch(batch_number: str, server_url: str):
            """Resume the batch with the given batch_number if not completed, or create a new one if completed/missing."""
            try:
                async with ClientSession() as session:
                    # Get batch info
                    url = f"{server_url}/batches/{batch_number}"
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            batch = await resp.json()
                            if batch and batch.get('status') != 'completed':
                                # Resume this batch (set to running)
                                patch_url = f"{server_url}/batches/{batch_number}"
                                patch_data = {"status": "running"}
                                async with session.patch(patch_url, json=patch_data, timeout=10) as patch_resp:
                                    if patch_resp.status == 200:
                                        logger.info(f"Resumed batch {batch_number} (set to running)")
                                        return
                    # If batch is completed or does not exist, create new
                    post_url = f"{server_url}/batches"
                    post_data = {"machineId": machine_id}
                    async with session.post(post_url, json=post_data, timeout=10) as post_resp:
                        if post_resp.status == 201:
                            new_batch = await post_resp.json()
                            logger.info(f"Created new batch {new_batch['batchNumber']} (set to running)")
            except Exception as e:
                logger.error(f"Failed to resume or create batch {batch_number}: {e}", exc_info=True)


        async def _post_device_control(action: str, machine_id: str, server_url: str, batch_number: str | None = None) -> dict | None:
            """Tokenless device control endpoint; returns JSON (may contain batchNumber)."""
            if not machine_id:
                return None
            payload = {"action": action}
            if batch_number:
                payload["batchNumber"] = batch_number
            headers = {"x-machine-id": machine_id}
            try:
                async with ClientSession() as session:
                    for endpoint in _url_variants(server_url, "machines/device/control"):
                        async with session.post(endpoint, json=payload, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                return await resp.json()
                            text = await resp.text()
                            logger.warning(f"Device control failed {resp.status} on {endpoint}: {text}")
                    return None
            except Exception as e:
                logger.error(f"Device control error: {e}", exc_info=True)
                return None


        async def _ensure_latest_batch_number(server_url: str, machine_id: str, hint_batch_number: str | None = None) -> str | None:
            """Resolve a batchNumber without calling list endpoints."""
            if hint_batch_number:
                _set_last_batch_number(machine_id, hint_batch_number)
                return hint_batch_number
            cached = _get_last_batch_number(machine_id)
            if cached:
                return cached
            data = await _post_device_control("start", machine_id, server_url)
            batch_number = (data or {}).get("batchNumber")
            if batch_number:
                _set_last_batch_number(machine_id, batch_number)
            return batch_number

        # Patch batch status (always in scope)
        async def patch_batch_status(batch_number: str, status: str, server_url: str):
            payload = {"status": status}
            try:
                async with ClientSession() as session:
                    headers = {"x-machine-id": machine_id} if machine_id else None
                    for endpoint in _url_variants(server_url, f"batches/{batch_number}"):
                        async with session.patch(endpoint, json=payload, headers=headers, timeout=10) as response:
                            logger.info(f"Server PATCH {endpoint} status: {response.status}")
                            if response.status < 400:
                                return
                            text = await response.text()
                            logger.error(f"Server error response: {text}")
            except Exception as e:
                logger.error(f"Failed to patch batch status: {e}", exc_info=True)

        async def start_local_keepalive_now(app_ref, reason: str = 'command'):
            if app_ref.get('camera_keepalive_task'):
                logger.info(f"Keepalive already running ({reason})")
                return

            app_ref['camera_keepalive_task'] = asyncio.create_task(camera_keepalive(app_ref))
            logger.info(f"Started keepalive ({reason})")

        async def stop_local_keepalive_now(app_ref, reason: str = 'command'):
            t = app_ref.get('camera_keepalive_task')
            if t:
                t.cancel()
                try:
                    await t
                except Exception:
                    pass
                app_ref.pop('camera_keepalive_task', None)
                logger.info(f"Stopped keepalive ({reason})")
            await SharedCamera.release_instance()

        # Callback for handling incoming MQTT control commands
        def on_esp32_control(client, userdata, message):
            # No machine_status changes here; only batch_states are updated
            """Handle control and process-stage commands via MQTT."""
            try:
                topic = message.topic
                if topic != mqtt_control_topic and '/rpi/control/' not in topic:
                    logger.debug(f"Ignoring MQTT message from non-control topic: {topic}")
                    return

                payload = json.loads(message.payload.decode())
                command = payload.get('command')
                # Aliases and more specific stage names
                if command == 'completion':
                    command = 'feed_completed'
                logger.info(f"Received ESP32 command via MQTT: {command}")

                if command == 'emergency_stop':
                    async def handle_emergency_stop():
                        try:
                            await stop_local_keepalive_now(app, reason='emergency_stop')

                            target_machine = payload.get('machineId') or machine_id
                            if not target_machine:
                                raise RuntimeError('Missing machineId for emergency stop forward')
                            esp_topic = mqtt_esp_command_topic.replace('{machineId}', target_machine)
                            forward_payload = {
                                'machine_id': target_machine,
                                'command': 'emergency_stop',
                                'batchNumber': payload.get('batchNumber'),
                                'timestamp': time.time(),
                            }

                            if mqtt_client:
                                mqtt_client.publish(esp_topic, json.dumps(forward_payload), qos=mqtt_qos)

                            batch_number = payload.get('batchNumber') or _get_last_batch_number(machine_id)
                            if batch_number:
                                await patch_batch_status(batch_number, 'idle', server_url)
                        except Exception as inner_error:
                            logger.error(f"Emergency stop handling failed: {inner_error}", exc_info=True)

                    asyncio.run_coroutine_threadsafe(handle_emergency_stop(), loop)
                    return

                # --- PATCH telemetry/feed fields (including estimatedWeight) to last-known batch if present ---
                if any(k in payload for k in ('humidity', 'temperature', 'feedOutput', 'compostOutput', 'feedStatus', 'estimatedWeight')):
                    async def patch_latest_batch():
                        try:
                            # Same behavior as sorting/dehydration: if ESP32 doesn't send batchNumber,
                            # use the latest cached batchNumber; if none exists yet, create one via start.
                            batch_num = await _ensure_latest_batch_number(
                                server_url,
                                machine_id,
                                hint_batch_number=payload.get('batchNumber')
                            )
                            if not batch_num:
                                logger.warning("No batchNumber available for sensor patch; skipping.")
                                return
                            async with ClientSession() as session:
                                headers = {"x-machine-id": machine_id} if machine_id else None
                                patch_data = {}
                                if 'humidity' in payload:
                                    patch_data["humidity"] = payload["humidity"]
                                if 'temperature' in payload:
                                    patch_data["temperature"] = payload["temperature"]
                                if 'feedOutput' in payload:
                                    patch_data["feedOutput"] = payload["feedOutput"]
                                if 'compostOutput' in payload:
                                    patch_data["compostOutput"] = payload["compostOutput"]
                                if 'feedStatus' in payload:
                                    patch_data["feedStatus"] = payload["feedStatus"]
                                if 'estimatedWeight' in payload:
                                    patch_data["estimatedWeight"] = payload["estimatedWeight"]
                                if patch_data:
                                    for patch_url in _url_variants(server_url, f"batches/{batch_num}"):
                                        async with session.patch(patch_url, json=patch_data, headers=headers, timeout=10) as patch_resp:
                                            if patch_resp.status == 200:
                                                _set_last_batch_number(machine_id, batch_num)
                                                logger.info(f"Patched batch {batch_num} with {patch_data}")
                                                return
                                            text = await patch_resp.text()
                                            logger.warning(f"Failed to patch batch {batch_num} on {patch_url}: {patch_resp.status} {text}")
                        except Exception as e:
                            logger.error(f"Failed to patch latest batch: {e}", exc_info=True)
                    asyncio.run_coroutine_threadsafe(patch_latest_batch(), loop)

                # --- CONTINUE UNFINISHED ACTIVITY LOGIC ---
                batch_number = payload.get('batchNumber')
                if not hasattr(on_esp32_control, 'batch_states'):
                    on_esp32_control.batch_states = {}
                batch_states = on_esp32_control.batch_states

                if command == 'start':
                    async def handle_start():
                        await start_local_keepalive_now(app, reason='start_command')

                        # Prefer tokenless device control endpoint to create/resume and return batchNumber.
                        data = await _post_device_control('start', machine_id, server_url)
                        server_batch = (data or {}).get('batchNumber')
                        final_batch = server_batch or batch_number
                        if final_batch:
                            _set_last_batch_number(machine_id, final_batch)
                            logger.info(f"Start resolved batchNumber={final_batch}")

                            # If start payload includes estimatedWeight, patch it immediately to the resolved batch.
                            if 'estimatedWeight' in payload:
                                await patch_batch_fields(
                                    final_batch,
                                    {"estimatedWeight": payload["estimatedWeight"]},
                                    server_url,
                                    machine_id,
                                )
                        else:
                            logger.warning("Start sent but no batchNumber available")
                    asyncio.run_coroutine_threadsafe(handle_start(), loop)
                elif command == 'stop' and batch_number:
                    asyncio.run_coroutine_threadsafe(
                        stop_local_keepalive_now(app, reason='stop_command'),
                        loop,
                    )

                    # Mark batch as idle (not finished, can be resumed)
                    if batch_number in batch_states:
                        batch_states[batch_number]['status'] = 'idle'
                        batch_states[batch_number]['in_progress'] = False
                        batch_states[batch_number]['finished'] = False
                        # Do not mark as finished, so it can be resumed
                elif command == 'stop':
                    asyncio.run_coroutine_threadsafe(
                        stop_local_keepalive_now(app, reason='stop_command'),
                        loop,
                    )
                elif command in ('feed_completed', 'reset') and batch_number:
                    asyncio.run_coroutine_threadsafe(
                        stop_local_keepalive_now(app, reason='batch_completed'),
                        loop,
                    )

                    # Mark as finished
                    machine_status = 'finished'
                    if batch_number in batch_states:
                        batch_states[batch_number]['finished'] = True
                        batch_states[batch_number]['in_progress'] = False
                        batch_states[batch_number]['status'] = 'finished'
                elif command in ('feed_completed', 'reset'):
                    asyncio.run_coroutine_threadsafe(
                        stop_local_keepalive_now(app, reason='batch_completed'),
                        loop,
                    )

                # --- ORIGINAL LOGIC ---
                if command in ('start', 'stop', 'sorting', 'sorting_compost', 'sorting_animal_feed', 'grinding', 'dehydration', 'feed_completed'):
                    # batch_number already set above
                    if command in ('sorting', 'sorting_compost', 'sorting_animal_feed'):
                        async def handle_sorting():
                            # Ensure we have a batchNumber (cached latest or create/resume on demand)
                            resolved = await _ensure_latest_batch_number(server_url, machine_id, hint_batch_number=batch_number)
                            if not resolved:
                                logger.error("Sorting received but cannot resolve batchNumber")
                                return
                            logger.info(f"{command} received; using latest batch {resolved}. Posting to server now.")
                            await post_stage_update(command, resolved, server_url, machine_id)
                        asyncio.run_coroutine_threadsafe(handle_sorting(), loop)
                    elif command in ('grinding', 'dehydration', 'feed_completed'):
                        async def handle_stage_patch():
                            resolved = await _ensure_latest_batch_number(server_url, machine_id, hint_batch_number=batch_number)
                            if not resolved:
                                logger.error(f"{command} received but cannot resolve batchNumber")
                                return
                            logger.info(f"{command} received; using latest batch {resolved}. Posting to server now.")
                            await post_stage_update(command, resolved, server_url, machine_id)

                        asyncio.run_coroutine_threadsafe(handle_stage_patch(), loop)
                    elif command == 'start':
                        # Already handled above
                        pass
                    elif command == 'stop':
                        # For 'stop', set batch status to idle
                        if batch_number:
                            logger.info(f"Stop command received for batch {batch_number}. Setting status to 'idle' via PATCH.")
                            asyncio.run_coroutine_threadsafe(
                                patch_batch_status(batch_number, 'idle', server_url), loop
                            )
                        else:
                            logger.info("No batchNumber provided in ESP32 message for stop. Will stop cached latest batch.")
                            async def stop_cached_batch():
                                cached = _get_last_batch_number(machine_id)
                                if not cached:
                                    logger.warning("No cached batch to stop.")
                                    return
                                await patch_batch_status(cached, 'idle', server_url)
                            asyncio.run_coroutine_threadsafe(stop_cached_batch(), loop)
                else:
                    logger.warning(f"Unknown command from ESP32: {command}")
            except Exception as e:
                logger.error(f"Error processing ESP32 control message: {e}", exc_info=True)

        async def post_stage_update(stage: str, batch_number: str, server_url: str, machine_id: str):
            """Best-effort stage update.

            Backends we saw:
            - /machines/device/control only supports start/stop (so don't send stage there)
            - /batches/{batch}/process may not exist
            So we patch the batch directly with feedStatus using x-machine-id header.
            """
            await patch_batch_feed_status(server_url, batch_number, stage, machine_id)


        async def patch_batch_fields(batch_number: str, fields: dict, server_url: str, machine_id: str | None):
            """Patch arbitrary batch fields via /batches/{batchNumber}."""
            if not fields:
                return
            headers = {"x-machine-id": machine_id} if machine_id else None
            async with ClientSession() as session:
                for patch_url in _url_variants(server_url, f"batches/{batch_number}"):
                    async with session.patch(patch_url, json=fields, headers=headers, timeout=10) as resp:
                        logger.info(f"Field PATCH {patch_url} status: {resp.status}")
                        if resp.status < 400:
                            return
                        text = await resp.text()
                        logger.error(f"Field PATCH error response: {text}")


        async def patch_batch_feed_status(server_url: str, batch_number: str, stage: str, machine_id: str | None):
            headers = {"x-machine-id": machine_id} if machine_id else None
            payload = {"feedStatus": stage}
            async with ClientSession() as session:
                for patch_url in _url_variants(server_url, f"batches/{batch_number}"):
                    async with session.patch(patch_url, json=payload, headers=headers, timeout=10) as resp:
                        logger.info(f"Stage PATCH {patch_url} status: {resp.status}")
                        if resp.status < 400:
                            return
                        text = await resp.text()
                        logger.error(f"Stage PATCH error response: {text}")
                # If both variants failed, keep the old /process attempt as a last resort for older servers.
                await post_stage_to_server('POST' if stage == 'sorting' else 'PATCH', stage, batch_number, server_url)

        async def post_stage_to_server(method: str, stage: str, batch_number: str, server_url: str):
            """
            POST: Create a new BatchProcess for the batch (used for 'sorting' stage)
            PATCH: Update the existing BatchProcess for the batch (used for 'grinding', 'dehydration', 'feed_completed')
            """
            endpoint = f"{server_url}/batches/{batch_number}/process"
            payload = {"feedStatus": stage}
            try:
                async with ClientSession() as session:
                    if method == 'POST':
                        async with session.post(endpoint, json=payload, timeout=10) as response:
                            logger.info(f"Server POST {endpoint} status: {response.status}")
                            if response.status >= 400:
                                text = await response.text()
                                logger.error(f"Server error response: {text}")
                    elif method == 'PATCH':
                        async with session.patch(endpoint, json=payload, timeout=10) as response:
                            logger.info(f"Server PATCH {endpoint} status: {response.status}")
                            if response.status >= 400:
                                text = await response.text()
                                logger.error(f"Server error response: {text}")
            except Exception as e:
                logger.error(f"Failed to post stage to server: {e}", exc_info=True)


        if mqtt_broker:
            try:
                import paho.mqtt.client as paho
                callback_api = getattr(getattr(paho, 'CallbackAPIVersion', None), 'VERSION2', None)
                if callback_api is not None:
                    mqtt_client = paho.Client(callback_api_version=callback_api)
                else:
                    mqtt_client = paho.Client()
                if getattr(args, 'mqtt_username', None):
                    mqtt_client.username_pw_set(getattr(args, 'mqtt_username'), getattr(args, 'mqtt_password', None))

                # Set callback for incoming control messages
                mqtt_client.on_message = on_esp32_control

                mqtt_client.connect(mqtt_broker, port=mqtt_port)

                # Subscribe to ESP32 control topic
                mqtt_client.subscribe(mqtt_control_topic, qos=mqtt_qos)
                logger.info(f"Subscribed to MQTT topic: {mqtt_control_topic}")

                mqtt_client.loop_start()
                app['mqtt_client'] = mqtt_client  # store on app for control handler
                logger.info(f"Connected to MQTT broker: {mqtt_broker}")
            except Exception as e:
                logger.error(f"Failed to connect MQTT: {e}")
                mqtt_client = None

        while True:
            evt = await event_queue.get()
            msg = json.dumps(evt)
            # Publish to MQTT
            if mqtt_client:
                try:
                    mqtt_client.publish(mqtt_topic, msg, qos=mqtt_qos)
                    # Publish compact state to ESP32: 1 when detected, 0 when clear.
                    mqtt_client.publish(
                        mqtt_esp_topic,
                        json.dumps({
                            'machine_id': evt.get('machine_id'),
                            'alert': 1 if evt.get('has_detection') else 0,
                        }),
                        qos=1,
                    )
                except Exception as e:
                    logger.warning(f"MQTT publish failed: {e}")
            # Log one line per transition only.
            logger.info(
                f"Detection state: {'1 (detected)' if evt.get('has_detection') else '0 (clear)'} "
                f"machine={evt.get('machine_id')} line_mode={evt.get('line_trigger_enabled')}"
            )

    # will register these tasks later on app startup


    async def camera_keepalive(app):
        """Continuously read camera frames and run YOLO inference even with no clients.
        This keeps the SharedCamera instance alive and publishes detection events to the
        existing event_queue so other systems (MQTT, logs) keep receiving detections.
        """
        try:
            camera = await SharedCamera.get_instance(args.source)
        except RuntimeError as e:
            logger.error(f"Keepalive failed to open camera: {e}")
            return

        logger.info("🔁 Camera keepalive started (persistent mode)")
        try:
            # run at a lower FPS than live streaming to reduce CPU; configurable via --keepalive-fps
            interval = 1.0 / max(1, getattr(args, 'keepalive_fps', 2))
            while True:
                loop = asyncio.get_event_loop()
                ret, frame = await loop.run_in_executor(None, camera.read)
                if not ret:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    t0 = time.time()
                    results = _run_model_inference(frame, conf_threshold=args.conf, imgsz=args.imgsz)
                    inference_time = time.time() - t0

                    annotated = results[0].plot()

                    # Update latest annotated frame for instant preview
                    try:
                        ret, buf = cv2.imencode('.jpg', annotated)
                        if ret:
                            async with latest_frame_lock:
                                globals()['latest_frame_jpeg'] = buf.tobytes()
                    except Exception:
                        pass

                    dets = []
                    for b in results[0].boxes:
                        try:
                            xyxy = _normalize_xyxy(b.xyxy.tolist() if hasattr(b, 'xyxy') else None)
                            dets.append({
                                'cls': int(b.cls),
                                'name': model.names[int(b.cls)] if hasattr(model, 'names') else str(int(b.cls)),
                                'conf': float(b.conf),
                                'xyxy': xyxy,
                            })
                        except Exception:
                            continue

                    _draw_trigger_overlay(annotated, dets)

                    await _enqueue_detection_state_if_changed(
                        dets=dets,
                        width=camera.width,
                        height=camera.height,
                        frame_id=None,
                        queue=event_queue,
                    )

                    # throttle keepalive loop to configured FPS
                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Keepalive inference error: {e}")
                    await asyncio.sleep(1.0)
        finally:
            # Ensure the camera reference is released when the keepalive task stops
            try:
                await SharedCamera.release_instance()
            except Exception:
                pass
            logger.info("🔁 Camera keepalive stopped")


    async def post_control_to_server(command: str, machine_id: str, server_url: str):
        """POST start/stop command to server to trigger batch creation/completion."""
        if not machine_id:
            logger.warning("Cannot post to server: machine_id not configured")
            return

        endpoint = f"{server_url}/machines/device/control"
        payload = {"action": command}
        headers = {"x-machine-id": machine_id}

        try:
            async with ClientSession() as session:
                async with session.post(endpoint, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        batch_number = data.get('batchNumber')
                        if batch_number:
                            _set_last_batch_number(machine_id, batch_number)
                            logger.info(f"Batch {batch_number} created on server for machine {machine_id}")
                            return batch_number
                        logger.info(f"{command.capitalize()} command sent to server successfully")
                        return None
                    text = await response.text()
                    logger.error(f"Server returned error {response.status}: {text}")
                    return None
        except Exception as e:
            logger.error(f"Failed to post {command} to server: {e}", exc_info=True)
            return None


    bootstrap_parser = argparse.ArgumentParser(add_help=False)
    bootstrap_parser.add_argument(
        "--env-file",
        default=str(Path(__file__).with_name(".env")),
        help="Path to .env file for defaults (default: deploy/.env)",
    )
    bootstrap_args, remaining_argv = bootstrap_parser.parse_known_args()

    env_file_path = Path(bootstrap_args.env_file)
    if not env_file_path.is_absolute():
        env_file_path = (Path.cwd() / env_file_path).resolve()

    if _load_env_file_into_environ(env_file_path):
        logger.info(f"Loaded env defaults from: {env_file_path}")
    else:
        logger.info(f"Env file not found at: {env_file_path} (using CLI/default values)")

    parser = argparse.ArgumentParser(description="WebRTC YOLO streaming server", parents=[bootstrap_parser])
    parser.add_argument("--model", default=os.environ.get("MODEL_PATH", "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt"),
                        help="Path to YOLO model (.pt, .onnx, or NCNN export directory)")
    parser.add_argument("--source", default=os.environ.get("VIDEO_SOURCE", "0"), help="Camera index or video file path")
    parser.add_argument("--conf", type=float, default=_env_float("CONFIDENCE", 0.5), help="Confidence threshold")
    parser.add_argument("--flip", choices=['none', 'vertical', 'horizontal', '180'], default=os.environ.get("FLIP_MODE", "none"),
                        help="Flip video: vertical=upside-down, horizontal, 180=rotate 180")
    parser.add_argument("--imgsz", type=int, default=_env_int("INFERENCE_IMGSZ", 320), help="Inference image size (pixels)")
    parser.add_argument("--capture-width", type=int, default=_env_int("CAPTURE_WIDTH", 640), help="Camera capture width (stream clarity)")
    parser.add_argument("--capture-height", type=int, default=_env_int("CAPTURE_HEIGHT", 480), help="Camera capture height (stream clarity)")
    parser.add_argument("--host", default=os.environ.get("WEBRTC_HOST", "0.0.0.0"), help="Server host")
    parser.add_argument("--port", type=int, default=_env_int("WEBRTC_PORT", 8080), help="Server port")
    parser.add_argument("--announce-server", default=os.environ.get("ANNOUNCE_SERVER", None), help="HTTP endpoint to POST machine_id + video URL")
    parser.add_argument("--machine-id", default=os.environ.get("MACHINE_ID", None), help="Unique Machine ID for this device")
    parser.add_argument("--announce-interval", type=int, default=_env_int("ANNOUNCE_INTERVAL", 60), help="Seconds between announce attempts")
    parser.add_argument("--public-url", default=os.environ.get("PUBLIC_URL", None), help="Public video URL if ngrok is used externally")
    parser.add_argument("--api-base-url", default=os.environ.get("API_BASE_URL", None), help="NutriCycle API base URL (e.g. https://api.example.com) for status updates")
    parser.add_argument("--machine-secret", default=os.environ.get("MACHINE_SECRET", None), help="Machine secret for authentication with NutriCycle API")
    parser.add_argument("--status-update-interval", type=int, default=_env_int("STATUS_UPDATE_INTERVAL", 60), help="Seconds between machine status updates to API")
    parser.add_argument("--persistent", action="store_true", default=_env_bool("PERSISTENT", False), help="Keep camera + inference running even when no clients are connected")
    parser.add_argument("--keepalive-fps", type=int, default=_env_int("KEEPALIVE_FPS", 2), help="FPS to run background inference when persistent (default: 2)")
    parser.add_argument("--line-trigger-enabled", action="store_true",
                        default=_env_bool("LINE_TRIGGER_ENABLED", False),
                        help="Enable horizontal trigger line mode for ESP32 ON/OFF signaling")
    parser.add_argument("--trigger-line-y", type=float, default=_env_float("TRIGGER_LINE_Y", 0.55),
                        help="Horizontal trigger line Y position as normalized value (0.0 top to 1.0 bottom)")
    parser.add_argument("--after-line-side", choices=['top', 'bottom'], default=os.environ.get("AFTER_LINE_SIDE", 'top'),
                        help="Which side of the trigger line is considered active zone")
    parser.add_argument("--trigger-stable-frames", type=int, default=_env_int("TRIGGER_STABLE_FRAMES", 3),
                        help="Consecutive frames required before trigger state changes")
    parser.add_argument("--trigger-min-conf", type=float, default=_env_optional_float("TRIGGER_MIN_CONF"),
                        help="Min confidence for line trigger checks (defaults to --conf)")
    parser.add_argument("--trigger-class", type=int, default=_env_optional_int("TRIGGER_CLASS"),
                        help="Optional class id filter for trigger checks")
    
    # MQTT options
    parser.add_argument("--mqtt-broker", default=os.environ.get("MQTT_BROKER", None), help="MQTT broker host (optional)")
    parser.add_argument("--mqtt-port", type=int, default=_env_int("MQTT_PORT", 1883), help="MQTT broker port")
    parser.add_argument("--mqtt-topic", default=os.environ.get("MQTT_TOPIC", "nutricycle/detections"), help="MQTT topic for detection events")
    parser.add_argument("--mqtt-esp-topic", default=os.environ.get("MQTT_ESP_TOPIC", "nutricycle/esp32"), help="MQTT topic to send compact alerts to ESP32")
    parser.add_argument("--mqtt-control-topic", default=os.environ.get("MQTT_CONTROL_TOPIC", "nutricycle/rpi/control/+"), help="MQTT topic to receive control commands for this Raspberry Pi")
    parser.add_argument("--mqtt-esp-command-topic", default=os.environ.get("MQTT_ESP_COMMAND_TOPIC", "nutricycle/esp32/{machineId}/command"), help="MQTT topic template for forwarding machine commands to ESP32")
    parser.add_argument("--mqtt-username", default=os.environ.get("MQTT_USERNAME", None), help="MQTT username")
    parser.add_argument("--mqtt-password", default=os.environ.get("MQTT_PASSWORD", None), help="MQTT password")
    parser.add_argument("--mqtt-qos", type=int, default=_env_int("MQTT_QOS", 1), help="MQTT QoS")
    parser.add_argument("--control-token", default=os.environ.get("CONTROL_TOKEN", None), help="Bearer token required for /control HTTP POSTs")
    parser.add_argument("--server-url", default=os.environ.get("SERVER_URL", "http://localhost:4000"), help="URL of NutriCycle server for batch creation")
    parser.add_argument(
        "--ice-stun-urls",
        default=os.environ.get(
            "ICE_STUN_URLS",
            "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302,stun:stun2.l.google.com:19302,stun:stun.relay.metered.ca:80",
        ),
        help="Comma-separated STUN URLs for ICE",
    )
    parser.add_argument("--ice-turn-url", default=os.environ.get("ICE_TURN_URL", None), help="TURN URL for ICE relay")
    parser.add_argument("--ice-turn-username", default=os.environ.get("ICE_TURN_USERNAME", None), help="TURN username")
    parser.add_argument("--ice-turn-password", default=os.environ.get("ICE_TURN_PASSWORD", None), help="TURN password")
    parser.add_argument("--ice-force-relay", action="store_true", default=_env_bool("ICE_FORCE_RELAY", False), help="Force relay-only ICE candidates (requires TURN)")

    args = parser.parse_args(remaining_argv)

    # Clamp line position so bad values don't break trigger logic.
    args.trigger_line_y = max(0.0, min(1.0, float(args.trigger_line_y)))
    args.ice_stun_urls = _parse_csv(args.ice_stun_urls)

    if not args.ice_stun_urls:
        args.ice_stun_urls = ["stun:stun.l.google.com:19302"]

    if args.ice_turn_url and not (args.ice_turn_username and args.ice_turn_password):
        logger.warning("ICE_TURN_URL provided without ICE_TURN_USERNAME/ICE_TURN_PASSWORD; TURN will be ignored")

    logger.info(f"ICE STUN servers: {args.ice_stun_urls}")
    if args.ice_turn_url and args.ice_turn_username and args.ice_turn_password:
        logger.info(f"ICE TURN server enabled: {args.ice_turn_url}")
    logger.info(f"ICE transport policy: {'relay' if args.ice_force_relay else 'all'}")
    
    # Parse source
    args.source = int(args.source) if args.source.isdigit() else args.source
    
    # Resolve model path
    model_path = args.model
    if not os.path.exists(model_path):
        alt = os.path.join("AI-Model", model_path) if not model_path.startswith("AI-Model") else None
        if alt and os.path.exists(alt):
            logger.info(f"Using model: {alt}")
            model_path = alt
        else:
            logger.error(f"Model '{args.model}' not found")
            sys.exit(1)
    
    # Handle ONNX runtime check
    if model_path.lower().endswith('.onnx'):
        try:
            import onnxruntime  # noqa: F401
        except Exception:
            pt_candidate = model_path[:-5] + '.pt'
            if os.path.exists(pt_candidate):
                logger.warning(f"onnxruntime not found; switching to '{pt_candidate}'")
                model_path = pt_candidate
            else:
                logger.error("onnxruntime not installed and no .pt fallback found")
                sys.exit(1)
    
    model_is_ncnn = _is_ncnn_export_path(model_path)
    logger.info(f"Loading model: {model_path}")
    if model_is_ncnn:
        model = YOLO(model_path, task='detect')
    else:
        model = YOLO(model_path)
    model_is_onnx = model_path.lower().endswith('.onnx')
    logger.info(f"Model loaded. Classes: {model.names}")
    if model_is_onnx:
        logger.info("ONNX model detected: ignoring --imgsz at runtime to avoid fixed-shape mismatch")
    if model_is_ncnn:
        logger.info("NCNN model detected: running detect task with Ultralytics NCNN backend")

    if args.line_trigger_enabled:
        trig_conf = args.trigger_min_conf if args.trigger_min_conf is not None else args.conf
        logger.info(
            f"Line trigger enabled: horizontal_y={args.trigger_line_y:.3f} "
            f"after_side={args.after_line_side} stable_frames={args.trigger_stable_frames} "
            f"min_conf={trig_conf} class_filter={args.trigger_class}"
        )
    else:
        logger.info("Line trigger disabled: state changes use full-frame detections")
    
    # Test camera access before starting server
    logger.info(f"Testing camera access: {args.source}")
    try:
        test_backend = cv2.CAP_V4L2 if os.name != 'nt' else cv2.CAP_DSHOW
        test_cap = cv2.VideoCapture(args.source if isinstance(args.source, int) else args.source, 
                                     test_backend if isinstance(args.source, int) else cv2.CAP_ANY)
        if not test_cap.isOpened():
            logger.error(f"❌ Cannot access camera: {args.source}")
            logger.error("Troubleshooting tips:")
            logger.error("  1. Check camera is connected: ls -la /dev/video*")
            logger.error("  2. Add user to video group: sudo usermod -a -G video $USER")
            logger.error("  3. Install v4l-utils: sudo apt-get install v4l-utils")
            logger.error("  4. Check devices: v4l2-ctl --list-devices")
            logger.error("  5. Try different camera index: --source 1 or --source 2")
            sys.exit(1)
        ret, test_frame = test_cap.read()
        if not ret:
            logger.error(f"❌ Camera opened but cannot read frames: {args.source}")
            sys.exit(1)
        test_cap.release()
        logger.info(f"✅ Camera test successful: {test_frame.shape}")
    except Exception as e:
        logger.error(f"❌ Camera test failed: {e}")
        sys.exit(1)
    
    # Setup web app
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)
    # WebSocket endpoint for registration/debugging (optional)
    async def ws_handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        logger.info('WebSocket client connected')
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    # Echo or possibly send control commands later
                    await ws.send_str(msg.data)
        finally:
            logger.info('WebSocket client disconnected')
        return ws

    app.router.add_get('/ws', ws_handler)

    # Control endpoint: accepts POST from Node server to command machine (start/stop/pause/reset)
    async def control_handler(request):
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")

        # Authorization (optional)
        if getattr(args, 'control_token', None):
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return web.Response(status=401, text='Missing Authorization')
            token = auth.split(None, 1)[1]
            if token != args.control_token:
                return web.Response(status=403, text='Forbidden')

        machine_id = data.get('machine_id') or data.get('machineId')
        if machine_id != args.machine_id:
            return web.Response(status=404, text='Machine ID mismatch')

        cmd = data.get('command')
        if cmd not in ('stop', 'pause', 'reset', 'emergency_stop'):
            return web.Response(status=400, text='Invalid command')

        logger.info(f"HTTP /control received command '{cmd}' for machine {machine_id}")

        # Normalize stop-like commands so local and ESP32 behavior is consistent.
        normalized_cmd = 'emergency_stop' if cmd in ('stop', 'emergency_stop') else cmd

        # Local control actions: execute immediately via HTTP path before forwarding to ESP32.
        try:
            if normalized_cmd == 'emergency_stop':
                t = request.app.get('camera_keepalive_task')
                if t:
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
                    request.app.pop('camera_keepalive_task', None)
                # Ensure camera released
                await SharedCamera.release_instance()
                logger.info(f"Local keepalive stopped and camera released via /control ({normalized_cmd})")

            elif normalized_cmd == 'pause':
                # stop keepalive but keep camera open for quicker resume
                t = request.app.get('camera_keepalive_task')
                if t:
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
                    request.app.pop('camera_keepalive_task', None)
                try:
                    await SharedCamera.get_instance(args.source)
                except RuntimeError as e:
                    return web.Response(status=503, text=f'Failed to open camera: {e}')
                logger.info('Local paused: camera open, inference stopped')

            elif normalized_cmd == 'reset':
                # restart keepalive
                t = request.app.get('camera_keepalive_task')
                if t:
                    t.cancel()
                    try:
                        await t
                    except Exception:
                        pass
                    request.app.pop('camera_keepalive_task', None)
                request.app['camera_keepalive_task'] = asyncio.create_task(camera_keepalive(request.app))
                logger.info('Local keepalive restarted via /control')

        except Exception as e:
            logger.error(f'Error handling control {normalized_cmd}: {e}', exc_info=True)
            return web.Response(status=500, text=f'Control handling failed: {e}')

        # Forward to ESP32 via MQTT after local action has been applied.
        mqtt_client = request.app.get('mqtt_client')
        esp_topic_template = getattr(args, 'mqtt_esp_command_topic', 'nutricycle/esp32/{machineId}/command')
        esp_topic = esp_topic_template.replace('{machineId}', machine_id)
        payload = {
            'machine_id': machine_id,
            'machineId': machine_id,
            'command': normalized_cmd,
            'timestamp': time.time(),
            'source': 'http_control',
        }

        forwarded = False
        dispatch_error = None
        if mqtt_client:
            try:
                mqtt_client.publish(esp_topic, json.dumps(payload), qos=1)
                forwarded = True
                logger.info(f"Forwarded HTTP control '{normalized_cmd}' to ESP32 via MQTT on topic {esp_topic}")
            except Exception as e:
                dispatch_error = str(e)
                logger.warning(f"MQTT publish failed: {e}")
        else:
            dispatch_error = 'MQTT client not connected'
            logger.warning('MQTT client not connected (local stop applied, ESP32 forward unavailable)')

        return web.json_response({
            'success': True,
            'machineId': machine_id,
            'command': normalized_cmd,
            'localApplied': True,
            'esp32Forwarded': forwarded,
            'dispatchError': dispatch_error,
        })

    app.router.add_post('/control', control_handler)

    async def status_handler(request):
        """Return JSON status about camera, keepalive, and connections."""
        camera_running = SharedCamera._instance is not None
        ref_count = SharedCamera._instance.ref_count if SharedCamera._instance else 0
        keepalive_running = bool(request.app.get('camera_keepalive_task'))
        peers = len(pcs)
        return web.json_response({
            'camera_running': camera_running,
            'camera_ref_count': ref_count,
            'keepalive_running': keepalive_running,
            'peer_connections': peers
        })

    app.router.add_get('/status', status_handler)

    async def ice_config_handler(request):
        """Return ICE configuration for browser clients."""
        return web.json_response(
            {
                'iceServers': _build_ice_servers_for_json(),
                'iceTransportPolicy': 'relay' if getattr(args, 'ice_force_relay', False) else 'all',
            }
        )

    app.router.add_get('/ice-config', ice_config_handler)

    async def last_frame_handler(request):
        """Return the latest annotated frame as JPEG for quick previews."""
        async with latest_frame_lock:
            data = globals().get('latest_frame_jpeg')
        if not data:
            return web.Response(status=404, text='No frame available')
        headers = {'Cache-Control': 'no-cache, no-store, must-revalidate'}
        return web.Response(body=data, content_type='image/jpeg', headers=headers)

    app.router.add_get('/last_frame.jpg', last_frame_handler)

    async def mjpeg_handler(request):
        """Serve latest frames as MJPEG over HTTP (fallback when WebRTC fails)."""
        boundary = 'frame'
        resp = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': f'multipart/x-mixed-replace; boundary={boundary}',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Connection': 'keep-alive',
            },
        )
        await resp.prepare(request)

        # Tiny black placeholder while first annotated frame is not available yet.
        placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(placeholder, 'Waiting for frame...', (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        ok, buf = cv2.imencode('.jpg', placeholder)
        placeholder_jpeg = buf.tobytes() if ok else b''

        try:
            while True:
                async with latest_frame_lock:
                    data = globals().get('latest_frame_jpeg')
                if not data:
                    data = placeholder_jpeg

                chunk = (
                    f'--{boundary}\r\n'
                    'Content-Type: image/jpeg\r\n'
                    f'Content-Length: {len(data)}\r\n\r\n'
                ).encode('ascii') + data + b'\r\n'

                await resp.write(chunk)
                await asyncio.sleep(0.25)
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            with contextlib.suppress(Exception):
                await resp.write_eof()

        return resp

    app.router.add_get('/mjpeg', mjpeg_handler)

    async def _start_background_tasks(app):
        app['announce_task'] = asyncio.create_task(announce_task(app))
        app['event_broadcaster_task'] = asyncio.create_task(event_broadcaster(app))
        if getattr(args, 'persistent', False):
            app['camera_keepalive_task'] = asyncio.create_task(camera_keepalive(app))

    async def _cleanup_background_tasks(app):
        # Cancel background tasks
        for name in ('announce_task', 'event_broadcaster_task', 'camera_keepalive_task'):
            t = app.get(name)
            if t:
                t.cancel()
                try:
                    await t
                except Exception:
                    pass
        
        # Send "offline" status to API on shutdown
        api_base_url = getattr(args, 'api_base_url', None)
        machine_secret = getattr(args, 'machine_secret', None)
        machine_id = getattr(args, 'machine_id', None)
        if api_base_url and machine_id and machine_secret:
            try:
                async with ClientSession() as session:
                    status_endpoint = f"{api_base_url}/machines/{machine_id}/device/status"
                    await session.post(status_endpoint, json={
                        'secret': machine_secret,
                        'status': 'offline',
                        'meta': {'timestamp': time.time(), 'reason': 'shutdown'}
                    }, timeout=5)
                    logger.info(f"✅ Machine status updated to 'offline' on shutdown")
            except Exception as e:
                logger.warning(f"Failed to send offline status: {e}")
        
        # Ensure camera released if persistent task was not running or left a reference
        try:
            # Attempt a graceful release in case refs linger
            await SharedCamera.release_instance()
        except Exception:
            pass

        # Stop mqtt client loop if present
        mqtt_client = app.get('mqtt_client')
        if mqtt_client:
            try:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
            except Exception:
                pass

    app.on_startup.append(_start_background_tasks)
    app.on_cleanup.append(_cleanup_background_tasks)

    logger.info(f"Starting WebRTC server on http://{args.host}:{args.port}")
    logger.info(f"Open http://localhost:{args.port} in your browser")
    logger.info("")
    logger.info("=== Network Access ===")
    
    # Display local network IPs
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        logger.info(f"Local network: http://{local_ip}:{args.port}")
    except:
        pass
    
    logger.info("")
    logger.info("=== For Internet Access ===")
    logger.info("Option 1 (Easiest): ngrok")
    logger.info(f"  1. Install: https://ngrok.com/download")
    logger.info(f"  2. Run: ngrok http {args.port}")
    logger.info(f"  3. Use the https URL ngrok provides")
    logger.info("")
    logger.info("Option 2 (Free & Persistent): Cloudflare Tunnel")
    logger.info(f"  1. Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
    logger.info(f"  2. Run: cloudflared tunnel --url http://localhost:{args.port}")
    logger.info("")
    
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()