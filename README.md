# Calv-a-lot

Copy-trading follower pour [Cash-a-lot](https://github.com/AlexandreFrancony/Cash-a-lot). Suit automatiquement les decisions de trading AI de Cash-a-lot en repliquant les trades proportionnellement a ton propre capital.

## Comment ca marche

```
Cash-a-lot (leader)             Calv-a-lot (follower)
+-----------------------+       +-----------------------+
| Claude AI decide      |       | Poll toutes les 2 min |
| BUY 7% BTC, SELL 5%  | HTTP  | Recoit le signal      |
| SOL...                |<------| Replique: BUY 7% de   |
| /api/signal/latest    |       | MON capital en BTC... |
+-----------------------+       +-----------------------+
```

- **Polling HTTP** : Calv-a-lot interroge Cash-a-lot toutes les 2 minutes via le reseau Docker interne (ou HTTPS si deploye sur un autre serveur)
- **Proportionnel** : les trades sont en % du capital, pas en montant absolu
- **Autonome** : ton argent reste sur TON compte Binance, tes cles API ne quittent jamais ta machine
- **Auth HMAC** : les signaux sont signes cryptographiquement (SHA-256)

## Prerequis

- **Docker** et **Docker Compose** installes
- Un compte **Binance** avec des USDC dans le **Spot wallet**
- Les **cles API Binance** (avec permissions Spot trading)
- Le **SIGNAL_SECRET** (a demander a Alex)

## Installation

### 1. Cloner le repo

```bash
git clone https://github.com/AlexandreFrancony/Calv-a-lot.git
cd Calv-a-lot
```

### 2. Configurer le `.env`

```bash
cp .env.example .env
```

Remplis le `.env` avec tes propres valeurs. Voici une commande pour tout remplir d'un coup :

```bash
cat > .env << 'EOF'
# === Leader (Cash-a-lot) ===
# Sur le meme serveur Docker : http://cashalot:8080
# Depuis un autre serveur : https://crypto.francony.fr
LEADER_URL=http://cashalot:8080
SIGNAL_SECRET=demander_a_alex

# === Binance API (tes propres cles) ===
BINANCE_API_KEY=ta_cle_api_binance
BINANCE_API_SECRET=ton_secret_api_binance
BINANCE_TESTNET=false

# === Trading ===
TRADING_MODE=dry_run
INITIAL_BUDGET_EUR=100
POLL_INTERVAL_SECONDS=120
EOF
```

> **Remplace** les valeurs `demander_a_alex`, `ta_cle_api_binance`, `ton_secret_api_binance` et `INITIAL_BUDGET_EUR` par tes vraies valeurs.

### 3. Lancer

```bash
chmod +x start.sh
./start.sh
```

L'URL du dashboard s'affiche automatiquement a la fin :
```
==========================================
  Calv-a-lot is running!
  Dashboard: http://192.168.1.42:8080
==========================================
```

Ouvre cette URL dans un navigateur (PC, telephone, tablette sur le meme reseau Wi-Fi).

## Modes de trading

| Mode | Comportement |
|------|-------------|
| `dry_run` | Simulation (aucun vrai ordre, parfait pour tester) |
| `live` | Vrais ordres Binance (**vrai argent !**) |

> **Commence TOUJOURS en `dry_run`** pour verifier que tout fonctionne. Quand tu es pret, change `TRADING_MODE=live` dans le `.env` puis relance :
> ```bash
> docker compose down && docker compose up -d
> ```

## Paires tradees

Memes paires USDC que Cash-a-lot (conformite MiCA Europe) :

| Paire | Crypto |
|-------|--------|
| BTCUSDC | Bitcoin |
| ETHUSDC | Ethereum |
| BNBUSDC | BNB |
| SOLUSDC | Solana |
| XRPUSDC | XRP |

> **Important** : tes USDC doivent etre dans le **Spot wallet** Binance (pas Funding, pas Earn).

## Dashboard

Le dashboard affiche en temps reel :
- **Total Value** en EUR et USD
- **P&L** (profit/loss) depuis le premier depot
- **Leader Status** (connecte ou non a Cash-a-lot)
- **Positions** actuelles avec prix d'entree et P&L par coin
- **Signaux recus** de Cash-a-lot
- **Trades executes**
- **Graphique** d'evolution du portfolio

## Cycle de polling

Toutes les 2 minutes, Calv-a-lot :
1. Interroge Cash-a-lot (`/api/signal/latest`) avec authentification HMAC
2. Verifie si le signal est nouveau (deduplication)
3. Si nouveau : execute les trades proportionnellement a ton capital
4. Enregistre le signal + trades dans la base de donnees
5. Sauvegarde un snapshot du portfolio
6. Verifie la survie (< 5 EUR = DEAD)

## Commandes utiles

```bash
# Demarrer (affiche l'URL du dashboard)
./start.sh

# Voir les logs en temps reel
docker compose logs -f

# Arreter
docker compose down

# Redemarrer apres modif du .env
docker compose down && docker compose up -d

# Verifier que le container tourne
docker ps | grep calvalot
```

## API Endpoints

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/health` | GET | Health check |
| `/` | GET | Dashboard |
| `/api/budget` | GET | Budget + valeur portfolio |
| `/api/budget/history` | GET | Historique pour graphique |
| `/api/budget/deposit` | POST | Enregistrer un depot |
| `/api/trades` | GET | Trades recents |
| `/api/positions` | GET | Positions actuelles |
| `/api/signals` | GET | Signaux recus |
| `/api/agent/status` | GET | Status du poller |
| `/api/agent/toggle` | POST | Pause/resume le poller |

## Architecture technique

- **Python 3.11** + Flask + gunicorn (1 worker, 2 threads)
- **SQLite** en WAL mode (zero dependance externe)
- **Docker** : non-root user, no-new-privileges, 192MB RAM max
- **Polling** thread-based (pas de cron, pas d'APScheduler)
- Pas d'appels a Claude AI (seul Cash-a-lot utilise l'IA)

## Troubleshooting

### Le dashboard affiche "Leader: Disconnected"
- Verifie que Cash-a-lot tourne (`docker ps | grep cashalot`)
- Verifie le `LEADER_URL` dans ton `.env` (Docker interne : `http://cashalot:8080`)
- Verifie le `SIGNAL_SECRET` dans ton `.env` (doit correspondre a celui de Cash-a-lot)
- Regarde les logs : `docker compose logs -f`

### Aucun trade ne s'execute
- Verifie que tu es en mode `live` (pas `dry_run`)
- Verifie que tu as des USDC dans ton **Spot wallet** Binance
- Verifie les permissions de tes cles API Binance (Spot trading active)

### "DEAD" sur le dashboard
- Le portfolio est tombe sous 5 EUR, le bot s'est arrete definitivement
- Il faut re-deposer et reinitialiser la base de donnees

---

*Calv-a-lot est un projet derive de [Cash-a-lot](https://github.com/AlexandreFrancony/Cash-a-lot), le bot de trading AI crypto.*
