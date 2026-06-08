from backtester.portfolio.pnl import AccountModel

class DrawdownControl:
    def __init__(self, max_drawdown_pct: float):
        self.max_drawdown_pct = max_drawdown_pct
        self.peak_equity = 0.0
        self.breached = False

    def check(self, portfolio: AccountModel) -> bool:
        if self.breached:
            return False # Halt trading forever

        current_equity = portfolio.total_equity # Simple MVP
        if portfolio.equity_curve:
            current_equity = portfolio.equity_curve[-1]

        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        if self.peak_equity > 0:
            dd = (self.peak_equity - current_equity) / self.peak_equity
            if dd >= self.max_drawdown_pct:
                self.breached = True
                return False

        return True
