#!/bin/bash
# Auto-updater pour Calv-a-lot (exécuté par cron toutes les 5 min)
#
# Vérifie si le container a demandé une mise à jour via un flag file.
# Si oui : git pull + docker compose rebuild.
#
# Installation (automatique via start.sh) :
#   */5 * * * * /chemin/vers/Calv-a-lot/updater.sh >> /chemin/vers/Calv-a-lot/data/updater.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FLAG_FILE="$SCRIPT_DIR/data/UPDATE_REQUESTED"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# Pas de flag = rien à faire
if [ ! -f "$FLAG_FILE" ]; then
    exit 0
fi

echo "$LOG_PREFIX Update requested, starting..."
echo "$LOG_PREFIX Flag: $(cat "$FLAG_FILE" 2>/dev/null)"

# Supprimer le flag immédiatement (évite double-trigger)
rm -f "$FLAG_FILE"

# Pull le code
cd "$SCRIPT_DIR"
BEFORE=$(git rev-parse --short HEAD)
echo "$LOG_PREFIX Pulling latest code (currently $BEFORE)..."
git fetch origin
git reset --hard origin/master

AFTER=$(git rev-parse --short HEAD)
echo "$LOG_PREFIX Git updated: $BEFORE -> $AFTER"

# Rebuild et redémarrer
echo "$LOG_PREFIX Building and deploying..."
GIT_COMMIT="$AFTER" docker compose up -d --build

echo "$LOG_PREFIX Update complete: now running $AFTER"
