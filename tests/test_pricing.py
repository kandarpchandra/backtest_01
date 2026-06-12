import pytest
from backtester.pricing.options import BlackScholesPricer
from backtester.events.types import OptionDataEvent

def test_black_scholes_call():
    # S=100, K=100, T=1 (one year), r=0.05, sigma=0.20
    # Expected call price: ~10.4506
    
    pricer = BlackScholesPricer(strike=100.0, expiry_timestamp=1.0, is_call=True, risk_free_rate=0.05)
    
    data = OptionDataEvent(
        timestamp=0.0, # T = 1.0 - 0.0 = 1.0
        symbol="OPT_C",
        bid=0, ask=0, # Bid/ask not used by theoretical pricer
        iv=0.20,
        underlying_price=100.0
    )
    
    price = pricer.get_value(data)
    assert price == pytest.approx(10.4506, rel=1e-3)

def test_black_scholes_put():
    # Expected put price: ~5.5735
    pricer = BlackScholesPricer(strike=100.0, expiry_timestamp=1.0, is_call=False, risk_free_rate=0.05)
    
    data = OptionDataEvent(
        timestamp=0.0,
        symbol="OPT_P",
        bid=0, ask=0,
        iv=0.20,
        underlying_price=100.0
    )
    
    price = pricer.get_value(data)
    assert price == pytest.approx(5.5735, rel=1e-3)

def test_black_scholes_expired():
    pricer = BlackScholesPricer(strike=100.0, expiry_timestamp=1.0, is_call=True, risk_free_rate=0.05)
    
    # Event timestamp > expiry_timestamp
    data = OptionDataEvent(
        timestamp=1.1, 
        symbol="OPT_C",
        bid=0, ask=0,
        iv=0.20,
        underlying_price=105.0 # In the money by 5
    )
    
    price = pricer.get_value(data)
    assert price == pytest.approx(5.0)

def test_black_scholes_expired_otm():
    pricer = BlackScholesPricer(strike=100.0, expiry_timestamp=1.0, is_call=True, risk_free_rate=0.05)
    
    data = OptionDataEvent(
        timestamp=1.1, 
        symbol="OPT_C",
        bid=0, ask=0,
        iv=0.20,
        underlying_price=95.0 # Out of the money
    )
    
    price = pricer.get_value(data)
    assert price == pytest.approx(0.0)
