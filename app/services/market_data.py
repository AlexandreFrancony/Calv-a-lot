"""Données marché simplifiées pour Calv-a-lot.

Uniquement les prix et le taux EUR/USDC (pas de sentiment, pas de news).
"""

import logging
import time
from decimal import Decimal

from config.coins import COIN_SYMBOLS

logger = logging.getLogger("calvalot.market")

_cache = {}
_cache_ttl = 60  # secondes


class MarketData:
    def __init__(self, exchange):
        self.exchange = exchange

    def get_prices(self):
        """Prix courants de tous les coins trackés. Cache 60s."""
        now = time.time()
        if _cache.get("prices_ts") and now - _cache["prices_ts"] < _cache_ttl:
            return _cache["prices"]

        prices = self.exchange.get_all_prices(COIN_SYMBOLS)
        _cache["prices"] = prices
        _cache["prices_ts"] = now
        return prices

    def get_eurusdc_rate(self):
        """Taux EUR/USDC live. Cache 60s.
        Returns Decimal (ex: 0.92 = 1 USDC vaut 0.92 EUR).
        """
        now = time.time()
        if _cache.get("eurusdc_ts") and now - _cache["eurusdc_ts"] < _cache_ttl:
            return _cache["eurusdc"]

        try:
            # EURUSDC = prix de 1 EUR en USDC (ex: 1.09)
            # Donc 1 USDC = 1 / EURUSDC EUR
            price = self.exchange.get_price("EURUSDC")
            if price and price > 0:
                rate = Decimal(1) / price
                _cache["eurusdc"] = rate
                _cache["eurusdc_ts"] = now
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch EUR/USDC rate: {e}")

        # Fallback
        return _cache.get("eurusdc", Decimal("0.92"))
