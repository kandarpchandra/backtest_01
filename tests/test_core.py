import pytest
from backtester.core.clock import SimulationClock
from backtester.events.types import TradeBarEvent, SignalEvent, SignalDirection, OrderEvent
from backtester.events.queue import SyncEventQueue

def test_simulation_clock():
    clock = SimulationClock()
    assert clock.current_time == 0.0
    
    clock.advance(1.5)
    assert clock.current_time == 1.5

    with pytest.raises(ValueError):
        clock.advance(1.0)

def test_event_queue_priority():
    queue = SyncEventQueue()
    
    # Create events out of order but with same timestamp
    signal = SignalEvent(timestamp=1.0, symbol="AAPL", direction=SignalDirection.LONG, strategy_id="test")
    bar = TradeBarEvent(timestamp=1.0, symbol="AAPL", open=100, high=101, low=99, close=100, volume=100)
    order = OrderEvent(timestamp=1.0, symbol="AAPL", direction=SignalDirection.LONG, quantity=1.0)
    
    queue.put(order)
    queue.put(signal)
    queue.put(bar)
    
    # Priority should be BAR -> SIGNAL -> ORDER based on enum value
    first = queue.get()
    assert isinstance(first, TradeBarEvent)
    
    second = queue.get()
    assert isinstance(second, SignalEvent)
    
    third = queue.get()
    assert isinstance(third, OrderEvent)

    assert queue.empty()
