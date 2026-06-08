from backtester.analytics.metrics import calculate_returns, sharpe_ratio, sortino_ratio, max_drawdown
from backtester.portfolio.pnl import AccountModel
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class Tearsheet:
    def __init__(self, portfolio: AccountModel):
        self.portfolio = portfolio
        self.equity_curve = portfolio.equity_curve

    def generate_stats(self) -> dict:
        returns = calculate_returns(self.equity_curve)
        return {
            "Final Equity": self.equity_curve[-1] if self.equity_curve else self.portfolio.total_equity,
            "Realized PnL": self.portfolio.realized_pnl,
            "Total Commission": self.portfolio.total_commission,
            "Sharpe Ratio": sharpe_ratio(returns),
            "Sortino Ratio": sortino_ratio(returns),
            "Max Drawdown": max_drawdown(self.equity_curve) * 100 # percentage
        }

    def print_stats(self):
        stats = self.generate_stats()
        print("\n" + "="*50)
        print("BACKTEST TEARSHEET")
        print("="*50)
        for k, v in stats.items():
            if isinstance(v, float):
                print(f"{k:20s}: {v:.4f}")
            else:
                print(f"{k:20s}: {v}")
        print("="*50)

    def plot(self, save_path: str = None):
        if not self.equity_curve:
            print("No equity curve data to plot.")
            return

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=self.equity_curve, mode='lines', name='Equity'))
        fig.update_layout(title="Equity Curve", xaxis_title="Periods", yaxis_title="Equity")
        
        if save_path:
            fig.write_html(save_path)
            print(f"Plot saved to {save_path}")
        else:
            # We don't try to pop up a browser in backtests blindly
            pass
