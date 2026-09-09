from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


PUBLIC_HORIZONS = {"1m": 21, "2m": 42, "3m": 63}


def confidence_label(score: float) -> str:
    if score >= 0.70:
        return "alta"
    if score >= 0.45:
        return "media"
    return "baixa"


def build_horizon_output(
    *,
    last_price: float,
    expected_return: float,
    interval_radius: float,
    confidence_score: float,
    horizon_days: int,
    source: str,
) -> dict:
    expected_return = float(expected_return)
    interval_radius = max(0.0, float(interval_radius))
    adverse_return = expected_return - interval_radius
    favorable_return = expected_return + interval_radius
    if expected_return > 0.01:
        direction = "alta"
    elif expected_return < -0.01:
        direction = "queda"
    else:
        direction = "estabilidade"
    prices = {
        "adverse": round(max(0.01, last_price * (1 + adverse_return)), 2),
        "base": round(max(0.01, last_price * (1 + expected_return)), 2),
        "favorable": round(max(0.01, last_price * (1 + favorable_return)), 2),
    }
    score = round(max(0.05, min(0.95, float(confidence_score))), 4)
    probability_up = float(np.clip(0.50 + expected_return / max(interval_radius * 2.0, 0.01), 0.05, 0.95))
    return_range = {
        "adverse": round(adverse_return, 6),
        "base": round(expected_return, 6),
        "favorable": round(favorable_return, 6),
    }
    return {
        "horizon_days": int(horizon_days),
        "expected_return": round(expected_return, 6),
        "expected_total_return": round(expected_return, 6),
        "expected_price_return": round(expected_return, 6),
        "expected_income_return": 0.0,
        "probability_up": round(probability_up, 6),
        "return_range": return_range,
        "total_return_range": dict(return_range),
        "price_range": prices,
        "direction": direction,
        "confidence": {"score": score, "label": confidence_label(score)},
        "source": source,
        "scenarios": {
            "adverse": f"Cenário adverso: o ativo pode se aproximar de R$ {prices['adverse']:.2f}.",
            "base": f"Cenário-base: o ativo pode ficar perto de R$ {prices['base']:.2f}.",
            "favorable": f"Cenário favorável: o ativo pode se aproximar de R$ {prices['favorable']:.2f}.",
        },
    }


class BaselineForecaster:
    """Always-available statistical fallback; it never claims model confidence."""

    def forecast(self, ticker: str, close_values) -> dict:
        close = pd.Series(close_values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
        if close.empty:
            raise ValueError("Ao menos um preco valido e obrigatorio")
        last_price = float(close.iloc[-1])
        daily = close.pct_change(fill_method=None).dropna()
        recent = daily.tail(63)
        daily_drift = float(recent.median()) if not recent.empty else 0.0
        daily_volatility = float(recent.std()) if len(recent) > 1 else 0.02
        horizons = {}
        for label, days in PUBLIC_HORIZONS.items():
            drift = float(np.clip(daily_drift * days, -0.20, 0.20))
            radius = float(np.clip(daily_volatility * np.sqrt(days) * 1.2816, 0.08, 0.45))
            horizons[label] = build_horizon_output(
                last_price=last_price,
                expected_return=drift,
                interval_radius=radius,
                confidence_score=0.30,
                horizon_days=days,
                source="baseline",
            )
        now = datetime.now(timezone.utc).isoformat()
        return {
            "ticker": ticker.upper(),
            "generated_at": now,
            "data_cutoff": now,
            "generation_mode": "baseline",
            "is_stale": False,
            "model_versions": {},
            "horizons": horizons,
        }
