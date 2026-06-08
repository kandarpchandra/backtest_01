import sys
from pathlib import Path

# Add src to Python path as the first entry
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtester.core.engine import BacktestEngine
from backtester.data.feed import SyntheticFeed
from backtester.instruments.equity import Equity
from backtester.strategy.base import Strategy
from backtester.portfolio.position import PositionTracker
from backtester.execution.fill_model import SimpleExecutionModel
from backtester.events.types import SignalEvent, SignalDirection

class MovingAverageCrossover(Strategy):
    def __init__(self):
        super().__init__("ma_cross")
        self.prices = []

    def on_bar(self, bar, queue):
        self.prices.append(bar.close)
        if len(self.prices) > 10:
            short_ma = sum(self.prices[-5:]) / 5
            long_ma = sum(self.prices[-10:]) / 10
            
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
    portfolio = PositionTracker(initial_cash=10000.0, instrument_registry=registry)
    execution = SimpleExecutionModel(commission_rate=0.0) # Zero commission for testing
    
    engine.set_feed(feed)
    engine.set_strategy(strategy)
    engine.set_portfolio(portfolio)
    engine.set_execution(execution)
    
    print("Running backtest...")
    engine.run()
    
    print("Backtest Complete!")
    print(f"Final Cash: {portfolio.cash:.2f}")
    print(f"Final Positions: {portfolio.positions}")
    print(f"Final Equity: {portfolio.equity_curve[-1] if portfolio.equity_curve else portfolio.cash:.2f}")

if __name__ == "__main__":
    main()
