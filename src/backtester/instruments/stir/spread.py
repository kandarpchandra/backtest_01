from backtester.instruments.base import Instrument, Decomposable
from backtester.instruments.stir.outright import STIROutright
from backtester.pricing.base import LinearPricer

class STIRSpread(Instrument, Decomposable):
    """
    Calendar spread (e.g. ERZ4-ERH5).
    Priced as Front Leg - Back Leg.
    """
    def __init__(self, symbol: str, front_leg: STIROutright, back_leg: STIROutright):
        # A spread moves based on the tick parameters of the underlying legs.
        super().__init__(symbol, pricer=LinearPricer(multiplier=front_leg.tick_value / front_leg.tick_size))
        self.front_leg = front_leg
        self.back_leg = back_leg

    def decompose(self, quantity: float) -> dict[str, float]:
        return {
            self.front_leg.symbol: quantity,
            self.back_leg.symbol: -quantity
        }
