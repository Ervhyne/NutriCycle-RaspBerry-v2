# Announcing Pi WebRTC Feed to Node Server

This document describes how a NutriCycle device (Raspberry Pi or Windows host) announces its public WebRTC video feed URL and MachineID to your Node server. The Pi will keep announcing periodically so the Node server can register/bind the device to a user. Detection events are published separately to an MQTT broker for ESP32 alerts.

---

## Quick flow (summary)
1. Start a public tunnel for the device (ngrok or Cloudflare Tunnel) that exposes the local WebRTC server on port 8080.
2. Start the WebRTC server on the Pi with `--machine-id` and `--announce-server` flags.
3. The WebRTC server auto-detects the public URL (via ngrok local API) or uses `--public-url` when provided, and POSTs JSON to your Node endpoint periodically.
4. Your Node server handles registration/binding (not handled by the Pi) and returns normal HTTP response codes.

---

## Start the WebRTC server (examples)
- Auto-detecting ngrok tunnel (recommended when ngrok runs locally):

```bash
python deploy/webrtc_server.py \
  --model deploy/models/best.onnx \
  --source 0 \
  --machine-id RPI-001 \
  --announce-server https://your-node.example.com/api/announce
```

- If you manage the tunnel externally and already know the public URL:

```bash
python deploy/webrtc_server.py \
  --model deploy/models/best.onnx \
  --source 0 \
  --machine-id RPI-001 \
  --public-url "https://xxxx.ngrok-free.app" \
  --announce-server https://your-node.example.com/api/announce
```

- Default announce interval: 60 seconds. Change with `--announce-interval <seconds>`.

---

## Announce payload (JSON)
When an announce action happens (periodically) the Pi will POST JSON to the `--announce-server` URL:

```json
{
  "machine_id": "RPI-001",
  "video_url": "https://xxxx.ngrok-free.app",
  "timestamp": 1675252800.123
}
```

- `machine_id`: Unique identifier for the device (passed in with `--machine-id`).
- `video_url`: Public https URL for accessing the WebRTC client page (ngrok/Cloudflare URL).
- `timestamp`: Unix epoch in seconds (floating point).

Your Node server should accept this JSON and respond with a 200/2xx status code to indicate successful receipt.

---

## Security & signing
- You can protect the announce endpoint with an API token. If you require a token I can add `--announce-token <token>` to include an `Authorization: Bearer <token>` header in announce POSTs.
- For strong security in production prefer Cloudflare Tunnel or Tailscale rather than ngrok free, and validate the token on the Node side.

---

## Example `curl` test (one-shot)
To simulate an announce from the Pi or test your Node endpoint:

```bash
curl -X POST https://your-node.example.com/api/announce \
  -H "Content-Type: application/json" \
  -d '{"machine_id":"RPI-001","video_url":"https://xxxx.ngrok-free.app"}'
```

If your endpoint requires authentication, add a header:

```bash
-H "Authorization: Bearer MY_SECRET_TOKEN"
```

---

## Detection → MQTT → ESP32 behavior
- The Pi publishes YOLO detection events to the configured MQTT broker (use `--mqtt-broker` and `--mqtt-topic`).
- The server also publishes compact alerts to `--mqtt-esp-topic` (default `nutricycle/esp32`) with payload `{"machine_id":"RPI-001","alert":true}` to be consumed by ESP32 clients.
- The Node server does not need to handle detection events unless you want central logging; detection streams to MQTT and the ESP32 subscribes to alerts.

---

## Troubleshooting
- If the server cannot find a public URL, ensure the tunnel is running locally (ngrok exposes API on `http://127.0.0.1:4040/api/tunnels`).
- If POSTs fail, the Pi logs warnings; check firewall and that the Node endpoint accepts HTTPS and the chosen token.
- For persistent/production use `cloudflared tunnel` or Tailscale rather than ngrok free.

---

## Remote Control (start/stop) API
Your Node server can send direct control commands (start/stop/pause/reset) to the device using the `/control` endpoint on the device's public URL. The device will forward commands to the ESP32 via MQTT (topic defaults to `nutricycle/esp32`).

### Endpoint
```
POST https://<device-public-url>/control
Content-Type: application/json
Authorization: Bearer <TOKEN>  # optional if configured with --control-token
```

### Payload
```json
{
  "machine_id": "RPI-001",
  "command": "stop"  # one of start|stop|pause|reset
}
```

### Responses
- `200 OK` — command forwarded to ESP32 (MQTT)
- `401/403` — authorization required or invalid token
- `404` — machine_id mismatch
- `400` — invalid payload
- `503` — MQTT client not connected on the device

### Example (curl)
```bash
curl -X POST https://xxxx.ngrok-free.app/control \
    -H "Authorization: Bearer MY_SECRET_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"machine_id":"RPI-001","command":"stop"}'
```

---
