import numpy as np
import pandas as pd

from app.schemas.portfolio import Portfolio
from app.services.asset_universe_service import AssetUniverseService
from app.services.market_data_service import MarketDataService
from app.services.financial_engine import (
    compute_portfolio_weights,
    compute_portfolio_concentration,
    compute_portfolio_volatility,
    compute_portfolio_return,
    compute_correlation_matrix,
    compute_covariance_matrix,
    compute_var,
    compute_cvar,
    compute_beta,
    compute_cagr,
)


class PortfolioAnalyticsService:
    def __init__(self):
        self.assets = AssetUniverseService()
        self.market = MarketDataService()

    def _benchmark_for_position(self, ticker: str, asset_class: str) -> tuple[str | None, str]:
        asset = self.assets.get_by_ticker(ticker)
        if asset_class == "FII":
            return "IFIX", "IFIX"
        if asset_class == "CRYPTO":
            return "BTC", "Bitcoin"
        if asset_class == "FIXED_INCOME":
            return None, "Sem benchmark"
        if asset and asset.country == "US":
            return "SP500", "S&P 500"
        return "IBOV", "Ibovespa"

    def _load_benchmark_returns(self, benchmark_ticker: str, length_hint: int = 252) -> pd.Series | None:
        history = self.market.get_history(benchmark_ticker, period="1y", interval="1d")
        if not history or not history.get("prices"):
            return None
        df = pd.DataFrame(history["prices"])
        if df.empty or "close" not in df.columns or len(df) < 3:
            return None
        returns = df["close"].pct_change().dropna().tail(length_hint)
        if returns.empty:
            return None
        returns.index = pd.RangeIndex(len(returns))
        return returns

    def analyze(self, portfolio: Portfolio, prices_data: dict[str, pd.DataFrame] | None = None) -> dict:
        if not portfolio.positions:
            return self._empty_analysis()

        tickers = [p.ticker for p in portfolio.positions]
        quantities = np.array([p.quantity for p in portfolio.positions])

        # Weights by quantity (equal weight if no prices)
        if prices_data:
            prices = []
            for t in tickers:
                df = prices_data.get(t)
                if df is not None and not df.empty:
                    prices.append(float(df["close"].iloc[-1]))
                else:
                    prices.append(1.0)
            prices_arr = np.array(prices)
            weights = compute_portfolio_weights(quantities, prices_arr)
        else:
            weights = np.ones(len(quantities)) / len(quantities)

        concentration = compute_portfolio_concentration(weights)

        # Build returns matrix if price history available
        correlation = None
        volatility = None
        portfolio_ret = None
        var_95 = None
        cvar_95 = None
        portfolio_beta = None
        benchmark_used = "Sem benchmark"
        benchmark_ticker = None
        benchmark_return_21d = None
        benchmark_return_63d = None
        benchmark_return_252d = None
        volatility_window_days = 252

        if prices_data:
            returns_list = []
            valid_tickers = []
            position_returns: dict[str, pd.Series] = {}
            for t in tickers:
                df = prices_data.get(t)
                if df is not None and len(df) > 1:
                    px = df["close"].values.astype(float)
                    ret = np.diff(px) / px[:-1]
                    series = pd.Series(ret, name=t)
                    returns_list.append(series)
                    position_returns[t] = series
                    valid_tickers.append(t)

            if len(returns_list) >= 1:
                returns_df = pd.concat(returns_list, axis=1).dropna()
                if len(returns_df) > 1:
                    corr_matrix = compute_correlation_matrix(returns_df)
                    cov_matrix = compute_covariance_matrix(returns_df)
                    correlation = corr_matrix.values.tolist()

                    # Portfolio volatility
                    w = np.array([weights[valid_tickers.index(t)] for t in valid_tickers])
                    if len(w) == cov_matrix.shape[0]:
                        volatility = compute_portfolio_volatility(w, cov_matrix)

                    # Portfolio return series and mean
                    portfolio_series = returns_df.mean(axis=1)
                    portfolio_ret = float(portfolio_series.mean())

                    # VaR / CVaR from equal-weighted portfolio
                    var_95 = compute_var(portfolio_series.values, 0.95)
                    cvar_95 = compute_cvar(portfolio_series.values, 0.95)

                    weighted_beta = 0.0
                    weighted_beta_base = 0.0
                    benchmark_weights: dict[str, float] = {}
                    benchmark_name_map: dict[str, str] = {}
                    for pos in portfolio.positions:
                        if pos.ticker not in position_returns:
                            continue
                        bench_ticker, bench_name = self._benchmark_for_position(pos.ticker, pos.asset_class)
                        weight = float(weights[tickers.index(pos.ticker)])
                        if bench_ticker is None:
                            continue
                        benchmark_weights[bench_ticker] = benchmark_weights.get(bench_ticker, 0.0) + weight
                        benchmark_name_map[bench_ticker] = bench_name
                        bench_returns = self._load_benchmark_returns(bench_ticker, len(position_returns[pos.ticker]))
                        if bench_returns is None:
                            continue
                        aligned = pd.concat([position_returns[pos.ticker], bench_returns], axis=1).dropna()
                        if len(aligned) < 10:
                            continue
                        beta_value = compute_beta(aligned.iloc[:, 0].values, aligned.iloc[:, 1].values)
                        if beta_value is None or np.isnan(beta_value):
                            continue
                        weighted_beta += weight * float(beta_value)
                        weighted_beta_base += weight

                    dominant_benchmark = None
                    if benchmark_weights:
                        dominant_benchmark = max(benchmark_weights.items(), key=lambda item: item[1])[0]
                        benchmark_ticker = dominant_benchmark
                        benchmark_used = benchmark_name_map.get(dominant_benchmark, dominant_benchmark)
                        benchmark_history = prices_data.get(dominant_benchmark)
                        if benchmark_history is None:
                            benchmark_raw = self.market.get_history(dominant_benchmark, period="1y", interval="1d")
                            if benchmark_raw and benchmark_raw.get("prices"):
                                benchmark_history = pd.DataFrame(benchmark_raw["prices"])
                        if benchmark_history is not None and len(benchmark_history) > 21:
                            closes = benchmark_history["close"].astype(float).reset_index(drop=True)
                            def _pct(window: int):
                                if len(closes) <= window:
                                    return None
                                base = float(closes.iloc[-window - 1])
                                last = float(closes.iloc[-1])
                                return ((last / base) - 1.0) * 100 if base else None
                            benchmark_return_21d = _pct(21)
                            benchmark_return_63d = _pct(63)
                            benchmark_return_252d = _pct(252)

                    if weighted_beta_base > 0:
                        portfolio_beta = weighted_beta / weighted_beta_base
                    elif dominant_benchmark:
                        bench_returns = self._load_benchmark_returns(dominant_benchmark, len(portfolio_series))
                        if bench_returns is not None:
                            aligned = pd.concat([portfolio_series, bench_returns], axis=1).dropna()
                            if len(aligned) >= 10:
                                portfolio_beta = compute_beta(aligned.iloc[:, 0].values, aligned.iloc[:, 1].values)

        # Class weights
        class_weights: dict[str, float] = {}
        sector_weights: dict[str, float] = {}
        for i, pos in enumerate(portfolio.positions):
            w_val = float(weights[i])
            class_weights[pos.asset_class] = class_weights.get(pos.asset_class, 0) + w_val

        return {
            "weights": {p.ticker: float(w) for p, w in zip(portfolio.positions, weights)},
            "class_weights": class_weights,
            "concentration": concentration,
            "concentration_label": self._concentration_label(concentration),
            "correlation_matrix": correlation,
            "volatility": volatility,
            "volatility_window_days": volatility_window_days,
            "portfolio_return": portfolio_ret,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "beta": portfolio_beta,
            "benchmark": {
                "ticker": benchmark_ticker,
                "label": benchmark_used,
                "return_21d_pct": round(benchmark_return_21d, 2) if benchmark_return_21d is not None else None,
                "return_63d_pct": round(benchmark_return_63d, 2) if benchmark_return_63d is not None else None,
                "return_252d_pct": round(benchmark_return_252d, 2) if benchmark_return_252d is not None else None,
            },
            "num_assets": len(portfolio.positions),
            "num_classes": len(class_weights),
        }

    def _concentration_label(self, concentration: float) -> str:
        if concentration >= 0.7:
            return "Alta concentração"
        if concentration >= 0.4:
            return "Concentração moderada"
        return "Bem diversificada"

    def _empty_analysis(self) -> dict:
        return {
            "weights": {},
            "class_weights": {},
            "concentration": 0.0,
            "concentration_label": "Sem ativos",
            "correlation_matrix": None,
            "volatility": None,
            "volatility_window_days": 252,
            "portfolio_return": None,
            "var_95": None,
            "cvar_95": None,
            "beta": None,
            "benchmark": {
                "ticker": None,
                "label": "Sem benchmark",
                "return_21d_pct": None,
                "return_63d_pct": None,
                "return_252d_pct": None,
            },
            "num_assets": 0,
            "num_classes": 0,
        }
