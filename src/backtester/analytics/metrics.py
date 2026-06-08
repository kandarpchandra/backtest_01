import numpy as np

def calculate_returns(equity_curve: list[float]) -> np.ndarray:
    if len(equity_curve) < 2:
        return np.array([])
    prices = np.array(equity_curve)
    return np.diff(prices) / prices[:-1]

def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0, periods: int = 252) -> float:
    if len(returns) == 0:
        return 0.0
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    if std_return == 0:
        return 0.0
    return (mean_return - risk_free_rate) / std_return * np.sqrt(periods)

def max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    equity = np.array(equity_curve)
    peaks = np.maximum.accumulate(equity)
    drawdowns = (peaks - equity) / peaks
    return np.max(drawdowns)

def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.0, periods: int = 252) -> float:
    if len(returns) == 0:
        return 0.0
    downside_returns = returns[returns < 0]
    if len(downside_returns) == 0:
        return float('inf') # Infinite sortino if no downside
    downside_std = np.std(downside_returns)
    mean_return = np.mean(returns)
    if downside_std == 0:
        return float('inf')
    return (mean_return - risk_free_rate) / downside_std * np.sqrt(periods)
