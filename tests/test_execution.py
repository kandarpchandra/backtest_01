import pytest
from backtester.execution.engine import OrderBookMatcher
from backtester.execution.oms import OrderTracker
from backtester.events.types import OrderEvent, SignalDirection, TradeBarEvent, OrderType
from backtester.events.queue import SyncEventQueue

def test_execution_no_lookahead_bias():
    oms = OrderTracker()
    execution = OrderBookMatcher(oms)
    queue = SyncEventQueue()
    
    # 1. First Bar Arrives (Time 1)
    bar1 = TradeBarEvent(timestamp=1.0, symbol="AAPL", open=100, high=100, low=100, close=100, volume=1000)
    execution.update_market_bar(bar1, queue)
    
    # 2. Strategy decides to buy based on bar1, sends Order
    order = OrderEvent(timestamp=1.0, symbol="AAPL", direction=SignalDirection.LONG, quantity=100, order_type=OrderType.MARKET)
    execution.on_order(order, queue)
    
    # Assert nothing filled yet (no immediate fill on the same bar)
    assert queue.empty()
    
    # 3. Next Bar Arrives (Time 2)
    bar2 = TradeBarEvent(timestamp=2.0, symbol="AAPL", open=105, high=105, low=105, close=105, volume=1000)
    execution.update_market_bar(bar2, queue)
    
    # Order should now fill at the new bar's price (105)
    assert not queue.empty()
    fill = queue.get()
    assert fill.fill_price == 105.0
    assert fill.quantity == 100.0

def test_limit_order_execution():
    oms = OrderTracker()
    execution = OrderBookMatcher(oms)
    queue = SyncEventQueue()
    
    # Limit Buy @ 98
    order = OrderEvent(timestamp=1.0, symbol="AAPL", direction=SignalDirection.LONG, quantity=100, order_type=OrderType.LIMIT, price=98.0)
    execution.on_order(order, queue)
    
    # Bar 1: Low is 99 (Does not reach limit)
    bar1 = TradeBarEvent(timestamp=2.0, symbol="AAPL", open=100, high=100, low=99, close=100, volume=1000)
    execution.update_market_bar(bar1, queue)
    assert queue.empty()
    
    # Bar 2: Low is 97 (Reaches limit)
    bar2 = TradeBarEvent(timestamp=3.0, symbol="AAPL", open=100, high=100, low=97, close=98, volume=1000)
    execution.update_market_bar(bar2, queue)
    
    assert not queue.empty()
    fill = queue.get()
    assert fill.fill_price == 98.0
