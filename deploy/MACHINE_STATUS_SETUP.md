# Machine Status Updates - Setup Guide

This guide explains how to configure the Raspberry Pi to automatically send status updates to the NutriCycle API, marking the machine as "online" when deployed.

## Overview

When the WebRTC server starts on the Raspberry Pi, it now:
1. Announces itself to the central node server (existing functionality)
2. **Sends an initial status update to the NutriCycle API** marking the machine as "online"
3. **Periodically sends heartbeat status updates** to keep the machine marked as online

This allows the mobile app and web dashboard to show real-time machine status without relying on other mechanisms.

## Architecture

### Server-Side (NutriCycle-Server)

A new API endpoint has been added:

```
POST /api/machines/:machineId/device/status
```

**Authentication:** Machine ID + Secret (no Firebase required)

**Request Body:**
```json
{
  "secret": "machine-secret-from-db",
  "status": "online",  // or "offline", "idle", "running", etc.
  "meta": {
    "video_url": "https://public-url-to-video",
    "timestamp": 1708000000000
  }
}
```

**Response:**
```json
{
  "ok": true,
  "machineId": "RPI-001",
  "status": "online",
  "updatedAt": "2026-02-16T12:34:56Z"
}
```

### Raspberry Pi Side

The `deploy/webrtc_server.py` has been updated to:
1. Accept new command-line arguments for API configuration
2. Send status updates in the `announce_task()` background task
3. Support environment variables for all configuration

## Setup Instructions

### Step 1: Get Machine Secret

First, you need the machine secret. The machine secret is generated when the machine is first registered in the database.

**Option A: Machine Already Registered**
Check the `Machine` table in your database:
```sql
SELECT machineId, secret FROM "Machine" WHERE machineId = 'RPI-001';
```

**Option B: Register New Machine**
If the machine isn't registered yet, send a request to create it:
```bash
curl -X POST https://nutricycle-server-production.up.railway.app/api/machines \
  -H "x-machine-id: RPI-001"
```

This will return:
```json
{
  "machine": { "id": "...", "machineId": "RPI-001", "secret": "your-secret-here", ... },
  "secret": "your-secret-here",
  "created": true
}
```

Save the `secret` value - you'll need it for configuration.

### Step 2: Configure Environment Variables

On the Raspberry Pi, edit the `.env` file in the deploy directory:

```bash
cd ~/NutriCycle-RaspBerry-v2/deploy
cp .env.example .env
nano .env
```

Update these variables:

```dotenv
# Machine identification
MACHINE_ID=RPI-001

# NutriCycle API Configuration (REQUIRED for status updates)
API_BASE_URL=https://nutricycle-server-production.up.railway.app
MACHINE_SECRET=your-machine-secret-from-step-1

# Status update frequency (optional, defaults to 60 seconds)
STATUS_UPDATE_INTERVAL=60

# Other existing configuration
ANNOUNCE_SERVER=https://your-node.example.com/api/announce
ANNOUNCE_INTERVAL=60
```

### Step 3: Load Environment Variables

Create a script to load the `.env` file and start the server:

**Option A: Using `python-dotenv`**

Install the package:
```bash
source venv/bin/activate
pip install python-dotenv
```

Then in `start_stream.sh`, add environment loading:
```bash
set -a
source .env
set +a
```

**Option B: Manual Environment Variables**

Pass them directly to the Python script:
```bash
export MACHINE_ID=RPI-001
export API_BASE_URL=https://nutricycle-server-production.up.railway.app
export MACHINE_SECRET=your-secret-here
python3 webrtc_server.py --machine-id $MACHINE_ID ...
```

### Step 4: Start the Server with Status Updates

Run the WebRTC server with the new arguments:

```bash
python3 webrtc_server.py \
  --model models/best.onnx \
  --source 0 \
  --conf 0.5 \
  --flip vertical \
  --port 8080 \
  --host 0.0.0.0 \
  --machine-id RPI-001 \
  --api-base-url https://nutricycle-server-production.up.railway.app \
  --machine-secret your-secret-here \
  --status-update-interval 60
```

Or with environment variables:
```bash
python3 webrtc_server.py \
  --model models/best.onnx \
  --source 0 \
  --conf 0.5 \
  --flip vertical \
  --port 8080 \
  --machine-id $MACHINE_ID \
  --api-base-url $API_BASE_URL \
  --machine-secret $MACHINE_SECRET \
  --status-update-interval $STATUS_UPDATE_INTERVAL
```

### Step 5: Verify Status Updates

Check the server logs for confirmation:

```
✅ Machine status updated to 'online': https://nutricycle-server-production.up.railway.app/api/machines/RPI-001/device/status
Machine status heartbeat sent
```

Or query the API:
```bash
curl https://nutricycle-server-production.up.railway.app/api/machines/RPI-001/status
```

## Example Systemd Service (Optional)

For automatic startup on Raspberry Pi, create a systemd service:

**File: `/etc/systemd/system/nutricycle-stream.service`**

```ini
[Unit]
Description=NutriCycle WebRTC Stream
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/NutriCycle-RaspBerry-v2/deploy
Environment="PATH=/home/pi/yolo/venv/bin"
EnvironmentFile=/home/pi/NutriCycle-RaspBerry-v2/deploy/.env
ExecStart=/home/pi/yolo/venv/bin/python3 webrtc_server.py \
  --model models/best.onnx \
  --source 0 \
  --conf 0.5 \
  --flip vertical \
  --port 8080 \
  --machine-id ${MACHINE_ID} \
  --api-base-url ${API_BASE_URL} \
  --machine-secret ${MACHINE_SECRET} \
  --status-update-interval ${STATUS_UPDATE_INTERVAL}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable nutricycle-stream.service
sudo systemctl start nutricycle-stream.service
sudo systemctl status nutricycle-stream.service
```

## Troubleshooting

### "No API configuration for status updates"
- Ensure `API_BASE_URL` and `MACHINE_SECRET` are set
- Check that environment variables are loaded correctly
- Verify the values in the `.env` file

### "Failed to update machine status"
- Check that the NutriCycle API server is running and accessible
- Verify the `MACHINE_ID` matches what's in the database
- Verify the `MACHINE_SECRET` is correct (check database)
- Check network connectivity: `curl -I $API_BASE_URL`

### Machine status not updating in database
- Verify the endpoint URL is correct: `{API_BASE_URL}/api/machines/{MACHINE_ID}/device/status`
- Check server logs: `journalctl -u nutricycle-stream -f`
- Test with curl:
  ```bash
  curl -X POST https://nutricycle-server-production.up.railway.app/api/machines/RPI-001/device/status \
    -H "Content-Type: application/json" \
    -d '{
      "secret": "your-secret",
      "status": "online",
      "meta": {"timestamp": '$(date +%s)'}
    }'
  ```

## What's Changed

### Code Changes

1. **NutriCycle-Server**
   - New endpoint: `POST /api/machines/:machineId/device/status`
   - New service function: `updateDeviceStatus()`
   - New repository function: `verifyMachineSecret()`

2. **NutriCycle-RaspBerry-v2/deploy/webrtc_server.py**
   - Enhanced `announce_task()` to send status updates
   - New command-line arguments: `--api-base-url`, `--machine-secret`, `--status-update-interval`

3. **Configuration**
   - Updated `.env.example` with new variables

## API Usage Examples

### Command Line with curl

```bash
# Mark machine as online
curl -X POST https://your-api.example.com/api/machines/RPI-001/device/status \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "machine-secret-value",
    "status": "online",
    "meta": {
      "video_url": "https://public-video-url",
      "timestamp": 1708000000000
    }
  }'

# Mark machine as offline
curl -X POST https://your-api.example.com/api/machines/RPI-001/device/status \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "machine-secret-value",
    "status": "offline"
  }'
```

### Python Client

```python
import requests
import time

def update_machine_status(machine_id, secret, api_base_url, status="online"):
    """Update machine status on the NutriCycle API."""
    url = f"{api_base_url}/api/machines/{machine_id}/device/status"
    payload = {
        "secret": secret,
        "status": status,
        "meta": {
            "timestamp": time.time()
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Machine status updated: {response.json()}")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

# Usage
update_machine_status(
    machine_id="RPI-001",
    secret="your-secret",
    api_base_url="https://nutricycle-server-production.up.railway.app",
    status="online"
)
```

## Next Steps

1. The machine will automatically be marked as "online" when the WebRTC server starts
2. Status updates are sent every `STATUS_UPDATE_INTERVAL` seconds (default: 60)
3. When the server shuts down, the machine will eventually be marked as "offline" (when heartbeats stop)
4. The mobile app can query the machine status to display real-time status indicators

## Additional Information

- Machine secret is stored in the database and should be treated like a password
- Status updates are best-effort; failures are logged but don't stop the server
- The API endpoint is not authenticated to allow IoT devices to call it
- Consider implementing a separate "offline" endpoint that devices call on shutdown for faster status updates
