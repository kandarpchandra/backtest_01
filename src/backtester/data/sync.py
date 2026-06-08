from typing import List
from backtester.events.types import MarketDataEvent
from backtester.data.feed import AbstractDataFeed

class MultiSymbolSynchronizer(AbstractDataFeed):
    """
    Takes multiple data feeds and emits MarketDataEvents in strict chronological order.
    """
    def __init__(self, feeds: List[AbstractDataFeed]):
        self.feeds = feeds
        self.next_bars = {}

        # Prime the pump
        for i, feed in enumerate(self.feeds):
            bar = feed.next()
            if bar is not None:
                self.next_bars[i] = bar

    def next(self) -> MarketDataEvent | None:
        if not self.next_bars:
            return None # All feeds exhausted
            
        # Find the feed with the earliest timestamp
        earliest_idx = min(self.next_bars.keys(), key=lambda k: self.next_bars[k].timestamp)
        earliest_bar = self.next_bars[earliest_idx]
        
        # Advance that specific feed
        next_bar = self.feeds[earliest_idx].next()
        if next_bar is not None:
            self.next_bars[earliest_idx] = next_bar
        else:
            del self.next_bars[earliest_idx]
            
        return earliest_bar
