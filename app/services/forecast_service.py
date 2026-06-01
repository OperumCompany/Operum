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


class ForecastService:
    def __init__(self):
        self.models: dict[str, object] = {}
        self.model_meta: dict[str, dict] = {}

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

    def _load_model(self, ticker: str):
        path = os.path.join(MODEL_DIR, f"forecast_{ticker}.pkl")
        if os.path.exists(path):
            try:
                self.models[ticker] = joblib.load(path)
                meta_path = os.path.join(MODEL_DIR, f"forecast_{ticker}_meta.json")
                if os.path.exists(meta_path):
                    import json
                    with open(meta_path, "r", encoding="utf-8") as f:
                        self.model_meta[ticker] = json.load(f)
                return True
            except Exception as e:
                logger.warning(f"Erro ao carregar modelo de {ticker}: {e}")
        return False

    def _save_model(self, ticker: str, model):
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"forecast_{ticker}.pkl")
        joblib.dump(model, path)
        logger.info(f"Modelo de forecast salvo para {ticker}")

    def _save_model_meta(self, ticker: str, meta: dict):
        import json
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"forecast_{ticker}_meta.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
        self.model_meta[ticker] = meta

    def _estimate_confidence(self, ticker: str, pred_return: float, df: pd.DataFrame) -> float:
        meta = self.model_meta.get(ticker, {})
        test_r2 = float(meta.get("test_r2", 0.0) or 0.0)
        data_quality = min(1.0, len(df) / 120.0)
        recent_returns = df["Close"].pct_change().dropna().tail(21)
        recent_vol = float(recent_returns.std()) if not recent_returns.empty else 0.0
        if recent_vol <= 1e-9:
            magnitude_penalty = 0.2
        else:
            z_score = abs(pred_return) / recent_vol
            magnitude_penalty = min(0.65, max(0.0, (z_score - 1.0) * 0.18))
        base = 0.35 + max(-0.25, min(test_r2, 0.45))
        confidence = base + data_quality * 0.2 - magnitude_penalty
        return round(max(0.05, min(0.95, confidence)), 4)

    def _download_data(self, ticker: str, period: str = "2y") -> pd.DataFrame | None:
        try:
            yf_ticker = ticker + ".SA" if not ticker.endswith(".SA") and not any(
                c in ticker for c in ["-", "USD"]
            ) else ticker
            df = yf.download(yf_ticker, period=period, progress=False)
            if df.empty:
                return None
            return df
        except Exception as e:
            logger.debug(f"Erro ao baixar dados de {ticker}: {e}")
            return None

    def train(self, ticker: str) -> dict:
        import xgboost as xgb

        df = self._download_data(ticker, period="2y")
        if df is None or len(df) < 30:
            return {"status": "error", "error": "Dados insuficientes"}

        px = df["Close"].values.astype(float)
        ret = np.diff(px) / px[:-1]

        X_list = []
        y_list = []
        for i in range(20, len(ret)):
            feat: dict[str, float] = {}
            for lag in [1, 2, 3, 5]:
                feat[f"ret_lag_{lag}"] = float(ret[i - lag]) if i >= lag else 0.0
            feat["vol_5"] = float(np.std(ret[i - 5 : i])) if i >= 5 else 0.0
            feat["vol_21"] = float(np.std(ret[i - 21 : i])) if i >= 21 else 0.0

            px_slice = px[: i + 1]
            sma_5 = np.mean(px_slice[-5:]) if len(px_slice) >= 5 else px_slice[-1]
            sma_20 = np.mean(px_slice[-20:]) if len(px_slice) >= 20 else px_slice[-1]
            feat["price_vs_sma5"] = float(px_slice[-1] / sma_5 - 1) if sma_5 > 0 else 0.0
            feat["price_vs_sma20"] = (
                float(px_slice[-1] / sma_20 - 1) if sma_20 > 0 else 0.0
            )

            recent_high = np.max(px_slice[-20:]) if len(px_slice) >= 20 else px_slice[-1]
            recent_low = np.min(px_slice[-20:]) if len(px_slice) >= 20 else px_slice[-1]
            feat["prox_high_20"] = float(px_slice[-1] / recent_high - 1)
            feat["prox_low_20"] = float(px_slice[-1] / recent_low - 1)

            X_list.append(feat)
            y_list.append(float(ret[i]))

        if len(X_list) < 10:
            return {"status": "error", "error": "Poucas amostras"}

        X = pd.DataFrame(X_list).fillna(0)
        y = np.array(y_list)

        split = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y[:split], y[split:]

        model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            random_state=42,
        )
        model.fit(X_train, y_train)

        train_score = float(model.score(X_train, y_train))
        test_score = float(model.score(X_test, y_test))

        self._save_model(ticker, model)
        self.models[ticker] = model
        self._save_model_meta(ticker, {
            "ticker": ticker,
            "train_r2": round(train_score, 6),
            "test_r2": round(test_score, 6),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "trained_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "status": "trained",
            "ticker": ticker,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "train_r2": round(train_score, 4),
            "test_r2": round(test_score, 4),
        }

    def predict(self, ticker: str) -> dict | None:
        if ticker not in self.models:
            loaded = self._load_model(ticker)
            if not loaded:
                logger.warning(f"Sem modelo treinado para {ticker}")
                return None

        model = self.models[ticker]

        df = self._download_data(ticker, period="6mo")
        if df is None or len(df) < 20:
            return None

        features = self._prepare_features(df)
        features = features.fillna(0)

        pred_return = float(model.predict(features)[0])

        last_price = float(df["Close"].values[-1])
        predicted_price = last_price * (1 + pred_return)
        confidence = self._estimate_confidence(ticker, pred_return, df)

        return {
            "ticker": ticker,
            "last_price": round(last_price, 2),
            "predicted_return_1d": round(pred_return, 6),
            "predicted_price_1d": round(predicted_price, 2),
            "direction": "up" if pred_return > 0 else "down",
            "confidence": confidence,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_trained(self) -> list[str]:
        if not os.path.exists(MODEL_DIR):
            return []
        files = os.listdir(MODEL_DIR)
        return [
            f.replace("forecast_", "").replace(".pkl", "")
            for f in files
            if f.startswith("forecast_") and f.endswith(".pkl")
        ]
