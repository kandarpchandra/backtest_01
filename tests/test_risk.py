import pytest
from backtester.portfolio.pnl import AccountModel
from backtester.risk.budget import DailyLossLimit
from backtester.risk.drawdown import DrawdownControl
from backtester.risk.pre_trade import PositionLimitCheck
from backtester.events.types import OrderEvent, SignalDirection

def test_daily_loss_limit():
    limit = DailyLossLimit(max_loss_pct=0.02) # 2% limit
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry={})
    
    # Start of day
    limit.start_day(portfolio)
    assert limit.check(portfolio) is True
    
    # Drop 1%
    portfolio.total_equity = 99000.0
    assert limit.check(portfolio) is True
    
    # Drop 2.5% -> Breach!
    portfolio.total_equity = 97500.0
    assert limit.check(portfolio) is False

def test_drawdown_control():
    dc = DrawdownControl(max_drawdown_pct=0.05) # 5% limit
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry={})
    
    # Equity goes up to 110,000 (New Peak)
    portfolio.total_equity = 110000.0
    assert dc.check(portfolio) is True
    assert dc.peak_equity == 110000.0
    
    # Drops to 106000 (4000 drop / 110000 peak = ~3.6% DD -> Safe)
    portfolio.total_equity = 106000.0
    assert dc.check(portfolio) is True
    
    # Drops to 104000 (6000 drop / 110000 peak = ~5.45% DD -> Breach)
    portfolio.total_equity = 104000.0
    assert dc.check(portfolio) is False
    
    # Even if it recovers, trading should remain halted
    portfolio.total_equity = 120000.0
    assert dc.check(portfolio) is False

def test_pre_trade_position_limits():
    limits = PositionLimitCheck({"AAPL": 100})
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry={})
    
    # Currently flat, request +50 AAPL -> OK
    order1 = OrderEvent(timestamp=0, symbol="AAPL", direction=SignalDirection.LONG, quantity=50)
    assert limits.validate(order1, portfolio) is True
    
    # Update portfolio to hold 80 AAPL
    portfolio.positions["AAPL"] = 80
    
    # Request +50 AAPL (80 + 50 = 130 > 100) -> FAIL
    order2 = OrderEvent(timestamp=0, symbol="AAPL", direction=SignalDirection.LONG, quantity=50)
    assert limits.validate(order2, portfolio) is False
    
    # Request -100 AAPL (80 - 100 = -20. abs(-20) < 100) -> OK
    order3 = OrderEvent(timestamp=0, symbol="AAPL", direction=SignalDirection.SHORT, quantity=100)
    assert limits.validate(order3, portfolio) is True
    
    # Request +500 MSFT (No limit defined) -> OK
    order4 = OrderEvent(timestamp=0, symbol="MSFT", direction=SignalDirection.LONG, quantity=500)
    assert limits.validate(order4, portfolio) is True
