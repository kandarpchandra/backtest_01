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

class Decomposable(ABC):
    """
    Interface for complex instruments that can be shattered into outright legs.
    """
    @abstractmethod
    def decompose(self, quantity: float) -> dict[str, float]:
        pass

    def pnl_scalar(self, price_move: float) -> float:
        """Deprecated: Retained for MVP compatibility until full pricer migration"""
        """
        Returns the cash PnL for a 1-lot move of price_move.
        Stateless calculation - knows nothing about position or cost basis.
        """
        pass
