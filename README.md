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

- **Proportionnel** : les trades sont en % du capital, pas en montant absolu
- **Autonome** : ton argent reste sur TON compte Binance, tes cles API ne quittent jamais ta machine
- **Auth HMAC** : les signaux sont signes cryptographiquement (SHA-256)
- **Setup web** : configuration via le navigateur, pas besoin de toucher au terminal

## Prerequis

- **Docker** et **Docker Compose** installes
- Un compte **Binance** avec des USDC dans le **Spot wallet**
- L'**URL** et le **code secret** (fournis par Alex)

## Installation

### 1. Cloner et lancer

```bash
git clone https://github.com/AlexandreFrancony/Calv-a-lot.git
cd Calv-a-lot
docker compose up -d
```

### 2. Configurer

Ouvre `http://<adresse-ip>:8080` dans ton navigateur. Un assistant de configuration te guide :

1. **Connexion** — entre l'URL du leader et le code secret (donnes par Alex)
2. **Binance** — entre tes cles API (le wizard verifie qu'elles fonctionnent)
3. **Budget** — choisis ton montant et le mode (simulation ou reel)

C'est tout ! Le bot demarre automatiquement apres la configuration.

> **Alternative** : tu peux aussi configurer via un fichier `.env` (voir `.env.example`). Les variables d'environnement ont priorite sur la config web.

## Modes de trading

| Mode | Comportement |
|------|-------------|
| `dry_run` | Simulation (aucun vrai ordre, parfait pour tester) |
| `live` | Vrais ordres Binance (**vrai argent !**) |

> **Commence TOUJOURS en simulation** pour verifier que tout fonctionne.

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

## Commandes utiles

```bash
# Demarrer
docker compose up -d

# Voir les logs en temps reel
docker compose logs -f

# Arreter
docker compose down

# Redemarrer
docker compose down && docker compose up -d
```

## Deploiement sur le meme serveur que Cash-a-lot

Si Calv-a-lot tourne sur le meme serveur Docker que Cash-a-lot, cree un fichier `docker-compose.override.yml` pour partager le reseau :

```yaml
services:
  follower:
    networks:
      - default
      - cashalot_network
networks:
  cashalot_network:
    external: true
```

Puis configure l'URL du leader comme `http://cashalot:8080` (reseau Docker interne).

## Auto-update

Calv-a-lot se met a jour automatiquement quand un nouveau commit est pousse sur le repo :

1. Cash-a-lot verifie la derniere version via l'API GitHub (toutes les 15 min)
2. Si la version du follower est differente, Cash-a-lot ajoute `update.required` au signal
3. Calv-a-lot detecte le flag et ecrit `UPDATE_REQUESTED` dans `/app/data/`
4. Le script `updater.sh` (cron toutes les 5 min) fait `git pull` + `docker compose up -d --build`

> **Prerequis** : `CALVALOT_REPO` et `GITHUB_TOKEN` doivent etre configures dans le `.env` de Cash-a-lot. Le cron est installe automatiquement par `start.sh`.

## Architecture technique

- **Python 3.11** + Flask + gunicorn (1 worker, 2 threads)
- **SQLite** en WAL mode (zero dependance externe)
- **Docker** : non-root user, no-new-privileges, 192MB RAM max
- **Polling** thread-based (pas de cron, pas d'APScheduler)
- **Setup web** : configuration via navigateur au premier lancement
- **Auto-update** via signal Cash-a-lot + cron `updater.sh`
- Pas d'appels a Claude AI (seul Cash-a-lot utilise l'IA)

## Troubleshooting

### Le dashboard affiche "Leader: Disconnected"
- Verifie que Cash-a-lot tourne (`docker ps | grep cashalot`)
- Verifie l'URL du leader dans ta config
- Verifie le code secret (doit correspondre a celui de Cash-a-lot)
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
