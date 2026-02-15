# RPI Control Flow Documentation

## Complete Request Chain

```
Mobile App (ControlPanel)
    ↓
startRPIProcessing() / stopRPIProcessing()
    ↓
POST http://localhost:4000/rpi/start | /rpi/stop
{
  "batchId": "batch-123",
  "machineId": "machine-456"
}
    ↓
Server (Port 4000) receives request
    ↓
RPIControlService publishes to MQTT
    ↓
MQTT Topic: nutricycle/rpi/control/machine-456
{
  "command": "start|stop",
  "batchId": "batch-123",
  "timestamp": "..."
}
    ↓
Raspberry Pi receives via MQTT (webrtc_server.py)
    ↓
RPI publishes to MQTT
    ↓
MQTT Topic: nutricycle/esp32/machine-456/command
{
  "machine_id": "machine-456",
  "command": "start|stop",
  "batch_id": "batch-123",
  "timestamp": "..."
}
    ↓
ESP32 receives and executes command
```

---

## Postman Requests

### Start Command
```http
POST http://localhost:8080/rpi/start
Content-Type: application/json
Authorization: Bearer {{idToken}}

{
  "batchId": "batch-123",
  "machineId": "machine-456"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Start command sent to Raspberry Pi and ESP32",
  "command": {
    "action": "start",
    "batchId": "batch-123",
    "machineId": "machine-456",
    "timestamp": "2026-02-11T10:30:45.123Z"
  }
}
```

### Stop Command
```http
POST http://localhost:8080/rpi/stop
Content-Type: application/json
Authorization: Bearer {{idToken}}

{
  "batchId": "batch-123",
  "machineId": "machine-456"
}
```

---

## RPI Direct Control Endpoint

The Raspberry Pi also has a direct HTTP endpoint that can receive commands with `rpiIpAddress`:

```http
POST http://192.168.1.100:8080/rpi/control
Content-Type: application/json

{
  "machine_id": "machine-456",
  "command": "start|stop|pause|reset",
  "batchId": "batch-123",
  "rpiIpAddress": "192.168.1.100"
}
```

This endpoint:
1. Receives control commands directly
2. Processes them locally
3. Forwards to ESP32 via MQTT topic `nutricycle/esp32/machine-456`

---

## MQTT Topics

| Topic | Direction | Payload |
|-------|-----------|---------|
| `nutricycle/rpi/control/{machineId}` | Server → RPI | `{command, batchId, timestamp}` |
| `nutricycle/esp32/{machineId}/command` | RPI → ESP32 | `{machine_id, command, batch_id, timestamp}` |

---

## How to Set Up in Postman

1. **Variables:**
   - `baseUrl` = `http://localhost:4000`
   - `rpiUrl` = `http://localhost:8080`
   - `idToken` = Your Firebase token
   - `batchId` = `batch-123`
   - `machineId` = `machine-456`

2. **Test Start:**
   - Method: POST
   - URL: `{{rpiUrl}}/rpi/start`
   - Body: `{"batchId": "{{batchId}}", "machineId": "{{machineId}}"}`

3. **Test Stop:**
   - Method: POST
   - URL: `{{rpiUrl}}/rpi/stop`
   - Body: `{"batchId": "{{batchId}}", "machineId": "{{machineId}}"}`

✅ Server changes reverted - now uses only MQTT for RPI control
✅ RPI receives commands via MQTT or direct HTTP with rpiIpAddress
✅ RPI forwards to ESP32 via MQTT
