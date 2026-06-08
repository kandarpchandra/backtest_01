from abc import ABC, abstractmethod
from typing import Dict
from backtester.events.types import SignalEvent, OrderEvent, OrderType, SignalDirection
from backtester.portfolio.pnl import AccountModel

class AbstractCapitalAllocator(ABC):
    @abstractmethod
    def allocate(self, signal: SignalEvent, portfolio: AccountModel) -> OrderEvent | None:
        pass

class FixedLotSizer(AbstractCapitalAllocator):
    def __init__(self, fixed_qty: float = 1.0):
        self.fixed_qty = fixed_qty

    def allocate(self, signal: SignalEvent, portfolio: AccountModel) -> OrderEvent | None:
        if signal.direction == SignalDirection.FLAT:
            # Need to close existing position
            current_qty = portfolio.positions.get(signal.symbol, 0.0)
            if current_qty == 0:
                return None
            direction = SignalDirection.SHORT if current_qty > 0 else SignalDirection.LONG
            qty = abs(current_qty)
        else:
            direction = signal.direction
            qty = self.fixed_qty * signal.strength

        return OrderEvent(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            direction=direction,
            quantity=qty,
            order_type=OrderType.MARKET
        )

class PercentEquitySizer(AbstractCapitalAllocator):
    def __init__(self, percent: float = 0.01):
        self.percent = percent

    def allocate(self, signal: SignalEvent, portfolio: AccountModel) -> OrderEvent | None:
        if signal.direction == SignalDirection.FLAT:
            current_qty = portfolio.positions.get(signal.symbol, 0.0)
            if current_qty == 0:
                return None
            direction = SignalDirection.SHORT if current_qty > 0 else SignalDirection.LONG
            return OrderEvent(
                timestamp=signal.timestamp,
                symbol=signal.symbol,
                direction=direction,
                quantity=abs(current_qty),
                order_type=OrderType.MARKET
            )
        
        # Simple implementation, real world needs to account for margin/leverage
        equity = portfolio.total_equity
        alloc_value = equity * self.percent * signal.strength
        price = portfolio.current_prices.get(signal.symbol, 0.0)
        
        if price <= 0:
            return None
            
        qty = round(alloc_value / price)
        if qty <= 0:
            return None

        return OrderEvent(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=qty,
            order_type=OrderType.MARKET
        )
