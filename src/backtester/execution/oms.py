from typing import Dict, List
from backtester.events.types import OrderEvent, OrderStatus, FillEvent

class OrderState:
    def __init__(self, order: OrderEvent):
        self.order = order
        self.status: OrderStatus = OrderStatus.PENDING
        self.filled_quantity: float = 0.0

class OrderTracker:
    """
    Stateful Order Management System (OMS).
    Tracks the lifecycle of orders from PENDING -> FILLED / CANCELLED.
    """
    def __init__(self):
        self.active_orders: Dict[str, OrderState] = {} # uuid -> OrderState
        self.closed_orders: Dict[str, OrderState] = {}

    def submit_order(self, order: OrderEvent) -> None:
        """Register a new order into the OMS."""
        state = OrderState(order)
        state.status = OrderStatus.ACCEPTED
        self.active_orders[order.event_id] = state

    def get_active_orders(self) -> List[OrderState]:
        return list(self.active_orders.values())

    def cancel_order(self, event_id: str) -> None:
        order = self.active_orders.get(event_id)
        if order:
            order.status = OrderStatus.CANCELLED
            self.closed_orders[event_id] = order
            del self.active_orders[event_id]
