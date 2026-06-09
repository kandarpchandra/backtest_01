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

class Decomposable(ABC):
    """
    Mixin interface for complex instruments that can be shattered into outright legs.
    """
    @abstractmethod
    def decompose(self, quantity: float) -> dict[str, float]:
        pass
