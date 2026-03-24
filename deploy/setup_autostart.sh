#!/usr/bin/env bash
set -euo pipefail

# Installs and enables a systemd service that starts NutriCycle WebRTC on boot.
# Usage:
#   bash deploy/setup_autostart.sh
# Optional env vars:
#   REPO_DIR=/home/pi/NutriCycle-RaspBerry-v2
#   SERVICE_NAME=nutricycle.service

SERVICE_NAME="${SERVICE_NAME:-nutricycle.service}"
SERVICE_USER="${SERVICE_USER:-$(id -un)}"
USER_HOME="${USER_HOME:-$HOME}"
REPO_DIR="${REPO_DIR:-${USER_HOME}/NutriCycle-RaspBerry-v2}"
DEPLOY_DIR="${REPO_DIR}/deploy"
START_SCRIPT="${DEPLOY_DIR}/start_stream_with_status.sh"
ENV_FILE="${DEPLOY_DIR}/.env"
VENV_DIR="${VENV_DIR:-${USER_HOME}/yolo/venv}"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

if [[ ! -f "${START_SCRIPT}" ]]; then
  echo "Error: start script not found at ${START_SCRIPT}"
  echo "Set REPO_DIR before running, for example:"
  echo "  REPO_DIR=/home/pi/nutricycle bash deploy/setup_autostart.sh"
  exit 1
fi

if [[ ! -x "${START_SCRIPT}" ]]; then
  chmod +x "${START_SCRIPT}"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Warning: ${ENV_FILE} not found."
  echo "Create it before starting service: cp ${DEPLOY_DIR}/.env.example ${ENV_FILE}"
fi

echo "Writing service to ${SERVICE_PATH}"
SERVICE_CONTENT="[Unit]
Description=NutriCycle auto start
After=network-online.target
Wants=network-online.target
After=systemd-udev-settle.service
Wants=systemd-udev-settle.service

[Service]
Type=simple
User=${SERVICE_USER}
SupplementaryGroups=video
WorkingDirectory=${DEPLOY_DIR}
ExecStartPre=/bin/sleep 8
ExecStart=/bin/bash -lc 'source ${VENV_DIR}/bin/activate; exec /bin/bash ${START_SCRIPT}'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"

echo "${SERVICE_CONTENT}" | sudo tee "${SERVICE_PATH}" >/dev/null

echo "Reloading systemd and enabling ${SERVICE_NAME}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

sleep 1
sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true

echo
echo "Done. Follow logs with:"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
