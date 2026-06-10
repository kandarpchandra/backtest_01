import sys
from pathlib import Path

# Add src to Python path as the first entry
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtester.core.engine import BacktestEngine
from backtester.data.feed import SyntheticFeed
from backtester.instruments.equity import Equity
from backtester.strategy.base import Strategy
from backtester.portfolio.pnl import AccountModel
from backtester.execution.engine import OrderBookMatcher
from backtester.execution.oms import OrderTracker
from backtester.sizing.base import FixedLotSizer
from backtester.events.types import SignalEvent, SignalDirection

class MovingAverageCrossover(Strategy):
    def __init__(self):
        super().__init__("ma_cross")
        self.prices = {}

    def on_bar(self, bar, queue):
        if bar.symbol not in self.prices:
            self.prices[bar.symbol] = []
            
        self.prices[bar.symbol].append(bar.close)
        if len(self.prices[bar.symbol]) > 10:
            short_ma = sum(self.prices[bar.symbol][-5:]) / 5
            long_ma = sum(self.prices[bar.symbol][-10:]) / 10
            
            # Very simple logic to generate some signals
            if short_ma > long_ma:
                self._emit(SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    direction=SignalDirection.LONG,
                    strategy_id=self.strategy_id
                ), queue)

def main():
    print("Setting up Backtest Engine MVP...")
    engine = BacktestEngine()
    
    symbol = "AAPL"
    registry = {symbol: Equity(symbol)}
    
    feed = SyntheticFeed(symbol, start_price=150.0, n_bars=100)
    strategy = MovingAverageCrossover()
    portfolio = AccountModel(initial_cash=10000.0, instrument_registry=registry)
    
    oms = OrderTracker()
    execution = OrderBookMatcher(oms=oms)
    allocator = FixedLotSizer(fixed_qty=100.0)
    
    engine.set_feed(feed)
    engine.set_strategy(strategy)
    engine.set_portfolio(portfolio)
    engine.set_execution(execution)
    engine.set_allocator(allocator)
    
    print("Running backtest...")
    engine.run()
    
    print("Backtest Complete!")
    print(f"Final Cash: {portfolio.available_cash:.2f}")
    print(f"Final Positions: {portfolio.positions}")
    print(f"Final Equity: {portfolio.total_equity:.2f}")

if __name__ == "__main__":
    main()
