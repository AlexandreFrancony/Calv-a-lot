"""Client Binance pour Calv-a-lot.

Copie du client Cash-a-lot : même logique d'exécution des ordres,
même simulation dry_run avec slippage réaliste.
"""

import logging
import math
from decimal import Decimal

from binance.client import Client
from binance.exceptions import BinanceAPIException

from config.settings import Settings

logger = logging.getLogger("calvalot.exchange")

# Timeout réseau Binance
_BINANCE_TIMEOUT = 15  # secondes

# stepSize par paire — nombre de décimales autorisées par Binance pour la quantité
# Source : GET /api/v3/exchangeInfo → filters LOT_SIZE → stepSize
_STEP_DECIMALS = {
    "BTCUSDC": 5,   # stepSize 0.00001
    "ETHUSDC": 4,   # stepSize 0.0001
    "BNBUSDC": 3,   # stepSize 0.001
    "SOLUSDC": 3,   # stepSize 0.001
    "XRPUSDC": 1,   # stepSize 0.1
}


def _truncate_qty(symbol: str, qty: float) -> str:
    """Tronque la quantité au stepSize Binance (arrondi vers le bas)."""
    decimals = _STEP_DECIMALS.get(symbol, 8)
    factor = 10 ** decimals
    truncated = math.floor(qty * factor) / factor
    return f"{truncated:.{decimals}f}"


class ExchangeClient:
    def __init__(self):
        self.testnet = Settings.BINANCE_TESTNET
        self.trading_mode = Settings.TRADING_MODE

        client_kwargs = {
            "requests_params": {"timeout": _BINANCE_TIMEOUT},
        }

        if self.testnet:
            self.client = Client(
                Settings.BINANCE_API_KEY,
                Settings.BINANCE_API_SECRET,
                testnet=True,
                **client_kwargs,
            )
            logger.info("Binance client initialized (TESTNET)")
        else:
            self.client = Client(
                Settings.BINANCE_API_KEY,
                Settings.BINANCE_API_SECRET,
                **client_kwargs,
            )
            logger.info("Binance client initialized (PRODUCTION)")

    def get_price(self, symbol):
        """Prix courant d'un symbole."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return Decimal(ticker["price"])
        except BinanceAPIException as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    def get_all_prices(self, symbols):
        """Prix de plusieurs symboles."""
        try:
            tickers = self.client.get_all_tickers()
            ticker_map = {t["symbol"]: Decimal(t["price"]) for t in tickers}
            return {s: ticker_map.get(s) for s in symbols}
        except BinanceAPIException as e:
            logger.error(f"Failed to get prices: {e}")
            return {}

    def execute_market_buy(self, symbol, quote_amount_usdt):
        """Exécuter un achat market."""
        if self.trading_mode == "dry_run":
            return self._simulate_buy(symbol, quote_amount_usdt)

        try:
            order = self.client.order_market_buy(
                symbol=symbol,
                quoteOrderQty=str(quote_amount_usdt),
            )
            logger.info(f"BUY executed: {symbol} for {quote_amount_usdt} USDC")
            return {
                "order_id": order["orderId"],
                "symbol": symbol,
                "side": "BUY",
                "quantity": Decimal(order["executedQty"]),
                "price": Decimal(order["fills"][0]["price"]) if order["fills"] else Decimal(0),
                "amount_usdt": Decimal(order["cummulativeQuoteQty"]),
                "fee": sum(Decimal(f["commission"]) for f in order.get("fills", [])),
                "simulated": False,
            }
        except BinanceAPIException as e:
            logger.error(f"BUY failed for {symbol}: {e}")
            return None

    def execute_market_sell(self, symbol, quantity):
        """Exécuter une vente market."""
        if self.trading_mode == "dry_run":
            return self._simulate_sell(symbol, quantity)

        try:
            order = self.client.order_market_sell(
                symbol=symbol,
                quantity=_truncate_qty(symbol, quantity),
            )
            logger.info(f"SELL executed: {symbol} qty {quantity}")
            return {
                "order_id": order["orderId"],
                "symbol": symbol,
                "side": "SELL",
                "quantity": Decimal(order["executedQty"]),
                "price": Decimal(order["fills"][0]["price"]) if order["fills"] else Decimal(0),
                "amount_usdt": Decimal(order["cummulativeQuoteQty"]),
                "fee": sum(Decimal(f["commission"]) for f in order.get("fills", [])),
                "simulated": False,
            }
        except BinanceAPIException as e:
            logger.error(f"SELL failed for {symbol}: {e}")
            return None

    def convert_usdc_to_eur(self, amount_usdc):
        """Convertir USDC en EUR via EURUSDC."""
        if self.trading_mode == "dry_run":
            return self._simulate_usdc_to_eur(amount_usdc)

        try:
            order = self.client.order_market_buy(
                symbol="EURUSDC",
                quoteOrderQty=str(amount_usdc),
            )
            eur_received = Decimal(order["executedQty"])
            usdc_spent = Decimal(order["cummulativeQuoteQty"])
            rate = eur_received / usdc_spent if usdc_spent > 0 else Decimal(0)
            logger.info(f"USDC→EUR: {usdc_spent} USDC → {eur_received} EUR (rate {float(rate):.4f})")
            return {
                "eur_received": eur_received,
                "usdt_spent": usdc_spent,
                "rate": rate,
                "simulated": False,
            }
        except BinanceAPIException as e:
            logger.error(f"USDC→EUR conversion failed: {e}")
            return None

    def _simulate_buy(self, symbol, quote_amount_usdt):
        """Simulation achat avec slippage réaliste."""
        price = self.get_price(symbol)
        if price is None or price == 0:
            return None
        slippage = self._get_slippage(symbol)
        fill_price = price * (Decimal(1) + slippage)
        quantity = Decimal(str(quote_amount_usdt)) / fill_price
        fee = Decimal(str(quote_amount_usdt)) * Decimal("0.001")
        logger.info(f"[DRY RUN] BUY {symbol}: {quantity:.8f} @ {fill_price} = {quote_amount_usdt} USDC")
        return {
            "order_id": None,
            "symbol": symbol,
            "side": "BUY",
            "quantity": quantity,
            "price": fill_price,
            "amount_usdt": Decimal(str(quote_amount_usdt)),
            "fee": fee,
            "simulated": True,
        }

    def _simulate_sell(self, symbol, quantity):
        """Simulation vente avec slippage réaliste."""
        price = self.get_price(symbol)
        if price is None or price == 0:
            return None
        slippage = self._get_slippage(symbol)
        fill_price = price * (Decimal(1) - slippage)
        amount_usdt = Decimal(str(quantity)) * fill_price
        fee = amount_usdt * Decimal("0.001")
        logger.info(f"[DRY RUN] SELL {symbol}: {quantity:.8f} @ {fill_price} = {amount_usdt:.4f} USDC")
        return {
            "order_id": None,
            "symbol": symbol,
            "side": "SELL",
            "quantity": Decimal(str(quantity)),
            "price": fill_price,
            "amount_usdt": amount_usdt,
            "fee": fee,
            "simulated": True,
        }

    def _simulate_usdc_to_eur(self, amount_usdc):
        """Simulation conversion USDC→EUR."""
        eurusdc_price = self.get_price("EURUSDC")
        if eurusdc_price is None or eurusdc_price == 0:
            return None
        slippage = Decimal("0.0002")
        fill_price = eurusdc_price * (Decimal(1) + slippage)
        eur_received = Decimal(str(amount_usdc)) / fill_price
        usdc_spent = Decimal(str(amount_usdc))
        rate = eur_received / usdc_spent if usdc_spent > 0 else Decimal(0)
        logger.info(f"[DRY RUN] USDC→EUR: {amount_usdc} USDC → {eur_received:.4f} EUR")
        return {
            "eur_received": eur_received,
            "usdt_spent": usdc_spent,
            "rate": rate,
            "simulated": True,
        }

    @staticmethod
    def _get_slippage(symbol):
        """Slippage réaliste selon la liquidité."""
        high_liquidity = ("BTCUSDC", "ETHUSDC")
        if symbol in high_liquidity:
            return Decimal("0.0002")  # 0.02%
        return Decimal("0.0005")  # 0.05%

    def get_account_balance(self, asset="USDC"):
        """Solde du compte pour un asset."""
        try:
            account = self.client.get_account()
            for balance in account["balances"]:
                if balance["asset"] == asset:
                    return Decimal(balance["free"])
            return Decimal(0)
        except BinanceAPIException as e:
            logger.error(f"Failed to get balance for {asset}: {e}")
            return Decimal(0)
