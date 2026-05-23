import numpy as np
import pandas as pd

from app.schemas.portfolio import Portfolio
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

        if prices_data:
            returns_list = []
            valid_tickers = []
            for t in tickers:
                df = prices_data.get(t)
                if df is not None and len(df) > 1:
                    px = df["close"].values.astype(float)
                    ret = np.diff(px) / px[:-1]
                    returns_list.append(pd.Series(ret, name=t))
                    valid_tickers.append(t)

            if len(returns_list) >= 2:
                returns_df = pd.concat(returns_list, axis=1).dropna()
                if len(returns_df) > 1:
                    corr_matrix = compute_correlation_matrix(returns_df)
                    cov_matrix = compute_covariance_matrix(returns_df)
                    correlation = corr_matrix.values.tolist()

                    # Portfolio volatility
                    w = np.array([weights[valid_tickers.index(t)] for t in valid_tickers])
                    if len(w) == cov_matrix.shape[0]:
                        volatility = compute_portfolio_volatility(w, cov_matrix)

                    # Portfolio return (equal weight average of latest)
                    portfolio_ret = float(returns_df.mean().mean())

                    # VaR / CVaR from equal-weighted portfolio
                    portfolio_series = returns_df.mean(axis=1).values
                    var_95 = compute_var(portfolio_series, 0.95)
                    cvar_95 = compute_cvar(portfolio_series, 0.95)

                    # Beta vs first asset as market proxy
                    if len(valid_tickers) >= 2:
                        asset_ret = returns_df[valid_tickers[0]].values
                        market_ret = returns_df[valid_tickers[1]].values
                        portfolio_beta = compute_beta(asset_ret, market_ret)

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
            "portfolio_return": portfolio_ret,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "beta": portfolio_beta,
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
            "portfolio_return": None,
            "var_95": None,
            "cvar_95": None,
            "beta": None,
            "num_assets": 0,
            "num_classes": 0,
        }
