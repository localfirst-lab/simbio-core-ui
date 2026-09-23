#!/bin/bash
# ==============================================================================
# Script di Installazione e Avvio Servizio Systemd: Simbio Core API
# VPS Target: Ubuntu / Debian
# ==============================================================================

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="simbio-api"
VENV_DIR="$APP_DIR/venv"

echo "=================================================="
echo "  Deploy Simbio Core API su VPS"
echo "  Cartella Progetto: $APP_DIR"
echo "=================================================="

# 1. Verifica Python3
if ! command -v python3 &>/dev/null; then
    echo "[!] python3 non trovato. Installazione..."
    apt-get update && apt-get install -y python3 python3-pip python3-venv
fi

# 2. Creazione ambiente virtuale se assente
if [ ! -d "$VENV_DIR" ]; then
    echo "[+] Creazione ambiente virtuale Python in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# 3. Installazione dipendenze
echo "[+] Aggiornamento pip e installazione dipendenze da requirements.txt..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

# 4. Controllo file .env
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.example" ]; then
        echo "[+] Copia di .env.example in .env..."
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    else
        echo "[!] Attenzione: file .env non trovato!"
    fi
fi

# 5. Creazione file di servizio systemd
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
echo "[+] Configurazione demone systemd in $SERVICE_FILE..."

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Simbio Core API Gateway Service
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
EnvironmentFile=-$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# 6. Ricarica e avvio servizio
echo "[+] Ricarica demoni systemd e avvio servizio..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

sleep 2

# 7. Verifica stato
echo "=================================================="
systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
echo "[+] Test salute API locale..."
curl -s http://127.0.0.1:8000/health || true
echo ""
echo "=================================================="
echo "  Deploy completato con successo!"
echo "  API attiva su http://0.0.0.0:8000"
echo "=================================================="
