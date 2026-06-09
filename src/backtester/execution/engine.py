from backtester.events.types import OrderEvent, FillEvent, OrderType, TradeBarEvent, OrderStatus
from backtester.events.queue import AbstractEventQueue
from backtester.execution.slippage import AbstractSlippageModel, ZeroSlippage
from backtester.execution.transaction_cost import AbstractTransactionCostModel, ZeroTCM
from backtester.execution.oms import OrderTracker

class OrderBookMatcher:
    def __init__(self, 
                 oms: OrderTracker,
                 slippage_model: AbstractSlippageModel = ZeroSlippage(),
                 tcm: AbstractTransactionCostModel = ZeroTCM()):
        self.oms = oms
        self.slippage_model = slippage_model
        self.tcm = tcm
        self.current_bars = {}

    def update_market_bar(self, bar: TradeBarEvent, queue: AbstractEventQueue) -> None:
        """Called on every new bar to evaluate all pending orders in the OMS."""
        self.current_bars[bar.symbol] = bar
        
        for state in self.oms.get_active_orders():
            if state.order.symbol == bar.symbol:
                self._evaluate_order_state(state, bar, queue)

    def on_order(self, order: OrderEvent, queue: AbstractEventQueue) -> None:
        """New order arrived from the queue."""
        self.oms.submit_order(order)
        # Attempt immediate fill if we have market data
        bar = self.current_bars.get(order.symbol)
        if bar:
            state = self.oms.active_orders.get(order.event_id)
            if state:
                self._evaluate_order_state(state, bar, queue)

    def _evaluate_order_state(self, state: 'OrderState', bar: TradeBarEvent, queue: AbstractEventQueue) -> None:
        if state.status not in (OrderStatus.ACCEPTED, OrderStatus.PARTIAL):
            return

        order = state.order
        base_fill_price = bar.close 
        
        if order.order_type == OrderType.LIMIT:
            if order.price is None:
                raise ValueError("Limit order missing price")
            if order.direction.name == 'LONG' and bar.low > order.price:
                return # Did not reach limit
            elif order.direction.name == 'SHORT' and bar.high < order.price:
                return # Did not reach limit
            base_fill_price = order.price
            
        elif order.order_type == OrderType.STOP:
            if order.price is None:
                raise ValueError("Stop order missing price")
            if order.direction.name == 'LONG' and bar.high < order.price:
                return
            elif order.direction.name == 'SHORT' and bar.low > order.price:
                return
            base_fill_price = order.price

        # Simulate Queue / Partial Fills
        # A simple model: you can only fill up to 10% of the bar's volume
        available_volume = bar.volume * 0.10
        remaining_qty = order.quantity - state.filled_quantity
        
        fill_qty = min(remaining_qty, available_volume)
        if fill_qty <= 0:
            return

        # Calculate slippage & commissions on the partial fill
        slippage = self.slippage_model.calculate_slippage(order, base_fill_price, bar.volume)
        actual_price = base_fill_price + slippage
        commission = self.tcm.calculate_commission(fill_qty, actual_price)

        # Update order state
        state.filled_quantity += fill_qty
        if state.filled_quantity >= order.quantity:
            state.status = OrderStatus.FILLED
            self.oms.close_order(order.event_id) # Preserves FILLED status
        else:
            state.status = OrderStatus.PARTIAL

        # Emit the fill
        fill = FillEvent(
            timestamp=bar.timestamp,
            symbol=order.symbol,
            direction=order.direction,
            quantity=fill_qty,
            fill_price=actual_price,
            commission=commission
        )
        queue.put(fill)
