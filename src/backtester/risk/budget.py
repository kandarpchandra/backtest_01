from backtester.portfolio.pnl import AccountModel

class DailyLossLimit:
    def __init__(self, max_loss_pct: float):
        self.max_loss_pct = max_loss_pct
        self.start_of_day_equity = 0.0

    def start_day(self, portfolio: AccountModel):
        self.start_of_day_equity = portfolio.equity_curve[-1] if portfolio.equity_curve else portfolio.total_equity

    def check(self, portfolio: AccountModel) -> bool:
        if self.start_of_day_equity <= 0:
            return True

        current_equity = portfolio.equity_curve[-1] if portfolio.equity_curve else portfolio.total_equity
        loss_pct = (self.start_of_day_equity - current_equity) / self.start_of_day_equity

        if loss_pct >= self.max_loss_pct:
            return False # Breached limit
            
        return True
