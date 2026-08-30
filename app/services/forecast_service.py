import logging
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "models"
)
DATASET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "datasets",
    "train",
)

FORECAST_HORIZONS = {
    "1d": 1,
    "1w": 5,
    "1m": 21,
    "2m": 42,
    "3m": 63,
}


class ForecastService:
    def __init__(self):
        self.models: dict[str, dict[int, object]] = {}
        self.model_meta: dict[str, dict[int, dict]] = {}

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        px = df["Close"].values.astype(float)
        ret = np.diff(px) / px[:-1]
        feat: dict[str, float] = {}

        for lag in [1, 2, 3, 5]:
            feat[f"ret_lag_{lag}"] = float(ret[-lag]) if len(ret) >= lag else 0.0

        feat["vol_5"] = float(np.std(ret[-5:])) if len(ret) >= 5 else 0.0
        feat["vol_21"] = float(np.std(ret[-21:])) if len(ret) >= 21 else 0.0

        sma_5 = np.mean(px[-5:]) if len(px) >= 5 else px[-1]
        sma_20 = np.mean(px[-20:]) if len(px) >= 20 else px[-1]
        feat["price_vs_sma5"] = float(px[-1] / sma_5 - 1) if sma_5 > 0 else 0.0
        feat["price_vs_sma20"] = float(px[-1] / sma_20 - 1) if sma_20 > 0 else 0.0

        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)
        recent_high = np.max(high[-20:]) if len(high) >= 20 else high[-1]
        recent_low = np.min(low[-20:]) if len(low) >= 20 else low[-1]
        feat["prox_high_20"] = float(px[-1] / recent_high - 1)
        feat["prox_low_20"] = float(px[-1] / recent_low - 1)

        return pd.DataFrame([feat])

    def _model_path(self, ticker: str, horizon_days: int) -> str:
        return os.path.join(MODEL_DIR, f"forecast_{ticker}_{horizon_days}d.pkl")

    def _meta_path(self, ticker: str, horizon_days: int) -> str:
        return os.path.join(MODEL_DIR, f"forecast_{ticker}_{horizon_days}d_meta.json")

    def _legacy_model_path(self, ticker: str) -> str:
        return os.path.join(MODEL_DIR, f"forecast_{ticker}.pkl")

    def _legacy_meta_path(self, ticker: str) -> str:
        return os.path.join(MODEL_DIR, f"forecast_{ticker}_meta.json")

    def _load_model(self, ticker: str, horizon_days: int) -> bool:
        path = self._model_path(ticker, horizon_days)
        legacy = horizon_days == 1 and os.path.exists(self._legacy_model_path(ticker))
        if not os.path.exists(path) and not legacy:
            return False
        try:
            self.models.setdefault(ticker, {})
            self.model_meta.setdefault(ticker, {})
            model_path = self._legacy_model_path(ticker) if legacy else path
            meta_path = self._legacy_meta_path(ticker) if legacy else self._meta_path(ticker, horizon_days)
            self.models[ticker][horizon_days] = joblib.load(model_path)
            if os.path.exists(meta_path):
                import json

                with open(meta_path, "r", encoding="utf-8") as f:
                    self.model_meta[ticker][horizon_days] = json.load(f)
            return True
        except Exception as e:
            logger.warning(f"Erro ao carregar modelo de {ticker} ({horizon_days}d): {e}")
        return False

    def _save_model(self, ticker: str, horizon_days: int, model) -> None:
        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(model, self._model_path(ticker, horizon_days))

    def _save_model_meta(self, ticker: str, horizon_days: int, meta: dict) -> None:
        import json

        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(self._meta_path(ticker, horizon_days), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
        self.model_meta.setdefault(ticker, {})[horizon_days] = meta

    def _estimate_confidence(
        self,
        ticker: str,
        horizon_days: int,
        pred_return: float,
        df: pd.DataFrame,
    ) -> float:
        meta = self.model_meta.get(ticker, {}).get(horizon_days, {})
        test_r2 = float(meta.get("test_r2", 0.0) or 0.0)
        rmse = float(meta.get("rmse", 0.0) or 0.0)
        data_quality = min(1.0, len(df) / max(120.0, horizon_days * 4))
        recent_returns = df["Close"].pct_change().dropna().tail(max(21, horizon_days))
        recent_vol = float(recent_returns.std()) if not recent_returns.empty else 0.0
        if recent_vol <= 1e-9:
            magnitude_penalty = 0.25
        else:
            scale = recent_vol * np.sqrt(max(horizon_days, 1))
            z_score = abs(pred_return) / max(scale, 1e-9)
            magnitude_penalty = min(0.7, max(0.0, (z_score - 1.0) * 0.16))
        error_penalty = min(0.3, rmse * 3.0)
        base = 0.34 + max(-0.2, min(test_r2, 0.42))
        confidence = base + data_quality * 0.22 - magnitude_penalty - error_penalty
        return round(max(0.05, min(0.95, confidence)), 4)

    def _download_data(self, ticker: str, period: str = "2y") -> pd.DataFrame | None:
        try:
            yf_ticker = ticker + ".SA" if not ticker.endswith(".SA") and not any(
                c in ticker for c in ["-", "USD"]
            ) else ticker
            df = yf.download(yf_ticker, period=period, progress=False)
            if df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            numeric_cols = [col for col in ["Close", "High", "Low", "Open", "Volume"] if col in df.columns]
            if numeric_cols:
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
                df = df.dropna(subset=["Close"])
            if df.empty:
                return None
            return df
        except Exception as e:
            logger.debug(f"Erro ao baixar dados de {ticker}: {e}")
            return None

    def _train_single_horizon(self, ticker: str, df: pd.DataFrame, horizon_days: int) -> dict:
        import xgboost as xgb

        px = df["Close"].values.astype(float)
        X_list = []
        y_list = []
        start_idx = max(25, horizon_days + 5)
        max_idx = len(px) - horizon_days
        for i in range(start_idx, max_idx):
            px_slice = px[: i + 1]
            ret_series = np.diff(px_slice) / px_slice[:-1]
            feat: dict[str, float] = {}
            for lag in [1, 2, 3, 5]:
                feat[f"ret_lag_{lag}"] = float(ret_series[-lag]) if len(ret_series) >= lag else 0.0
            feat["vol_5"] = float(np.std(ret_series[-5:])) if len(ret_series) >= 5 else 0.0
            feat["vol_21"] = float(np.std(ret_series[-21:])) if len(ret_series) >= 21 else 0.0

            sma_5 = np.mean(px_slice[-5:]) if len(px_slice) >= 5 else px_slice[-1]
            sma_20 = np.mean(px_slice[-20:]) if len(px_slice) >= 20 else px_slice[-1]
            feat["price_vs_sma5"] = float(px_slice[-1] / sma_5 - 1) if sma_5 > 0 else 0.0
            feat["price_vs_sma20"] = float(px_slice[-1] / sma_20 - 1) if sma_20 > 0 else 0.0

            recent_high = np.max(px_slice[-20:]) if len(px_slice) >= 20 else px_slice[-1]
            recent_low = np.min(px_slice[-20:]) if len(px_slice) >= 20 else px_slice[-1]
            feat["prox_high_20"] = float(px_slice[-1] / recent_high - 1)
            feat["prox_low_20"] = float(px_slice[-1] / recent_low - 1)

            future_price = px[i + horizon_days]
            current_price = px[i]
            if current_price == 0 or not np.isfinite(current_price) or not np.isfinite(future_price):
                continue
            future_return = float((future_price / current_price) - 1.0)
            if not np.isfinite(future_return):
                continue

            X_list.append(feat)
            y_list.append(future_return)

        if len(X_list) < 20:
            return {"status": "error", "error": f"Poucas amostras para horizonte {horizon_days}d"}

        X = pd.DataFrame(X_list).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        y = np.array(y_list, dtype=float)

        valid_mask = np.isfinite(y)
        if not valid_mask.all():
            X = X.loc[valid_mask].reset_index(drop=True)
            y = y[valid_mask]

        if len(X) < 20 or len(y) < 20:
            return {"status": "error", "error": f"Dados invalidos apos limpeza para horizonte {horizon_days}d"}

        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y[:split], y[split:]

        if len(X_train) < 5 or not np.isfinite(y_train).all():
            return {"status": "error", "error": f"Base de treino invalida para horizonte {horizon_days}d"}

        if len(y_test) and not np.isfinite(y_test).all():
            valid_test_mask = np.isfinite(y_test)
            X_test = X_test.iloc[valid_test_mask]
            y_test = y_test[valid_test_mask]

        model = xgb.XGBRegressor(
            n_estimators=220,
            max_depth=4,
            learning_rate=0.05,
            random_state=42,
        )
        model.fit(X_train, y_train)

        train_score = float(model.score(X_train, y_train))
        test_score = float(model.score(X_test, y_test)) if len(X_test) > 1 else float(model.score(X_train, y_train))
        preds = model.predict(X_test if len(X_test) else X_train)
        target = y_test if len(X_test) else y_train
        rmse = float(np.sqrt(np.mean(np.square(preds - target)))) if len(target) else 0.0

        self.models.setdefault(ticker, {})[horizon_days] = model
        self._save_model(ticker, horizon_days, model)
        self._save_model_meta(
            ticker,
            horizon_days,
            {
                "ticker": ticker,
                "horizon_days": horizon_days,
                "train_r2": round(train_score, 6),
                "test_r2": round(test_score, 6),
                "rmse": round(rmse, 6),
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "trained_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {
            "status": "trained",
            "horizon_days": horizon_days,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "train_r2": round(train_score, 4),
            "test_r2": round(test_score, 4),
            "rmse": round(rmse, 6),
        }

    def train(self, ticker: str, horizons: list[int] | None = None) -> dict:
        df = self._download_data(ticker, period="2y")
        if df is None or len(df) < 80:
            return {"status": "error", "error": "Dados insuficientes"}

        horizons = horizons or sorted(set(FORECAST_HORIZONS.values()))
        results = []
        for horizon_days in horizons:
            try:
                results.append(self._train_single_horizon(ticker, df, horizon_days))
            except Exception as exc:
                logger.exception("Falha ao treinar horizonte %sd para %s", horizon_days, ticker)
                results.append({"status": "error", "error": f"Falha no treino {horizon_days}d: {exc}"})

        errors = [item["error"] for item in results if item.get("status") == "error"]
        trained = [item for item in results if item.get("status") == "trained"]
        if not trained:
            return {"status": "error", "error": "; ".join(errors) if errors else "Falha ao treinar"}

        return {
            "status": "trained",
            "ticker": ticker,
            "horizons": trained,
            "errors": errors,
        }

    def _predict_horizon(
        self,
        ticker: str,
        horizon_days: int,
        df: pd.DataFrame,
    ) -> dict | None:
        if ticker not in self.models or horizon_days not in self.models[ticker]:
            loaded = self._load_model(ticker, horizon_days)
            if not loaded:
                return None

        features = self._prepare_features(df).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        model = self.models[ticker][horizon_days]
        pred_return = float(model.predict(features)[0])
        last_price = float(df["Close"].values[-1])
        if not np.isfinite(pred_return) or not np.isfinite(last_price):
            return None
        predicted_price = last_price * (1 + pred_return)
        if not np.isfinite(predicted_price):
            return None
        confidence = self._estimate_confidence(ticker, horizon_days, pred_return, df)
        label = next((key for key, value in FORECAST_HORIZONS.items() if value == horizon_days), f"{horizon_days}d")
        return {
            "horizon_label": label,
            "horizon_days": horizon_days,
            "predicted_return": round(pred_return, 6),
            "predicted_price": round(predicted_price, 2),
            "direction": "up" if pred_return >= 0 else "down",
            "confidence": confidence,
        }

    def _interpolate_series(
        self,
        last_price: float,
        generated_at: datetime,
        predictions: list[dict],
    ) -> list[dict]:
        if not predictions:
            return []
        anchors = [{"day": 0, "price": round(last_price, 2), "date": generated_at.date().isoformat()}]
        business_days = pd.bdate_range(start=generated_at.date(), periods=65)
        for prediction in predictions:
            idx = min(prediction["horizon_days"], len(business_days) - 1)
            anchors.append({
                "day": prediction["horizon_days"],
                "price": prediction["predicted_price"],
                "date": business_days[idx].date().isoformat(),
            })

        anchors = sorted(anchors, key=lambda item: item["day"])
        series = []
        for left, right in zip(anchors, anchors[1:]):
            span = max(1, right["day"] - left["day"])
            date_range = pd.bdate_range(start=left["date"], end=right["date"])
            for step in range(span):
                price = left["price"] + ((right["price"] - left["price"]) * (step / span))
                if step < len(date_range):
                    series.append(
                        {
                            "date": date_range[step].date().isoformat(),
                            "value": round(price, 2),
                        }
                    )
        series.append({"date": anchors[-1]["date"], "value": anchors[-1]["price"]})
        deduped = []
        seen_dates = set()
        for item in series:
            if item["date"] in seen_dates:
                continue
            seen_dates.add(item["date"])
            deduped.append(item)
        return deduped

    def predict(self, ticker: str) -> dict | None:
        result = self.predict_multi(ticker, requested_horizons=[1])
        if result is None:
            return None
        horizon = result["predictions"][0]
        return {
            "ticker": ticker,
            "last_price": result["last_price"],
            "predicted_return_1d": horizon["predicted_return"],
            "predicted_price_1d": horizon["predicted_price"],
            "direction": horizon["direction"],
            "confidence": horizon["confidence"],
            "generated_at": result["generated_at"],
            "horizons": result["predictions"],
        }

    def predict_multi(self, ticker: str, requested_horizons: list[int] | None = None) -> dict | None:
        df = self._download_data(ticker, period="9mo")
        if df is None or len(df) < 40:
            return None

        requested_horizons = requested_horizons or [5, 21, 42, 63]
        missing = [
            horizon
            for horizon in requested_horizons
            if ticker not in self.models or horizon not in self.models.get(ticker, {})
        ]
        if missing:
            train_result = self.train(ticker, horizons=missing)
            if train_result.get("status") == "error":
                logger.warning("Falha ao treinar forecast de %s: %s", ticker, train_result.get("error"))

        predictions = []
        for horizon_days in sorted(set(requested_horizons)):
            prediction = self._predict_horizon(ticker, horizon_days, df)
            if prediction:
                predictions.append(prediction)

        if not predictions:
            return None

        last_price = float(df["Close"].values[-1])
        generated_at = datetime.now(timezone.utc)
        return {
            "ticker": ticker,
            "last_price": round(last_price, 2),
            "generated_at": generated_at.isoformat(),
            "predictions": predictions,
            "forecast_anchor_points": [
                {
                    "date": item["horizon_label"],
                    "horizon_days": item["horizon_days"],
                    "predicted_price": item["predicted_price"],
                    "predicted_return": item["predicted_return"],
                    "confidence": item["confidence"],
                }
                for item in predictions
            ],
            "forecast_series": self._interpolate_series(last_price, generated_at, predictions),
        }

    def list_trained(self) -> list[str]:
        if not os.path.exists(MODEL_DIR):
            return []
        files = os.listdir(MODEL_DIR)
        tickers = set()
        for file_name in files:
            if file_name.startswith("forecast_") and file_name.endswith(".pkl"):
                payload = file_name.replace("forecast_", "").replace(".pkl", "")
                if "_" in payload:
                    ticker, _ = payload.rsplit("_", 1)
                    tickers.add(ticker)
                else:
                    tickers.add(payload)
        return sorted(tickers)
