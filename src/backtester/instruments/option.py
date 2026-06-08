from backtester.instruments.base import Instrument
from backtester.pricing.options import BlackScholesPricer

class VanillaOption(Instrument):
    def __init__(self, symbol: str, strike: float, expiry_years: float, is_call: bool):
        pricer = BlackScholesPricer(strike, expiry_years, is_call)
        super().__init__(symbol, pricer=pricer)
