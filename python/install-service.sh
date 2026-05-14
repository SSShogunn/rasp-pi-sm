#!/bin/bash
# Installs pi-dashboard as a systemd service that starts on boot.
# Run once with: sudo bash install-service.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="pi-dashboard"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo bash $0"
    exit 1
fi

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Pi Dashboard LCD Monitor
After=multi-user.target
Wants=dev-spidev0.0.device
After=dev-spidev0.0.device

[Service]
Type=simple
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/python3 ${SCRIPT_DIR}/monitor.py
WorkingDirectory=${SCRIPT_DIR}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
echo "Service installed at: $SERVICE_FILE"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
