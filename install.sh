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
    CURRENT_DIR=$(pwd)
    SERVICE_FILE="edge-metrics-exporter.service"

    # Ask for CONFIG_SERVER_URL first
    echo "🌐 Enter Config Server URL (press Enter for default: http://localhost:8080):"
    read -r CONFIG_SERVER_URL
    CONFIG_SERVER_URL=${CONFIG_SERVER_URL:-http://localhost:8080}

    # Update paths in service file
    echo "📝 Updating service file with current directory: $CURRENT_DIR"
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" $SERVICE_FILE
    sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $CURRENT_DIR/exporter.py|g" $SERVICE_FILE
    sed -i "s|Environment=\"LOCAL_CONFIG_PATH=.*\"|Environment=\"LOCAL_CONFIG_PATH=$CURRENT_DIR/config.yaml\"|g" $SERVICE_FILE
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

    # Install shelly-server service
    echo ""
    read -p "📡 Install shelly-server service for Shelly plug integration? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SHELLY_SERVICE_FILE="shelly-server.service"

        # Update paths in shelly service file
        echo "📝 Updating shelly-server service file..."
        sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" $SHELLY_SERVICE_FILE
        sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $CURRENT_DIR/shelly_server.py|g" $SHELLY_SERVICE_FILE

        # Copy shelly service file
        echo "📋 Installing shelly-server service..."
        $SUDO cp $SHELLY_SERVICE_FILE /etc/systemd/system/

        # Reload systemd
        $SUDO systemctl daemon-reload

        # Enable shelly service
        echo "✅ Enabling shelly-server service..."
        $SUDO systemctl enable shelly-server

        echo "✅ Shelly server service installed!"
    else
        echo "Shelly server service not installed."
    fi

    # Extract ports from config.yaml
    METRICS_PORT=$(grep -E "^port:\s*[0-9]+" $CURRENT_DIR/config.yaml | awk '{print $2}')
    RELOAD_PORT=$(grep -E "^reload_port:\s*[0-9]+" $CURRENT_DIR/config.yaml | awk '{print $2}')
    METRICS_PORT=${METRICS_PORT:-9100}
    RELOAD_PORT=${RELOAD_PORT:-9101}

    # Extract Shelly ports from shelly_server.py or use defaults
    SHELLY_WS_PORT=${SHELLY_WS_PORT:-8765}
    SHELLY_HTTP_PORT=${SHELLY_HTTP_PORT:-8766}

    echo ""
    # Ask if user wants to start now
    read -p "▶️  Start services now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $SUDO systemctl start edge-metrics-exporter

        # Start shelly-server if installed
        if systemctl list-unit-files | grep -q shelly-server.service; then
            $SUDO systemctl start shelly-server
        fi

        echo ""
        echo "✅ Services started!"
        echo "📊 Check status:"
        echo "  - Edge exporter: sudo systemctl status edge-metrics-exporter"
        echo "  - Shelly server: sudo systemctl status shelly-server"
        echo "📝 View logs:"
        echo "  - Edge exporter: sudo journalctl -u edge-metrics-exporter -f"
        echo "  - Shelly server: sudo journalctl -u shelly-server -f"
        echo "📈 Endpoints:"
        echo "  - Metrics: curl http://localhost:$METRICS_PORT/metrics"
        echo "  - Reload: curl -X POST http://localhost:$RELOAD_PORT/reload"
        echo "  - Shelly devices: curl http://localhost:$SHELLY_HTTP_PORT/devices"
    else
        echo "Services installed but not started."
        echo "Start with:"
        echo "  - sudo systemctl start edge-metrics-exporter"
        echo "  - sudo systemctl start shelly-server"
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
echo "  - Port check: netstat -tlnp | grep $METRICS_PORT (should show exporter listening)"
echo "  - Port check: netstat -tlnp | grep $SHELLY_WS_PORT (should show shelly WebSocket)"
echo "  - Process check: ps aux | grep exporter.py (should show running process)"
echo ""
echo "📖 Quick reference:"
echo "  - Metrics endpoint: http://localhost:$METRICS_PORT/metrics"
echo "  - Reload endpoint: http://localhost:$RELOAD_PORT/reload"
echo "  - Health check: http://localhost:$RELOAD_PORT/health"
echo "  - Config file: $CURRENT_DIR/config.yaml"
echo "  - Logs: sudo journalctl -u edge-metrics-exporter -f"
echo ""
echo "📚 See README.md for more details"
