#!/bin/bash
# Démarrage de Calv-a-lot avec affichage de l'URL du dashboard

docker compose up -d --build

# Récupérer le port exposé
PORT=$(docker compose port follower 8080 2>/dev/null | cut -d: -f2)
PORT=${PORT:-8080}

# Récupérer l'IP locale
IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "  Calv-a-lot is running!"
echo "  Dashboard: http://${IP}:${PORT}"
echo "=========================================="
