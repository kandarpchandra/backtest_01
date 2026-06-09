import sys
from pathlib import Path

# Add src to Python path as the first entry
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtester.core.engine import BacktestEngine
from backtester.core.config import BacktestConfig
from backtester.data.feed import SyntheticFeed
from backtester.instruments.equity import Equity
from backtester.strategy.base import Strategy
from backtester.strategy.warmup import WarmupWrapper
from backtester.portfolio.pnl import AccountModel
from backtester.execution.oms import OrderTracker
from backtester.execution.engine import OrderBookMatcher
from backtester.data.sync import MultiSymbolSynchronizer
from backtester.execution.slippage import VolumeLinearSlippage
from backtester.execution.transaction_cost import PercentOfValueTCM
from backtester.sizing.base import PercentEquitySizer
from backtester.risk.pre_trade import PreTradeRiskEngine, PositionLimitCheck
from backtester.risk.post_trade import PostTradeRiskEngine
from backtester.risk.drawdown import DrawdownControl
from backtester.events.types import SignalEvent, SignalDirection
from backtester.reporting.tearsheet import Tearsheet

class MovingAverageCrossover(Strategy):
    def __init__(self):
        super().__init__("ma_cross")
        self.prices = []
        self.in_position = False

    def on_bar(self, bar, queue):
        self.prices.append(bar.close)
        if len(self.prices) > 20:
            short_ma = sum(self.prices[-10:]) / 10
            long_ma = sum(self.prices[-20:]) / 20
            
            if short_ma > long_ma and not self.in_position:
                self._emit(SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    direction=SignalDirection.LONG,
                    strategy_id=self.strategy_id
                ), queue)
                self.in_position = True
            elif short_ma < long_ma and self.in_position:
                self._emit(SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    direction=SignalDirection.FLAT, # Close position
                    strategy_id=self.strategy_id
                ), queue)
                self.in_position = False

def main():
    print("Setting up FULL Backtest Engine...")
    config = BacktestConfig(initial_cash=100000.0)
    engine = BacktestEngine(config)
    
    registry = {
        "AAPL": Equity("AAPL"),
        "MSFT": Equity("MSFT")
    }
    
    feed_aapl = SyntheticFeed("AAPL", start_price=150.0, n_bars=200, dt=1.0, seed=42)
    feed_msft = SyntheticFeed("MSFT", start_price=300.0, n_bars=200, dt=1.0, seed=99)
    feed = MultiSymbolSynchronizer([feed_aapl, feed_msft])
    
    strategy = WarmupWrapper(MovingAverageCrossover(), warmup_bars=25)
    portfolio = AccountModel(initial_cash=config.initial_cash, instrument_registry=registry)
    
    # Advanced Execution & OMS
    oms = OrderTracker()
    slippage = VolumeLinearSlippage(impact_factor=0.01)
    tcm = PercentOfValueTCM(bps=config.commission_bps)
    execution = OrderBookMatcher(oms=oms, slippage_model=slippage, tcm=tcm)
    
    # Sizing & Risk
    allocator = PercentEquitySizer(percent=0.20) # Risk 20% of equity per trade
    
    pre_risk = PreTradeRiskEngine()
    pre_risk.add_check(PositionLimitCheck({"AAPL": 1000, "MSFT": 500}))
    
    post_risk = PostTradeRiskEngine()
    post_risk.set_drawdown_control(DrawdownControl(max_drawdown_pct=config.max_drawdown_pct))
    
    engine.set_feed(feed)
    engine.set_strategy(strategy)
    engine.set_portfolio(portfolio)
    engine.set_execution(execution)
    engine.set_allocator(allocator)
    engine.set_pre_trade_risk(pre_risk)
    engine.set_post_trade_risk(post_risk)
    
    print("Running backtest...")
    engine.run()
    
    print("\nSaving Event Log to Parquet...")
    engine.recorder.save(str(Path(__file__).parent.parent / "event_log.parquet"))
    
    print("\nGenerating Tearsheet...")
    tearsheet = Tearsheet(portfolio)
    tearsheet.print_stats()
    
    plot_path = str(Path(__file__).parent.parent / "equity_curve.html")
    tearsheet.plot(save_path=plot_path)

if __name__ == "__main__":
    main()
