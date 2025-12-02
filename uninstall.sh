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

# ============================================
# Configuration Constants
# ============================================

# System Paths
SYSTEMD_DIR="/etc/systemd/system"
SUDOERS_DIR="/etc/sudoers.d"

# Service Names
EXPORTER_SERVICE_NAME="edge-metrics-exporter"
SHELLY_SERVICE_NAME="shelly-server"

# Ports (for verification display)
SHELLY_WS_PORT="8765"
SHELLY_HTTP_PORT="8766"

# ============================================
# Uninstallation Logic
# ============================================

# 1. Check if systemd service exists
if [ -f "$SYSTEMD_DIR/$EXPORTER_SERVICE_NAME.service" ]; then
    echo "📋 Found systemd service"

    # Stop service if running
    if systemctl is-active --quiet $EXPORTER_SERVICE_NAME; then
        echo "⏹️  Stopping $EXPORTER_SERVICE_NAME service..."
        $SUDO systemctl stop $EXPORTER_SERVICE_NAME
    fi

    # Disable service
    if systemctl is-enabled --quiet $EXPORTER_SERVICE_NAME 2>/dev/null; then
        echo "🔓 Disabling $EXPORTER_SERVICE_NAME service..."
        $SUDO systemctl disable $EXPORTER_SERVICE_NAME
    fi

    # Remove service file
    echo "🗑️  Removing systemd service file..."
    $SUDO rm -f "$SYSTEMD_DIR/$EXPORTER_SERVICE_NAME.service"

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
SUDOERS_FILE="$SUDOERS_DIR/tegrastats-${CURRENT_USER}"
if [ -f "$SUDOERS_FILE" ]; then
    echo "🔑 Removing sudoers configuration for tegrastats..."
    $SUDO rm -f "$SUDOERS_FILE"
    echo "✅ Sudoers configuration removed"
else
    echo "ℹ️  No sudoers configuration found"
fi

# 3. Remove shelly-server service if exists
if [ -f "$SYSTEMD_DIR/$SHELLY_SERVICE_NAME.service" ]; then
    echo "📋 Found $SHELLY_SERVICE_NAME service"

    # Stop service if running
    if systemctl is-active --quiet $SHELLY_SERVICE_NAME; then
        echo "⏹️  Stopping $SHELLY_SERVICE_NAME service..."
        $SUDO systemctl stop $SHELLY_SERVICE_NAME
    fi

    # Disable service
    if systemctl is-enabled --quiet $SHELLY_SERVICE_NAME 2>/dev/null; then
        echo "🔓 Disabling $SHELLY_SERVICE_NAME service..."
        $SUDO systemctl disable $SHELLY_SERVICE_NAME
    fi

    # Remove service file
    echo "🗑️  Removing $SHELLY_SERVICE_NAME service file..."
    $SUDO rm -f "$SYSTEMD_DIR/$SHELLY_SERVICE_NAME.service"

    # Reload systemd
    echo "🔄 Reloading systemd daemon..."
    $SUDO systemctl daemon-reload
    $SUDO systemctl reset-failed 2>/dev/null || true

    echo "✅ $SHELLY_SERVICE_NAME service uninstalled"
else
    echo "ℹ️  No $SHELLY_SERVICE_NAME service found"
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

echo ""
echo "🔍 Verification:"
echo "  - Service status: systemctl status $EXPORTER_SERVICE_NAME (should show 'not found')"
echo "  - Service status: systemctl status $SHELLY_SERVICE_NAME (should show 'not found')"
echo "  - Port check: netstat -tlnp | grep $METRICS_PORT (should be empty)"
echo "  - Port check: netstat -tlnp | grep $SHELLY_WS_PORT (should be empty)"
echo "  - Process check: ps aux | grep exporter.py (should be empty)"
echo "  - Process check: ps aux | grep shelly_server.py (should be empty)"
