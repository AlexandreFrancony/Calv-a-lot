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
├── config/         # Settings, coin definitions
├── app/
│   ├── routes/     # Flask API endpoints
│   ├── services/   # Business logic (exchange, poller, follower, budget)
│   └── static/     # Dashboard HTML
├── data/           # SQLite database (Docker volume)
└── docker-compose.yml
```

## Key Patterns
- No ORM — plain SQL with sqlite3 (parameterized queries)
- Environment variables for all config
- Docker: no-new-privileges, cap_drop ALL, non-root user, 192MB limit
- Thread-based poller (pas APScheduler)
- HMAC-SHA256 authentication avec Cash-a-lot
- Polling pull model (Calv-a-lot interroge, pas besoin d'ouvrir de ports)

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
- `GET /api/signals` — Historique des signaux reçus
- `GET /api/agent/status` — Poller status
- `POST /api/agent/toggle` — Pause/resume poller

## Polling Cycle (every 2 min)
1. Fetch signal from Cash-a-lot (`/api/signal/latest`) with HMAC auth
2. Check if signal is new (deduplication by signal_id)
3. If new: execute trades proportionally to local capital
4. Record signal + trades in SQLite
5. Save portfolio snapshot for chart
6. Check survival (< 5€ → DEAD)

## Modes
- **dry_run**: Simulated trades (même slippage que Cash-a-lot)
- **live**: Real Binance orders

## Survival Mechanic
- If total portfolio value < 5€ → agent DEAD (permanent)
- No AI budget tracking (pas d'appels API AI)

## Important Notes
- `.env` changes require `docker compose down && docker compose up -d`
- French comments preferred
- Dashboard version: v1.0
- SQLite DB stored in `./data/calvalot.db` (Docker volume)
- USDC must be in **Spot wallet** on Binance
