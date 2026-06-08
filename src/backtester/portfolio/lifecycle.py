from typing import Dict
from backtester.events.types import LifecycleEvent, OptionExpiryEvent, CouponPaymentEvent
from backtester.portfolio.pnl import AccountModel
from backtester.instruments.option import VanillaOption
from backtester.instruments.bond import FixedRateBond

class LifecycleHandler:
    """
    Automatically processes corporate actions and lifecycle events for the portfolio.
    """
    def __init__(self, portfolio: AccountModel):
        self.portfolio = portfolio

    def process_lifecycle_event(self, event: LifecycleEvent) -> None:
        symbol = event.symbol
        qty = self.portfolio.positions.get(symbol, 0.0)
        
        if qty == 0:
            return # We don't hold this instrument

        instrument = self.portfolio.instrument_registry.get(symbol)

        if isinstance(event, OptionExpiryEvent) and isinstance(instrument, VanillaOption):
            self._handle_option_expiry(event, qty, instrument)
            
        elif isinstance(event, CouponPaymentEvent) and isinstance(instrument, FixedRateBond):
            self._handle_coupon_payment(event, qty)

    def _handle_option_expiry(self, event: OptionExpiryEvent, qty: float, option: VanillaOption) -> None:
        """
        Calculates intrinsic value at expiration and settles the option position for cash.
        In a realistic engine, this might result in assignment of the underlying.
        """
        S = event.underlying_price
        K = option.pricer.strike
        is_call = option.pricer.is_call
        
        intrinsic_value = max(0.0, S - K) if is_call else max(0.0, K - S)
        settlement_cash = intrinsic_value * abs(qty) * 100 # Assuming 100 multiplier
        
        if qty > 0:
            # We were long, we receive intrinsic value
            self.portfolio.available_cash += settlement_cash
        else:
            # We were short, we pay intrinsic value
            self.portfolio.available_cash -= settlement_cash
            
        # Remove the option position
        del self.portfolio.positions[event.symbol]
        self.portfolio.cost_basis.pop(event.symbol, None)
        print(f"LIFECYCLE: Option {event.symbol} expired. Cash settled: {settlement_cash if qty > 0 else -settlement_cash}")

    def _handle_coupon_payment(self, event: CouponPaymentEvent, qty: float) -> None:
        payment = event.coupon_amount * abs(qty)
        self.portfolio.available_cash += payment
        print(f"LIFECYCLE: Received coupon payment of {payment} for bond {event.symbol}")
