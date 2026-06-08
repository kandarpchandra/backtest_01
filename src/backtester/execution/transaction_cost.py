from abc import ABC, abstractmethod

class AbstractTransactionCostModel(ABC):
    @abstractmethod
    def calculate_commission(self, quantity: float, price: float) -> float:
        pass

class ZeroTCM(AbstractTransactionCostModel):
    def calculate_commission(self, quantity: float, price: float) -> float:
        return 0.0

class PerShareTCM(AbstractTransactionCostModel):
    def __init__(self, rate_per_share: float = 0.005):
        self.rate = rate_per_share

    def calculate_commission(self, quantity: float, price: float) -> float:
        return quantity * self.rate

class PercentOfValueTCM(AbstractTransactionCostModel):
    def __init__(self, bps: float = 5.0):
        self.rate = bps / 10000.0

    def calculate_commission(self, quantity: float, price: float) -> float:
        return quantity * price * self.rate
