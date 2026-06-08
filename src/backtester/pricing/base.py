from abc import ABC, abstractmethod
from backtester.events.types import MarketDataEvent

class AbstractPricer(ABC):
    @abstractmethod
    def get_value(self, data: MarketDataEvent) -> float:
        """Returns the theoretical mark-to-market dollar value based on market data."""
        pass

class LinearPricer(AbstractPricer):
    """
    Standard pricer for linear assets (Equities, Futures).
    Value = Price * Multiplier
    """
    def __init__(self, multiplier: float = 1.0):
        self.multiplier = multiplier

    def get_value(self, data: MarketDataEvent) -> float:
        if not hasattr(data, 'close'):
            raise ValueError("LinearPricer requires TradeBarEvent with 'close' price")
        return data.close * self.multiplier
