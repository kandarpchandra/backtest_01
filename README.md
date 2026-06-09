# Universal Event-Driven Backtesting Engine

A production-grade, event-driven backtesting engine built in Python. This engine simulates institutional trading environments by processing market data, strategies, risk checks, and portfolio accounting tick-by-tick. It supports **Equities, Futures (STIR), Options (Black-Scholes), and Bonds** in a single unified simulation with full deterministic replay.

## Key Features

- **Event-Driven Architecture** — No look-ahead bias. The strategy cannot see the future.
- **Multi-Asset Synchronization** — Trade AAPL, MSFT, SONIA futures, and Options simultaneously.
- **Synthetic Leg Decomposition** — Buy a Butterfly, exit as individual legs. Real clearinghouse netting.
- **Black-Scholes Options Pricing** — Dynamic mark-to-market using implied volatility.
- **Lifecycle Event Bus** — Automatic option expiry settlement and bond coupon payments.
- **Partial Fills & Queue Position** — Orders fill up to 10% of bar volume. Realistic microstructure.
- **Deterministic Replay** — Every event serialized to Parquet for exact debugging.
- **Per-Symbol Warmup** — Strategy indicators hydrate independently per symbol before live trading.

---

## Architecture Overview

The engine operates on a strict **Priority Queue**. Components communicate by generating and consuming immutable `Event` objects. Events at the same timestamp are processed in explicit priority order:

| Priority | Event Type | Description |
|----------|-----------|-------------|
| 10 | `MarketDataEvent` | Market data updates (`TradeBarEvent`, `OptionDataEvent`, `YieldDataEvent`) |
| 20 | `SignalEvent` | Strategy generates alpha (Long/Short/Flat) |
| 30 | `OrderEvent` | Allocator sizes the signal into an order |
| 40 | `FillEvent` | Execution engine simulates realistic exchange fills |
| 50 | `LifecycleEvent` | Corporate actions (`OptionExpiryEvent`, `CouponPaymentEvent`) |

---

## Directory & File Breakdown

### 1. `core/` — Engine Foundations
The central nervous system of the backtester.
- **`config.py`**: `BacktestConfig` (Pydantic) — global settings (cash, commissions, risk limits). Supports environment variable overrides via `BT_` prefix.
- **`clock.py`**: `SimulationClock` — enforces strict monotonic time. If any event tries to go backwards, the engine raises a fatal error to prevent look-ahead bias.
- **`engine.py`**: `BacktestEngine` — the main event loop. Pumps data from the feed, routes events to the correct handler, and integrates the `LifecycleHandler` for non-trade events.
- **`recorder.py`**: `EventSerializer` — logs every tick, signal, order, and fill, then serializes them to a compressed Parquet file for deterministic replay.

### 2. `events/` — Data Structures
- **`types.py`**: Frozen immutable dataclasses (`kw_only=True`).
  - `BaseEvent`: Base class with timestamp, UUID, and priority sorting (`__lt__`).
  - `MarketDataEvent` hierarchy: `TradeBarEvent` (OHLCV), `OptionDataEvent` (IV + Greeks), `YieldDataEvent` (YTM + Duration).
  - `LifecycleEvent` hierarchy: `OptionExpiryEvent`, `CouponPaymentEvent`.
  - Core routing: `SignalEvent`, `OrderEvent`, `FillEvent`.
- **`queue.py`**: `SyncEventQueue` — wraps Python's `PriorityQueue`. Sorts by Time → Priority → UUID.

### 3. `pricing/` & `instruments/` — Asset Modeling
Stateless instruments with pluggable dynamic pricing models.
- **`pricing/base.py`**: `AbstractPricer` interface + `LinearPricer` (Equities, Futures).
- **`pricing/options.py`**: `BlackScholesPricer` — European option valuation using `scipy.stats.norm`.
- **`pricing/bonds.py`**: `YieldToPricePricer` — converts yield data into dirty bond prices via duration/convexity approximation.
- **`instruments/base.py`**: `Instrument` base class with `get_value(data)` and `pnl_scalar(price_move)`. Also defines the `Decomposable` mixin for synthetic instruments.
- **`instruments/equity.py`**: `Equity` (linear, 1:1 multiplier).
- **`instruments/option.py`**: `VanillaOption` (non-linear, Black-Scholes).
- **`instruments/bond.py`**: `FixedRateBond` (fixed income).
- **`instruments/stir/`**: `STIROutright`, `STIRSpread`, `STIRFly` — STIR futures with exact tick-size/tick-value math. Spreads and Flies implement `Decomposable` for automatic leg decomposition.

### 4. `data/` — Market Data Integration
- **`feed.py`**: `AbstractDataFeed` interface + `SyntheticFeed` (GBM random walk with per-instance RNG).
- **`sync.py`**: `MultiSymbolSynchronizer` — merges multiple asynchronous data feeds and emits events in strict chronological order.

### 5. `strategy/` — Alpha Generation
- **`base.py`**: `Strategy` ABC. Users implement `on_bar()` for indicator logic. `_emit()` safely pushes `SignalEvent`s to the queue.
- **`warmup.py`**: `WarmupWrapper` — per-symbol warmup tracking. Each symbol independently hydrates its indicators before live trading begins.

### 6. `sizing/` — Capital Allocation
Converts `SignalEvent`s into quantified `OrderEvent`s.
- **`base.py`**: `FixedLotSizer` and `PercentEquitySizer`.
- **`vol_target.py`**: `VolTargetSizer` — sizes positions inversely proportional to recent volatility for constant risk exposure.

### 7. `risk/` — Pre & Post Trade Risk
- **`pre_trade.py`**: `PositionLimitCheck` — blocks orders exceeding position limits before they reach execution.
- **`post_trade.py`**: `PostTradeRiskEngine` — evaluates portfolio health after every fill.
- **`drawdown.py`**: `DrawdownControl` — halts trading if peak-to-trough drawdown exceeds threshold.
- **`budget.py`**: `DailyLossLimit` — tracks intraday PnL limits.

### 8. `execution/` — Market Simulation
Simulates realistic exchange interactions with institutional-grade microstructure.
- **`slippage.py`**: `VolumeLinearSlippage`, `FixedBasisPointSlippage` — adverse price impact proportional to market participation.
- **`transaction_cost.py`**: `PercentOfValueTCM`, `PerShareTCM` — realistic broker commissions.
- **`oms.py`**: `OrderTracker` — stateful Order Management System. Tracks orders through `PENDING` → `ACCEPTED` → `PARTIAL` → `FILLED` lifecycle. Uses `close_order()` to preserve fill status in history.
- **`engine.py`**: `OrderBookMatcher` — evaluates Market/Limit/Stop orders against bar data. Caps fills at 10% of bar volume to simulate realistic liquidity constraints.

### 9. `portfolio/` — Accounting & Clearing
- **`pnl.py`**: `AccountModel` — manages Cash, Total Equity, Cost Basis, and positions. Handles position flipping and **Synthetic Leg Decomposition** (automatically shatters Fly/Spread fills into outright legs for cross-margining).
- **`margin.py`**: `MarginModel` + `EquityMarginModel` — tracks Initial and Maintenance Margin requirements.
- **`lifecycle.py`**: `LifecycleHandler` — intercepts `OptionExpiryEvent` (settles intrinsic value) and `CouponPaymentEvent` (credits interest).

### 10. `analytics/` & `reporting/` — Results
- **`analytics/metrics.py`**: Pure math — `calculate_returns`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`.
- **`reporting/tearsheet.py`**: `Tearsheet` — prints console stats and generates interactive `equity_curve.html` via Plotly.

---

## How to Run

### Prerequisites
```bash
pip install numpy pandas pyarrow scipy pydantic pydantic-settings plotly pytest
```

### Full Integration Test
Multi-asset backtest (AAPL + MSFT) with warmup, slippage, partial fills, and drawdown control:
```bash
python scripts/smoke_test_full.py
```

### STIR Legging Test
Demonstrates buying a Spread, morphing it into a Butterfly, and legging out:
```bash
python scripts/smoke_test_legging.py
```

### Output
- `equity_curve.html` — Interactive Plotly chart.
- `event_log.parquet` — Deterministic event log for replay/debugging.

---

## Documentation

- **`ARCHITECTURE_DEEPDIVE.md`** — Detailed technical walkthrough of every architectural decision. Includes interview Q&A prep.
