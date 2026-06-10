from backtester.instruments.base import Instrument
from backtester.pricing.options import BlackScholesPricer

class VanillaOption(Instrument):
    def __init__(self, symbol: str, strike: float, expiry_timestamp: float, is_call: bool):
        pricer = BlackScholesPricer(strike, expiry_timestamp, is_call)
        super().__init__(symbol, pricer=pricer)

    def pnl_scalar(self, price_move: float) -> float:
        return price_move * 100.0
