from pydantic_settings import BaseSettings

class BacktestConfig(BaseSettings):
    initial_cash: float = 1_000_000.0
    commission_bps: float = 0.5
    slippage_impact_factor: float = 0.1
    max_drawdown_pct: float = 0.20
    vol_target: float = 0.10
    
    class Config:
        env_prefix = 'BT_'
