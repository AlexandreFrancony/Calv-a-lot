"""Logique de réplication des signaux Cash-a-lot.

Reçoit un signal du poller et exécute les mêmes trades
proportionnellement au capital local du follower.
"""

import logging
from decimal import Decimal

from config.settings import Settings
from app import models

logger = logging.getLogger("calvalot.follower")


class Follower:
    def __init__(self, exchange, market_data, budget_manager):
        self.exchange = exchange
        self.market = market_data
        self.budget_mgr = budget_manager
        self.is_simulated = Settings.TRADING_MODE == "dry_run"

    def execute_signal(self, signal):
        """Réplique un signal Cash-a-lot proportionnellement au capital local.

        Args:
            signal: dict avec actions, confidence, signal_id, portfolio_state

        Returns:
            dict avec status et nombre de trades exécutés
        """
        signal_id = signal.get("signal_id", "unknown")
        logger.info(f"=== Exécution signal {signal_id} ===")

        # Vérifier qu'on peut trader
        can_trade, reason = self.budget_mgr.can_trade()
        if not can_trade:
            logger.warning(f"Cannot trade: {reason}")
            models.update_signal_status(signal_id, "skipped", reason)
            return {"status": "skipped", "reason": reason, "trades_executed": 0}

        actions = signal.get("actions", [])
        if not actions:
            logger.info("Signal sans action (HOLD)")
            models.update_signal_status(signal_id, "executed")
            return {"status": "ok", "trades_executed": 0}

        # Calculer notre capital total
        prices = self.market.get_prices()
        cash_usdt = self._get_cash_balance()
        positions = models.get_positions()
        portfolio_value = self._calc_portfolio_value(positions, prices)
        total_value_usdt = cash_usdt + portfolio_value

        if total_value_usdt <= 0:
            logger.warning("Capital total = 0, impossible de trader")
            models.update_signal_status(signal_id, "skipped", "No capital")
            return {"status": "skipped", "reason": "No capital", "trades_executed": 0}

        # Exécuter chaque action
        executed = 0
        errors = []
        skips = []
        for action in actions:
            try:
                result = self._execute_action(
                    action, signal_id, prices, total_value_usdt, positions,
                )
                if result is None:
                    # Action ignorée (pct <= 0 ou échec exchange)
                    continue
                if isinstance(result, dict) and result.get("skipped"):
                    skips.append(result["reason"])
                elif result:
                    executed += 1
            except Exception as e:
                logger.error(f"Erreur exécution {action}: {e}")
                errors.append(str(e))

        # Sauver un snapshot
        eur_rate = self.market.get_eurusdc_rate()
        # Recalculer après les trades
        cash_usdt = self._get_cash_balance()
        positions = models.get_positions()
        portfolio_value = self._calc_portfolio_value(positions, prices)
        total_usdt = cash_usdt + portfolio_value
        total_eur = float(total_usdt * eur_rate)

        models.insert_snapshot(
            total_value_eur=total_eur,
            portfolio_value_usdt=float(portfolio_value),
            cash_usdt=float(cash_usdt),
        )

        # Vérifier survie
        self.budget_mgr.check_survival(total_eur)

        # Mettre à jour le status du signal
        if errors:
            models.update_signal_status(signal_id, "error", "; ".join(errors))
        elif executed == 0 and skips:
            # Toutes les actions ont été skippées — pas un vrai "executed"
            models.update_signal_status(signal_id, "skipped", "; ".join(skips))
        else:
            models.update_signal_status(signal_id, "executed")

        logger.info(f"=== Signal {signal_id}: {executed} trade(s), {len(skips)} skip(s) ===")
        return {"status": "ok", "trades_executed": executed}

    def _execute_action(self, action, signal_id, prices, total_value_usdt, positions):
        """Exécute une action individuelle du signal.

        L'action contient pct_of_capital (pourcentage du capital du leader).
        On applique ce même pourcentage à notre propre capital.
        """
        coin = action["coin"]
        side = action["action"]
        pct = action.get("pct_of_capital", 0)

        if pct <= 0:
            return None

        # Montant en USDC = pourcentage × notre capital
        amount_usdt = Decimal(str(pct)) * total_value_usdt

        if side == "BUY":
            return self._execute_buy(coin, amount_usdt, signal_id, prices, total_value_usdt, positions)
        elif side == "SELL":
            return self._execute_sell(coin, amount_usdt, signal_id, prices, positions)

        return None

    def _execute_buy(self, coin, amount_usdt, signal_id, prices, total_value_usdt, positions):
        """Exécute un achat. Le leader gère déjà le cap par position."""
        # Minimum Binance
        if amount_usdt < Decimal(str(Settings.MIN_ORDER_USDC)):
            reason = f"BUY {coin}: ${float(amount_usdt):.2f} < min ${Settings.MIN_ORDER_USDC}"
            logger.info(f"Skip {reason}")
            return {"skipped": True, "reason": reason}

        result = self.exchange.execute_market_buy(coin, float(amount_usdt))
        if not result:
            return None

        # Enregistrer le trade
        trade_id = models.insert_trade(
            coin=coin, action="BUY",
            amount_usdt=float(result["amount_usdt"]),
            price=float(result["price"]),
            quantity=float(result["quantity"]),
            fee_usdt=float(result.get("fee", 0)),
            signal_id=signal_id,
            is_simulated=result["simulated"],
        )

        # Mettre à jour la position
        self._update_position(coin, "BUY", result)

        logger.info(f"Trade #{trade_id}: BUY {coin} ${float(result['amount_usdt']):.2f}")
        return {"trade_id": trade_id, "coin": coin, "side": "BUY"}

    def _execute_sell(self, coin, amount_usdt, signal_id, prices, positions):
        """Exécute une vente."""
        pos = next((p for p in positions if p["coin"] == coin), None)
        if not pos or Decimal(str(pos["quantity"])) <= 0:
            reason = f"SELL {coin}: pas de position"
            logger.info(f"Skip {reason}")
            return {"skipped": True, "reason": reason}

        price = prices.get(coin)
        if not price or price == 0:
            reason = f"SELL {coin}: prix indisponible"
            logger.warning(f"Skip {reason}")
            return {"skipped": True, "reason": reason}

        qty_to_sell = amount_usdt / price
        available = Decimal(str(pos["quantity"]))
        if qty_to_sell > available:
            qty_to_sell = available

        # Minimum Binance
        sell_value = qty_to_sell * price
        if sell_value < Decimal(str(Settings.MIN_ORDER_USDC)):
            reason = f"SELL {coin}: ${float(sell_value):.2f} < min ${Settings.MIN_ORDER_USDC}"
            logger.info(f"Skip {reason}")
            return {"skipped": True, "reason": reason}

        result = self.exchange.execute_market_sell(coin, float(qty_to_sell))
        if not result:
            return None

        trade_id = models.insert_trade(
            coin=coin, action="SELL",
            amount_usdt=float(result["amount_usdt"]),
            price=float(result["price"]),
            quantity=float(result["quantity"]),
            fee_usdt=float(result.get("fee", 0)),
            signal_id=signal_id,
            is_simulated=result["simulated"],
        )

        self._update_position(coin, "SELL", result)

        logger.info(f"Trade #{trade_id}: SELL {coin} ${float(result['amount_usdt']):.2f}")
        return {"trade_id": trade_id, "coin": coin, "side": "SELL"}

    def _update_position(self, coin, side, result):
        """Met à jour une position après un trade."""
        pos = models.get_position(coin)
        qty = Decimal(str(result["quantity"]))
        price = Decimal(str(result["price"]))
        amount = Decimal(str(result["amount_usdt"]))

        if side == "BUY":
            if pos and Decimal(str(pos["quantity"])) > 0:
                old_qty = Decimal(str(pos["quantity"]))
                old_invested = Decimal(str(pos["total_invested_usdt"]))
                new_qty = old_qty + qty
                new_invested = old_invested + amount
                new_avg = new_invested / new_qty if new_qty > 0 else Decimal(0)
            else:
                new_qty = qty
                new_invested = amount
                new_avg = price
            models.upsert_position(coin, float(new_qty), float(new_avg), float(new_invested))

        elif side == "SELL":
            if pos:
                old_qty = Decimal(str(pos["quantity"]))
                old_invested = Decimal(str(pos["total_invested_usdt"]))
                new_qty = old_qty - qty
                if new_qty <= 0:
                    new_qty = Decimal(0)
                    new_invested = Decimal(0)
                    new_avg = Decimal(0)
                else:
                    ratio = new_qty / old_qty if old_qty > 0 else Decimal(0)
                    new_invested = old_invested * ratio
                    new_avg = Decimal(str(pos["avg_entry_price"]))
                models.upsert_position(coin, float(new_qty), float(new_avg), float(new_invested))

    def _get_cash_balance(self):
        """Solde USDC disponible."""
        if self.is_simulated:
            budget = models.get_budget()
            if not budget:
                return Decimal(0)
            # En dry_run : budget initial - investi + ventes - retraits
            eur_rate = self.market.get_eurusdc_rate()
            total_usdc = Decimal(str(budget["initial_total_eur"])) / eur_rate
            positions = models.get_positions()
            invested = sum(Decimal(str(p["total_invested_usdt"])) for p in positions)
            sells = self._get_total_sell_proceeds()
            withdrawals = Decimal(str(models.get_total_withdrawals()))
            return total_usdc - invested + sells - withdrawals

        # En live, solde réel Binance
        return self.exchange.get_account_balance("USDC")

    def _get_total_sell_proceeds(self):
        """Total USDC reçu des ventes (pour calcul cash dry_run)."""
        from app.db import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount_usdt), 0) FROM trades WHERE action = 'SELL'"
            )
            return Decimal(str(cur.fetchone()[0]))

    def _calc_portfolio_value(self, positions, prices):
        """Valeur totale des positions en USDC."""
        total = Decimal(0)
        for pos in positions:
            qty = Decimal(str(pos["quantity"]))
            if qty <= 0:
                continue
            price = prices.get(pos["coin"])
            if price:
                total += qty * price
        return total
