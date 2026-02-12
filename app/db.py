"""Base de données SQLite pour Calv-a-lot.

Zéro dépendance externe — un simple fichier sur le volume Docker.
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager

from config.settings import Settings

logger = logging.getLogger("calvalot.db")

_local = threading.local()


def _get_conn():
    """Connexion SQLite thread-local (une par thread gunicorn)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(
            Settings.DB_PATH,
            check_same_thread=False,
        )
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


@contextmanager
def get_cursor():
    """Context manager pour obtenir un cursor avec auto-commit/rollback."""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = _get_conn()
    conn.executescript("""
        -- Budget simplifié (pas de budget AI)
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY,
            initial_total_eur REAL NOT NULL,
            total_deposited_eur REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Trades exécutés (réplication des signaux)
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coin TEXT NOT NULL,
            action TEXT NOT NULL,
            amount_usdt REAL NOT NULL,
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            fee_usdt REAL DEFAULT 0,
            signal_id TEXT,
            is_simulated INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Positions actuelles
        CREATE TABLE IF NOT EXISTS positions (
            coin TEXT PRIMARY KEY,
            quantity REAL NOT NULL DEFAULT 0,
            avg_entry_price REAL NOT NULL DEFAULT 0,
            total_invested_usdt REAL NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Signaux reçus de Cash-a-lot
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT UNIQUE NOT NULL,
            confidence REAL,
            reasoning TEXT,
            actions TEXT NOT NULL,
            portfolio_state TEXT,
            status TEXT DEFAULT 'received',
            error_message TEXT,
            received_at TEXT DEFAULT (datetime('now')),
            executed_at TEXT
        );

        -- Snapshots pour le graphique
        CREATE TABLE IF NOT EXISTS budget_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_value_eur REAL,
            portfolio_value_usdt REAL,
            cash_usdt REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Retraits
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount_eur_requested REAL,
            amount_usdt_sold REAL,
            amount_eur_received REAL,
            eurusdc_rate REAL,
            positions_sold TEXT,
            status TEXT DEFAULT 'completed',
            is_simulated INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Index pour les requêtes fréquentes
        CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_signals_signal_id ON signals(signal_id);
        CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON budget_snapshots(created_at DESC);
    """)
    logger.info(f"Database initialized: {Settings.DB_PATH}")
