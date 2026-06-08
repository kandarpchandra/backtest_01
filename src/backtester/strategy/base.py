from abc import ABC, abstractmethod
from backtester.events.queue import AbstractEventQueue
from backtester.events.types import SignalEvent, TradeBarEvent

class Strategy(ABC):
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    @abstractmethod
    def on_bar(self, bar: TradeBarEvent, queue: AbstractEventQueue) -> None:
        pass

    def _emit(self, signal: SignalEvent, queue: AbstractEventQueue) -> None:
        queue.put(signal)
