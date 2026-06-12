from backtester.sizing.base import AbstractCapitalAllocator
from backtester.events.types import SignalEvent, OrderEvent, OrderType, SignalDirection
from backtester.portfolio.pnl import AccountModel
import numpy as np

class VolTargetSizer(AbstractCapitalAllocator):
    """
    Institutional Volatility Targeting Sizer.
    Sizes positions inversely proportional to their recent volatility.
    """
    def __init__(self, vol_target: float = 0.10, window: int = 20, max_leverage: float = 2.0):
        self.vol_target = vol_target
        self.window = window
        self.max_leverage = max_leverage
        self.price_history = {} # symbol -> list of prices

    def update_price(self, symbol: str, price: float):
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        if len(self.price_history[symbol]) > self.window + 1:
            self.price_history[symbol].pop(0)

    def allocate(self, signal: SignalEvent, portfolio: AccountModel) -> OrderEvent | None:
        if signal.direction == SignalDirection.FLAT:
            current_qty = portfolio.positions.get(signal.symbol, 0.0)
            if current_qty == 0:
                return None
            direction = SignalDirection.SHORT if current_qty > 0 else SignalDirection.LONG
            return OrderEvent(
                timestamp=signal.timestamp,
                symbol=signal.symbol,
                direction=direction,
                quantity=abs(current_qty),
                order_type=OrderType.MARKET
            )

        symbol = signal.symbol
        if symbol not in self.price_history or len(self.price_history[symbol]) <= self.window:
            return None # Not enough history to calculate vol

        prices = np.array(self.price_history[symbol])
        returns = np.diff(prices) / prices[:-1]
        
        # Annualized realized volatility
        realized_vol = np.std(returns, ddof=1) * np.sqrt(252)
        
        if realized_vol <= 0.0001:
            return None

        # Target exposure to hit vol target
        target_exposure = portfolio.total_equity * (self.vol_target / realized_vol) * signal.strength
        
        # Cap leverage
        max_exposure = portfolio.total_equity * self.max_leverage
        target_exposure = min(target_exposure, max_exposure)

        current_price = prices[-1]
        qty = round(target_exposure / current_price)

        if qty <= 0:
            return None

        return OrderEvent(
            timestamp=signal.timestamp,
            symbol=symbol,
            direction=signal.direction,
            quantity=qty,
            order_type=OrderType.MARKET
        )
