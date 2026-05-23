"""
Funções financeiras puras — sem efeitos colaterais, sem IO.
Cada função recebe dados, retorna resultado.
"""
import numpy as np
import pandas as pd


def compute_simple_return(prices: np.ndarray) -> np.ndarray:
    return np.diff(prices) / prices[:-1]


def compute_log_return(prices: np.ndarray) -> np.ndarray:
    return np.diff(np.log(prices))


def compute_cumulative_return(returns: np.ndarray) -> float:
    return float(np.prod(1 + returns) - 1)


def compute_volatility(returns: np.ndarray, window: int = 252) -> float:
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(window))


def compute_covariance_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    return returns_df.cov()


def compute_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    return returns_df.corr()


def compute_beta(asset_returns: np.ndarray, market_returns: np.ndarray) -> float:
    if len(asset_returns) < 2 or len(market_returns) < 2:
        return 1.0
    cov = np.cov(asset_returns, market_returns, ddof=1)[0, 1]
    mkt_var = np.var(market_returns, ddof=1)
    if mkt_var == 0:
        return 1.0
    return float(cov / mkt_var)


def compute_alpha(
    asset_returns: np.ndarray,
    market_returns: np.ndarray,
    risk_free_rate: float = 0.0,
) -> float:
    beta = compute_beta(asset_returns, market_returns)
    expected = risk_free_rate + beta * (np.mean(market_returns) - risk_free_rate)
    return float(np.mean(asset_returns) - expected)


def compute_var(returns: np.ndarray, confidence_level: float = 0.95) -> float:
    if len(returns) < 2:
        return 0.0
    return float(np.percentile(returns, (1 - confidence_level) * 100))


def compute_cvar(returns: np.ndarray, confidence_level: float = 0.95) -> float:
    var = compute_var(returns, confidence_level)
    tail = returns[returns <= var]
    if len(tail) == 0:
        return var
    return float(np.mean(tail))


def compute_drawdown(prices: np.ndarray) -> float:
    if len(prices) < 2:
        return 0.0
    peak = np.maximum.accumulate(prices)
    drawdown = (prices - peak) / peak
    return float(np.min(drawdown))


def compute_moving_average(prices: np.ndarray, window: int = 20) -> np.ndarray:
    if len(prices) < window:
        return np.full_like(prices, np.nan)
    return pd.Series(prices).rolling(window=window).mean().values


def compute_ema(prices: np.ndarray, span: int = 20) -> np.ndarray:
    if len(prices) < 2:
        return prices
    return pd.Series(prices).ewm(span=span, adjust=False).mean().values


def compute_rsi(prices: np.ndarray, window: int = 14) -> np.ndarray:
    if len(prices) < window + 1:
        return np.full_like(prices, 50.0)
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = pd.Series(gains).rolling(window=window).mean().values
    avg_loss = pd.Series(losses).rolling(window=window).mean().values
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    rs = np.where(avg_loss == 0, np.where(avg_gain == 0, 1.0, 100.0), rs)
    rs = np.where(avg_gain == 0, np.where(avg_loss == 0, 1.0, 0.0), rs)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(
    prices: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    ema_fast = compute_ema(prices, fast)
    ema_slow = compute_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def compute_portfolio_weights(quantities: np.ndarray, prices: np.ndarray) -> np.ndarray:
    values = quantities * prices
    total = np.sum(values)
    if total == 0:
        return np.full_like(quantities, 1.0 / len(quantities))
    return values / total


def compute_portfolio_return(weights: np.ndarray, returns: np.ndarray) -> float:
    if weights.shape != returns.shape:
        returns = returns[-len(weights):] if len(returns) >= len(weights) else np.pad(returns, (len(weights) - len(returns), 0), 'edge')
    return float(np.dot(weights, returns))


def compute_portfolio_volatility(
    weights: np.ndarray, cov_matrix: pd.DataFrame
) -> float:
    w = np.array(weights)
    if w.shape[0] != cov_matrix.shape[0]:
        return 0.0
    var = w.T @ cov_matrix.values @ w
    return float(np.sqrt(max(0, var)))


def compute_portfolio_concentration(weights: np.ndarray) -> float:
    hhi = np.sum(weights**2)
    return float((hhi - 1 / len(weights)) / (1 - 1 / len(weights))) if len(weights) > 1 else 1.0


def compute_capm_expected_return(
    risk_free_rate: float, beta: float, market_return: float
) -> float:
    return risk_free_rate + beta * (market_return - risk_free_rate)


def compute_cagr(initial_value: float, final_value: float, periods: int) -> float:
    if initial_value <= 0 or periods <= 0:
        return 0.0
    return float((final_value / initial_value) ** (1 / periods) - 1)
