#!/bin/bash
# Installs pi-dashboard as a systemd service that starts on boot.
# Run once with: sudo bash install-service.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="${SCRIPT_DIR}/python"
SERVICE_NAME="pi-dashboard"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo bash $0"
    exit 1
fi

VENV_DIR="${SCRIPT_DIR}/.venv"
PYTHON="${VENV_DIR}/bin/python3"

echo "Setting up virtual environment..."
python3 -m venv "${VENV_DIR}"

# Set SKIP_DEPS=1 to skip pip entirely and just (re)write the service unit,
# e.g. when the network is down but the venv already has the packages:
#     sudo SKIP_DEPS=1 bash install-service.sh
if [ "${SKIP_DEPS:-0}" = "1" ]; then
    echo "SKIP_DEPS=1 — skipping pip, using existing venv packages."
else
    # Best-effort: piwheels can be slow/flaky. Fail fast and don't abort the
    # script, so the systemd unit below is still written.
    PIP_OPTS="--timeout 30 --retries 2"
    set +e
    "${PYTHON}" -m pip install --upgrade pip ${PIP_OPTS} --quiet
    "${PYTHON}" -m pip install ${PIP_OPTS} "${SCRIPT_DIR}" --quiet
    PIP_RC=$?
    set -e
    if [ "${PIP_RC}" -ne 0 ]; then
        echo "WARNING: dependency install failed (network?). Continuing with the"
        echo "         existing venv. Re-run when online, or use SKIP_DEPS=1."
    else
        echo "Dependencies installed."
    fi
fi

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Pi Dashboard LCD Monitor
After=multi-user.target
Wants=dev-spidev0.0.device
After=dev-spidev0.0.device

[Service]
Type=simple
# ── memory tuning ────────────────────────────────────────────────────────────
# glibc spawns up to 8 malloc arenas per core for threaded apps (the cause of
# the huge VSZ + fragmented RSS). Cap arenas and trim aggressively. Pin the
# numpy/OpenBLAS threadpools to 1 so importing numpy doesn't fan out threads.
Environment=MALLOC_ARENA_MAX=2
Environment=MALLOC_TRIM_THRESHOLD_=131072
Environment=OPENBLAS_NUM_THREADS=1
Environment=OMP_NUM_THREADS=1
Environment=PYTHONUNBUFFERED=1
# Blank the panel FIRST (kills the power-on white screen), then settle.
ExecStartPre=${PYTHON} ${PYTHON_DIR}/lcd_off.py
ExecStartPre=/bin/sleep 2
ExecStart=${PYTHON} ${PYTHON_DIR}/monitor.py
ExecStopPost=${PYTHON} ${PYTHON_DIR}/lcd_off.py
WorkingDirectory=${PYTHON_DIR}
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
