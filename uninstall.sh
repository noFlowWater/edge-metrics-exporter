#!/bin/bash
# Edge Metrics Exporter Uninstallation Script

set -e

echo "🗑️  Uninstalling Edge Metrics Exporter..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

# 1. Check if systemd service exists
if [ -f "/etc/systemd/system/edge-metrics-exporter.service" ]; then
    echo "📋 Found systemd service"

    # Stop service if running
    if systemctl is-active --quiet edge-metrics-exporter; then
        echo "⏹️  Stopping edge-metrics-exporter service..."
        $SUDO systemctl stop edge-metrics-exporter
    fi

    # Disable service
    if systemctl is-enabled --quiet edge-metrics-exporter 2>/dev/null; then
        echo "🔓 Disabling edge-metrics-exporter service..."
        $SUDO systemctl disable edge-metrics-exporter
    fi

    # Remove service file
    echo "🗑️  Removing systemd service file..."
    $SUDO rm -f /etc/systemd/system/edge-metrics-exporter.service

    # Reload systemd
    echo "🔄 Reloading systemd daemon..."
    $SUDO systemctl daemon-reload
    $SUDO systemctl reset-failed 2>/dev/null || true

    echo "✅ Systemd service uninstalled"
else
    echo "ℹ️  No systemd service found"
fi

# 2. Remove sudoers configuration for tegrastats
CURRENT_USER=${USER}
SUDOERS_FILE="/etc/sudoers.d/tegrastats-${CURRENT_USER}"
if [ -f "$SUDOERS_FILE" ]; then
    echo "🔑 Removing sudoers configuration for tegrastats..."
    $SUDO rm -f "$SUDOERS_FILE"
    echo "✅ Sudoers configuration removed"
else
    echo "ℹ️  No sudoers configuration found"
fi

# 3. Remove shelly-server service if exists
if [ -f "/etc/systemd/system/shelly-server.service" ]; then
    echo "📋 Found shelly-server service"

    # Stop service if running
    if systemctl is-active --quiet shelly-server; then
        echo "⏹️  Stopping shelly-server service..."
        $SUDO systemctl stop shelly-server
    fi

    # Disable service
    if systemctl is-enabled --quiet shelly-server 2>/dev/null; then
        echo "🔓 Disabling shelly-server service..."
        $SUDO systemctl disable shelly-server
    fi

    # Remove service file
    echo "🗑️  Removing shelly-server service file..."
    $SUDO rm -f /etc/systemd/system/shelly-server.service

    # Reload systemd
    echo "🔄 Reloading systemd daemon..."
    $SUDO systemctl daemon-reload
    $SUDO systemctl reset-failed 2>/dev/null || true

    echo "✅ Shelly server service uninstalled"
else
    echo "ℹ️  No shelly-server service found"
fi

# 4. Kill any running processes
if pgrep -f "python3.*exporter.py" > /dev/null; then
    echo "🛑 Stopping running exporter processes..."
    $SUDO pkill -f "python3.*exporter.py" || true
    sleep 1
fi

if pgrep -f "python3.*shelly_server.py" > /dev/null; then
    echo "🛑 Stopping running shelly_server processes..."
    $SUDO pkill -f "python3.*shelly_server.py" || true
    sleep 1
fi

# Extract ports from config.yaml if it exists
CURRENT_DIR=$(pwd)
if [ -f "$CURRENT_DIR/config.yaml" ]; then
    METRICS_PORT=$(grep -E "^port:\s*[0-9]+" $CURRENT_DIR/config.yaml | awk '{print $2}')
    RELOAD_PORT=$(grep -E "^reload_port:\s*[0-9]+" $CURRENT_DIR/config.yaml | awk '{print $2}')
fi
METRICS_PORT=${METRICS_PORT:-9102}
RELOAD_PORT=${RELOAD_PORT:-9101}
SHELLY_WS_PORT=${SHELLY_WS_PORT:-8765}
SHELLY_HTTP_PORT=${SHELLY_HTTP_PORT:-8766}

echo ""
echo "🔍 Verification:"
echo "  - Service status: systemctl status edge-metrics-exporter (should show 'not found')"
echo "  - Service status: systemctl status shelly-server (should show 'not found')"
echo "  - Port check: netstat -tlnp | grep $METRICS_PORT (should be empty)"
echo "  - Port check: netstat -tlnp | grep $SHELLY_WS_PORT (should be empty)"
echo "  - Process check: ps aux | grep exporter.py (should be empty)"
echo "  - Process check: ps aux | grep shelly_server.py (should be empty)"
