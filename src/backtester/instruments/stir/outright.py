from backtester.instruments.base import Instrument
from backtester.pricing.base import LinearPricer

class STIROutright(Instrument):
    def __init__(self, symbol: str, tick_size: float, tick_value: float):
        super().__init__(symbol, pricer=LinearPricer(multiplier=tick_value / tick_size))
        self.tick_size = tick_size
        self.tick_value = tick_value

    def pnl_scalar(self, price_move: float) -> float:
        """
        PnL for 1 lot: (price_move / tick_size) * tick_value
        """
        return (price_move / self.tick_size) * self.tick_value

    def dv01(self) -> float:
        """
        Dollar value of a 1 basis point (0.01) move.
        """
        return self.pnl_scalar(0.01)

# Factory helpers for common STIR contracts
def make_euribor(symbol: str) -> STIROutright:
    # ICE Euribor: 0.005 tick size = €12.50 tick value (frontend)
    # Using 0.005 / €12.50 for all for simplicity in backtest unless frontend vs deferred needed
    return STIROutright(symbol, tick_size=0.005, tick_value=12.50)

def make_sofr(symbol: str) -> STIROutright:
    # CME SR3: 0.005 tick size = $12.50 tick value (mostly)
    return STIROutright(symbol, tick_size=0.005, tick_value=12.50)

def make_sonia(symbol: str) -> STIROutright:
    # ICE SONIA: 0.005 tick size = £12.50 tick value
    return STIROutright(symbol, tick_size=0.005, tick_value=12.50)

def make_fed_funds(symbol: str) -> STIROutright:
    # CBOT ZQ: 0.005 tick size = $20.835 tick value
    return STIROutright(symbol, tick_size=0.005, tick_value=20.835)
