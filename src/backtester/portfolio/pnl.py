from typing import Dict
from backtester.events.types import FillEvent, SignalDirection
from backtester.instruments.base import Instrument, Decomposable
from backtester.portfolio.margin import MarginModel, EquityMarginModel

class AccountModel:
    def __init__(self, initial_cash: float, instrument_registry: Dict[str, Instrument], margin_model: MarginModel = EquityMarginModel()):
        self.available_cash = initial_cash
        self.total_equity = initial_cash
        self.initial_margin_req = 0.0
        self.maintenance_margin_req = 0.0
        self.margin_model = margin_model
        
        self.positions: Dict[str, float] = {}  # symbol -> qty
        self.cost_basis: Dict[str, float] = {} # symbol -> avg entry price
        self.instrument_registry = instrument_registry
        
        self.realized_pnl = 0.0
        self.total_commission = 0.0
        
        self.current_prices: Dict[str, float] = {}
        self.equity_curve = []
        self.equity_curve_timestamps = []

    def record_equity_snapshot(self, timestamp: float) -> None:
        if not self.equity_curve_timestamps or timestamp > self.equity_curve_timestamps[-1]:
            self.equity_curve.append(self.total_equity)
            self.equity_curve_timestamps.append(timestamp)
        else:
            self.equity_curve[-1] = self.total_equity

    def update_market_price(self, symbol: str, price: float) -> None:
        self.current_prices[symbol] = price
        self._recalculate_account()

    def on_fill(self, fill: FillEvent) -> None:
        symbol = fill.symbol
        qty = fill.quantity if fill.direction == SignalDirection.LONG else -fill.quantity
        price = fill.fill_price
        
        self.total_commission += fill.commission
        self.available_cash -= fill.commission

        instrument = self.instrument_registry.get(symbol)
        
        if isinstance(instrument, Decomposable):
            # Use instrument-aware cash impact for the synthetic
            self.available_cash -= instrument.cash_impact(qty, price)
            legs = instrument.decompose(qty)
            n_legs = len(legs)
            
            for leg_sym, leg_qty in legs.items():
                # Distribute the synthetic price proportionally across legs
                # Each leg gets the synthetic price as its cost basis reference
                leg_instrument = self.instrument_registry.get(leg_sym)
                self._update_position(leg_sym, leg_qty, price / n_legs if n_legs > 0 else 0.0, leg_instrument)
                
            self._recalculate_account()
            return
            
        # Instrument-aware cash accounting
        self.available_cash -= instrument.cash_impact(qty, price) if instrument else qty * price
        self._update_position(symbol, qty, price, instrument)
        self._recalculate_account()

    def _update_position(self, symbol: str, qty: float, price: float, instrument: Instrument | None) -> None:
        current_qty = self.positions.get(symbol, 0.0)
        current_cb = self.cost_basis.get(symbol, 0.0)
        
        if current_qty == 0:
            # Open new
            self.positions[symbol] = qty
            self.cost_basis[symbol] = price
        elif (current_qty > 0 and qty > 0) or (current_qty < 0 and qty < 0):
            # Adding to position
            new_qty = current_qty + qty
            # Volume weighted average price
            new_cb = ((current_cb * current_qty) + (price * qty)) / new_qty
            self.positions[symbol] = new_qty
            self.cost_basis[symbol] = new_cb
        else:
            # Closing or flipping
            close_qty = min(abs(current_qty), abs(qty)) * (1 if current_qty < 0 else -1)
            remaining_qty = current_qty + qty
            
            # Calculate realized PnL
            price_diff = price - current_cb if current_qty > 0 else current_cb - price
            if instrument:
                realized = instrument.pnl_scalar(price_diff) * abs(close_qty)
            else:
                realized = price_diff * abs(close_qty) # Fallback to raw price 
            
            self.realized_pnl += realized
            
            # Position flips?
            if (current_qty > 0 and remaining_qty < 0) or (current_qty < 0 and remaining_qty > 0):
                self.positions[symbol] = remaining_qty
                self.cost_basis[symbol] = price # Cost basis is the flip price
            else:
                self.positions[symbol] = remaining_qty
                if remaining_qty == 0:
                    self.cost_basis.pop(symbol, None)

    def _recalculate_account(self) -> None:
        im_req = 0.0
        mm_req = 0.0
        
        # Instrument-aware portfolio valuation
        portfolio_value = self.available_cash
        for symbol, qty in self.positions.items():
            price = self.current_prices.get(symbol, 0.0)
            cb = self.cost_basis.get(symbol, price)
            instrument = self.instrument_registry.get(symbol)
            if instrument:
                # Each instrument knows how to value its own position
                # Equities: qty * price (standard model)
                # Futures: unrealized variation margin PnL
                portfolio_value += instrument.position_value(qty, price, cb)
                
                # Margin
                im_req += self.margin_model.get_initial_margin(symbol, qty, price, instrument)
                mm_req += self.margin_model.get_maintenance_margin(symbol, qty, price, instrument)
            else:
                # Fallback: equity model for unknown instruments
                portfolio_value += qty * price

        self.total_equity = portfolio_value
        self.initial_margin_req = im_req
        self.maintenance_margin_req = mm_req
