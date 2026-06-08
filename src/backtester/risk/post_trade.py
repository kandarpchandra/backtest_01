from enum import Enum, auto
from dataclasses import dataclass
from typing import List
from backtester.portfolio.pnl import AccountModel

class PostTradeAction(Enum):
    CONTINUE = auto()
    FLATTEN_ALL = auto()
    HALT_TRADING = auto()

@dataclass
class RiskDecision:
    action: PostTradeAction
    reason: str = ""

class PostTradeRiskEngine:
    def __init__(self):
        self.drawdown_control = None
        self.daily_loss_limit = None
        
    def set_drawdown_control(self, dc):
        self.drawdown_control = dc
        
    def set_daily_loss_limit(self, dll):
        self.daily_loss_limit = dll

    def check(self, portfolio: AccountModel) -> RiskDecision:
        if self.drawdown_control and not self.drawdown_control.check(portfolio):
            return RiskDecision(action=PostTradeAction.FLATTEN_ALL, reason="Max drawdown breached")
            
        if self.daily_loss_limit and not self.daily_loss_limit.check(portfolio):
            return RiskDecision(action=PostTradeAction.FLATTEN_ALL, reason="Daily loss limit breached")
            
        return RiskDecision(action=PostTradeAction.CONTINUE)
