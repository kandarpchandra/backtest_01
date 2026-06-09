from backtester.strategy.base import Strategy
from backtester.events.queue import SyncEventQueue
from backtester.events.types import TradeBarEvent

class WarmupWrapper(Strategy):
    """
    Wraps a strategy to prevent it from emitting real orders during its warmup period.
    The strategy still receives data to hydrate its indicators.
    Tracks warmup per-symbol to handle multi-asset synchronization correctly.
    """
    def __init__(self, strategy: Strategy, warmup_bars: int):
        super().__init__(f"{strategy.strategy_id}_warmup")
        self.strategy = strategy
        self.warmup_bars = warmup_bars
        self._bars_per_symbol: dict[str, int] = {}
        self._dummy_queue = SyncEventQueue()

    def on_bar(self, bar: TradeBarEvent, queue) -> None:
        symbol = bar.symbol
        self._bars_per_symbol[symbol] = self._bars_per_symbol.get(symbol, 0) + 1
        
        if self._bars_per_symbol[symbol] <= self.warmup_bars:
            # Hydrate strategy, but trap any emitted SignalEvents in a dummy queue
            self.strategy.on_bar(bar, self._dummy_queue)
        else:
            # Warmup complete for this symbol, allow signals to flow
            self.strategy.on_bar(bar, queue)
