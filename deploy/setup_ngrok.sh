#!/bin/bash
# Install and setup ngrok on Raspberry Pi

set -e

echo "🔧 Installing ngrok for Raspberry Pi..."

# Detect architecture
ARCH=$(uname -m)

if [ "$ARCH" = "aarch64" ]; then
    echo "Detected: ARM64 (64-bit)"
    NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz"
elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv6l" ]; then
    echo "Detected: ARM32 (32-bit)"
    NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz"
else
    echo "❌ Unsupported architecture: $ARCH"
    exit 1
fi

# Download and install
cd ~
wget -O ngrok.tgz "$NGROK_URL"
tar -xvzf ngrok.tgz
sudo mv ngrok /usr/local/bin/
rm ngrok.tgz

# Verify
if command -v ngrok &> /dev/null; then
    echo "✅ ngrok installed successfully!"
    ngrok --version
    echo ""
    echo "📋 Next steps:"
    echo "1. Sign up at: https://dashboard.ngrok.com/signup"
    echo "2. Get your auth token: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "3. Run: ngrok config add-authtoken YOUR_TOKEN_HERE"
    echo ""
    echo "Then start your tunnel with: ngrok http 8080"
else
    echo "❌ Installation failed"
    exit 1
fi
