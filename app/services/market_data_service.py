import logging
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

from app.services.local_storage_service import LocalStorageService

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self):
        self.storage = LocalStorageService()
        self._cache_dir = "market/prices"

    def _yfinance_ticker(self, ticker: str) -> str:
        mapping = {
            "BTC": "BTC-USD",
            "ETH": "ETH-USD",
            "SOL": "SOL-USD",
            "BNB": "BNB-USD",
            "XRP": "XRP-USD",
            "ADA": "ADA-USD",
            "DOT": "DOT-USD",
            "DOGE": "DOGE-USD",
            "AVAX": "AVAX-USD",
            "LINK": "LINK-USD",
            "MATIC": "MATIC-USD",
            "ATOM": "ATOM-USD",
            "LTC": "LTC-USD",
            "USDT": "USDT-USD",
            "USDC": "USDC-USD",
            "IVVB11": "IVVB11.SA",
        }
        if ticker in mapping:
            return mapping[ticker]

        ticker_upper = ticker.upper()
        # BDRs and Brazilian stocks
        if ticker_upper.endswith(".SA") or ticker_upper.endswith("11") or ticker_upper.endswith("34"):
            if not ticker_upper.endswith(".SA"):
                return f"{ticker_upper}.SA"
            return ticker_upper
        if ticker_upper in ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3",
                             "WEGE3", "ELET3", "ELET6", "RENT3", "LREN3", "MGLU3",
                             "JBSS3", "SUZB3", "GGBP4", "CSNA3", "RAIL3", "CCRO3",
                             "EMBR3", "HAPV3", "RDOR3", "RADL3", "PRIO3", "EQTL3",
                             "B3SA3", "BPAC11", "CMIG4", "CPLE6", "SANB11", "TAEE11"]:
            return f"{ticker_upper}.SA"

        return ticker_upper

    def get_current_price(self, ticker: str) -> dict | None:
        cache_key = f"{self._cache_dir}/current_{ticker}.json"
        cached = self.storage.load_json(cache_key)
        if cached:
            cached_dt = datetime.fromisoformat(cached.get("updated_at", "").replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - cached_dt < timedelta(hours=1):
                return cached

        try:
            yf_ticker = self._yfinance_ticker(ticker)
            tk = yf.Ticker(yf_ticker)
            info = tk.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            currency = info.get("currency", "USD")
            name = info.get("shortName") or info.get("longName") or ticker

            if price is None:
                return None

            result = {
                "ticker": ticker,
                "price": price,
                "currency": currency,
                "name": name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.storage.save_json(cache_key, result)
            return result
        except Exception as e:
            logger.debug(f"Erro ao buscar preço de {ticker}: {e}")
            return None

    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d") -> dict | None:
        cache_key = f"{self._cache_dir}/history_{ticker}_{period}_{interval}.json"
        cached = self.storage.load_json(cache_key)
        if cached:
            cached_dt = datetime.fromisoformat(cached.get("cached_at", "").replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - cached_dt < timedelta(hours=4):
                return cached

        try:
            yf_ticker = self._yfinance_ticker(ticker)
            df = yf.download(yf_ticker, period=period, interval=interval, progress=False)
            if df.empty:
                return None

            df = df.reset_index()
            prices = []
            for _, row in df.iterrows():
                dt = row["Date"]
                if isinstance(dt, pd.Timestamp):
                    dt = dt.isoformat()
                prices.append({
                    "date": str(dt),
                    "open": float(row.get("Open", row.get("Close", 0))),
                    "high": float(row.get("High", row.get("Close", 0))),
                    "low": float(row.get("Low", row.get("Close", 0))),
                    "close": float(row.get("Close", 0)),
                    "volume": float(row.get("Volume", 0)),
                })

            result = {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "prices": prices,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            self.storage.save_json(cache_key, result)
            return result
        except Exception as e:
            logger.debug(f"Erro ao buscar histórico de {ticker}: {e}")
            return None
