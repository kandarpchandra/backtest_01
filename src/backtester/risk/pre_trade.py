from abc import ABC, abstractmethod
from typing import Dict
from backtester.events.types import OrderEvent, SignalDirection
from backtester.portfolio.pnl import AccountModel

class AbstractPreTradeCheck(ABC):
    @abstractmethod
    def validate(self, order: OrderEvent, portfolio: AccountModel) -> bool:
        pass

class PositionLimitCheck(AbstractPreTradeCheck):
    def __init__(self, limits: Dict[str, float]):
        self.limits = limits

    def validate(self, order: OrderEvent, portfolio: AccountModel) -> bool:
        limit = self.limits.get(order.symbol)
        if limit is None:
            return True # No limit set
            
        current_qty = portfolio.positions.get(order.symbol, 0.0)
        
        # Calculate new absolute position
        if order.direction == SignalDirection.LONG:
            new_qty = current_qty + order.quantity
        elif order.direction == SignalDirection.SHORT:
            new_qty = current_qty - order.quantity
        else:
            return True # Flat orders are always allowed
            
        return abs(new_qty) <= limit

class PreTradeRiskEngine:
    def __init__(self):
        self.checks = []

    def add_check(self, check: AbstractPreTradeCheck) -> None:
        self.checks.append(check)

    def validate(self, order: OrderEvent, portfolio: AccountModel) -> bool:
        for check in self.checks:
            if not check.validate(order, portfolio):
                return False
        return True
