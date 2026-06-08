from typing import Dict
from backtester.events.types import FillEvent, SignalDirection
from backtester.instruments.base import Instrument

class PositionTracker:
    def __init__(self, initial_cash: float, instrument_registry: Dict[str, Instrument]):
        self.cash = initial_cash
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.average_prices: Dict[str, float] = {} # symbol -> avg price
        self.instrument_registry = instrument_registry
        
        self.realized_pnl = 0.0
        self.total_commission = 0.0
        
        # Keep track of current prices for unrealized PnL
        self.current_prices: Dict[str, float] = {}
        
        # History for tracking equity curve
        self.equity_curve = []

    def update_market_price(self, symbol: str, price: float) -> None:
        self.current_prices[symbol] = price
        self._record_equity()

    def on_fill(self, fill: FillEvent) -> None:
        symbol = fill.symbol
        qty = fill.quantity if fill.direction == SignalDirection.LONG else -fill.quantity
        price = fill.fill_price
        
        self.total_commission += fill.commission
        self.cash -= fill.commission

        # Simplified Position Update (assuming no shorting for MVP, or treating shorting symmetrically)
        # Real logic requires careful handling of cost basis
        current_qty = self.positions.get(symbol, 0.0)
        
        # Very simple accounting for MVP
        self.positions[symbol] = current_qty + qty
        self.cash -= qty * price # Debit cash for buys, credit for sells
        
        # We need a robust PnL calculation, but for MVP we will rely heavily on Mark-to-Market
        self._record_equity()

    def _record_equity(self) -> None:
        portfolio_value = self.cash
        for symbol, qty in self.positions.items():
            price = self.current_prices.get(symbol, 0.0)
            instrument = self.instrument_registry.get(symbol)
            if instrument:
                # The total value of the position
                # Assuming price is absolute value for equity
                # For futures, we would use pnl_scalar from entry price
                portfolio_value += instrument.pnl_scalar(price) * qty
        
        self.equity_curve.append(portfolio_value)
