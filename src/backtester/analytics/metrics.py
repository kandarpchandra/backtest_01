import numpy as np

def calculate_returns(equity_curve: list[float]) -> np.ndarray:
    if len(equity_curve) < 2:
        return np.array([])
    prices = np.array(equity_curve)
    return np.diff(prices) / prices[:-1]

def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0, periods: int = 252) -> float:
    if len(returns) == 0:
        return 0.0
    per_period_rfr = risk_free_rate / periods
    excess_returns = returns - per_period_rfr
    mean_excess = np.mean(excess_returns)
    std_return = np.std(returns, ddof=1)
    if std_return == 0:
        return 0.0
    return (mean_excess / std_return) * np.sqrt(periods)

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
    per_period_rfr = risk_free_rate / periods
    mean_excess = np.mean(returns) - per_period_rfr
    # Proper downside deviation: RMS of all observations below target
    downside = np.minimum(returns - per_period_rfr, 0.0)
    downside_dev = np.sqrt(np.mean(downside ** 2))
    if downside_dev == 0:
        return float('inf')
    return (mean_excess / downside_dev) * np.sqrt(periods)

