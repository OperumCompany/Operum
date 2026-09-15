from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


RESEARCH_LOOKBACK_SESSIONS = 252
RESEARCH_MIN_COVERAGE = 0.98
RESEARCH_MINIMUM_ASSETS = {"BR_STOCK": 80, "FII": 20}


@dataclass(frozen=True)
class CohortAsset:
    ticker: str
    asset_class: str
    bars: int
    coverage: float
    median_traded_value: float

    def as_dict(self) -> dict:
        return asdict(self)


def select_liquid_cohort(
    market: pd.DataFrame,
    *,
    stocks: int = 24,
    fiis: int = 6,
    min_bars: int = 1_250,
    min_coverage: float = 0.98,
    strict: bool = True,
) -> tuple[list[CohortAsset], list[dict]]:
    required = {"date", "ticker", "asset_class", "close", "volume"}
    missing = required.difference(market.columns)
    if missing:
        raise ValueError(f"Colunas ausentes para selecao da coorte: {sorted(missing)}")

    candidates: list[CohortAsset] = []
    excluded: list[dict] = []
    trading_calendars = {
        asset_class: pd.DatetimeIndex(pd.to_datetime(group["date"]).drop_duplicates().sort_values())
        for asset_class, group in market.groupby("asset_class")
    }
    global_latest = pd.Timestamp(pd.to_datetime(market["date"]).max())
    for (ticker, asset_class), raw in market.groupby(["ticker", "asset_class"], sort=True):
        frame = raw.sort_values("date").drop_duplicates("date", keep="last")
        calendar = trading_calendars.get(asset_class, pd.DatetimeIndex([]))
        expected = int(
            ((calendar >= pd.Timestamp(frame["date"].min())) & (calendar <= pd.Timestamp(frame["date"].max()))).sum()
        )
        coverage = len(frame) / max(expected, 1)
        traded_value = (frame["close"] * frame["volume"]).tail(252)
        median_traded_value = float(traded_value.median()) if not traded_value.empty else 0.0
        reasons = []
        if len(frame) < min_bars:
            reasons.append("insufficient_bars")
        if coverage < min_coverage:
            reasons.append("insufficient_coverage")
        if median_traded_value <= 0:
            reasons.append("invalid_liquidity")
        if global_latest - pd.Timestamp(frame["date"].max()) > pd.Timedelta(days=10):
            reasons.append("stale_history")
        if asset_class not in {"BR_STOCK", "FII"}:
            reasons.append("unsupported_asset_class")
        if reasons:
            excluded.append({"ticker": ticker, "asset_class": asset_class, "reasons": reasons})
            continue
        candidates.append(
            CohortAsset(
                ticker=str(ticker),
                asset_class=str(asset_class),
                bars=len(frame),
                coverage=round(float(coverage), 6),
                median_traded_value=median_traded_value,
            )
        )

    selected: list[CohortAsset] = []
    quotas = {"BR_STOCK": stocks, "FII": fiis}
    for asset_class, quota in quotas.items():
        ranked = sorted(
            (item for item in candidates if item.asset_class == asset_class),
            key=lambda item: (item.median_traded_value, item.ticker),
            reverse=True,
        )
        selected.extend(ranked[:quota])
        excluded.extend(
            {"ticker": item.ticker, "asset_class": item.asset_class, "reasons": ["outside_liquidity_quota"]}
            for item in ranked[quota:]
        )
        if strict and len(ranked) < quota:
            raise ValueError(
                f"Coorte incompleta para {asset_class}: {len(ranked)} elegiveis, {quota} exigidos"
            )
    return selected, excluded


def build_dynamic_research_universe(
    market: pd.DataFrame,
    *,
    lookback_sessions: int = RESEARCH_LOOKBACK_SESSIONS,
    min_coverage: float = RESEARCH_MIN_COVERAGE,
    minimum_assets: dict[str, int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute date-local eligibility without using eventual asset lifetime or membership."""
    required = {"date", "ticker", "asset_class", "volume"}
    price_column = "raw_close" if "raw_close" in market else "close"
    required.add(price_column)
    missing = required.difference(market.columns)
    if missing:
        raise ValueError(f"Colunas ausentes para universo de pesquisa: {sorted(missing)}")
    if lookback_sessions <= 0 or not 0 < min_coverage <= 1:
        raise ValueError("Janela e cobertura do universo de pesquisa sao invalidas")

    minimums = {**RESEARCH_MINIMUM_ASSETS, **(minimum_assets or {})}
    normalized = market.copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.tz_localize(None)
    normalized["_liquidity_close"] = pd.to_numeric(
        normalized[price_column], errors="coerce"
    )
    normalized["_liquidity_volume"] = pd.to_numeric(
        normalized["volume"], errors="coerce"
    )
    normalized = normalized.sort_values(["asset_class", "ticker", "date"]).drop_duplicates(
        ["asset_class", "ticker", "date"], keep="last"
    )

    parts: list[pd.DataFrame] = []
    for asset_class, class_frame in normalized.groupby("asset_class", sort=True):
        calendar = pd.DatetimeIndex(class_frame["date"].drop_duplicates().sort_values())
        calendar_positions = pd.Series(np.arange(len(calendar)), index=calendar)
        for ticker, ticker_frame in class_frame.groupby("ticker", sort=True):
            indexed = ticker_frame.set_index("date").reindex(calendar)
            close = indexed["_liquidity_close"]
            volume = indexed["_liquidity_volume"]
            valid = (
                close.notna()
                & volume.notna()
                & np.isfinite(close)
                & np.isfinite(volume)
                & (close > 0)
                & (volume > 0)
            )
            prior_valid = valid.shift(1, fill_value=False)
            observed = prior_valid.astype(int).rolling(
                lookback_sessions, min_periods=1
            ).sum()
            coverage = observed / float(lookback_sessions)
            traded_value = (close * volume).where(valid).shift(1)
            median_traded_value = traded_value.rolling(
                lookback_sessions, min_periods=1
            ).median()
            history_ready = calendar_positions >= lookback_sessions
            window_liquidity_valid = (
                np.isfinite(median_traded_value) & (median_traded_value > 0)
            )
            eligible = (
                history_ready
                & (coverage >= min_coverage)
                & window_liquidity_valid
            )
            actual_dates = pd.DatetimeIndex(ticker_frame["date"])
            metrics = pd.DataFrame(
                {
                    "date": calendar,
                    "ticker": str(ticker),
                    "asset_class": str(asset_class),
                    "observed_sessions": observed.astype(int).to_numpy(),
                    "coverage": coverage.to_numpy(dtype=float),
                    "median_traded_value": median_traded_value.to_numpy(dtype=float),
                    "eligible": eligible.to_numpy(dtype=bool),
                    "_history_ready": history_ready.to_numpy(dtype=bool),
                    "_valid": window_liquidity_valid.to_numpy(dtype=bool),
                }
            ).set_index("date").loc[actual_dates].reset_index()

            def exclusion_reasons(row: pd.Series) -> list[str]:
                reasons: list[str] = []
                if not row["_history_ready"]:
                    reasons.append("insufficient_history")
                if row["coverage"] < min_coverage:
                    reasons.append("insufficient_coverage")
                if not row["_valid"] or not np.isfinite(row["median_traded_value"]):
                    reasons.append("invalid_liquidity")
                return reasons

            metrics["reasons"] = metrics.apply(exclusion_reasons, axis=1)
            parts.append(metrics.drop(columns=["_history_ready", "_valid"]))

    eligibility = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if eligibility.empty:
        raise ValueError("Mercado vazio para universo de pesquisa")
    eligibility["liquidity_rank"] = eligibility.groupby(
        ["date", "asset_class"]
    )["median_traded_value"].rank(method="first", ascending=False)
    eligibility["in_research_universe"] = eligibility["eligible"]
    eligibility = eligibility.sort_values(["date", "asset_class", "ticker"]).reset_index(drop=True)

    counts = (
        eligibility.loc[eligibility["eligible"]]
        .groupby(["date", "asset_class"])["ticker"]
        .nunique()
        .unstack(fill_value=0)
    )
    all_dates = pd.DatetimeIndex(eligibility["date"].drop_duplicates().sort_values())
    counts = counts.reindex(all_dates, fill_value=0)
    gate = pd.DataFrame({"date": all_dates})
    gate["eligible_br_stock"] = counts.get("BR_STOCK", pd.Series(0, index=all_dates)).to_numpy()
    gate["eligible_fii"] = counts.get("FII", pd.Series(0, index=all_dates)).to_numpy()
    gate["required_br_stock"] = int(minimums.get("BR_STOCK", 0))
    gate["required_fii"] = int(minimums.get("FII", 0))
    gate["shortfall_br_stock"] = (
        gate["required_br_stock"] - gate["eligible_br_stock"]
    ).clip(lower=0)
    gate["shortfall_fii"] = (gate["required_fii"] - gate["eligible_fii"]).clip(lower=0)
    gate["promotion_blocked"] = (
        (gate["shortfall_br_stock"] > 0) | (gate["shortfall_fii"] > 0)
    )
    return eligibility, gate
