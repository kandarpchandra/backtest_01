from backtester.instruments.base import Instrument
from backtester.pricing.bonds import YieldToPricePricer

class FixedRateBond(Instrument):
    def __init__(self, symbol: str, face_value: float, coupon_rate: float):
        pricer = YieldToPricePricer(face_value, coupon_rate)
        super().__init__(symbol, pricer=pricer)
