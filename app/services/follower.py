"""Logique de réplication des signaux Cash-a-lot.

V2 : rebalancing par allocation cible. Au lieu de répliquer les trades
individuels, le follower compare son allocation actuelle à l'allocation
cible du leader et exécute les trades nécessaires pour les aligner.
"""

import logging
from decimal import Decimal

from config.settings import Settings
from config.coins import COIN_SYMBOLS
from app import models

logger = logging.getLogger("calvalot.follower")


class Follower:
    def __init__(self, exchange, market_data, budget_manager):
        self.exchange = exchange
        self.market = market_data
        self.budget_mgr = budget_manager
        self.is_simulated = Settings.TRADING_MODE == "dry_run"

    def execute_signal(self, signal):
        """Point d'entrée : route vers v1 ou v2 selon la version du signal."""
        # Valider le signal avant exécution
        valid, reason = self._validate_signal(signal)
        if not valid:
            signal_id = signal.get("signal_id", "unknown")
            logger.warning(f"Signal {signal_id} rejeté: {reason}")
            models.update_signal_status(signal_id, "rejected", reason)
            return {"status": "rejected", "reason": reason, "trades_executed": 0}

        version = signal.get("version", 1)
        if version >= 2:
            return self._execute_signal_v2(signal)
        return self._execute_signal_v1(signal)

    def _validate_signal(self, signal):
        """Valide un signal avant exécution.

        Vérifie que les coins sont connus, les pourcentages valides,
        et l'allocation totale <= 1.0.
        """
        # Valider les actions (v1)
        for action in signal.get("actions", []):
            coin = action.get("coin", "")
            if coin and coin not in COIN_SYMBOLS:
                return False, f"Coin inconnu: {coin}"
            pct = action.get("pct_of_capital", 0)
            if not (0 <= pct <= 1):
                return False, f"pct_of_capital invalide: {pct}"

        # Valider le portfolio_state (v2)
        portfolio_state = signal.get("portfolio_state")
        if portfolio_state:
            positions = portfolio_state.get("positions", [])
            total_pct = 0
            for pos in positions:
                coin = pos.get("coin", "")
                if coin and coin not in COIN_SYMBOLS:
                    return False, f"Coin inconnu dans portfolio_state: {coin}"
                pct = pos.get("pct_of_portfolio", 0)
                if not (0 <= pct <= 1):
                    return False, f"pct_of_portfolio invalide: {pct}"
                total_pct += pct
            if total_pct > 1.05:  # 5% de tolérance pour arrondis
                return False, f"Allocation totale > 100%: {total_pct:.2%}"

        return True, ""

    # ================================================================
    # V2 — Rebalancing par allocation cible
    # ================================================================

    def _execute_signal_v2(self, signal):
        """Rebalance le portfolio pour coller à l'allocation du leader."""
        signal_id = signal.get("signal_id", "unknown")
        logger.info(f"=== Rebalancing signal {signal_id} (v2) ===")

        can_trade, reason = self.budget_mgr.can_trade()
        if not can_trade:
            logger.warning(f"Cannot trade: {reason}")
            models.update_signal_status(signal_id, "skipped", reason)
            return {"status": "skipped", "reason": reason, "trades_executed": 0}

        portfolio_state = signal.get("portfolio_state")
        if not portfolio_state:
            logger.warning("Signal v2 sans portfolio_state")
            models.update_signal_status(signal_id, "skipped", "no portfolio_state")
            return {"status": "skipped", "reason": "no portfolio_state", "trades_executed": 0}

        # État actuel
        prices = self.market.get_prices()
        positions = models.get_positions()
        cash = self._get_cash_balance()
        portfolio_value = self._calc_portfolio_value(positions, prices)
        total = cash + portfolio_value

        if total <= 0:
            logger.warning("Capital total = 0, impossible de rebalancer")
            models.update_signal_status(signal_id, "skipped", "No capital")
            return {"status": "skipped", "reason": "No capital", "trades_executed": 0}

        # Allocation actuelle (% par coin)
        current_alloc = {}
        for pos in positions:
            qty = Decimal(str(pos["quantity"]))
            price = prices.get(pos["coin"])
            if qty > 0 and price:
                current_alloc[pos["coin"]] = float(qty * price / total)

        # Allocation cible du leader
        target_alloc = {
            p["coin"]: p["pct_of_portfolio"]
            for p in portfolio_state.get("positions", [])
        }

        # Calculer les deltas
        all_coins = set(list(current_alloc.keys()) + list(target_alloc.keys()))
        sells = []
        buys = []

        for coin in all_coins:
            current_pct = current_alloc.get(coin, 0)
            target_pct = target_alloc.get(coin, 0)
            delta = target_pct - current_pct

            if abs(delta) < Settings.REBALANCE_THRESHOLD_PCT:
                continue

            amount_usdt = abs(delta) * float(total)
            if amount_usdt < Settings.MIN_ORDER_USDC:
                continue

            if delta < 0:
                sells.append({"coin": coin, "amount_usdt": Decimal(str(amount_usdt))})
            else:
                buys.append({"coin": coin, "amount_usdt": Decimal(str(amount_usdt))})

        if not sells and not buys:
            logger.info("Allocations alignées, aucun trade nécessaire")
            models.update_signal_status(signal_id, "executed")
            return {"status": "ok", "trades_executed": 0}

        logger.info(f"Rebalancing: {len(sells)} sell(s), {len(buys)} buy(s)")

        # Exécuter les SELL d'abord (libérer du cash)
        executed = 0
        skips = []
        errors = []

        for s in sells:
            try:
                result = self._execute_sell(
                    s["coin"], s["amount_usdt"], signal_id, prices, positions,
                )
                if result and not result.get("skipped"):
                    executed += 1
                elif result and result.get("skipped"):
                    skips.append(result["reason"])
            except Exception as e:
                logger.error(f"Erreur SELL {s['coin']}: {e}")
                errors.append(str(e))

        # Rafraîchir les positions après les ventes
        positions = models.get_positions()

        # Exécuter les BUY (re-check cash avant chaque)
        for b in buys:
            try:
                cash = self._get_cash_balance()
                amount = min(b["amount_usdt"], cash)
                if amount < Decimal(str(Settings.MIN_ORDER_USDC)):
                    reason = f"BUY {b['coin']}: cash insuffisant (${float(cash):.2f})"
                    logger.info(f"Skip {reason}")
                    skips.append(reason)
                    continue

                result = self._execute_buy(
                    b["coin"], amount, signal_id, prices,
                    total, positions,
                )
                if result and not result.get("skipped"):
                    executed += 1
                elif result and result.get("skipped"):
                    skips.append(result["reason"])
            except Exception as e:
                logger.error(f"Erreur BUY {b['coin']}: {e}")
                errors.append(str(e))

        # Snapshot post-rebalancing
        self._save_snapshot(prices)

        # Mettre à jour le status du signal
        if errors:
            models.update_signal_status(signal_id, "error", "; ".join(errors))
        elif executed == 0 and skips:
            models.update_signal_status(signal_id, "skipped", "; ".join(skips))
        else:
            models.update_signal_status(signal_id, "executed")

        logger.info(f"=== Signal {signal_id}: {executed} trade(s), {len(skips)} skip(s) ===")
        return {"status": "ok", "trades_executed": executed}

    # ================================================================
    # V1 — Ancien mode (réplication des actions individuelles)
    # ================================================================

    def _execute_signal_v1(self, signal):
        """Ancien mode : réplique les actions individuelles du signal."""
        signal_id = signal.get("signal_id", "unknown")
        logger.info(f"=== Exécution signal {signal_id} (v1) ===")

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

        prices = self.market.get_prices()
        cash_usdt = self._get_cash_balance()
        positions = models.get_positions()
        portfolio_value = self._calc_portfolio_value(positions, prices)
        total_value_usdt = cash_usdt + portfolio_value

        if total_value_usdt <= 0:
            logger.warning("Capital total = 0, impossible de trader")
            models.update_signal_status(signal_id, "skipped", "No capital")
            return {"status": "skipped", "reason": "No capital", "trades_executed": 0}

        executed = 0
        errors = []
        skips = []
        for action in actions:
            try:
                result = self._execute_action(
                    action, signal_id, prices, total_value_usdt, positions,
                )
                if result is None:
                    continue
                if isinstance(result, dict) and result.get("skipped"):
                    skips.append(result["reason"])
                elif result:
                    executed += 1
            except Exception as e:
                logger.error(f"Erreur exécution {action}: {e}")
                errors.append(str(e))

        self._save_snapshot(prices)

        if errors:
            models.update_signal_status(signal_id, "error", "; ".join(errors))
        elif executed == 0 and skips:
            models.update_signal_status(signal_id, "skipped", "; ".join(skips))
        else:
            models.update_signal_status(signal_id, "executed")

        logger.info(f"=== Signal {signal_id}: {executed} trade(s), {len(skips)} skip(s) ===")
        return {"status": "ok", "trades_executed": executed}

    def sync_to_leader(self, portfolio_state):
        """Sync initial via rebalancing v2.

        Construit un faux signal v2 à partir du portfolio_state
        et délègue au rebalancing.
        """
        logger.info("=== Sync initial sur le leader (via rebalancing v2) ===")
        fake_signal = {
            "version": 2,
            "signal_id": "initial_sync",
            "portfolio_state": portfolio_state,
            "confidence": 0,
            "reasoning": "Initial sync",
            "actions": [],
        }
        return self.execute_signal(fake_signal)

    # ================================================================
    # Exécution des trades (partagé v1/v2)
    # ================================================================

    def _execute_action(self, action, signal_id, prices, total_value_usdt, positions):
        """Exécute une action individuelle du signal (v1 uniquement)."""
        coin = action["coin"]
        side = action["action"]
        pct = action.get("pct_of_capital", 0)

        if pct <= 0:
            return None

        amount_usdt = Decimal(str(pct)) * total_value_usdt

        if side == "BUY":
            return self._execute_buy(coin, amount_usdt, signal_id, prices, total_value_usdt, positions)
        elif side == "SELL":
            return self._execute_sell(coin, amount_usdt, signal_id, prices, positions)

        return None

    def _execute_buy(self, coin, amount_usdt, signal_id, prices, total_value_usdt, positions):
        """Exécute un achat."""
        # Vérifier le cash disponible en simulation (évite le cash négatif)
        if self.is_simulated:
            available = self._get_cash_balance()
            if available < amount_usdt:
                if available >= Decimal(str(Settings.MIN_ORDER_USDC)):
                    logger.info(f"BUY {coin}: réduit ${float(amount_usdt):.2f} -> ${float(available):.2f} (cash dispo)")
                    amount_usdt = available
                else:
                    reason = f"BUY {coin}: cash insuffisant (${float(available):.2f} dispo, ${float(amount_usdt):.2f} voulu)"
                    logger.warning(f"Skip {reason}")
                    return {"skipped": True, "reason": reason}

        # Minimum Binance
        if amount_usdt < Decimal(str(Settings.MIN_ORDER_USDC)):
            reason = f"BUY {coin}: ${float(amount_usdt):.2f} < min ${Settings.MIN_ORDER_USDC}"
            logger.info(f"Skip {reason}")
            return {"skipped": True, "reason": reason}

        result = self.exchange.execute_market_buy(coin, float(amount_usdt))
        if not result:
            return None

        trade_id = models.insert_trade(
            coin=coin, action="BUY",
            amount_usdt=float(result["amount_usdt"]),
            price=float(result["price"]),
            quantity=float(result["quantity"]),
            fee_usdt=float(result.get("fee", 0)),
            signal_id=signal_id,
            is_simulated=result["simulated"],
        )

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

    # ================================================================
    # Helpers
    # ================================================================

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

    def _save_snapshot(self, prices):
        """Sauvegarde un snapshot du portfolio."""
        eur_rate = self.market.get_eurusdc_rate()
        cash = self._get_cash_balance()
        positions = models.get_positions()
        portfolio_value = self._calc_portfolio_value(positions, prices)
        total_usdt = cash + portfolio_value
        total_eur = float(total_usdt * eur_rate)

        models.insert_snapshot(
            total_value_eur=total_eur,
            portfolio_value_usdt=float(portfolio_value),
            cash_usdt=float(cash),
        )

        self.budget_mgr.check_survival(total_eur)

    def _get_cash_balance(self):
        """Solde USDC disponible."""
        if self.is_simulated:
            budget = models.get_budget()
            if not budget:
                return Decimal(0)
            # En dry_run : budget initial en USDC - achats + ventes - retraits
            eur_rate = self.market.get_eurusdc_rate()
            total_usdc = Decimal(str(budget["initial_total_eur"])) / eur_rate
            total_bought = self._get_total_trade_amount("BUY")
            total_sold = self._get_total_trade_amount("SELL")
            withdrawals = Decimal(str(models.get_total_withdrawals()))
            return total_usdc - total_bought + total_sold - withdrawals

        # En live, solde réel Binance
        return self.exchange.get_account_balance("USDC")

    def _get_total_trade_amount(self, action):
        """Total USDC dépensé (BUY) ou reçu (SELL) depuis les trades."""
        from app.db import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount_usdt), 0) FROM trades WHERE action = ?",
                (action,),
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
