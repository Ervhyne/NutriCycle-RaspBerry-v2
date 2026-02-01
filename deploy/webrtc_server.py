#!/usr/bin/env python3
"""
WebRTC server for NutriCycle live detection streaming.
Streams camera + YOLO inference to browser clients via WebRTC.

Usage:
  python deploy/webrtc_server.py --model AI-Model/runs/detect/.../best.pt --source 1 --flip vertical --conf 0.5
"""

import argparse
import asyncio
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

# Event queue for detection events
from asyncio import Queue
event_queue: Queue = Queue(maxsize=32)  # non-blocking if full


class YOLOVideoTrack(VideoStreamTrack):
    """Video track that captures from camera and applies YOLO inference."""
    
    def __init__(self, source, flip_mode, model_instance, conf_threshold, event_queue=None):
        self.event_queue = event_queue
        if self.event_queue is None:
            self.event_queue = event_queue  # still None, but safe

        super().__init__()
        self.source = source
        self.flip_mode = flip_mode
        self.model = model_instance
        self.conf = conf_threshold
        
        # Open camera with DirectShow on Windows for better USB camera support
        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
        else:
            self.cap = cv2.VideoCapture(source)
        
        if not self.cap.isOpened():
            logger.error(f"Failed to open camera/video source: {source}")
            sys.exit(1)
        
        # Set 480p resolution (fast performance, lower bandwidth)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Get camera properties (actual values after setting - camera will use closest supported resolution)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        logger.info(f"Camera opened: {self.width}x{self.height} @ {self.fps}fps")
        
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps_counter = 0
        
    async def recv(self):
        """Receive the next frame (with YOLO inference applied)."""
        try:
            pts, time_base = await self.next_timestamp()
            
            # Run blocking I/O in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            ret, frame = await loop.run_in_executor(None, self.cap.read)
            
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
            results = self.model(frame, conf=self.conf, verbose=False)
            annotated = results[0].plot()
            inference_time = time.time() - t0

            # Build detection list
            dets = []
            for b in results[0].boxes:
                try:
                    xyxy = b.xyxy.tolist() if hasattr(b, 'xyxy') else None
                    dets.append({
                        'cls': int(b.cls),
                        'name': self.model.names[int(b.cls)] if hasattr(self.model, 'names') else str(int(b.cls)),
                        'conf': float(b.conf),
                        'xyxy': xyxy,
                    })
                except Exception:
                    continue

            # If there are detections, enqueue an event (non-blocking)
            if dets and self.event_queue is not None:
                event = {
                    'timestamp': time.time(),
                    'frame_id': self.frame_count,
                    'width': self.width,
                    'height': self.height,
                    'detections': dets,
                    'machine_id': getattr(args, 'machine_id', None)
                }
                try:
                    self.event_queue.put_nowait(event)
                except Exception:
                    # queue full, drop event to avoid blocking
                    pass
            
            # Add FPS overlay
            self.fps_counter += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                fps = self.fps_counter / (current_time - self.last_fps_time)
                self.last_fps_time = current_time
                self.fps_counter = 0
                logger.info(f"Streaming at {fps:.1f} FPS, inference: {inference_time*1000:.0f}ms")
            else:
                fps = self.fps
            
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
    
    def __del__(self):
        if hasattr(self, 'cap'):
            self.cap.release()


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
    
    # ICE servers for internet connectivity (STUN/TURN)
    ice_servers = [
        RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
        RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        RTCIceServer(urls=["stun:stun2.l.google.com:19302"]),
        RTCIceServer(urls=["stun:stun.relay.metered.ca:80"]),
    ]
    
    configuration = RTCConfiguration(iceServers=ice_servers)
    pc = RTCPeerConnection(configuration=configuration)
    pcs.add(pc)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
    
    # Create video track
    video_track = YOLOVideoTrack(
        source=args.source,
        flip_mode=args.flip,
        model_instance=model,
        conf_threshold=args.conf
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


def main():
    global args, model

    # MQTT client (optional)
    mqtt_client = None

    async def announce_task(app):
        """Announce machine_id and public URL to central node server periodically."""
        announce_server = getattr(args, 'announce_server', None)
        interval = getattr(args, 'announce_interval', 60)
        machine_id = getattr(args, 'machine_id', None)
        public_url = getattr(args, 'public_url', None)

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
                except Exception as e:
                    logger.error(f"Error in announce_task: {e}")
                await asyncio.sleep(interval)

    async def event_broadcaster(app):
        """Consume detection events and publish via MQTT (if configured) and optionally log."""
        nonlocal mqtt_client
        mqtt_broker = getattr(args, 'mqtt_broker', None)
        mqtt_topic = getattr(args, 'mqtt_topic', 'nutricycle/detections')
        mqtt_esp_topic = getattr(args, 'mqtt_esp_topic', 'nutricycle/esp32')
        mqtt_port = getattr(args, 'mqtt_port', 1883)
        mqtt_qos = getattr(args, 'mqtt_qos', 1)

        if mqtt_broker:
            try:
                import paho.mqtt.client as paho
                mqtt_client = paho.Client()
                if getattr(args, 'mqtt_username', None):
                    mqtt_client.username_pw_set(getattr(args, 'mqtt_username'), getattr(args, 'mqtt_password', None))
                mqtt_client.connect(mqtt_broker, port=mqtt_port)
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
                    # If we want to signal ESP32 directly on detection, publish a compact alert topic
                    mqtt_client.publish(mqtt_esp_topic, json.dumps({'machine_id': evt.get('machine_id'), 'alert': True}), qos=1)
                except Exception as e:
                    logger.warning(f"MQTT publish failed: {e}")
            # Also log to server console
            logger.info(f"Detection event: {len(evt.get('detections', []))} objects from {evt.get('machine_id')}")

    # will register these tasks later on app startup

    
    parser = argparse.ArgumentParser(description="WebRTC YOLO streaming server")
    parser.add_argument("--model", default="AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt",
                        help="Path to YOLO model (.pt or .onnx)")
    parser.add_argument("--source", default="0", help="Camera index or video file path")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--flip", choices=['none', 'vertical', 'horizontal', '180'], default='none',
                        help="Flip video: vertical=upside-down, horizontal, 180=rotate 180")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--announce-server", default=None, help="HTTP endpoint to POST machine_id + video URL")
    parser.add_argument("--machine-id", default=None, help="Unique Machine ID for this device")
    parser.add_argument("--announce-interval", type=int, default=60, help="Seconds between announce attempts")
    parser.add_argument("--public-url", default=None, help="Public video URL if ngrok is used externally")
    
    # MQTT options
    parser.add_argument("--mqtt-broker", default=None, help="MQTT broker host (optional)")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--mqtt-topic", default="nutricycle/detections", help="MQTT topic for detection events")
    parser.add_argument("--mqtt-esp-topic", default="nutricycle/esp32", help="MQTT topic to send compact alerts to ESP32")
    parser.add_argument("--mqtt-username", default=None, help="MQTT username")
    parser.add_argument("--mqtt-password", default=None, help="MQTT password")
    parser.add_argument("--mqtt-qos", type=int, default=1, help="MQTT QoS")
    parser.add_argument("--control-token", default=None, help="Bearer token required for /control HTTP POSTs")

    args = parser.parse_args()
    
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
    
    logger.info(f"Loading model: {model_path}")
    model = YOLO(model_path)
    logger.info(f"Model loaded. Classes: {model.names}")
    
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

        machine_id = data.get('machine_id')
        if machine_id != args.machine_id:
            return web.Response(status=404, text='Machine ID mismatch')

        cmd = data.get('command')
        if cmd not in ('start', 'stop', 'pause', 'reset'):
            return web.Response(status=400, text='Invalid command')

        # Publish to ESP32 via MQTT
        mqtt_client = request.app.get('mqtt_client')
        esp_topic = getattr(args, 'mqtt_esp_topic', 'nutricycle/esp32')
        payload = {'machine_id': machine_id, 'command': cmd, 'timestamp': time.time()}

        if mqtt_client:
            try:
                mqtt_client.publish(esp_topic, json.dumps(payload), qos=1)
                logger.info(f"Forwarded control '{cmd}' to ESP32 via MQTT on topic {esp_topic}")
                return web.Response(status=200, text='Command forwarded')
            except Exception as e:
                logger.error(f"MQTT publish failed: {e}")
                return web.Response(status=500, text='MQTT publish failed')
        else:
            logger.warning('MQTT client not connected')
            return web.Response(status=503, text='MQTT client not connected')

    app.router.add_post('/control', control_handler)

    async def _start_background_tasks(app):
        app['announce_task'] = asyncio.create_task(announce_task(app))
        app['event_broadcaster_task'] = asyncio.create_task(event_broadcaster(app))

    async def _cleanup_background_tasks(app):
        # Cancel background tasks
        for name in ('announce_task', 'event_broadcaster_task'):
            t = app.get(name)
            if t:
                t.cancel()
                try:
                    await t
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
