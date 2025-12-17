#!/bin/bash
# Install systemd services and timers for AIBackgroundWorker

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "Installing AIBackgroundWorker systemd services and timers..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Check if systemd is available
if ! systemctl --version > /dev/null 2>&1; then
    echo "Error: systemd is not available. Please enable systemd in WSL."
    echo "Add the following to /etc/wsl.conf:"
    echo ""
    echo "[boot]"
    echo "systemd=true"
    echo ""
    echo "Then restart WSL: wsl --shutdown"
    exit 1
fi

# Install lifelog daemon service
echo ""
echo "Installing lifelog-daemon service..."
cp "$SCRIPT_DIR/lifelog-daemon.service" "$SYSTEMD_DIR/"
systemctl daemon-reload
systemctl enable lifelog-daemon.service
echo "  ✓ lifelog-daemon.service installed and enabled"

# Install merge windows logs service and timer
echo ""
echo "Installing merge-windows-logs service and timer..."
cp "$SCRIPT_DIR/merge-windows-logs.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/merge-windows-logs.timer" "$SYSTEMD_DIR/"
systemctl daemon-reload
systemctl enable merge-windows-logs.timer
echo "  ✓ merge-windows-logs.service and timer installed and enabled"

# Install brave history poller service and timer
echo ""
echo "Installing brave-history-poller service and timer..."
cp "$SCRIPT_DIR/brave-history-poller.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/brave-history-poller.timer" "$SYSTEMD_DIR/"
systemctl daemon-reload
systemctl enable brave-history-poller.timer
echo "  ✓ brave-history-poller.service and timer installed and enabled"

echo ""
echo "All services and timers installed successfully!"
echo ""
echo "To start services:"
echo "  sudo systemctl start lifelog-daemon.service"
echo "  sudo systemctl start merge-windows-logs.timer"
echo "  sudo systemctl start brave-history-poller.timer"
echo ""
echo "To check status:"
echo "  sudo systemctl status lifelog-daemon.service"
echo "  sudo systemctl status merge-windows-logs.timer"
echo "  sudo systemctl status brave-history-poller.timer"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u lifelog-daemon.service -f"
echo "  sudo journalctl -u merge-windows-logs.service -f"
echo "  sudo journalctl -u brave-history-poller.service -f"
echo "  tail -f /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log"
