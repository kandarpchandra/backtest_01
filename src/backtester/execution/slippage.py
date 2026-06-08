from abc import ABC, abstractmethod
from backtester.events.types import OrderEvent, SignalDirection

class AbstractSlippageModel(ABC):
    @abstractmethod
    def calculate_slippage(self, order: OrderEvent, fill_price: float, bar_volume: float = 0.0) -> float:
        pass

class ZeroSlippage(AbstractSlippageModel):
    def calculate_slippage(self, order: OrderEvent, fill_price: float, bar_volume: float = 0.0) -> float:
        return 0.0

class FixedBasisPointSlippage(AbstractSlippageModel):
    def __init__(self, bps: float = 1.0):
        self.bps = bps / 10000.0

    def calculate_slippage(self, order: OrderEvent, fill_price: float, bar_volume: float = 0.0) -> float:
        slip_amount = fill_price * self.bps
        # Slippage is always adverse
        if order.direction == SignalDirection.LONG:
            return slip_amount
        elif order.direction == SignalDirection.SHORT:
            return -slip_amount
        return 0.0

class VolumeLinearSlippage(AbstractSlippageModel):
    def __init__(self, impact_factor: float = 0.1):
        self.impact_factor = impact_factor

    def calculate_slippage(self, order: OrderEvent, fill_price: float, bar_volume: float = 0.0) -> float:
        if bar_volume <= 0:
            return 0.0
            
        # Impact is proportional to participation rate
        participation_rate = order.quantity / bar_volume
        slip_pct = participation_rate * self.impact_factor
        slip_amount = fill_price * slip_pct
        
        if order.direction == SignalDirection.LONG:
            return slip_amount
        elif order.direction == SignalDirection.SHORT:
            return -slip_amount
        return 0.0
