from backtester.core.clock import SimulationClock
from backtester.events.queue import AbstractEventQueue, SyncEventQueue
from backtester.events.types import BaseEvent, EventType, OrderEvent, TradeBarEvent, SignalDirection, OrderType
from backtester.sizing.base import AbstractCapitalAllocator
from backtester.risk.pre_trade import PreTradeRiskEngine
from backtester.risk.post_trade import PostTradeRiskEngine, PostTradeAction
from backtester.portfolio.pnl import AccountModel
from backtester.execution.engine import OrderBookMatcher
from backtester.core.recorder import EventSerializer
from backtester.core.config import BacktestConfig
from backtester.portfolio.lifecycle import LifecycleHandler
import logging

logger = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(self, config: BacktestConfig = BacktestConfig()):
        self.config = config
        self.clock = SimulationClock()
        self.queue: AbstractEventQueue = SyncEventQueue()
        
        self.data_feed = None
        self.strategy = None
        self.portfolio: AccountModel | None = None
        self.execution: OrderBookMatcher | None = None
        self.recorder = EventSerializer()
        self.lifecycle_handler: LifecycleHandler | None = None
        
        self.allocator: AbstractCapitalAllocator | None = None
        self.pre_trade_risk: PreTradeRiskEngine | None = None
        self.post_trade_risk: PostTradeRiskEngine | None = None

    def set_feed(self, feed) -> None:
        self.data_feed = feed

    def set_strategy(self, strategy) -> None:
        self.strategy = strategy

    def set_portfolio(self, portfolio: AccountModel) -> None:
        self.portfolio = portfolio
        self.lifecycle_handler = LifecycleHandler(portfolio)

    def set_execution(self, execution: OrderBookMatcher) -> None:
        self.execution = execution
        
    def set_allocator(self, allocator: AbstractCapitalAllocator) -> None:
        self.allocator = allocator
        
    def set_pre_trade_risk(self, pre_trade_risk: PreTradeRiskEngine) -> None:
        self.pre_trade_risk = pre_trade_risk
        
    def set_post_trade_risk(self, post_trade_risk: PostTradeRiskEngine) -> None:
        self.post_trade_risk = post_trade_risk

    def run(self) -> None:
        if not all([self.data_feed, self.strategy, self.portfolio, self.execution, self.allocator]):
            raise ValueError("Must set feed, strategy, portfolio, execution, and allocator before running.")

        self._current_day: int = -1  # Track day boundary for DailyLossLimit

        while True:
            # 1. Pump data feed if queue is empty
            if self.queue.empty():
                bar = self.data_feed.next()
                if bar is None:
                    break # End of backtest
                self.queue.put(bar)

            # 2. Process next event
            event = self.queue.get()
            self._process_event(event)

    def _process_event(self, event: BaseEvent) -> None:
        self.recorder.log_event(event)
        
        # Advance simulation time safely
        self.clock.advance(event.timestamp)

        # Detect day boundary for DailyLossLimit
        event_day = int(event.timestamp)
        if event_day > self._current_day:
            self._current_day = event_day
            if self.post_trade_risk and self.post_trade_risk.daily_loss_limit and self.portfolio:
                self.post_trade_risk.daily_loss_limit.start_day(self.portfolio)

        if event.event_type == EventType.BAR:
            # Only TradeBarEvents have OHLCV data for execution and portfolio
            if isinstance(event, TradeBarEvent):
                self.execution.update_market_bar(event, self.queue)
                self.portfolio.update_market_price(event.symbol, event.close)
            
            # Pass to strategy (strategy decides if it can handle the event type)
            self.strategy.on_bar(event, self.queue)
            
        elif event.event_type == EventType.SIGNAL:
            # Route to allocator
            order = self.allocator.allocate(event, self.portfolio)
            if order:
                # Pre-trade risk check
                if self.pre_trade_risk is None or self.pre_trade_risk.validate(order, self.portfolio):
                    self.queue.put(order)

        elif event.event_type == EventType.ORDER:
            # Send to execution
            self.execution.on_order(event, self.queue)

        elif event.event_type == EventType.FILL:
            # Send to portfolio
            self.portfolio.on_fill(event)
            
            # Post-trade risk check
            if self.post_trade_risk:
                decision = self.post_trade_risk.check(self.portfolio)
                if decision.action == PostTradeAction.FLATTEN_ALL:
                    logger.warning(f"Risk Breach: {decision.reason} - Flattening all positions.")
                    for sym, qty in list(self.portfolio.positions.items()):
                        if qty != 0:
                            direction = SignalDirection.SHORT if qty > 0 else SignalDirection.LONG
                            order = OrderEvent(
                                timestamp=event.timestamp,
                                symbol=sym,
                                direction=direction,
                                quantity=abs(qty),
                                order_type=OrderType.MARKET
                            )
                            self.queue.put(order)
                elif decision.action == PostTradeAction.HALT_TRADING:
                    raise RuntimeError(f"Risk Breach: {decision.reason} - Trading Halted.")
                    
        elif event.event_type == EventType.LIFECYCLE:
            if self.lifecycle_handler:
                self.lifecycle_handler.process_lifecycle_event(event)

        if self.portfolio:
            self.portfolio.record_equity_snapshot(event.timestamp)
