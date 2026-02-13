# Calv-a-lot - Copy-Trading Follower pour Cash-a-lot

## Architecture
- **Single Python container** (Flask + gunicorn + thread poller)
- **SQLite** database (zéro dépendance, fichier local)
- **Dashboard**: Static HTML (Tailwind CDN + vanilla JS)
- **Exchange**: Binance API (USDC pairs — MiCA Europe)
- **Leader**: Cash-a-lot via polling HTTPS + HMAC auth

## Project Structure
```
Calv-a-lot/
├── config/
│   ├── settings.py             # Env vars (LEADER_URL, SIGNAL_SECRET, Binance)
│   └── coins.py                # USDC trading pairs
├── app/
│   ├── __init__.py             # Flask factory + services init + poller start
│   ├── db.py                   # SQLite WAL mode, thread-local connections
│   ├── models.py               # CRUD (sqlite3 ? placeholders)
│   ├── routes/
│   │   ├── health.py           # GET /health
│   │   ├── dashboard.py        # GET / (sert le HTML)
│   │   ├── budget.py           # API budget, deposit
│   │   ├── trades.py           # API trades et positions
│   │   ├── signals.py          # API signaux reçus
│   │   └── agent.py            # Pause/resume poller
│   ├── services/
│   │   ├── exchange.py         # Client Binance (copié de Cash-a-lot)
│   │   ├── market_data.py      # Prix + EUR/USDC rate (simplifié)
│   │   ├── budget_manager.py   # Budget sans AI tracking
│   │   ├── poller.py           # Thread polling + HMAC signing
│   │   └── follower.py         # Logique de réplication des trades
│   └── static/
│       └── index.html          # Dashboard vert (Tailwind, favicon 🐋, crypto icons)
├── data/                       # Volume Docker pour SQLite
│   └── calvalot.db
├── docker-compose.yml          # Single service (follower)
├── Dockerfile                  # Python 3.11-slim, UID 1000 (match host user), non-root
├── gunicorn.conf.py            # 1 worker, 2 threads, preload_app=False
├── start.sh                    # Lance Docker + affiche l'URL du dashboard avec IP locale
├── requirements.txt
└── .env.example
```

## Key Patterns
- No ORM — plain SQL with sqlite3 (parameterized queries)
- Environment variables for all config
- Docker: no-new-privileges, cap_drop ALL, non-root user, 192MB limit
- Thread-based poller (pas APScheduler)
- HMAC-SHA256 authentication avec Cash-a-lot
- Polling pull model (Calv-a-lot interroge, pas besoin d'ouvrir de ports)
- Pas de cap MAX_POSITION_PCT — le follower fait confiance aux décisions du leader
- Signal status amélioré : "skipped" (orange) quand toutes les actions sont en dessous du minimum Binance

## Trading Pairs (USDC — MiCA Europe)
- BTCUSDC, ETHUSDC, BNBUSDC, SOLUSDC, XRPUSDC
- Mêmes paires que Cash-a-lot

## API Endpoints
- `GET /health` — Health check
- `GET /` — Dashboard (static HTML)
- `GET /api/budget` — Budget status + portfolio value
- `GET /api/budget/history` — Snapshots for chart
- `POST /api/budget/deposit` — Enregistrer un dépôt
- `PUT /api/budget/deposit` — Corriger le total déposé
- `GET /api/budget/withdrawals` — Historique retraits
- `GET /api/trades` — Recent trades
- `GET /api/positions` — Current positions
- `GET /api/prices` — Prix courants (pour P&L dashboard)
- `GET /api/signals` — Historique des signaux reçus
- `GET /api/agent/status` — Poller status
- `POST /api/agent/toggle` — Pause/resume poller

## Polling Cycle (every 2 min)
1. Fetch signal from Cash-a-lot (`/api/signal/latest`) with HMAC auth
2. **Sync initial** : si aucune position locale, calque le `portfolio_state` du leader (achats proportionnels)
3. Check if signal is new (deduplication by signal_id)
4. If new: execute trades proportionally to local capital
5. Record signal + trades in SQLite
6. Save portfolio snapshot for chart
7. Check survival (< 5€ → DEAD)

## Initial Sync (démarrage)
- Au premier poll, si le follower est vierge (table positions vide), il utilise le `portfolio_state` du dernier signal
- Achète chaque coin proportionnellement au capital local (ex: leader 15% BTC → follower achète 15% de son capital en BTC)
- Trades enregistrés avec `signal_id = "initial_sync"` pour traçabilité
- Ne se déclenche qu'une fois (`_initial_sync_done` flag en mémoire)
- Si Cash-a-lot n'a pas encore de signal (204), réessaye au prochain poll

## Modes
- **dry_run**: Simulated trades (même slippage que Cash-a-lot)
- **live**: Real Binance orders

## Survival Mechanic
- If total portfolio value < 5€ → agent DEAD (permanent)
- No AI budget tracking (pas d'appels API AI)

## Dashboard
- Version: v1.0
- Favicon 🐋 (inline SVG)
- Crypto icons via CoinCap CDN (`assets.coincap.io/assets/icons/{symbol}@2x.png`) dans Positions et Trades
- Leader Status: connecté/déconnecté, dernier signal reçu

## Important Notes
- `.env` changes require `docker compose down && docker compose up -d`
- French comments preferred
- SQLite DB stored in `./data/calvalot.db` (Docker volume)
- `.gitignore` includes `data/calvalot.db-shm` and `data/calvalot.db-wal` (SQLite WAL temp files)
- USDC must be in **Spot wallet** on Binance
- Dockerfile utilise UID 1000 (`useradd -u 1000`) pour matcher l'utilisateur host (évite les erreurs de permissions SQLite)
- `start.sh` : lance docker compose + affiche l'URL dashboard avec l'IP locale du Pi
- Mode dry_run indépendant de Cash-a-lot (peut simuler pendant que le leader est en live)
- Pas de webhook auto-deploy (déployé localement chez les amis, pas sur le Pi central)
- Docker container timezone: `TZ=Europe/Paris` (logs en heure locale)
- Sur le Rasp d'Alex, le port host est overridé à `8081:8080` (localement) car `8080` est pris par Cash-a-lot
- Déployé sur Rasp dans `~/Hosting/Calv-a-lot/` (pas `~/Calv-a-lot`)
- Docker service name: `follower` (container name: `calvalot`)
