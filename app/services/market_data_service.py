import logging
import os
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests
import yfinance as yf

from app.services.local_storage_service import LocalStorageService

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self):
        self.storage = LocalStorageService()
        self._cache_dir = "market/prices"
        self._brapi_base_url = "https://brapi.dev/api/v2"
        self._brapi_token = os.environ.get("BRAPI_TOKEN", "").strip()

    def _brapi_headers(self) -> dict[str, str]:
        headers = {"User-Agent": "Operum/1.0"}
        if self._brapi_token:
            headers["Authorization"] = f"Bearer {self._brapi_token}"
        return headers

    def _brapi_symbol(self, ticker: str) -> str:
        return ticker.upper().replace(".SA", "")

    def _is_brapi_candidate(self, ticker: str) -> bool:
        ticker_upper = ticker.upper().replace(".SA", "")
        crypto = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOT", "DOGE", "AVAX", "LINK", "MATIC", "ATOM", "LTC", "USDT", "USDC"}
        return ticker_upper not in crypto and ticker_upper != "SP500"

    def _extract_brapi_results(self, payload: dict) -> list[dict]:
        for key in ("results", "stocks", "fiis", "indexes"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return self._extract_brapi_results(data)
        return []

    def _extract_brapi_price(self, item: dict) -> float | None:
        for key in ("regularMarketPrice", "price", "close", "currentPrice"):
            value = item.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None

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
            "IBOV": "^BVSP",
            "SP500": "^GSPC",
            "IFIX": "IFIX.SA",
        }
        if ticker in mapping:
            return mapping[ticker]

        ticker_upper = ticker.upper()
        if ticker_upper.endswith(".SA"):
            return ticker_upper
        if ticker_upper.endswith(("11", "34", "39")):
            return f"{ticker_upper}.SA"
        if ticker_upper in [
            "PETR4", "PETR3", "VALE3", "ITUB4", "ITUB3", "BBDC4", "BBDC3", "BBAS3",
            "ABEV3", "WEGE3", "ELET3", "ELET6", "RENT3", "LREN3", "MGLU3", "JBSS3",
            "SUZB3", "GGBP4", "CSNA3", "RAIL3", "CCRO3", "EMBR3", "HAPV3", "RDOR3",
            "RADL3", "PRIO3", "EQTL3", "B3SA3", "BPAC11", "CMIG4", "CPLE6", "SANB11",
            "TAEE11",
        ]:
            return f"{ticker_upper}.SA"

        return ticker_upper

    def _fetch_brapi_current_price(self, ticker: str) -> dict | None:
        if not self._is_brapi_candidate(ticker):
            return None

        symbol = self._brapi_symbol(ticker)
        try:
            response = requests.get(
                f"{self._brapi_base_url}/stocks/quote",
                params={"symbols": symbol},
                headers=self._brapi_headers(),
                timeout=8,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            results = self._extract_brapi_results(response.json())
            if not results:
                return None

            item = results[0]
            item_data = item.get("data") if isinstance(item.get("data"), dict) else item
            price = self._extract_brapi_price(item_data)
            if price is None:
                return None

            return {
                "ticker": ticker,
                "price": price,
                "currency": item_data.get("currency") or "BRL",
                "name": item_data.get("shortName") or item_data.get("longName") or item_data.get("name") or ticker,
                "source": "brapi",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.debug(f"Erro ao buscar preco na brapi para {ticker}: {exc}")
            return None

    def _fetch_yfinance_current_price(self, ticker: str) -> dict | None:
        try:
            tk = yf.Ticker(self._yfinance_ticker(ticker))
            info = tk.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            if price is None:
                return None

            return {
                "ticker": ticker,
                "price": float(price),
                "currency": info.get("currency", "USD"),
                "name": info.get("shortName") or info.get("longName") or ticker,
                "source": "yfinance",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.debug(f"Erro ao buscar preco no Yahoo Finance para {ticker}: {exc}")
            return None

    def get_current_price(self, ticker: str) -> dict | None:
        cache_key = f"{self._cache_dir}/current_{ticker}.json"
        cached = self.storage.load_json(cache_key)
        if cached:
            cached_dt = datetime.fromisoformat(cached.get("updated_at", "").replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - cached_dt < timedelta(hours=1):
                return cached

        result = self._fetch_brapi_current_price(ticker) or self._fetch_yfinance_current_price(ticker)
        if result:
            self.storage.save_json(cache_key, result)
            return result
        return None

    def _extract_brapi_history_points(self, item: dict) -> list[dict]:
        for key in ("historicalDataPrice", "prices", "historical", "data"):
            value = item.get(key)
            if isinstance(value, list):
                return value
        return []

    def _fetch_brapi_history(self, ticker: str, period: str, interval: str) -> dict | None:
        if not self._is_brapi_candidate(ticker):
            return None

        symbol = self._brapi_symbol(ticker)
        try:
            response = requests.get(
                f"{self._brapi_base_url}/stocks/historical",
                params={"symbols": symbol, "range": period, "interval": interval},
                headers=self._brapi_headers(),
                timeout=10,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            results = self._extract_brapi_results(response.json())
            if not results:
                return None

            prices = []
            item = results[0]
            item_data = item.get("data") if isinstance(item.get("data"), dict) else item
            for point in self._extract_brapi_history_points(item_data):
                close = point.get("close") or point.get("regularMarketPrice")
                if close is None:
                    continue
                date_value = point.get("date") or point.get("pricedAt") or point.get("updatedAt")
                if isinstance(date_value, (int, float)):
                    date_value = datetime.fromtimestamp(date_value, timezone.utc).date().isoformat()
                prices.append({
                    "date": str(date_value),
                    "open": float(point.get("open", close) or close),
                    "high": float(point.get("high", close) or close),
                    "low": float(point.get("low", close) or close),
                    "close": float(close),
                    "volume": float(point.get("volume", 0) or 0),
                })

            if not prices:
                return None

            return {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "prices": prices,
                "source": "brapi",
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.debug(f"Erro ao buscar historico na brapi para {ticker}: {exc}")
            return None

    def _fetch_yfinance_history(self, ticker: str, period: str, interval: str) -> dict | None:
        try:
            df = yf.download(self._yfinance_ticker(ticker), period=period, interval=interval, progress=False)
            if df.empty:
                return None

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            numeric_cols = [col for col in ["Open", "High", "Low", "Close", "Volume"] if col in df.columns]
            if numeric_cols:
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
                df = df.dropna(subset=["Close"])
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

            return {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "prices": prices,
                "source": "yfinance",
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.debug(f"Erro ao buscar historico no Yahoo Finance para {ticker}: {exc}")
            return None

    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d") -> dict | None:
        cache_key = f"{self._cache_dir}/history_{ticker}_{period}_{interval}.json"
        cached = self.storage.load_json(cache_key)
        if cached:
            cached_dt = datetime.fromisoformat(cached.get("cached_at", "").replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - cached_dt < timedelta(hours=4):
                return cached

        result = self._fetch_brapi_history(ticker, period, interval) or self._fetch_yfinance_history(ticker, period, interval)
        if result:
            self.storage.save_json(cache_key, result)
            return result
        return None
