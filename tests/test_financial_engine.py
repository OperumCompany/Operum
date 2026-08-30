import numpy as np
import pandas as pd

from app.services.financial_engine import (
    compute_simple_return,
    compute_log_return,
    compute_cumulative_return,
    compute_volatility,
    compute_covariance_matrix,
    compute_correlation_matrix,
    compute_beta,
    compute_alpha,
    compute_var,
    compute_cvar,
    compute_drawdown,
    compute_moving_average,
    compute_ema,
    compute_rsi,
    compute_macd,
    compute_portfolio_weights,
    compute_portfolio_return,
    compute_portfolio_volatility,
    compute_portfolio_concentration,
    compute_capm_expected_return,
    compute_cagr,
)


def test_simple_return():
    prices = np.array([100, 102, 101, 105])
    ret = compute_simple_return(prices)
    expected = np.array([0.02, -0.00980392, 0.03960396])
    np.testing.assert_allclose(ret, expected, rtol=1e-4)


def test_log_return():
    prices = np.array([100, 102, 101])
    ret = compute_log_return(prices)
    expected = np.log(102 / 100), np.log(101 / 102)
    assert abs(ret[0] - expected[0]) < 1e-6
    assert abs(ret[1] - expected[1]) < 1e-6


def test_cumulative_return():
    returns = np.array([0.02, -0.01, 0.03])
    cr = compute_cumulative_return(returns)
    expected = (1.02 * 0.99 * 1.03) - 1
    assert abs(cr - expected) < 1e-6


def test_volatility():
    returns = np.array([0.01, -0.01, 0.02, -0.02, 0.01])
    vol = compute_volatility(returns, window=252)
    assert vol > 0
    assert isinstance(vol, float)


def test_covariance_and_correlation():
    df = pd.DataFrame({"a": [0.01, -0.01, 0.02], "b": [0.02, -0.02, 0.01]})
    cov = compute_covariance_matrix(df)
    corr = compute_correlation_matrix(df)
    assert cov.shape == (2, 2)
    assert corr.shape == (2, 2)


def test_beta():
    asset = np.array([0.01, -0.01, 0.02, 0.015, -0.005])
    market = np.array([0.008, -0.008, 0.015, 0.01, -0.003])
    beta = compute_beta(asset, market)
    assert isinstance(beta, float)
    assert beta > 0


def test_alpha():
    asset = np.array([0.01, -0.01, 0.02])
    market = np.array([0.008, -0.008, 0.015])
    alpha = compute_alpha(asset, market)
    assert isinstance(alpha, float)


def test_var():
    returns = np.array([-0.05, -0.03, 0.01, 0.02, -0.04, 0.03, -0.02, 0.01])
    var_95 = compute_var(returns, 0.95)
    assert var_95 <= 0
    assert var_95 > -1


def test_cvar():
    returns = np.array([-0.05, -0.03, 0.01, 0.02, -0.04, 0.03, -0.02, 0.01])
    cvar_95 = compute_cvar(returns, 0.95)
    assert cvar_95 <= 0
    assert cvar_95 >= -1


def test_drawdown():
    prices = np.array([100, 105, 102, 110, 108, 115])
    dd = compute_drawdown(prices)
    assert dd <= 0


def test_moving_average():
    prices = np.array([1, 2, 3, 4, 5])
    ma = compute_moving_average(prices, window=3)
    assert len(ma) == 5
    assert np.isnan(ma[0])
    assert np.isnan(ma[1])
    assert not np.isnan(ma[2])


def test_ema():
    prices = np.array([10, 11, 12, 11, 10])
    ema = compute_ema(prices, span=3)
    assert len(ema) == 5
    assert ema[0] == 10


def test_rsi():
    prices = np.array([100]*20)
    rsi = compute_rsi(prices, window=14)
    assert rsi[-1] == 50.0


def test_macd():
    prices = np.array([10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10])
    macd = compute_macd(prices)
    assert "macd" in macd
    assert "signal" in macd
    assert "histogram" in macd
    assert len(macd["macd"]) == len(prices)


def test_portfolio_weights():
    quantities = np.array([100, 50])
    prices = np.array([10, 20])
    weights = compute_portfolio_weights(quantities, prices)
    np.testing.assert_allclose(weights, [0.5, 0.5], rtol=1e-4)


def test_portfolio_return():
    weights = np.array([0.6, 0.4])
    returns = np.array([0.05, 0.03])
    pr = compute_portfolio_return(weights, returns)
    assert abs(pr - 0.042) < 1e-6


def test_portfolio_volatility():
    weights = np.array([0.5, 0.5])
    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]])
    vol = compute_portfolio_volatility(weights, cov)
    assert vol > 0


def test_portfolio_concentration():
    weights = np.array([0.5, 0.5])
    conc = compute_portfolio_concentration(weights)
    assert abs(conc) < 1e-6  # equal weights -> 0 concentration

    weights2 = np.array([1.0, 0.0])
    conc2 = compute_portfolio_concentration(weights2)
    assert abs(conc2 - 1.0) < 1e-6  # single asset -> 1


def test_capm_expected_return():
    er = compute_capm_expected_return(0.05, 1.2, 0.10)
    expected = 0.05 + 1.2 * (0.10 - 0.05)
    assert abs(er - expected) < 1e-6


def test_cagr():
    cagr = compute_cagr(100, 121, 2)
    assert abs(cagr - 0.1) < 1e-6
