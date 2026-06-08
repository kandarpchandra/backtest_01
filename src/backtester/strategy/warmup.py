from backtester.strategy.base import Strategy
from backtester.events.queue import SyncEventQueue
from backtester.events.types import TradeBarEvent

class WarmupWrapper(Strategy):
    """
    Wraps a strategy to prevent it from emitting real orders during its warmup period.
    The strategy still receives data to hydrate its indicators.
    """
    def __init__(self, strategy: Strategy, warmup_bars: int):
        super().__init__(f"{strategy.strategy_id}_warmup")
        self.strategy = strategy
        self.warmup_bars = warmup_bars
        self.bars_processed = 0
        self._dummy_queue = SyncEventQueue()

    def on_bar(self, bar: TradeBarEvent, queue) -> None:
        self.bars_processed += 1
        
        if self.bars_processed <= self.warmup_bars:
            # Hydrate strategy, but trap any emitted SignalEvents in a dummy queue
            self.strategy.on_bar(bar, self._dummy_queue)
        else:
            # Warmup complete, allow signals to flow to the real queue
            self.strategy.on_bar(bar, queue)
