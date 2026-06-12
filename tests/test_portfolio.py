import pytest
from backtester.portfolio.pnl import AccountModel
from backtester.events.types import FillEvent, SignalDirection
from backtester.instruments.equity import Equity
from backtester.instruments.stir.outright import STIROutright
from backtester.instruments.stir.spread import STIRSpread

def test_equity_portfolio_valuation():
    registry = {"AAPL": Equity("AAPL")}
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    
    # Buy 100 shares at 150
    fill = FillEvent(timestamp=1.0, symbol="AAPL", direction=SignalDirection.LONG, quantity=100, fill_price=150.0, commission=1.0)
    portfolio.on_fill(fill)
    
    assert portfolio.positions["AAPL"] == 100
    assert portfolio.available_cash == 100000.0 - (100 * 150.0) - 1.0 # 84999.0
    
    # Price updates to 160
    portfolio.update_market_price("AAPL", 160.0)
    
    # Total equity = cash + (100 * 160)
    assert portfolio.total_equity == 84999.0 + 16000.0

def test_futures_portfolio_valuation():
    # ERZ4: tick_size 0.005, tick_value 12.50. So 1 point move = 1 / 0.005 * 12.50 = $2500 per lot
    stir = STIROutright("ERZ4", tick_size=0.005, tick_value=12.50)
    registry = {"ERZ4": stir}
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    
    # Buy 1 lot at 95.50
    fill = FillEvent(timestamp=1.0, symbol="ERZ4", direction=SignalDirection.LONG, quantity=1, fill_price=95.50, commission=1.0)
    portfolio.on_fill(fill)
    
    assert portfolio.positions["ERZ4"] == 1
    # Cash should ONLY be reduced by commission, not notional for futures
    assert portfolio.available_cash == 99999.0
    
    # Price updates to 95.51 (2 ticks up -> +$25)
    portfolio.update_market_price("ERZ4", 95.51)
    
    # Total equity = cash + variation margin
    assert portfolio.total_equity == pytest.approx(99999.0 + 25.0)

def test_futures_short_valuation():
    stir = STIROutright("ERZ4", tick_size=0.005, tick_value=12.50)
    registry = {"ERZ4": stir}
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    
    # Sell 2 lots at 95.50
    fill = FillEvent(timestamp=1.0, symbol="ERZ4", direction=SignalDirection.SHORT, quantity=2, fill_price=95.50, commission=2.0)
    portfolio.on_fill(fill)
    
    # Price updates to 95.49 (2 ticks down -> +$25 * 2 = +$50 for a short)
    portfolio.update_market_price("ERZ4", 95.49)
    assert portfolio.total_equity == pytest.approx(99998.0 + 50.0)

def test_spread_decomposition_and_cost_basis():
    front = STIROutright("ERZ4", tick_size=0.005, tick_value=12.50)
    back = STIROutright("ERH5", tick_size=0.005, tick_value=12.50)
    spread = STIRSpread("ERZ4-ERH5", front, back)
    
    registry = {"ERZ4": front, "ERH5": back, "ERZ4-ERH5": spread}
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    
    # Buy 10 lots of the spread at 0.50
    fill = FillEvent(timestamp=1.0, symbol="ERZ4-ERH5", direction=SignalDirection.LONG, quantity=10, fill_price=0.50, commission=5.0)
    portfolio.on_fill(fill)
    
    # Should decompose into +10 ERZ4, -10 ERH5
    assert portfolio.positions.get("ERZ4") == 10
    assert portfolio.positions.get("ERH5") == -10
    
    # Cost basis should be distributed proportionally (0.25 each)
    assert portfolio.cost_basis.get("ERZ4") == 0.25
    assert portfolio.cost_basis.get("ERH5") == 0.25
    
    # The spread symbol itself shouldn't have a position
    assert "ERZ4-ERH5" not in portfolio.positions

def test_vwap_cost_basis():
    registry = {"AAPL": Equity("AAPL")}
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    
    fill1 = FillEvent(timestamp=1.0, symbol="AAPL", direction=SignalDirection.LONG, quantity=100, fill_price=50.0, commission=0.0)
    portfolio.on_fill(fill1)
    
    fill2 = FillEvent(timestamp=2.0, symbol="AAPL", direction=SignalDirection.LONG, quantity=50, fill_price=65.0, commission=0.0)
    portfolio.on_fill(fill2)
    
    # VWAP = (100*50 + 50*65) / 150 = 8250 / 150 = 55.0
    assert portfolio.positions["AAPL"] == 150
    assert portfolio.cost_basis["AAPL"] == 55.0
