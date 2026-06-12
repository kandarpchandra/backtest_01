from abc import ABC, abstractmethod
from backtester.pricing.base import AbstractPricer
from backtester.events.types import MarketDataEvent

class Instrument(ABC):
    """
    Base class for all tradable instruments.
    """
    def __init__(self, symbol: str, pricer: AbstractPricer):
        self.symbol = symbol
        self.pricer = pricer

    def get_value(self, data: MarketDataEvent) -> float:
        return self.pricer.get_value(data)

    def pnl_scalar(self, price_move: float) -> float:
        """
        Returns the cash PnL for a 1-lot move of price_move.
        Default: 1-to-1 mapping. Subclasses (e.g., STIR) override.
        """
        return price_move

    def position_value(self, qty: float, current_price: float, cost_basis: float) -> float:
        """
        Returns the contribution of this position to total portfolio equity.
        Equities: qty * current_price (standard equity model).
        Futures: unrealized variation margin PnL (overridden by subclasses).
        """
        return qty * current_price

    def cash_impact(self, qty: float, price: float) -> float:
        """
        Returns the cash impact of opening/adding to a position.
        Equities: deduct full notional (qty * price).
        Futures: deduct zero (margin is tracked separately). Overridden by subclasses.
        """
        return qty * price

class Decomposable(ABC):
    """
    Mixin interface for complex instruments that can be shattered into outright legs.
    """
    @abstractmethod
    def decompose(self, quantity: float) -> dict[str, float]:
        pass
