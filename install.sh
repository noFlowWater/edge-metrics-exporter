#!/bin/bash
# Edge Metrics Exporter Installation Script

set -e

echo "🚀 Installing Edge Metrics Exporter..."

# Check if running as root for systemd installation
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

# 1. Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# 2. Make exporter executable
echo "🔧 Making exporter executable..."
chmod +x exporter.py

# 3. Test run (quick check)
echo "🧪 Testing exporter (dry run)..."
timeout 3 python3 exporter.py || true

# 4. Ask if user wants to install systemd service
read -p "📋 Install as systemd service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Update paths in service file
    CURRENT_DIR=$(pwd)
    SERVICE_FILE="edge-metrics-exporter.service"

    echo "📝 Updating service file with current directory: $CURRENT_DIR"
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" $SERVICE_FILE
    sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $CURRENT_DIR/exporter.py|g" $SERVICE_FILE
    sed -i "s|Environment=\"LOCAL_CONFIG_PATH=.*\"|Environment=\"LOCAL_CONFIG_PATH=$CURRENT_DIR/config.yaml\"|g" $SERVICE_FILE

    # Ask for CONFIG_SERVER_URL
    echo "🌐 Enter Config Server URL (press Enter for default: http://localhost:8080):"
    read -r CONFIG_SERVER_URL
    CONFIG_SERVER_URL=${CONFIG_SERVER_URL:-http://localhost:8080}

    sed -i "s|Environment=\"CONFIG_SERVER_URL=.*\"|Environment=\"CONFIG_SERVER_URL=$CONFIG_SERVER_URL\"|g" $SERVICE_FILE

    # Configure sudoers for tegrastats (Jetson devices)
    if command -v tegrastats &> /dev/null; then
        echo "🔑 Configuring passwordless sudo for tegrastats..."
        CURRENT_USER=${USER}
        SUDOERS_FILE="/etc/sudoers.d/tegrastats-${CURRENT_USER}"

        # Create sudoers entry
        echo "${CURRENT_USER} ALL=(ALL) NOPASSWD: /usr/bin/tegrastats" | $SUDO tee $SUDOERS_FILE > /dev/null
        $SUDO chmod 0440 $SUDOERS_FILE

        echo "✅ Sudoers configured: ${CURRENT_USER} can run tegrastats without password"
    else
        echo "ℹ️  tegrastats not found - skipping sudoers configuration (not a Jetson device?)"
    fi

    # Copy service file
    echo "📋 Installing systemd service..."
    $SUDO cp $SERVICE_FILE /etc/systemd/system/

    # Reload systemd
    $SUDO systemctl daemon-reload

    # Enable service
    echo "✅ Enabling edge-metrics-exporter service..."
    $SUDO systemctl enable edge-metrics-exporter

    # Ask if user wants to start now
    read -p "▶️  Start service now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $SUDO systemctl start edge-metrics-exporter
        echo ""
        echo "✅ Service started!"
        echo "📊 Check status: sudo systemctl status edge-metrics-exporter"
        echo "📝 View logs: sudo journalctl -u edge-metrics-exporter -f"
        echo "📈 Metrics: curl http://localhost:9100/metrics"
    else
        echo "Service installed but not started."
        echo "Start with: sudo systemctl start edge-metrics-exporter"
    fi
else
    echo "Systemd service not installed."
    echo "You can run manually: python3 exporter.py"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔍 Verification:"
echo "  - Service status: systemctl status edge-metrics-exporter (should show 'active' if started)"
echo "  - Port check: netstat -tlnp | grep 9100 (should show exporter listening)"
echo "  - Process check: ps aux | grep exporter.py (should show running process)"
echo ""
echo "📖 Quick reference:"
echo "  - Metrics endpoint: http://localhost:9100/metrics"
echo "  - Reload endpoint: http://localhost:9101/reload"
echo "  - Config file: $CURRENT_DIR/config.yaml"
echo "  - Logs: sudo journalctl -u edge-metrics-exporter -f"
echo ""
echo "📚 See README.md for more details"
