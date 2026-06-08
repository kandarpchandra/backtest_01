from backtester.instruments.base import Instrument
from backtester.pricing.base import LinearPricer

class Equity(Instrument):
    def __init__(self, symbol: str, multiplier: float = 1.0):
        super().__init__(symbol, pricer=LinearPricer(multiplier=multiplier))
        self.multiplier = multiplier

    def pnl_scalar(self, price_move: float) -> float:
        return price_move * self.multiplier
