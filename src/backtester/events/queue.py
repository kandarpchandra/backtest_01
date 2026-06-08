from abc import ABC, abstractmethod
import queue
from backtester.events.types import BaseEvent

class AbstractEventQueue(ABC):
    @abstractmethod
    def put(self, event: BaseEvent) -> None:
        pass

    @abstractmethod
    def get(self) -> BaseEvent:
        pass

    @abstractmethod
    def empty(self) -> bool:
        pass

class SyncEventQueue(AbstractEventQueue):
    def __init__(self):
        self._queue = queue.PriorityQueue()

    def put(self, event: BaseEvent) -> None:
        self._queue.put(event)

    def get(self) -> BaseEvent:
        return self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()
