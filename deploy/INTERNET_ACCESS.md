# Internet Access for WebRTC Stream 🌐

Stream your NutriCycle detection from anywhere over the internet.

---

## Quick Options (Ranked by Ease)

### ✅ Option 1: ngrok (Easiest, 2 minutes)

**Pros**: Dead simple, works immediately  
**Cons**: Free tier has random URLs, session expires after 2 hours

**Steps**:
1. Download ngrok: https://ngrok.com/download
2. Start your WebRTC server:
   ```powershell
   python deploy/webrtc_server.py --model "AI-Model/runs/detect/nutricycle_foreign_only/weights/best.pt" --source 1 --flip vertical
   ```
3. In another terminal:
   ```powershell
   ngrok http 8080
   ```
4. Copy the `https://xxxx.ngrok-free.app` URL
5. Open that URL on any device anywhere

**Windows Quick Install**:
```powershell
# Using Chocolatey
choco install ngrok

# Or download from https://ngrok.com/download and add to PATH
```

**Pi Install**:
```bash
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz
tar xvzf ngrok-v3-stable-linux-arm64.tgz
sudo mv ngrok /usr/local/bin/
```

---

### ✅ Option 2: Cloudflare Tunnel (Free, Persistent, Better for Production)

**Pros**: Free forever, custom domains, persistent, faster than ngrok  
**Cons**: Slightly more setup (5-10 min)

**Steps**:
1. Install cloudflared:
   - Windows: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
   - Pi:
     ```bash
     wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
     sudo mv cloudflared-linux-arm64 /usr/local/bin/cloudflared
     sudo chmod +x /usr/local/bin/cloudflared
     ```

2. Start tunnel (no account needed for quick test):
   ```bash
   cloudflared tunnel --url http://localhost:8080
   ```
   Copy the `https://xxxx.trycloudflare.com` URL.

3. **For persistent setup** (custom domain, always-on):
   ```bash
   cloudflared login
   cloudflared tunnel create nutricycle
   cloudflared tunnel route dns nutricycle nutricycle.yourdomain.com
   cloudflared tunnel run nutricycle --url http://localhost:8080
   ```

**Auto-start on Pi**:
```bash
sudo cloudflared service install
```

---

### ✅ Option 3: Tailscale (VPN - Secure Private Network)

**Pros**: Most secure, works behind any firewall, free for personal use  
**Cons**: Requires app on viewing device

**Steps**:
1. Install Tailscale on Pi and viewing device: https://tailscale.com/download
2. Start server on Pi as normal (`python deploy/webrtc_server.py ...`)
3. On viewing device, use Pi's Tailscale IP:
   ```
   http://100.x.x.x:8080
   ```

---

### ⚠️ Option 4: Self-Hosted with SSL (Advanced)

**Pros**: Full control, professional  
**Cons**: Requires domain, port forwarding, SSL setup

**Requirements**:
- Domain name
- Port 443 forwarded to your Pi/server
- SSL certificate (Let's Encrypt)

**Not recommended unless you need full control.**

---

## Recommended for NutriCycle

### Development/Testing:
- Use **ngrok** on your laptop (instant)

### Pi Deployment (local network):
- Just use local IP: `http://192.168.x.x:8080`

### Pi Deployment (internet access):
- Use **Cloudflare Tunnel** (free, persistent, fast)
- Or **Tailscale** if you want VPN security

---

## Security Notes

- **Local network**: No encryption needed (already secure LAN)
- **Internet**: HTTPS is automatic with ngrok/Cloudflare
- **Production**: Add authentication (basic auth or API key)

---

## Troubleshooting

### "Video not showing over internet"
- Ensure STUN servers are configured (they are in the updated code)
- Check browser console (F12) for WebRTC errors
- Try different STUN servers if one fails

### "ngrok session expired"
- Free tier expires after 2 hours
- Restart `ngrok http 8080` to get new URL
- Or upgrade to ngrok paid plan for persistent URLs

### "Cloudflare tunnel won't start"
- Check port 8080 isn't blocked by firewall
- Ensure server is running first before starting tunnel

---

## Quick Commands Summary

**Windows + ngrok**:
```powershell
# Terminal 1
python deploy/webrtc_server.py --model "AI-Model/.../best.pt" --source 1 --flip vertical

# Terminal 2
ngrok http 8080
```

**Pi + Cloudflare**:
```bash
# Terminal 1
python deploy/webrtc_server.py --model deploy/models/best.onnx --source 0 --conf 0.25

# Terminal 2
cloudflared tunnel --url http://localhost:8080
```

---

## Next Steps

1. Test locally first (`http://localhost:8080`)
2. Test on LAN (`http://LOCAL_IP:8080`)
3. Choose internet option (ngrok for quick test, Cloudflare for deployment)
4. Add authentication if needed (see deploy/README.md)

🎉 Now your NutriCycle detection is accessible from anywhere!
