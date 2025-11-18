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

# 2. Kill any running exporter processes
if pgrep -f "python3.*exporter.py" > /dev/null; then
    echo "🛑 Stopping running exporter processes..."
    $SUDO pkill -f "python3.*exporter.py" || true
    sleep 1
fi

echo ""
echo "🔍 Verification:"
echo "  - Service status: systemctl status edge-metrics-exporter (should show 'not found')"
echo "  - Port check: netstat -tlnp | grep 9100 (should be empty)"
echo "  - Process check: ps aux | grep exporter.py (should be empty)"
