#!/bin/bash
# Démarrage de Calv-a-lot avec affichage de l'URL du dashboard

GIT_COMMIT=$(git rev-parse --short HEAD) docker compose up -d --build

# Récupérer le port exposé
PORT=$(docker compose port follower 8080 2>/dev/null | cut -d: -f2)
PORT=${PORT:-8080}

# Récupérer l'IP locale
IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "  Calv-a-lot is running! ($(git rev-parse --short HEAD))"
echo "  Dashboard: http://${IP}:${PORT}"
echo "=========================================="

# Installer le cron auto-updater (idempotent)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_CMD="*/5 * * * * $SCRIPT_DIR/updater.sh >> $SCRIPT_DIR/data/updater.log 2>&1"
(crontab -l 2>/dev/null | grep -v "updater.sh"; echo "$CRON_CMD") | crontab -
echo "  Auto-updater cron installed (every 5 min)"
