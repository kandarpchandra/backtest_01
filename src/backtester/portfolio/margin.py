from abc import ABC, abstractmethod
from typing import Dict
from backtester.instruments.base import Instrument

class MarginModel(ABC):
    @abstractmethod
    def get_initial_margin(self, symbol: str, quantity: float, current_price: float, instrument: Instrument) -> float:
        """Required cash to open the position."""
        pass

    @abstractmethod
    def get_maintenance_margin(self, symbol: str, quantity: float, current_price: float, instrument: Instrument) -> float:
        """Minimum equity required to keep the position open."""
        pass

class EquityMarginModel(MarginModel):
    """
    Standard Reg T Margin for US Equities.
    50% Initial Margin, 25% Maintenance Margin.
    """
    def __init__(self, initial_pct: float = 0.50, maintenance_pct: float = 0.25):
        self.initial_pct = initial_pct
        self.maintenance_pct = maintenance_pct

    def get_initial_margin(self, symbol: str, quantity: float, current_price: float, instrument: Instrument) -> float:
        return abs(quantity) * current_price * self.initial_pct

    def get_maintenance_margin(self, symbol: str, quantity: float, current_price: float, instrument: Instrument) -> float:
        return abs(quantity) * current_price * self.maintenance_pct

class FuturesMarginModel(MarginModel):
    """
    Fixed dollar margin per contract, common in futures.
    """
    def __init__(self, initial_margin_per_contract: float, maintenance_margin_per_contract: float):
        self.im = initial_margin_per_contract
        self.mm = maintenance_margin_per_contract

    def get_initial_margin(self, symbol: str, quantity: float, current_price: float, instrument: Instrument) -> float:
        return abs(quantity) * self.im

    def get_maintenance_margin(self, symbol: str, quantity: float, current_price: float, instrument: Instrument) -> float:
        return abs(quantity) * self.mm
