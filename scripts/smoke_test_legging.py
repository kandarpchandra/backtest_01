import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtester.portfolio.pnl import AccountModel
from backtester.instruments.stir.outright import STIROutright
from backtester.instruments.stir.spread import STIRSpread
from backtester.instruments.stir.fly import STIRFly
from backtester.events.types import FillEvent, SignalDirection
import uuid

def main():
    z4 = STIROutright("ERZ4", tick_size=0.005, tick_value=12.5)
    h5 = STIROutright("ERH5", tick_size=0.005, tick_value=12.5)
    m5 = STIROutright("ERM5", tick_size=0.005, tick_value=12.5)
    
    # Synthetic tickers
    spread1 = STIRSpread("ERZ4-ERH5", z4, h5)
    spread2 = STIRSpread("ERH5-ERM5", h5, m5)
    fly = STIRFly("ERZ4-ERH5-ERM5", z4, h5, m5)
    
    registry = {
        "ERZ4": z4,
        "ERH5": h5,
        "ERM5": m5,
        "ERZ4-ERH5": spread1,
        "ERH5-ERM5": spread2,
        "ERZ4-ERH5-ERM5": fly
    }
    
    portfolio = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    
    print("--- SCENARIO: LEGGING INTO A FLY ---")
    
    # 1. Buy 1 Z4-H5 Spread
    fill1 = FillEvent(timestamp=1.0, symbol="ERZ4-ERH5", quantity=1.0, fill_price=0.5, commission=0.0, direction=SignalDirection.LONG, event_id=uuid.uuid4())
    portfolio.on_fill(fill1)
    print("After Buying Z4-H5 Spread:")
    print(portfolio.positions)
    
    # 2. Sell 1 H5-M5 Spread (Legging into the Fly)
    fill2 = FillEvent(timestamp=2.0, symbol="ERH5-ERM5", quantity=1.0, fill_price=0.2, commission=0.0, direction=SignalDirection.SHORT, event_id=uuid.uuid4())
    portfolio.on_fill(fill2)
    print("\nAfter Selling H5-M5 Spread (Net = Fly):")
    print(portfolio.positions)
    
    # 3. Verify it is exactly equal to buying a Fly
    portfolio2 = AccountModel(initial_cash=100000.0, instrument_registry=registry)
    fill3 = FillEvent(timestamp=3.0, symbol="ERZ4-ERH5-ERM5", quantity=1.0, fill_price=0.3, commission=0.0, direction=SignalDirection.LONG, event_id=uuid.uuid4())
    portfolio2.on_fill(fill3)
    
    print("\nPositions if we had just bought the Fly directly:")
    print(portfolio2.positions)
    
    assert portfolio.positions == portfolio2.positions, "Legged Fly does not match Direct Fly!"
    
    # 4. Dump the Z4 outright (Legging out of the front wing)
    print("\n--- SCENARIO: LEGGING OUT ---")
    fill4 = FillEvent(timestamp=4.0, symbol="ERZ4", quantity=1.0, fill_price=95.0, commission=0.0, direction=SignalDirection.SHORT, event_id=uuid.uuid4())
    portfolio.on_fill(fill4)
    print("After Dumping Z4 (Legging out):")
    print(portfolio.positions)
    print(f"Realized PnL from dumping Z4: {portfolio.realized_pnl}")

if __name__ == "__main__":
    main()
