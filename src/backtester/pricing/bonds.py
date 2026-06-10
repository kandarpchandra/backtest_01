from backtester.pricing.base import AbstractPricer
from backtester.events.types import YieldDataEvent, MarketDataEvent

class YieldToPricePricer(AbstractPricer):
    """
    Standard bond math to convert Yield to Price.
    """
    def __init__(self, face_value: float, coupon_rate: float, periods_per_year: int = 2):
        self.face_value = face_value
        self.coupon_rate = coupon_rate
        self.periods = periods_per_year

    def get_value(self, data: MarketDataEvent) -> float:
        if not isinstance(data, YieldDataEvent):
            raise ValueError("YieldToPricePricer requires YieldDataEvent")
            
        # Simplified continuous duration pricing for MVP
        # In reality, this requires full cash-flow discounting over remaining periods
        dy = data.ytm - self.coupon_rate
        price_change_pct = -data.duration * dy + 0.5 * data.convexity * (dy ** 2)
        
        # Approximate price
        return float(self.face_value * (1 + price_change_pct))
