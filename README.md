# Event-Driven Backtesting Engine

A professional-grade, event-driven backtesting engine built in Python. This engine simulates institutional trading environments by processing market data, strategies, risk checks, and portfolio accounting tick-by-tick to prevent look-ahead bias and ensure production-readiness.

## Architecture Overview

The engine operates on a strict **Event Queue**. Components communicate by generating and consuming immutable `Event` objects in the following priority order:
1. `BarEvent` -> Market data updates.
2. `SignalEvent` -> Strategy generates alpha (Long/Short/Flat).
3. `OrderEvent` -> Allocator sizes the signal into an order.
4. `FillEvent` -> Execution engine simulates realistic exchange fills.

---

## Directory & File Breakdown

### 1. `core/` (Engine Foundations)
The central nervous system of the backtester.
- **`config.py`**: Contains `BacktestConfig` (powered by Pydantic) which holds global settings like starting cash, commissions, and risk limits.
- **`clock.py`**: Contains `SimulationClock`. 
  - `advance(next_time)`: Enforces monotonic time. All modules rely on this clock to prevent look-ahead bias.
- **`engine.py`**: Contains the `BacktestEngine`.
  - `run()`: The main `while True` loop that pumps data from the feed and routes events from the queue.
  - `_process_event(event)`: The router that sends `BarEvent` to strategies, `SignalEvent` to allocators, `OrderEvent` to execution, and `FillEvent` to the portfolio.
- **`recorder.py`**: Contains `EventSerializer`.
  - Logs every tick, signal, order, and fill during execution and serializes them to a deterministic Parquet file for exact replay.

### 2. `events/` (Data Structures)
- **`types.py`**: Defines immutable dataclasses using `kw_only=True` for strict typing.
  - `BaseEvent`: Base class with timestamp, UUID, and priority sorting logic (`__lt__`).
  - `MarketDataEvent` hierarchy: `TradeBarEvent`, `OptionDataEvent`, `YieldDataEvent`.
  - `LifecycleEvent` hierarchy: `OptionExpiryEvent`, `CouponPaymentEvent`.
  - Core routing events: `SignalEvent`, `OrderEvent`, `FillEvent`.
- **`queue.py`**: Contains `SyncEventQueue`.
  - Wraps Python's built-in `queue.PriorityQueue` to sort events strictly by Time -> Priority -> UUID.

### 3. `pricing/` & `instruments/` (Asset Modeling)
Stateless representation of tradable assets and their mathematical valuation.
- **`pricing/base.py`**: Contains `AbstractPricer` and `LinearPricer`.
- **`pricing/options.py`**: `BlackScholesPricer` (Theoretical option valuation using SciPy).
- **`pricing/bonds.py`**: `YieldToPricePricer` (Bond pricing math).
- **`instruments/base.py`**: `Instrument` base class. Uses its assigned `Pricer` to calculate mark-to-market value based on polymorphic market data.
- **`instruments/equity.py`**: `Equity` class (Linear).
- **`instruments/option.py`**: `VanillaOption` class (Non-linear).
- **`instruments/bond.py`**: `FixedRateBond` class (Fixed Income).

### 4. `data/` (Market Data Integration)
- **`feed.py`**: 
  - `AbstractDataFeed`: The interface the engine expects (`next() -> BarEvent`).
  - `SyntheticFeed`: Generates a realistic random-walk stock chart on the fly using Geometric Brownian Motion (GBM).
- **`sync.py`**: Contains `MultiSymbolSynchronizer`.
  - Merges multiple data feeds (e.g., AAPL and MSFT) using a priority queue to emit `BarEvent`s in strict chronological order.

### 5. `strategy/` (Alpha Generation)
- **`base.py`**: Contains the `Strategy` base class.
  - `on_bar()`: Where users write their indicator logic.
  - `_emit()`: Emits `SignalEvent`s to the queue. Isolates the strategy so it cannot illegally cheat by modifying the portfolio directly.
- **`warmup.py`**: Contains `WarmupWrapper`.
  - Decorator that intercepts strategy execution during an initial "burn-in" period, allowing indicators to hydrate without generating orders.

### 6. `sizing/` (Capital Allocation)
Converts raw `SignalEvents` into quantified `OrderEvents`.
- **`base.py`**: Contains `FixedLotSizer` (buys X shares) and `PercentEquitySizer` (allocates X% of account equity per trade).
- **`vol_target.py`**: Contains `VolTargetSizer`.
  - `update_price()`: Tracks rolling standard deviation.
  - `allocate()`: Sizes the order inversely proportional to recent market volatility, ensuring constant risk exposure.

### 7. `risk/` (Pre and Post Trade Risk)
Protects the portfolio from invalid states.
- **`pre_trade.py`**: `PositionLimitCheck` validates an `OrderEvent` before execution. If buying 500 shares exceeds max limits, the order is dropped.
- **`post_trade.py`**: The `PostTradeRiskEngine` evaluates portfolio health after fills.
- **`drawdown.py`**: `DrawdownControl` calculates peak-to-trough drops. If a threshold is breached, trading halts.
- **`budget.py`**: `DailyLossLimit` tracks start-of-day vs end-of-day PnL.

### 8. `execution/` (Market Simulation)
Simulates realistic exchange interactions.
- **`slippage.py`**: `VolumeLinearSlippage` punishes large orders by making their fill price worse depending on the market volume participation rate.
- **`transaction_cost.py`**: `PercentOfValueTCM` and `PerShareTCM` calculate realistic broker commissions.
- **`oms.py`**: Contains `OrderTracker`.
  - A stateful Order Management System that tracks `PENDING`, `PARTIAL`, and `FILLED` order states.
- **`engine.py`**: Contains the `OrderBookMatcher`.
  - Processes orders against market data. Calculates queue position, limits fills to a maximum percent of bar volume, and generates partial `FillEvent`s.

### 9. `portfolio/` (Accounting)
- **`pnl.py`**: Contains the `AccountModel`.
  - Advanced portfolio tracking. Manages Cash, Total Equity, and Cost Basis. Handles complex position flipping (Long 2 -> Short 1).
- **`margin.py`**: Contains `MarginModel` and `EquityMarginModel`.
  - Tracks Initial Margin and Maintenance Margin requirements continuously to support leveraged strategies safely.
- **`lifecycle.py`**: Contains `LifecycleHandler`.
  - Intercepts non-trade events (like `OptionExpiryEvent` or `CouponPaymentEvent`) and automatically exercises options or credits cash.

### 10. `analytics/` & `reporting/` (Results)
- **`analytics/metrics.py`**: Pure math functions (`calculate_returns`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`).
- **`reporting/tearsheet.py`**: Contains the `Tearsheet` generator.
  - `print_stats()`: Prints console metrics.
  - `plot()`: Uses Plotly to generate an interactive `equity_curve.html` chart.

---

## How to Run

To run a full end-to-end integration test featuring a Moving Average crossover strategy, synthetic data, volume slippage, percent-equity sizing, and drawdown control:

1. Ensure dependencies are installed:
   ```bash
   pip install numpy pandas pyarrow scipy pydantic pydantic-settings plotly pytest
   ```

2. Run the full smoke test:
   ```bash
   python scripts/smoke_test_full.py
   ```

3. Open the generated `equity_curve.html` file in your browser to view the interactive performance chart.
