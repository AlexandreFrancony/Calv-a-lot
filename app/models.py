"""Requêtes SQL pour Calv-a-lot (SQLite)."""

import json
import logging

from app.db import get_cursor

logger = logging.getLogger("calvalot.models")


# ── Budget ──────────────────────────────────────────────

def get_budget():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM budget ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)


def create_budget(initial_total_eur):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO budget (initial_total_eur, total_deposited_eur)
               VALUES (?, ?)""",
            (initial_total_eur, initial_total_eur),
        )
        return cur.lastrowid


def update_budget_status(budget_id, status):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE budget SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, budget_id),
        )


def update_budget_deposited(budget_id, total_deposited_eur):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE budget SET total_deposited_eur = ?, updated_at = datetime('now') WHERE id = ?",
            (total_deposited_eur, budget_id),
        )


# ── Trades ──────────────────────────────────────────────

def insert_trade(coin, action, amount_usdt, price, quantity, fee_usdt=0,
                 signal_id=None, is_simulated=True):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO trades (coin, action, amount_usdt, price, quantity,
                                   fee_usdt, signal_id, is_simulated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (coin, action, amount_usdt, price, quantity, fee_usdt,
             signal_id, 1 if is_simulated else 0),
        )
        return cur.lastrowid


def get_recent_trades(limit=20):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


# ── Positions ───────────────────────────────────────────

def get_positions():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions ORDER BY coin")
        return [dict(row) for row in cur.fetchall()]


def get_position(coin):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM positions WHERE coin = ?", (coin,))
        row = cur.fetchone()
        return dict(row) if row else None


def upsert_position(coin, quantity, avg_entry_price, total_invested_usdt):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO positions (coin, quantity, avg_entry_price, total_invested_usdt)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (coin) DO UPDATE SET
                   quantity = excluded.quantity,
                   avg_entry_price = excluded.avg_entry_price,
                   total_invested_usdt = excluded.total_invested_usdt,
                   updated_at = datetime('now')""",
            (coin, quantity, avg_entry_price, total_invested_usdt),
        )


# ── Signaux ─────────────────────────────────────────────

def insert_signal(signal_id, confidence, reasoning, actions, portfolio_state,
                  status="received"):
    with get_cursor() as cur:
        cur.execute(
            """INSERT OR IGNORE INTO signals
               (signal_id, confidence, reasoning, actions, portfolio_state, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (signal_id, confidence, reasoning,
             json.dumps(actions), json.dumps(portfolio_state), status),
        )
        return cur.lastrowid


def signal_exists(signal_id):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM signals WHERE signal_id = ?", (signal_id,))
        return cur.fetchone() is not None


def update_signal_status(signal_id, status, error_message=None):
    with get_cursor() as cur:
        if status == "executed":
            cur.execute(
                """UPDATE signals SET status = ?, executed_at = datetime('now')
                   WHERE signal_id = ?""",
                (status, signal_id),
            )
        else:
            cur.execute(
                "UPDATE signals SET status = ?, error_message = ? WHERE signal_id = ?",
                (status, error_message, signal_id),
            )


def get_recent_signals(limit=20):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM signals ORDER BY received_at DESC LIMIT ?",
            (limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            if row.get("actions"):
                row["actions"] = json.loads(row["actions"])
            if row.get("portfolio_state"):
                row["portfolio_state"] = json.loads(row["portfolio_state"])
        return rows


def get_last_signal_id():
    """Retourne le signal_id du dernier signal traité."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT signal_id FROM signals ORDER BY received_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        return row["signal_id"] if row else None


# ── Budget Snapshots ───────────────────────────────────

def insert_snapshot(total_value_eur, portfolio_value_usdt, cash_usdt):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO budget_snapshots (total_value_eur, portfolio_value_usdt, cash_usdt)
               VALUES (?, ?, ?)""",
            (total_value_eur, portfolio_value_usdt, cash_usdt),
        )


def get_snapshots(limit=1440, hours=None):
    with get_cursor() as cur:
        if hours:
            cur.execute(
                """SELECT * FROM budget_snapshots
                   WHERE created_at > datetime('now', ? || ' hours')
                   ORDER BY created_at DESC LIMIT ?""",
                (f"-{hours}", limit),
            )
        else:
            cur.execute(
                "SELECT * FROM budget_snapshots ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in cur.fetchall()]


# ── Withdrawals ────────────────────────────────────────

def insert_withdrawal(amount_eur_requested, amount_usdt_sold=0,
                      amount_eur_received=0, eurusdc_rate=None,
                      positions_sold=None, status="completed", is_simulated=True):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO withdrawals
               (amount_eur_requested, amount_usdt_sold, amount_eur_received,
                eurusdc_rate, positions_sold, status, is_simulated)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (amount_eur_requested, amount_usdt_sold, amount_eur_received,
             eurusdc_rate, json.dumps(positions_sold or []), status,
             1 if is_simulated else 0),
        )
        return cur.lastrowid


def get_withdrawals(limit=50):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM withdrawals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            if row.get("positions_sold"):
                row["positions_sold"] = json.loads(row["positions_sold"])
        return rows


def get_total_withdrawals():
    """Total USDC retiré."""
    with get_cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(amount_usdt_sold), 0) FROM withdrawals")
        return cur.fetchone()[0]


# ── Cleanup ────────────────────────────────────────────

def cleanup_old_snapshots(days=30):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM budget_snapshots WHERE created_at < datetime('now', ? || ' days')",
            (f"-{days}",),
        )
        deleted = cur.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old snapshots")
        return deleted
