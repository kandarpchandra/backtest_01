from backtester.events.types import OrderEvent, FillEvent
from backtester.events.queue import AbstractEventQueue

class SimpleExecutionModel:
    def __init__(self, commission_rate: float = 0.001):
        self.commission_rate = commission_rate
        self.current_prices = {}

    def update_market_price(self, symbol: str, price: float) -> None:
        self.current_prices[symbol] = price

    def on_order(self, order: OrderEvent, queue: AbstractEventQueue) -> None:
        # Simple fill at last known price (or 0 if unknown)
        fill_price = self.current_prices.get(order.symbol, 0.0)
        
        commission = fill_price * order.quantity * self.commission_rate

        fill = FillEvent(
            timestamp=order.timestamp,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission
        )
        queue.put(fill)
