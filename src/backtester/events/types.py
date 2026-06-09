from dataclasses import dataclass, field
from enum import Enum, auto
import uuid

class EventType(Enum):
    """Explicit priority values. Lower = processed first at the same timestamp."""
    BAR = 10
    SIGNAL = 20
    ORDER = 30
    FILL = 40
    LIFECYCLE = 50

@dataclass(frozen=True, kw_only=True)
class BaseEvent:
    timestamp: float
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    
    @property
    def event_type(self) -> EventType:
        raise NotImplementedError

    @property
    def priority(self) -> int:
        return self.event_type.value

    def __lt__(self, other: 'BaseEvent') -> bool:
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.event_id < other.event_id

@dataclass(frozen=True, kw_only=True)
class MarketDataEvent(BaseEvent):
    symbol: str

    @property
    def event_type(self) -> EventType:
        return EventType.BAR

@dataclass(frozen=True, kw_only=True)
class TradeBarEvent(MarketDataEvent):
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass(frozen=True, kw_only=True)
class OptionDataEvent(MarketDataEvent):
    bid: float
    ask: float
    iv: float
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    underlying_price: float

@dataclass(frozen=True, kw_only=True)
class YieldDataEvent(MarketDataEvent):
    ytm: float
    duration: float = 0.0
    convexity: float = 0.0

@dataclass(frozen=True, kw_only=True)
class LifecycleEvent(BaseEvent):
    symbol: str

    @property
    def event_type(self) -> EventType:
        return EventType.LIFECYCLE

@dataclass(frozen=True, kw_only=True)
class OptionExpiryEvent(LifecycleEvent):
    underlying_price: float

@dataclass(frozen=True, kw_only=True)
class CouponPaymentEvent(LifecycleEvent):
    coupon_amount: float

class SignalDirection(Enum):
    LONG = auto()
    SHORT = auto()
    FLAT = auto()

@dataclass(frozen=True, kw_only=True)
class SignalEvent(BaseEvent):
    symbol: str
    direction: SignalDirection
    strategy_id: str
    strength: float = 1.0

    @property
    def event_type(self) -> EventType:
        return EventType.SIGNAL

class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()

class OrderStatus(Enum):
    PENDING = auto()
    ACCEPTED = auto()
    PARTIAL = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()

@dataclass(frozen=True, kw_only=True)
class OrderEvent(BaseEvent):
    symbol: str
    direction: SignalDirection
    quantity: float
    order_type: OrderType = OrderType.MARKET
    price: float | None = None

    @property
    def event_type(self) -> EventType:
        return EventType.ORDER

@dataclass(frozen=True, kw_only=True)
class FillEvent(BaseEvent):
    symbol: str
    direction: SignalDirection
    quantity: float
    fill_price: float
    commission: float

    @property
    def event_type(self) -> EventType:
        return EventType.FILL
