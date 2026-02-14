"""Données marché simplifiées pour Calv-a-lot.

Uniquement les prix et le taux EUR/USDC (pas de sentiment, pas de news).
"""

import logging
import threading
import time
from decimal import Decimal

from config.coins import COIN_SYMBOLS

logger = logging.getLogger("calvalot.market")

_cache = {}
_cache_ttl = 60  # secondes
_cache_lock = threading.Lock()


class MarketData:
    def __init__(self, exchange):
        self.exchange = exchange

    def get_prices(self):
        """Prix courants de tous les coins trackés. Cache 60s, thread-safe."""
        now = time.time()
        with _cache_lock:
            if _cache.get("prices_ts") and now - _cache["prices_ts"] < _cache_ttl:
                return _cache["prices"]

        prices = self.exchange.get_all_prices(COIN_SYMBOLS)
        with _cache_lock:
            _cache["prices"] = prices
            _cache["prices_ts"] = time.time()
        return prices

    def get_eurusdc_rate(self):
        """Taux EUR/USDC live. Cache 60s, thread-safe.
        Returns Decimal (ex: 0.92 = 1 USDC vaut 0.92 EUR).
        """
        now = time.time()
        with _cache_lock:
            if _cache.get("eurusdc_ts") and now - _cache["eurusdc_ts"] < _cache_ttl:
                return _cache["eurusdc"]

        try:
            # EURUSDC = prix de 1 EUR en USDC (ex: 1.09)
            # Donc 1 USDC = 1 / EURUSDC EUR
            price = self.exchange.get_price("EURUSDC")
            if price and price > 0:
                rate = Decimal(1) / price
                with _cache_lock:
                    _cache["eurusdc"] = rate
                    _cache["eurusdc_ts"] = time.time()
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch EUR/USDC rate: {e}")

        # Fallback : dernier taux connu, sinon 0.92
        with _cache_lock:
            fallback = _cache.get("eurusdc", Decimal("0.92"))
        if fallback == Decimal("0.92"):
            logger.warning("Utilisation du taux EUR/USDC par défaut (0.92)")
        return fallback
