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

# ============================================
# Configuration Constants
# ============================================

# System Paths
PYTHON_BIN="/usr/bin/python3"
SYSTEMD_DIR="/etc/systemd/system"
SUDOERS_DIR="/etc/sudoers.d"

# Service Names
EXPORTER_SERVICE_NAME="edge-metrics-exporter"
SHELLY_SERVICE_NAME="shelly-server"

# Exporter Service Configuration
EXPORTER_CONFIG_SERVER_DEFAULT="http://localhost:8080"
EXPORTER_CONFIG_TIMEOUT="5"
EXPORTER_RESTART_SEC="5"

# Shelly Service Configuration
SHELLY_WS_PORT="8765"
SHELLY_HTTP_PORT="8766"
SHELLY_RESTART_SEC="10"

# Security Settings (주석 해제하면 활성화)
# SHELLY_SECURITY_ENABLED="true"

# ============================================
# Service Generation Functions
# ============================================

generate_exporter_service() {
    local working_dir="$1"
    local config_server_url="$2"
    local user="$3"

    $SUDO tee "$SYSTEMD_DIR/$EXPORTER_SERVICE_NAME.service" > /dev/null <<EOF
[Unit]
Description=Edge Power Metrics Exporter
Documentation=https://github.com/your-org/edge-metrics-exporter
After=network.target

[Service]
Type=simple
User=$user
Group=$user
WorkingDirectory=$working_dir

# Environment variables
Environment="CONFIG_SERVER_URL=$config_server_url"
Environment="CONFIG_TIMEOUT=$EXPORTER_CONFIG_TIMEOUT"
Environment="LOCAL_CONFIG_PATH=$working_dir/config.yaml"

# Start command
ExecStart=$PYTHON_BIN $working_dir/exporter.py

# Restart policy
Restart=always
RestartSec=$EXPORTER_RESTART_SEC

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$EXPORTER_SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF
}

generate_shelly_service() {
    local working_dir="$1"
    local user="$2"

    # Security 설정 (상수로 제어)
    local security_settings=""
    if [ -n "$SHELLY_SECURITY_ENABLED" ]; then
        security_settings="NoNewPrivileges=true
PrivateTmp=true"
    fi

    $SUDO tee "$SYSTEMD_DIR/$SHELLY_SERVICE_NAME.service" > /dev/null <<EOF
[Unit]
Description=Shelly WebSocket Server for Power Metrics
Documentation=https://github.com/anthropics/claude-code
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$working_dir
ExecStart=$PYTHON_BIN $working_dir/shelly_server.py
Restart=always
RestartSec=$SHELLY_RESTART_SEC

# Environment variables
Environment="SHELLY_WS_PORT=$SHELLY_WS_PORT"
Environment="SHELLY_HTTP_PORT=$SHELLY_HTTP_PORT"

${security_settings:+# Security settings
$security_settings}

[Install]
WantedBy=multi-user.target
EOF
}

# ============================================
# Main Installation Script
# ============================================

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
    CURRENT_USER=${USER}

    # Ask for CONFIG_SERVER_URL
    echo "🌐 Enter Config Server URL (press Enter for default: $EXPORTER_CONFIG_SERVER_DEFAULT):"
    read -r CONFIG_SERVER_URL
    CONFIG_SERVER_URL=${CONFIG_SERVER_URL:-$EXPORTER_CONFIG_SERVER_DEFAULT}

    # Generate service file
    echo "📝 Generating $EXPORTER_SERVICE_NAME service..."
    generate_exporter_service "$CURRENT_DIR" "$CONFIG_SERVER_URL" "$CURRENT_USER"

    # Configure sudoers for tegrastats (Jetson devices)
    if command -v tegrastats &> /dev/null; then
        echo "🔑 Configuring passwordless sudo for tegrastats..."
        SUDOERS_FILE="$SUDOERS_DIR/tegrastats-${CURRENT_USER}"

        # Create sudoers entry
        echo "${CURRENT_USER} ALL=(ALL) NOPASSWD: /usr/bin/tegrastats" | $SUDO tee $SUDOERS_FILE > /dev/null
        $SUDO chmod 0440 $SUDOERS_FILE

        echo "✅ Sudoers configured: ${CURRENT_USER} can run tegrastats without password"
    else
        echo "ℹ️  tegrastats not found - skipping sudoers configuration (not a Jetson device?)"
    fi

    # Reload systemd
    $SUDO systemctl daemon-reload

    # Enable service
    echo "✅ Enabling $EXPORTER_SERVICE_NAME service..."
    $SUDO systemctl enable $EXPORTER_SERVICE_NAME

    # Install shelly-server service
    echo ""
    read -p "📡 Install $SHELLY_SERVICE_NAME service for Shelly plug integration? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Generate shelly service file
        echo "📝 Generating $SHELLY_SERVICE_NAME service..."
        generate_shelly_service "$CURRENT_DIR" "$CURRENT_USER"

        # Reload systemd
        $SUDO systemctl daemon-reload

        # Enable shelly service
        echo "✅ Enabling $SHELLY_SERVICE_NAME service..."
        $SUDO systemctl enable $SHELLY_SERVICE_NAME

        echo "✅ $SHELLY_SERVICE_NAME service installed!"
    else
        echo "$SHELLY_SERVICE_NAME service not installed."
    fi

    # Extract ports from config.yaml
    METRICS_PORT=$(grep -E "^port:\s*[0-9]+" $CURRENT_DIR/config.yaml | awk '{print $2}')
    RELOAD_PORT=$(grep -E "^reload_port:\s*[0-9]+" $CURRENT_DIR/config.yaml | awk '{print $2}')
    METRICS_PORT=${METRICS_PORT:-9102}
    RELOAD_PORT=${RELOAD_PORT:-9101}

    echo ""
    # Ask if user wants to start now
    read -p "▶️  Start services now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $SUDO systemctl start $EXPORTER_SERVICE_NAME

        # Start shelly-server if installed
        if systemctl list-unit-files | grep -q "$SHELLY_SERVICE_NAME.service"; then
            $SUDO systemctl start $SHELLY_SERVICE_NAME
        fi

        echo ""
        echo "✅ Services started!"
        echo "📊 Check status:"
        echo "  - Edge exporter: sudo systemctl status $EXPORTER_SERVICE_NAME"
        echo "  - Shelly server: sudo systemctl status $SHELLY_SERVICE_NAME"
        echo "📝 View logs:"
        echo "  - Edge exporter: sudo journalctl -u $EXPORTER_SERVICE_NAME -f"
        echo "  - Shelly server: sudo journalctl -u $SHELLY_SERVICE_NAME -f"
        echo "📈 Endpoints:"
        echo "  - Metrics: curl http://localhost:$METRICS_PORT/metrics"
        echo "  - Reload: curl -X POST http://localhost:$RELOAD_PORT/reload"
        echo "  - Shelly devices: curl http://localhost:$SHELLY_HTTP_PORT/devices"
    else
        echo "Services installed but not started."
        echo "Start with:"
        echo "  - sudo systemctl start $EXPORTER_SERVICE_NAME"
        echo "  - sudo systemctl start $SHELLY_SERVICE_NAME"
    fi
else
    echo "Systemd service not installed."
    echo "You can run manually: python3 exporter.py"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔍 Verification:"
echo "  - Service status: systemctl status $EXPORTER_SERVICE_NAME (should show 'active' if started)"
echo "  - Port check: netstat -tlnp | grep $METRICS_PORT (should show exporter listening)"
echo "  - Port check: netstat -tlnp | grep $SHELLY_WS_PORT (should show shelly WebSocket)"
echo "  - Process check: ps aux | grep exporter.py (should show running process)"
echo ""
echo "📖 Quick reference:"
echo "  - Metrics endpoint: http://localhost:$METRICS_PORT/metrics"
echo "  - Reload endpoint: http://localhost:$RELOAD_PORT/reload"
echo "  - Health check: http://localhost:$RELOAD_PORT/health"
echo "  - Config file: $CURRENT_DIR/config.yaml"
echo "  - Logs: sudo journalctl -u $EXPORTER_SERVICE_NAME -f"
echo ""
echo "📚 See README.md for more details"
