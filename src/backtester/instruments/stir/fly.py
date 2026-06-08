from backtester.instruments.base import Instrument, Decomposable
from backtester.instruments.stir.outright import STIROutright
from backtester.pricing.base import LinearPricer

class STIRFly(Instrument, Decomposable):
    """
    Butterfly spread (e.g. ERZ4-ERH5-ERM5).
    Priced as Front - 2*Mid + Back.
    """
    def __init__(self, symbol: str, front_leg: STIROutright, mid_leg: STIROutright, back_leg: STIROutright):
        super().__init__(symbol, pricer=LinearPricer(multiplier=front_leg.tick_value / front_leg.tick_size))
        self.front_leg = front_leg
        self.mid_leg = mid_leg
        self.back_leg = back_leg

    def decompose(self, quantity: float) -> dict[str, float]:
        return {
            self.front_leg.symbol: quantity,
            self.mid_leg.symbol: -2.0 * quantity,
            self.back_leg.symbol: quantity
        }
