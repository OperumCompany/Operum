from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.ml.forecasting import BaselineForecaster
from app.ml.inference import VersionedForecaster
from app.services.llm_service import LLMService
from app.services.market_data_service import MarketDataService
from app.services.news_fusion_service import NewsFusionService
from app.services.prediction_repository import PredictionRepository


class PredictiveAnalysisService:
    def __init__(
        self,
        *,
        repository: PredictionRepository | None = None,
        market: MarketDataService | None = None,
        news_provider=None,
        forecaster=None,
        llm: LLMService | None = None,
        fusion: NewsFusionService | None = None,
    ):
        self.repository = repository or PredictionRepository()
        self.market = market or MarketDataService()
        if news_provider is None:
            from app.services.asset_analysis_service import AssetAnalysisService

            news_provider = AssetAnalysisService()
        self.news_provider = news_provider
        self.forecaster = forecaster or VersionedForecaster(self.repository)
        self.llm = llm or LLMService()
        self.fusion = fusion or NewsFusionService()

    @staticmethod
    def _deterministic_message(payload: dict) -> dict:
        direction_text = {"alta": "viés de alta", "queda": "viés de queda", "estabilidade": "tendência de estabilidade"}
        horizon_names = {"1m": "um mês", "2m": "dois meses", "3m": "três meses"}
        by_horizon = {}
        for key, horizon in payload["horizons"].items():
            confidence = horizon["confidence"]["label"]
            caution = (
                "A faixa é mais ampla e os cenários devem ser acompanhados com cautela."
                if confidence == "baixa"
                else "Os cenários ainda podem mudar com novos preços e notícias."
            )
            by_horizon[key] = (
                f"Para {horizon_names[key]}, a leitura aponta {direction_text[horizon['direction']]}. {caution}"
            )
        return {
            "summary": "A análise combina comportamento do ativo, volatilidade e notícias recentes em cenários, sem representar promessa de resultado.",
            "by_horizon": by_horizon,
            "confidence_note": "Confiança baixa amplia a faixa de resultados, mas não elimina a análise.",
        }

    @staticmethod
    def _valid_llm_message(message: dict | None) -> bool:
        if not isinstance(message, dict):
            return False
        if not isinstance(message.get("summary"), str) or not isinstance(message.get("confidence_note"), str):
            return False
        by_horizon = message.get("by_horizon")
        if not isinstance(by_horizon, dict) or set(by_horizon) != {"1m", "2m", "3m"}:
            return False
        if not all(isinstance(value, str) and value.strip() for value in by_horizon.values()):
            return False
        text = json.dumps(message, ensure_ascii=False).lower()
        blocked = (
            "compre", "comprar", "venda", "vender", "garantia", "garantido",
            "lucro certo", "previsibilidade insuficiente",
        )
        return not any(term in text for term in blocked) and re.search(r"\d", text) is None

    def _friendly_message(self, payload: dict) -> dict:
        deterministic = self._deterministic_message(payload)
        if not getattr(self.llm, "enabled", False):
            return deterministic
        refined = self.llm.chat_json(
            (
                "Reescreva a análise em português brasileiro claro. Não inclua números, preços, percentuais, "
                "recomendação de compra/venda ou promessa. Responda no schema recebido e preserve a incerteza."
            ),
            {
                "ticker": payload["ticker"],
                "directions": {key: value["direction"] for key, value in payload["horizons"].items()},
                "confidence": {key: value["confidence"]["label"] for key, value in payload["horizons"].items()},
                "dominant_news_signal": payload.get("news_signal", {}).get("signal", 0.0),
                "required_schema": deterministic,
            },
            temperature=0.1,
            max_tokens=500,
        )
        return refined if self._valid_llm_message(refined) else deterministic

    @staticmethod
    def _sync_prices_and_scenarios(horizon: dict, last_price: float) -> dict:
        result = dict(horizon)
        returns = result["return_range"]
        prices = {
            key: round(max(0.01, last_price * (1 + float(returns[key]))), 2)
            for key in ("adverse", "base", "favorable")
        }
        result["price_range"] = prices
        result["scenarios"] = {
            "adverse": f"O cenário adverso considera aproximação de R$ {prices['adverse']:.2f}.",
            "base": f"O cenário-base considera aproximação de R$ {prices['base']:.2f}.",
            "favorable": f"O cenário favorável considera aproximação de R$ {prices['favorable']:.2f}.",
        }
        return result

    @staticmethod
    def _materially_changed(previous: dict | None, current: dict) -> bool:
        if not previous:
            return True
        for key in ("1m", "2m", "3m"):
            old = previous.get("horizons", {}).get(key, {})
            new = current.get("horizons", {}).get(key, {})
            if not old or not new:
                return True
            if abs(float(old.get("expected_return", 0)) - float(new.get("expected_return", 0))) >= 0.005:
                return True
            if old.get("direction") != new.get("direction"):
                return True
            if old.get("confidence", {}).get("label") != new.get("confidence", {}).get("label"):
                return True
            old_width = float(old.get("return_range", {}).get("favorable", 0)) - float(old.get("return_range", {}).get("adverse", 0))
            new_width = float(new.get("return_range", {}).get("favorable", 0)) - float(new.get("return_range", {}).get("adverse", 0))
            if abs(old_width - new_width) >= 0.01:
                return True
        old_signal = previous.get("news_signal", {})
        new_signal = current.get("news_signal", {})
        for key, threshold in (("impact", 0.10), ("novelty", 0.20), ("disagreement", 0.15)):
            if abs(float(old_signal.get(key, 0)) - float(new_signal.get(key, 0))) >= threshold:
                return True
        old_material_sources = {
            item.get("id")
            for item in previous.get("sources", [])
            if float(item.get("impact_score", 0)) >= 0.70
        }
        new_material_sources = {
            item.get("id")
            for item in current.get("sources", [])
            if float(item.get("impact_score", 0)) >= 0.70
        }
        if old_material_sources != new_material_sources:
            return True
        return False

    def generate(self, ticker: str, asset_class: str, *, activate: bool = True) -> dict:
        ticker = ticker.upper()
        history = self.market.get_history(ticker, period="1y", interval="1d")
        if not history or not history.get("prices"):
            active = self.repository.get_active_snapshot(ticker)
            if active:
                return active["payload"]
            raise ValueError(f"Sem histórico de preço para {ticker}")
        market = pd.DataFrame(history["prices"])
        market["ticker"] = ticker
        market["asset_class"] = asset_class
        context = self.market.get_external_context(period="1y") if hasattr(self.market, "get_external_context") else None
        macro_path = Path(self.repository.storage.base_dir) / "macro" / "releases.parquet"
        macro_releases = pd.read_parquet(macro_path) if macro_path.exists() else None
        try:
            forecast = self.forecaster.forecast(
                ticker,
                asset_class,
                market,
                context=context,
                macro_releases=macro_releases,
            )
        except TypeError as exc:
            if "unexpected keyword" not in str(exc):
                raise
            forecast = self.forecaster.forecast(ticker, asset_class, market)
        news = self.news_provider.get_related_news(ticker, limit=25, days_back=120)
        signal = self.fusion.aggregate(news)
        last_price = float(pd.to_numeric(market["close"], errors="coerce").dropna().iloc[-1])
        horizons = {
            key: self._sync_prices_and_scenarios(self.fusion.apply_to_horizon(value, signal), last_price)
            for key, value in forecast["horizons"].items()
        }
        payload = {
            **forecast,
            "analysis_id": str(uuid.uuid4()),
            "ticker": ticker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "last_price": last_price,
            "historical_series": [
                {"date": str(row["date"]), "value": round(float(row["close"]), 4)}
                for _, row in market.tail(252).iterrows()
                if pd.notna(row.get("close"))
            ],
            "horizons": horizons,
            "news_signal": signal.as_dict(),
            "sources": news,
        }
        payload["friendly_message"] = self._friendly_message(payload)
        active = self.repository.get_active_snapshot(ticker)
        previous = active.get("payload") if active else None
        if activate and not self._materially_changed(previous, payload):
            return previous
        fingerprint = self.fusion.fingerprint(news)
        snapshot = self.repository.save_snapshot(
            ticker=ticker,
            payload=payload,
            data_cutoff=payload["data_cutoff"],
            news_fingerprint=fingerprint,
            activate=activate,
            model_versions=payload.get("model_versions", {}),
        )
        return snapshot["payload"]

    def get_or_bootstrap(self, ticker: str, asset_class: str) -> dict:
        """Returns the active snapshot or publishes a fast deterministic baseline."""
        ticker = ticker.upper()
        active = self.repository.get_active_snapshot(ticker)
        if active:
            return active["payload"]

        if hasattr(self.market, "get_cached_history"):
            history = self.market.get_cached_history(ticker, period="1y", interval="1d") or {}
        else:
            history = self.market.get_history(ticker, period="1y", interval="1d") or {}
        prices = history.get("prices") or []
        market = pd.DataFrame(prices)
        data_warning = None
        if market.empty or "close" not in market:
            quote = self.market.get_current_price(ticker) if hasattr(self.market, "get_current_price") else None
            fallback_price = float((quote or {}).get("price") or 1.0)
            market = pd.DataFrame(
                [{"date": datetime.now(timezone.utc).isoformat(), "close": fallback_price}]
            )
            data_warning = "Historico indisponivel; baseline temporario baseado no ultimo preco em cache."

        valid_close = pd.to_numeric(market["close"], errors="coerce").dropna()
        if valid_close.empty:
            valid_close = pd.Series([1.0])
            data_warning = "Preco indisponivel; snapshot temporario aguardando atualizacao da fonte."
        last_price = float(valid_close.iloc[-1])
        forecast = BaselineForecaster().forecast(ticker, valid_close)
        if "date" in market and not market["date"].empty:
            cutoff = pd.to_datetime(market["date"], errors="coerce", utc=True).max()
            if pd.notna(cutoff):
                forecast["data_cutoff"] = cutoff.isoformat()

        news = self.news_provider.get_related_news(ticker, limit=25, days_back=120)
        signal = self.fusion.aggregate(news)
        horizons = {
            key: self._sync_prices_and_scenarios(
                self.fusion.apply_to_horizon(value, signal), last_price
            )
            for key, value in forecast["horizons"].items()
        }
        payload = {
            **forecast,
            "analysis_id": str(uuid.uuid4()),
            "ticker": ticker,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_mode": "baseline",
            "last_price": last_price,
            "horizons": horizons,
            "news_signal": signal.as_dict(),
            "sources": news,
            "historical_series": [
                {"date": str(row.get("date", "")), "value": round(float(row["close"]), 4)}
                for _, row in market.tail(252).iterrows()
                if pd.notna(row.get("close"))
            ],
            "data_quality_warnings": [data_warning] if data_warning else [],
        }
        payload["friendly_message"] = self._deterministic_message(payload)
        snapshot = self.repository.save_snapshot(
            ticker=ticker,
            payload=payload,
            data_cutoff=payload["data_cutoff"],
            news_fingerprint=self.fusion.fingerprint(news),
            activate=True,
            model_versions={},
        )
        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")[:-1]
        self.repository.enqueue_job(
            ticker,
            reason="missing_snapshot",
            dedupe_key=f"{ticker}:missing_snapshot:{bucket}",
            priority=100,
        )
        return snapshot["payload"]
