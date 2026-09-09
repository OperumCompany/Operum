from __future__ import annotations

import numpy as np
import pandas as pd


def _ticker_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.sort_values("date").copy()
    close = pd.to_numeric(frame["close"], errors="coerce")
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    daily_return = close.pct_change(fill_method=None)

    for window in (1, 5, 21, 63):
        frame[f"return_{window}"] = close.pct_change(window, fill_method=None)
    for window in (5, 21, 63):
        frame[f"volatility_{window}"] = daily_return.rolling(window, min_periods=window).std()
        average = close.rolling(window, min_periods=window).mean()
        frame[f"price_to_sma_{window}"] = close / average - 1.0

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    frame["rsi_14"] = (100 - (100 / (1 + rs))).fillna(50.0)

    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    frame["macd_normalized"] = (ema_12 - ema_26) / close.replace(0, np.nan)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low).abs(), (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    frame["atr_14_normalized"] = true_range.rolling(14, min_periods=14).mean() / close.replace(0, np.nan)
    frame["drawdown_63"] = close / close.rolling(63, min_periods=63).max() - 1.0

    volume_mean = volume.rolling(21, min_periods=21).mean()
    volume_std = volume.rolling(21, min_periods=21).std()
    frame["volume_zscore_21"] = (volume - volume_mean) / volume_std.replace(0, np.nan)
    frame["liquidity_21"] = (close * volume).rolling(21, min_periods=21).median()
    return frame


def _prepare_external_context(context: pd.DataFrame) -> pd.DataFrame:
    required = {
        "reference_date",
        "available_at",
        "ibov_close",
        "usdbrl_close",
        "brent_close",
    }
    missing = required.difference(context.columns)
    if missing:
        raise ValueError(f"Colunas ausentes no contexto externo: {sorted(missing)}")

    frame = context.loc[:, list(required)].copy()
    frame["reference_date"] = pd.to_datetime(
        frame["reference_date"], utc=False, errors="coerce"
    ).dt.tz_localize(None)
    frame["available_at"] = pd.to_datetime(
        frame["available_at"], utc=False, errors="coerce"
    ).dt.tz_localize(None)
    if frame[["reference_date", "available_at"]].isna().any().any():
        raise ValueError("Contexto externo contem datas point-in-time invalidas")
    if (frame["reference_date"] > frame["available_at"]).any():
        raise ValueError("Contexto externo disponivel antes da reference_date")
    if frame["reference_date"].duplicated().any() or frame["available_at"].duplicated().any():
        raise ValueError("Contexto externo contem timestamps duplicados")
    frame = frame.sort_values("reference_date")
    for source, prefix in (
        ("ibov_close", "benchmark"),
        ("usdbrl_close", "usdbrl"),
        ("brent_close", "brent"),
    ):
        values = pd.to_numeric(frame[source], errors="coerce")
        frame[f"{prefix}_return_1"] = values.pct_change(1, fill_method=None)
        frame[f"{prefix}_return_21"] = values.pct_change(21, fill_method=None)
        frame[f"{prefix}_return_63"] = values.pct_change(63, fill_method=None)
    return frame.drop(columns=["ibov_close", "usdbrl_close", "brent_close"]).rename(
        columns={"reference_date": "context_reference_date"}
    ).sort_values("available_at")


def _add_relative_market_features(frame: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for _, raw in frame.groupby("ticker", sort=False):
        group = raw.sort_values("date").copy()
        asset_daily = pd.to_numeric(group["return_1"], errors="coerce")
        benchmark_daily = pd.to_numeric(group["benchmark_return_1"], errors="coerce")
        covariance = asset_daily.rolling(63, min_periods=63).cov(benchmark_daily)
        variance = benchmark_daily.rolling(63, min_periods=63).var()
        group["beta_63"] = covariance / variance.replace(0, np.nan)
        group["correlation_63"] = asset_daily.rolling(63, min_periods=63).corr(benchmark_daily)
        group["relative_return_21"] = group["return_21"] - group["benchmark_return_21"]
        parts.append(group)
    return pd.concat(parts, ignore_index=True)


def build_point_in_time_features(
    market: pd.DataFrame,
    context: pd.DataFrame | None = None,
) -> pd.DataFrame:
    required = {"date", "ticker", "asset_class", "open", "high", "low", "close", "volume"}
    missing = required.difference(market.columns)
    if missing:
        raise ValueError(f"Colunas ausentes para features: {sorted(missing)}")
    frame = market.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=False)
    featured = pd.concat(
        [_ticker_features(group) for _, group in frame.groupby("ticker", sort=False)],
        ignore_index=True,
    )
    if context is not None:
        prepared_context = _prepare_external_context(context)
        featured["_feature_cutoff"] = (
            pd.to_datetime(featured["date"]).dt.normalize()
            + pd.Timedelta(days=1)
            - pd.Timedelta(nanoseconds=1)
        )
        featured = pd.merge_asof(
            featured.sort_values("_feature_cutoff"),
            prepared_context,
            left_on="_feature_cutoff",
            right_on="available_at",
            direction="backward",
            allow_exact_matches=True,
        ).drop(columns=["_feature_cutoff", "available_at"])
        featured = _add_relative_market_features(featured)
    return add_class_specific_features(featured).reset_index(drop=True).replace(
        [np.inf, -np.inf], np.nan
    )


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def _add_derived(result: pd.DataFrame, column: str, values: pd.Series) -> None:
    if column in result:
        result[column] = _numeric_column(result, column).combine_first(values)
    else:
        result[column] = values


def _coalesce_numeric_columns(
    frame: pd.DataFrame, columns: tuple[str, ...]
) -> pd.Series | None:
    available = [column for column in columns if column in frame]
    if not available:
        return None
    values = _numeric_column(frame, available[0])
    for column in available[1:]:
        values = values.combine_first(_numeric_column(frame, column))
    return values


def add_class_specific_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive row-local FII/equity features from already PIT-joined inputs.

    This function deliberately performs no external lookup, fill-forward, or
    imputation. A derived value exists only when its authentic inputs already
    exist on the row. Fold-local missingness and imputation are handled by
    :class:`app.ml.feature_pipeline.FoldFeaturePipeline`.
    """
    if "asset_class" not in frame:
        raise ValueError("asset_class ausente para features especificas")
    result = frame.copy()
    fii = result["asset_class"].eq("FII")
    equity = result["asset_class"].eq("BR_STOCK")

    for window in (1, 21, 63):
        asset_return = f"return_{window}"
        ifix_return = f"ifix_return_{window}"
        if asset_return in result and ifix_return in result:
            _add_derived(
                result,
                f"relative_return_ifix_{window}",
                (
                    _numeric_column(result, asset_return)
                    - _numeric_column(result, ifix_return)
                ).where(fii),
            )

    inflation = _coalesce_numeric_columns(result, ("ipca_12m", "ipca"))
    policy_rate = _coalesce_numeric_columns(
        result, ("cdi_rate", "cdi", "selic")
    )
    if policy_rate is not None and inflation is not None:
        _add_derived(
            result,
            "real_rate",
            (policy_rate - inflation).where(fii),
        )
    if "dividend_yield" in result and policy_rate is not None:
        _add_derived(
            result,
            "dividend_yield_spread_cdi",
            (
                _numeric_column(result, "dividend_yield")
                - policy_rate
            ).where(fii),
        )

    if "net_income" in result and "market_cap" in result:
        _add_derived(
            result,
            "earnings_yield",
            _safe_ratio(
                _numeric_column(result, "net_income"),
                _numeric_column(result, "market_cap"),
            ).where(equity),
        )
    if "net_equity" in result and "market_cap" in result:
        _add_derived(
            result,
            "book_to_market",
            _safe_ratio(
                _numeric_column(result, "net_equity"),
                _numeric_column(result, "market_cap"),
            ).where(equity),
        )
    if "net_income" in result and "net_equity" in result:
        _add_derived(
            result,
            "roe",
            _safe_ratio(
                _numeric_column(result, "net_income"),
                _numeric_column(result, "net_equity"),
            ).where(equity),
        )
    if "revenue" in result:
        for source, feature in (
            ("gross_profit", "gross_margin"),
            ("operating_income", "operating_margin"),
            ("net_income", "net_margin"),
        ):
            if source in result:
                _add_derived(
                    result,
                    feature,
                    _safe_ratio(
                        _numeric_column(result, source),
                        _numeric_column(result, "revenue"),
                    ).where(equity),
                )
    if "net_debt" in result and "ebitda" in result:
        _add_derived(
            result,
            "net_debt_to_ebitda",
            _safe_ratio(
                _numeric_column(result, "net_debt"),
                _numeric_column(result, "ebitda"),
            ).where(equity),
        )
    if "operating_cash_flow" in result and "net_income" in result:
        _add_derived(
            result,
            "cashflow_to_net_income",
            _safe_ratio(
                _numeric_column(result, "operating_cash_flow"),
                _numeric_column(result, "net_income"),
            ).where(equity),
        )

    return result.replace([np.inf, -np.inf], np.nan)
