import numpy as np
from scipy.stats import norm
from backtester.pricing.base import AbstractPricer
from backtester.events.types import OptionDataEvent, MarketDataEvent

class BlackScholesPricer(AbstractPricer):
    """
    Theoretical Black-Scholes pricing model for European options.
    """
    def __init__(self, strike: float, expiry_years: float, is_call: bool, risk_free_rate: float = 0.0):
        self.strike = strike
        self.expiry_years = expiry_years
        self.is_call = is_call
        self.r = risk_free_rate

    def get_value(self, data: MarketDataEvent) -> float:
        if not isinstance(data, OptionDataEvent):
            raise ValueError("BlackScholesPricer requires OptionDataEvent")
            
        S = data.underlying_price
        K = self.strike
        T = self.expiry_years
        r = self.r
        sigma = data.iv
        
        if T <= 0:
            return max(0.0, S - K) if self.is_call else max(0.0, K - S)

        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if self.is_call:
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        return float(price)
