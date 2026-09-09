from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml import HORIZONS


def add_forward_targets(frame: pd.DataFrame, *, horizons=HORIZONS) -> pd.DataFrame:
    required = {"date", "ticker", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Colunas ausentes para alvos: {sorted(missing)}")
    result = frame.sort_values(["ticker", "date"]).copy()
    price = pd.to_numeric(
        result.get("split_adjusted_close", result["close"]), errors="coerce"
    )
    total = pd.to_numeric(
        result.get("total_return_index", result["close"]), errors="coerce"
    )
    for horizon in horizons:
        days = int(horizon)
        future_price = price.groupby(result["ticker"]).shift(-days)
        future_total = total.groupby(result["ticker"]).shift(-days)
        price_return = future_price / price - 1.0
        total_return = future_total / total - 1.0
        income_denominator = 1.0 + price_return
        observed_pair = price.notna() & future_price.notna()
        invalid_denominator = observed_pair & (
            ~np.isfinite(income_denominator) | (income_denominator <= 0)
        )
        if invalid_denominator.any():
            rows = result.loc[invalid_denominator, ["ticker", "date"]].to_dict("records")
            raise ValueError(f"Invalid price return denominator for income identity: {rows}")
        income_return = (1.0 + total_return) / income_denominator - 1.0
        observed_total_pair = total.notna() & future_total.notna()
        invalid_total = observed_total_pair & (
            ~np.isfinite(total_return) | ~np.isfinite(income_return)
        )
        if invalid_total.any():
            rows = result.loc[invalid_total, ["ticker", "date"]].to_dict("records")
            raise ValueError(f"Invalid non-finite total or income return: {rows}")
        result[f"target_price_return_{days}"] = price_return
        result[f"target_income_return_{days}"] = income_return
        result[f"target_total_return_{days}"] = total_return
        # Backward-compatible alias: target_return has always represented total return.
        result[f"target_return_{days}"] = total_return
    return result

