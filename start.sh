#!/bin/bash
# Démarrage de Calv-a-lot avec affichage de l'URL du dashboard

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Pre-flight: check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Installe Docker puis relance."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas démarré. Lance Docker puis relance."
    exit 1
fi

# Build and start
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

# Check if config exists
if [ ! -f "$SCRIPT_DIR/data/config.json" ] && [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "  ⚙️  Premier lancement détecté !"
    echo "  Ouvre le lien ci-dessus pour configurer."
fi

echo "=========================================="

# Installer le cron auto-updater (idempotent)
CRON_CMD="*/5 * * * * $SCRIPT_DIR/updater.sh >> $SCRIPT_DIR/data/updater.log 2>&1"
(crontab -l 2>/dev/null | grep -v "updater.sh"; echo "$CRON_CMD") | crontab -
echo "  Auto-updater cron installed (every 5 min)"
