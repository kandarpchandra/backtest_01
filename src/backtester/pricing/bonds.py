from backtester.pricing.base import AbstractPricer
from backtester.events.types import YieldDataEvent, MarketDataEvent

class YieldToPricePricer(AbstractPricer):
    """
    Duration-convexity approximation for bond price changes.
    Tracks the reference yield across calls so that dy is measured
    from the previous yield observation, not from the coupon rate.
    """
    def __init__(self, face_value: float, coupon_rate: float, periods_per_year: int = 2):
        self.face_value = face_value
        self.coupon_rate = coupon_rate
        self.periods = periods_per_year
        # Reference yield: start at par (coupon_rate), updated on each call
        self._reference_ytm: float | None = None
        self._reference_price: float = face_value  # Par price initially

    def get_value(self, data: MarketDataEvent) -> float:
        if not isinstance(data, YieldDataEvent):
            raise ValueError("YieldToPricePricer requires YieldDataEvent")

        if self._reference_ytm is None:
            # First observation: set reference and compute price at par
            self._reference_ytm = data.ytm
            self._reference_price = self.face_value
            return self._reference_price

        # Duration-convexity approximation: dP/P ≈ -D*dy + 0.5*C*dy²
        dy = data.ytm - self._reference_ytm
        price_change_pct = -data.duration * dy + 0.5 * data.convexity * (dy ** 2)
        new_price = float(self._reference_price * (1 + price_change_pct))

        # Update reference for next call
        self._reference_ytm = data.ytm
        self._reference_price = new_price

        return new_price
