import pytest
import numpy as np
from backtester.analytics.metrics import calculate_returns, sharpe_ratio, sortino_ratio, max_drawdown

def test_calculate_returns():
    equity_curve = [100.0, 105.0, 99.75, 109.725]
    returns = calculate_returns(equity_curve)
    
    assert len(returns) == 3
    assert returns[0] == pytest.approx(0.05)
    assert returns[1] == pytest.approx(-0.05)
    assert returns[2] == pytest.approx(0.10)

def test_sharpe_ratio():
    # Returns with mean = 0.05, std (ddof=1) = ~0.0707
    # Note ddof=1 means we divide by N-1
    returns = np.array([0.10, 0.0])
    
    # RFR = 0, so mean_excess = 0.05
    # std = sqrt((0.05^2 + (-0.05)^2) / 1) = sqrt(0.005) = 0.0707106
    # Sharpe = (0.05 / 0.0707106) * sqrt(252) = 0.707106 * 15.8745 = 11.225
    
    sharpe = sharpe_ratio(returns, risk_free_rate=0.0, periods=252)
    assert sharpe == pytest.approx(11.22497, rel=1e-4)

def test_sortino_ratio():
    returns = np.array([0.10, -0.05, 0.05, 0.0])
    # Mean = 0.025
    # RFR = 0
    # Downside = [0, -0.05, 0, 0]
    # Downside dev = sqrt(mean(0 + 0.0025 + 0 + 0)) = sqrt(0.000625) = 0.025
    # Sortino = (0.025 / 0.025) * sqrt(252) = 1.0 * 15.8745
    
    sortino = sortino_ratio(returns, risk_free_rate=0.0, periods=252)
    assert sortino == pytest.approx(np.sqrt(252), rel=1e-4)

def test_sortino_ratio_no_downside():
    returns = np.array([0.10, 0.05, 0.02])
    # Downside dev = 0
    sortino = sortino_ratio(returns, risk_free_rate=0.0, periods=252)
    assert sortino == float('inf')

def test_max_drawdown():
    equity_curve = [100.0, 110.0, 99.0, 105.0, 89.1, 120.0]
    # Peaks: 100, 110, 110, 110, 110, 120
    # Drawdowns: 0, 0, 11/110=0.10, 5/110=~0.045, 20.9/110=0.19, 0
    
    dd = max_drawdown(equity_curve)
    assert dd == pytest.approx(0.19)
