from abc import ABC, abstractmethod
import numpy as np
from typing import Optional
from backtester.events.types import TradeBarEvent

class AbstractDataFeed(ABC):
    @abstractmethod
    def next(self) -> Optional[TradeBarEvent]:
        pass

class SyntheticFeed(AbstractDataFeed):
    def __init__(self, symbol: str, start_price: float = 100.0, n_bars: int = 252, dt: float = 1.0, seed: int = 42):
        self.symbol = symbol
        self.current_idx = 0
        self.n_bars = n_bars
        self.dt = dt
        self.current_time = 0.0
        
        # Per-instance RNG to avoid cross-feed seed corruption
        self._rng = np.random.default_rng(seed)
        returns = self._rng.normal(0.0001, 0.01, n_bars)
        self.prices = start_price * np.exp(np.cumsum(returns))

    def next(self) -> Optional[TradeBarEvent]:
        if self.current_idx >= self.n_bars:
            return None

        # Simulate High, Low, Open relative to close
        price = self.prices[self.current_idx]
        self.current_time += self.dt
        high = price * (1 + abs(self._rng.normal(0, 0.005)))
        low = price * (1 - abs(self._rng.normal(0, 0.005)))
        open_price = price * (1 + self._rng.normal(0, 0.002))
        
        bar = TradeBarEvent(
            timestamp=self.current_time,
            symbol=self.symbol,
            open=open_price,
            high=high,
            low=low,
            close=price,
            volume=max(1, int(self._rng.normal(10000, 2000)))
        )
        self.current_idx += 1
        return bar
