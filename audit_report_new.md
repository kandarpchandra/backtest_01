# Institutional Audit Report — `can_backtest` Engine

> **Auditor Perspective:** Principal Quantitative Developer / Trading Systems Architect
> **Audit Date:** 2026-06-11
> **Codebase:** 48 Python files · 1,296 source lines (excl. tests/scripts)
> **Claimed Grade:** "Production-grade, event-driven backtesting engine"

---

## Executive Summary

| Category | Score (/10) | Notes |
|---|---|---|
| Architecture | **6.5** | Clean layer separation; extensibility via ABCs; but setter-injection, missing dependency validation, and `hasattr` duck-typing weaken it |
| Event Engine | **6.0** | Priority queue is correct; determinism is **broken** by UUID event IDs |
| Instrument Models | **5.0** | STIR futures are genuinely modeled (spread/fly decomposition); equities are skeletal; options and bonds are MVP stubs |
| Mathematics | **4.5** | Sharpe/Sortino have textbook errors; bond pricer is mathematically wrong; Black-Scholes is correct |
| Portfolio Accounting | **4.0** | Fundamental equity-model accounting applied to futures produces **wrong PnL**; realized PnL double-counts via `pnl_scalar` |
| Risk Engine | **5.0** | Pre-trade position limits + post-trade drawdown present; easily bypassable; no margin enforcement |
| Execution Simulation | **6.0** | Partial fills, slippage models, and OMS are present; limit/stop logic has directional errors |
| Performance | **5.5** | Adequate for <1M events; O(n) active-order scan per bar; no vectorization path |
| Testing | **2.0** | 2 unit tests, 3 smoke scripts; ~5% coverage; no edge-case, regression, or property tests |
| Code Quality | **6.0** | Consistent naming, type hints, ABCs; no logging; print-based diagnostics; minimal docs |
| **Overall** | **4.5** | |

> [!CAUTION]
> **The engine contains mathematical and accounting errors that silently produce incorrect backtest results.** It cannot be trusted for quantitative research without significant remediation.

---

## PART 1 — Architectural Audit

### Project Structure

```
src/backtester/
├── core/          (engine, clock, config, recorder)
├── events/        (types, queue)
├── data/          (feed, sync)
├── strategy/      (base, warmup)
├── sizing/        (base, vol_target)
├── risk/          (pre_trade, post_trade, drawdown, budget)
├── portfolio/     (pnl, lifecycle, margin)
├── execution/     (engine, oms, slippage, transaction_cost)
├── instruments/   (base, equity, option, bond, stir/)
├── pricing/       (base, bonds, options)
├── analytics/     (metrics)
└── reporting/     (tearsheet)
```

**Strengths:**
- Clean vertical slicing by domain concept
- No circular imports detected
- Consistent use of Abstract Base Classes for extension points (`AbstractPricer`, `AbstractSlippageModel`, `AbstractCapitalAllocator`, `AbstractPreTradeCheck`, `AbstractDataFeed`, `AbstractEventQueue`)
- `Decomposable` mixin for multi-leg instruments is a sound design pattern

**SOLID Analysis:**

| Principle | Status | Evidence |
|---|---|---|
| **Single Responsibility** | ⚠️ Partial | [AccountModel](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py) handles position tracking, cost basis, PnL, margin, equity curve recording, and market price updates — at least 4 responsibilities |
| **Open-Closed** | ✅ Good | Strategies, slippage models, pricers, sizers, risk checks are all pluggable via ABCs |
| **Liskov Substitution** | ⚠️ Violated | [engine.py L76](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L76): `hasattr(event, 'close')` duck-types instead of using the type hierarchy — `MarketDataEvent` subtypes are not substitutable uniformly |
| **Interface Segregation** | ✅ Good | Narrow ABCs with 1-2 methods each |
| **Dependency Inversion** | ⚠️ Partial | Engine depends on concrete `AccountModel`, `OrderBookMatcher`, `EventSerializer` rather than abstractions |

**Architectural Violations:**

| File | Module | Problem | Severity |
|---|---|---|---|
| [engine.py](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py) | core | Setter injection with no builder/validation — engine can `run()` with `None` components if check is bypassed | Medium |
| [engine.py L76](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L76) | core | `hasattr(event, 'close')` breaks type hierarchy; should use `isinstance(event, TradeBarEvent)` | Medium |
| [engine.py L104-114](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L104-L114) | core | **Uses `SignalDirection` and `OrderType` without importing them** — this is a runtime `NameError` waiting to happen on any drawdown breach | **Critical** |
| [pnl.py](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py) | portfolio | God-class: position management + PnL + margin + equity curve + market prices | High |
| [recorder.py](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/recorder.py#L20-L23) | core | `hasattr(value, 'name')` catches any object with a `.name` attribute, not just Enums — silent data corruption risk | Medium |

---

## PART 2 — Event Engine Audit

### Event Queue

[SyncEventQueue](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/events/queue.py) wraps `queue.PriorityQueue` and relies on `BaseEvent.__lt__` for ordering.

**Event Priority Ordering** (correct):
```
BAR(10) → SIGNAL(20) → ORDER(30) → FILL(40) → LIFECYCLE(50)
```

Same-timestamp tie-breaking: `timestamp → priority → event_id`

### Determinism Verdict: ❌ BROKEN

> [!WARNING]
> **[BaseEvent.event_id](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/events/types.py#L16) uses `uuid.uuid4().hex`** — a random UUID. When two events share the same timestamp and priority, the tie-breaker is a random string. This means **two identical backtests will process events in different orders** whenever ties occur.

**Impact:** Any multi-asset backtest with synchronized feeds (identical timestamps) will have non-deterministic event ordering between symbols at the same timestamp.

**Fix:** Replace `uuid.uuid4().hex` with a deterministic monotonic counter (e.g., `itertools.count()`).

### Event Loop Analysis

[engine.py L56-66](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L56-L66):

```python
while True:
    if self.queue.empty():
        bar = self.data_feed.next()
        if bar is None:
            break
        self.queue.put(bar)
    event = self.queue.get()
    self._process_event(event)
```

**Issue:** The engine only pumps the data feed when the queue is empty. If a single BAR generates a SIGNAL → ORDER → FILL chain, all derived events are processed before the next BAR. This is **correct for single-symbol** backtests but creates subtle ordering issues in multi-asset scenarios: a FILL on symbol A could trigger a risk-flatten that races with pending events for symbol B already in the queue.

---

## PART 3 — Instrument Model Audit

### Equities

| Feature | Status | Evidence |
|---|---|---|
| Position accounting | ✅ Basic | Via `AccountModel._update_position` |
| Multiplier support | ✅ | `Equity(symbol, multiplier)` |
| Dividends | ❌ Missing | No `DividendEvent`, no ex-date handling |
| Stock splits | ❌ Missing | No split ratio adjustment |
| Corporate actions | ❌ Missing | Only option expiry and coupon events exist |

**Verdict:** Minimal equity stub. No corporate action handling.

### STIR Futures

| Feature | Status | Evidence |
|---|---|---|
| Contract spec (tick size / tick value) | ✅ | [STIROutright](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/instruments/stir/outright.py) |
| PnL scalar | ✅ | `(price_move / tick_size) * tick_value` — correct |
| DV01 | ✅ | `pnl_scalar(0.01)` — correct |
| Calendar spread decomposition | ✅ | [STIRSpread.decompose](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/instruments/stir/spread.py#L16-L20) |
| Butterfly decomposition | ✅ | [STIRFly.decompose](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/instruments/stir/fly.py#L16-L21) — `+1, -2, +1` is correct |
| Factory helpers (Euribor, SOFR, SONIA, Fed Funds) | ✅ | Tick sizes/values match CME/ICE specs |
| Daily settlement / variation margin | ❌ Missing | No daily mark-to-market settlement cycle |
| Roll handling | ❌ Missing | No contract expiry or roll logic |
| Initial/maintenance margin enforcement | ⚠️ Partial | `FuturesMarginModel` exists but is never enforced at order time |

**Verdict:** The STIR instrument modeling (outright + spread + fly decomposition) is the strongest part of the codebase. Genuine understanding of multi-leg structure. However, the accounting layer does not properly support futures (see Part 6).

### Options

| Feature | Status | Evidence |
|---|---|---|
| Black-Scholes formula | ✅ Correct | [options.py L31-37](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/pricing/options.py#L31-L37) |
| Greeks calculation | ❌ Missing | Greeks fields exist on `OptionDataEvent` but are **passed in** from data, not computed |
| IV → Price | ✅ | Uses feed-provided IV correctly |
| Expiry handling | ⚠️ Stub | [OptionExpiryEvent](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/lifecycle.py#L29-L51) cash-settles; no physical exercise/assignment |
| Time format | ⚠️ Ambiguous | [options.py L24](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/pricing/options.py#L24): `T = expiry_timestamp - data.timestamp` — comment admits timestamps should be in years but no conversion is performed |
| Put-call parity | Not verified | No test |

**Verdict:** The BSM formula itself is textbook-correct. But the engine does not compute Greeks, does not handle early exercise (American options), and has an unresolved timestamp-unit ambiguity that would silently produce wrong prices with real data.

### Bonds

| Feature | Status | Evidence |
|---|---|---|
| Pricing | ❌ **Wrong** | [bonds.py L19-23](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/pricing/bonds.py#L19-L23) |
| Yield calculations | ❌ Missing | No YTM solver |
| Accrued interest | ❌ Missing | |
| Coupon handling | ⚠️ Stub | [CouponPaymentEvent](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/lifecycle.py#L53-L56) adds cash but doesn't track accrual |
| Duration/Convexity | ❌ Not computed | Passed in from data feed, not calculated |
| Day count conventions | ❌ Missing | |

> [!CAUTION]
> **The bond pricer is mathematically invalid.** It computes:
> ```python
> dy = data.ytm - self.coupon_rate
> price_change_pct = -data.duration * dy + 0.5 * data.convexity * (dy**2)
> price = face_value * (1 + price_change_pct)
> ```
> This is a Taylor expansion of price **change** around a reference yield, but it uses `ytm - coupon_rate` as the yield change `dy`, which is **conceptually wrong**. The duration-convexity approximation should use `dy = ytm - y_reference` where `y_reference` is the yield at which duration/convexity were measured. Using the coupon rate as the reference point is an error: a par bond (ytm = coupon) would correctly price at face, but any other bond will be wrong.
>
> Additionally, this is not a pricer — it's an approximation. Real bond pricing requires discounting each cash flow.

**Verdict:** Not institutionally valid. The bond module is a non-functional stub.

---

## PART 4 — Mathematical Audit

### Performance Metrics

| Formula | File | Correct? | Issue | Fix |
|---|---|---|---|---|
| **Simple Returns** | [metrics.py L3-7](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L3-L7) | ✅ | `np.diff(prices) / prices[:-1]` | — |
| **Sharpe Ratio** | [metrics.py L9-16](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L9-L16) | ❌ | Uses `np.std(returns)` which is **population std** (ddof=0). Should use **sample std** (ddof=1). Also, `risk_free_rate` is subtracted per-period but is not annualized — if 0.02 is passed, it subtracts 2% per bar, not per year. | Use `np.std(returns, ddof=1)` and `risk_free_rate / periods` for per-bar adjustment |
| **Sortino Ratio** | [metrics.py L26-36](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L26-L36) | ❌ | Same population-std error. Additionally, `downside_std` is computed only over negative returns, which is the **semi-deviation**, not the proper downside deviation. Institutional Sortino uses the square root of the mean of squared negative deviations from the target across *all* observations. | Compute: `np.sqrt(np.mean(np.minimum(returns - target, 0)**2))` |
| **Max Drawdown** | [metrics.py L18-24](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L18-L24) | ✅ | Peak-to-trough percentage, correct | — |
| **Calmar Ratio** | — | ❌ Missing | | |
| **Information Ratio** | — | ❌ Missing | | |
| **Tracking Error** | — | ❌ Missing | | |
| **Beta / Rolling Regression** | — | ❌ Missing | | |
| **Factor Exposures** | — | ❌ Missing | | |
| **Attribution** | — | ❌ Missing | | |

### Volatility Targeting

[vol_target.py L46](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/sizing/vol_target.py#L46):
```python
realized_vol = np.std(returns) * np.sqrt(252)
```
**Issue:** Population std again (`ddof=0`). With a 20-bar window, this underestimates vol by ~2.5%, leading to systematic over-sizing.

### PnL Calculations

[pnl.py L84-89](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L84-L89):
```python
price_diff = price - current_cb if current_qty > 0 else current_cb - price
realized = instrument.pnl_scalar(price_diff) * abs(close_qty)
```

**Issue:** `pnl_scalar` for STIR instruments already converts price moves to dollar PnL: `(price_move / tick_size) * tick_value`. Multiplying by `abs(close_qty)` is correct. However, in [_recalculate_account L130](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L130):
```python
portfolio_value += qty * price  # Standard equity model
```
This applies equity-style accounting (position_value = qty × price) to **all** instrument types including futures. For a STIR future at price 95.50, this adds `1 × 95.50 = $95.50` to portfolio value, which is meaningless. Futures positions have zero cost (margin-posted), and their value comes from mark-to-market PnL. **This produces fundamentally wrong total_equity for any non-equity instrument.**

---

## PART 5 — Backtest Validity Audit

| Bias Type | Found? | Location | Severity | Impact |
|---|---|---|---|---|
| **Look-ahead bias** | ⚠️ Potential | [execution/engine.py L40](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/engine.py#L40): Market orders fill at `bar.close` — strategy sees the close, signals, and fills at that same close price in the same bar | **High** | Fills at the price used to generate the signal is a classic look-ahead bias. Orders should fill at next-bar open. |
| **Survivorship bias** | N/A | No real data loader — synthetic data only | Low | Engine doesn't address this; user responsibility |
| **Data leakage** | ⚠️ | [warmup.py](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/strategy/warmup.py): warmup wrapper traps signals in dummy queue but strategy **internal state** (e.g., `in_position`) still mutates, which is correct. However the dummy queue accumulates events forever without draining — memory leak. | Low | |
| **Execution timing** | ⚠️ | Strategy `on_bar` receives the bar, emits a signal, which becomes an order, which fills — all within the **same event processing cycle**. In reality, there should be at minimum a 1-bar delay. | **High** | Overstates strategy performance |
| **Forward leakage in OHLCV** | ⚠️ | [SyntheticFeed](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/data/feed.py#L29-L33): High/Low are generated around Close, meaning Close is known before High/Low are set. With real data this isn't an issue, but the synthetic data structure doesn't enforce proper OHLC sequencing. | Low | |

---

## PART 6 — Portfolio Accounting Audit

### Cash Accounting

| Operation | Correct for Equities? | Correct for Futures? |
|---|---|---|
| Buy: `cash -= qty * price` | ✅ | ❌ Futures don't deduct notional from cash |
| Sell: `cash += qty * price` (via negative qty) | ✅ | ❌ |
| Commission: `cash -= commission` | ✅ | ✅ |

### Position Accounting

| Feature | Status |
|---|---|
| Long positions | ✅ Works |
| Short positions | ✅ Works (negative qty) |
| Position flips | ✅ Handles sign change |
| VWAP cost basis | ✅ Correct formula |
| Decomposed leg positions | ✅ Correct |

### Critical Accounting Bug: Equity Model for Futures

[pnl.py L127-132](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L127-L132):

```python
portfolio_value = self.available_cash
for symbol, qty in self.positions.items():
    price = self.current_prices.get(symbol, 0.0)
    portfolio_value += qty * price  # Standard equity model
```

> [!CAUTION]
> This is **fundamentally wrong for futures.** A STIR future with a price of 95.50 does not have a position value of `qty × 95.50`. The correct futures accounting is:
> ```
> total_equity = cash_balance + unrealized_variation_margin
> ```
> where variation margin = `Σ (current_price - entry_price) × contract_multiplier × qty`
>
> The engine already computes `unrealized_pnl` correctly in [L107-114](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L107-L114) but **never uses it** for total equity calculation. The variable `unrealized_pnl` is computed and then discarded.

### Decomposable Instrument Cost Basis Bug

[pnl.py L50-53](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L50-L53):
```python
for i, (leg_sym, leg_qty) in enumerate(legs.items()):
    leg_price = price if i == 0 else 0.0
```

The entire synthetic price is assigned to the first leg, and remaining legs get cost basis = 0. This means realized PnL on individual legs will be wrong. If you buy a spread at 0.50, leg 1 gets CB=0.50 and leg 2 gets CB=0.00. Closing leg 2 at any price shows infinite percentage gain/loss.

---

## PART 7 — Risk Engine Audit

### Pre-Trade Risk

| Check | Implemented | Bypassable? |
|---|---|---|
| Position limits (per symbol) | ✅ [PositionLimitCheck](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/risk/pre_trade.py#L11-L30) | Yes — if `pre_trade_risk` is `None`, all orders pass ([engine.py L88](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L88)) |
| Exposure limits (gross/net) | ❌ Missing | — |
| Leverage limits | ❌ Missing | — |
| Concentration limits | ❌ Missing | — |
| Margin sufficiency check | ❌ Missing | Margin is **calculated** but never **enforced** |
| Order size validation | ❌ Missing | Negative/zero quantity orders are not rejected |

### Post-Trade Risk

| Check | Implemented | Notes |
|---|---|---|
| Max drawdown flatten | ✅ [DrawdownControl](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/risk/drawdown.py) | Correct: tracks peak equity, computes percentage drawdown |
| Daily loss limit | ⚠️ Partial | [DailyLossLimit](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/risk/budget.py) exists but `start_day()` is **never called** by the engine — it's dead code |
| Halt trading | ✅ | `PostTradeAction.HALT_TRADING` raises `RuntimeError` |

> [!WARNING]
> **The post-trade flatten logic in [engine.py L104-114](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L104-L114) references `SignalDirection` and `OrderType` which are NOT imported.** This code will throw a `NameError` at runtime whenever a drawdown breach occurs. The risk system's most critical safety mechanism is non-functional.

---

## PART 8 — Execution Simulation Audit

### Order Types

| Type | Implemented | Issues |
|---|---|---|
| Market | ✅ | Fills at bar close (look-ahead concern) |
| Limit | ✅ | Logic checks `bar.low > order.price` for buys — correct but fills at limit price instead of accounting for potential price improvement |
| Stop | ✅ | Logic checks `bar.high < order.price` for buy-stops — correct. Fills at stop price, not at a worse price (unrealistic) |
| Partial fills | ✅ | 10% of bar volume cap per order per bar |

### Slippage Models

| Model | Correct? |
|---|---|
| [ZeroSlippage](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/slippage.py#L9-L11) | ✅ |
| [FixedBasisPointSlippage](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/slippage.py#L13-L24) | ✅ Adverse direction correct |
| [VolumeLinearSlippage](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/slippage.py#L26-L43) | ✅ Square-root model would be more realistic but linear is acceptable |

### Execution Timing Issue

[execution/engine.py L25-33](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/engine.py#L25-L33): When a new order arrives, `on_order` immediately attempts to fill it against `current_bars`. Combined with the engine processing chain (BAR → strategy.on_bar → SIGNAL → allocator → ORDER → execution.on_order), an order can be generated and filled **within the same bar**. This is a significant source of look-ahead bias.

---

## PART 9 — Performance Audit

### Time Complexity

| Operation | Complexity | Notes |
|---|---|---|
| Event queue put/get | O(log n) | `PriorityQueue` (heap) |
| Bar processing | O(k) per bar | k = number of active orders (linear scan in `update_market_bar`) |
| Position update | O(1) | Dict lookup |
| Account recalculation | O(p) | p = number of positions (scans all positions) |
| Multi-symbol sync | O(f) per event | f = number of feeds |

### Scalability Estimates

| Event Count | Feasibility | Estimated Time | Bottleneck |
|---|---|---|---|
| 1M | ✅ Feasible | ~10-30 seconds | Event serialization (list append + dict conversion) |
| 10M | ⚠️ Strained | ~5-15 minutes | `EventSerializer.events` list consumes ~4-8 GB RAM; PriorityQueue overhead |
| 100M | ❌ Infeasible | Hours+ / OOM | In-memory event log, no streaming serialization |

### Key Bottlenecks

1. **[EventSerializer](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/recorder.py):** Stores every event as a dict in an unbounded list. At 100M events, this alone requires ~40+ GB RAM.
2. **[OrderBookMatcher.update_market_bar](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/engine.py#L21-L23):** Iterates all active orders for every bar for every symbol. With many pending limit orders, this is O(bars × orders).
3. **No vectorized path:** Everything is tick-by-tick with Python object overhead. No Cython/Numba acceleration.

---

## PART 10 — Testing Audit

### Test Inventory

| Test File | Type | Tests | What it covers |
|---|---|---|---|
| [test_core.py](file:///c:/Users/kanda/Desktop/can_backtest_new/tests/test_core.py) | Unit | 2 | Clock advancement, event priority ordering |
| [smoke_test.py](file:///c:/Users/kanda/Desktop/can_backtest_new/scripts/smoke_test.py) | Smoke | 1 | Basic MA crossover on synthetic equity |
| [smoke_test_full.py](file:///c:/Users/kanda/Desktop/can_backtest_new/scripts/smoke_test_full.py) | Smoke | 1 | Multi-asset with risk, slippage, warmup |
| [smoke_test_legging.py](file:///c:/Users/kanda/Desktop/can_backtest_new/scripts/smoke_test_legging.py) | Integration | 1 | STIR leg decomposition + fly equivalence |

### Coverage Analysis

| Module | Tested? | Missing |
|---|---|---|
| `core/engine.py` | Smoke only | No unit tests for event processing, component validation |
| `events/*` | ✅ Priority test | No tests for event serialization, frozen dataclass behavior |
| `execution/*` | ❌ | Limit/stop order logic, partial fills, slippage calculations |
| `portfolio/pnl.py` | Smoke only | Cost basis, position flips, short positions, multi-asset PnL |
| `portfolio/lifecycle.py` | ❌ | Option expiry, coupon payments |
| `portfolio/margin.py` | ❌ | Margin calculations |
| `pricing/*` | ❌ | Black-Scholes accuracy, bond pricing |
| `risk/*` | ❌ | Drawdown control, position limits, daily loss |
| `sizing/*` | ❌ | Vol targeting, percent-equity sizer |
| `analytics/*` | ❌ | Sharpe, Sortino, max drawdown |
| `data/*` | ❌ | Multi-symbol synchronization |
| `strategy/warmup.py` | ❌ | Warmup per-symbol tracking |

**Approximate Coverage:** ~5%

### Missing Test Categories

- ❌ **Edge cases:** Zero positions, zero volume bars, zero-price instruments, negative prices, NaN handling
- ❌ **Regression tests:** No golden-file comparison for deterministic replay
- ❌ **Property tests:** No Hypothesis-style fuzzing
- ❌ **Mathematical validation:** No known-answer tests for BS, Sharpe, bond pricing
- ❌ **Boundary tests:** Position flip (long→short), max drawdown exactly at threshold

---

## PART 11 — Production Readiness Audit

| Use Case | Suitable? | Justification |
|---|---|---|
| Educational use | ✅ | Good pedagogical structure; demonstrates event-driven concepts clearly |
| Personal research | ⚠️ Conditional | Only for equities with significant caveats about look-ahead bias |
| Professional research | ❌ | Mathematical errors, accounting bugs, no determinism |
| Hedge fund research | ❌ | Would not pass any institutional code review |
| Live trading preparation | ❌ | No market connectivity, no real-time event handling, fatal accounting issues |

### Missing Requirements for Professional Use

**Essential:**
- [ ] Deterministic event ordering (replace UUID)
- [ ] Fix Sharpe/Sortino calculations (sample std, proper downside deviation)
- [ ] Proper futures accounting (variation margin model)
- [ ] Fix missing imports in engine.py flatten logic
- [ ] Next-bar execution (eliminate same-bar look-ahead)
- [ ] Comprehensive unit test suite (>80% coverage)
- [ ] Logging framework (replace all `print` statements)

**Important:**
- [ ] Real data loaders (CSV, Parquet, database)
- [ ] Benchmark comparison (alpha, beta, tracking error)
- [ ] Greeks computation for options
- [ ] Proper bond cash-flow discounting
- [ ] Daily settlement cycle for futures
- [ ] Margin enforcement at order time
- [ ] Order cancellation from strategy
- [ ] Walk-forward / out-of-sample splitting
- [ ] Parameter sensitivity / Monte Carlo

**Nice-to-Have:**
- [ ] Vectorized fast-path for simple strategies
- [ ] Multi-currency support
- [ ] Dividend/split handling
- [ ] Portfolio-level risk attribution
- [ ] Integration with QuantLib for pricing

---

## PART 12 — Quant Research Capability Audit

| Strategy Type | Supported? | Limitations |
|---|---|---|
| Trend following | ⚠️ Partial | Works on equities; look-ahead bias inflates results |
| Mean reversion | ⚠️ Partial | No short-selling cost model, no borrow availability |
| Statistical arbitrage | ❌ | No cointegration tools, no pairs construction, no real-time spread pricing |
| Relative value | ⚠️ Partial | STIR spread/fly structure supports it; accounting is broken for futures |
| Factor investing | ❌ | No factor loading, no universe management, no cross-sectional ranking |
| Volatility trading | ❌ | No vol surface, no delta hedging, options accounting incomplete |
| Futures spread trading | ⚠️ Partial | Decomposition is correct; PnL accounting is wrong |
| Butterfly strategies | ⚠️ Partial | Same as spreads — structure correct, accounting wrong |
| Options strategies | ❌ | No multi-leg option positions, no Greeks P&L, no assignment risk |
| Multi-asset portfolios | ⚠️ Partial | Multi-symbol sync works; portfolio accounting assumes equity model for all |

---

## PART 13 — Code Quality Audit

| Aspect | Score | Notes |
|---|---|---|
| Naming | 8/10 | Consistent, descriptive class/function names; `pnl_scalar` slightly ambiguous |
| Readability | 7/10 | Small files, clear flow; MVP comments are honest about limitations |
| Type hints | 7/10 | Present on most public APIs; some `Any`-equivalent untyped params (`set_feed(self, feed)`) |
| Logging | 1/10 | Zero `logging` module usage; all diagnostics via `print()` |
| Error handling | 4/10 | Some `ValueError` raises; no graceful degradation; `RuntimeError` for risk halt |
| Configuration | 7/10 | `pydantic-settings` with env-var prefix is a good pattern |
| Documentation | 4/10 | Docstrings on ~30% of classes; no API docs; inline comments are sparse but honest |

### Technical Debt

1. **`print()` everywhere** — 8 occurrences across production code; should use `logging`
2. **No `__all__` exports** — public API surface is undefined
3. **Untyped setter methods** — `set_feed(self, feed)` accepts anything
4. **`hasattr` checks** — Used instead of `isinstance` for type discrimination in 2 critical locations
5. **Hardcoded 10% volume participation** — [execution/engine.py L62](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/execution/engine.py#L62) should be configurable
6. **Event serializer memory** — Unbounded list growth

---

## PART 14 — Critical Review (Adversarial)

### Hidden Bugs

| File | Bug | Impact |
|---|---|---|
| [engine.py L104-114](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L104-L114) | `SignalDirection` and `OrderType` are used but not imported. The flatten-on-risk-breach code **will crash at runtime**. | **Fatal** — risk system's primary safety mechanism is broken |
| [engine.py L81](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L81) | `strategy.on_bar(event, ...)` is called for **all** BAR events, including `YieldDataEvent` and `OptionDataEvent`. But `Strategy.on_bar` is typed as `bar: TradeBarEvent`. Non-OHLCV events will silently pass through without useful data. | Silent data confusion |
| [pnl.py L130](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L130) | `qty * price` for futures positions adds meaningless notional to portfolio value. A 1-lot SOFR future at 95.50 adds $95.50 instead of the actual variation margin P&L. | **Silently wrong equity curve and risk calculations for all non-equity instruments** |
| [pnl.py L81](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L81) | `close_qty` calculation: `min(abs(current_qty), abs(qty)) * (1 if current_qty < 0 else -1)`. This negates close_qty for long positions, making it negative. Then `abs(close_qty)` is used later, so the sign is discarded. But the intent is unclear and the intermediate value is confusing. Functionally it works but is fragile. | Latent fragility |
| [pnl.py L60](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L60) | `self.available_cash -= qty * price` — for a SHORT (qty is negative), this **adds** cash. This is correct for equity short-sell proceeds but wrong for futures. | Wrong cash for futures |
| [types.py L16](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/events/types.py#L16) | `uuid.uuid4().hex` for event IDs breaks determinism | Irreproducible results |
| [budget.py](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/risk/budget.py) | `start_day()` is never called by the engine. `DailyLossLimit` has `start_of_day_equity = 0.0` by default, so `check()` always returns `True` (since `0 <= 0`). | Dead code — daily loss limit never triggers |
| [lifecycle.py L49](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/lifecycle.py#L49) | `del self.portfolio.positions[event.symbol]` — if the symbol isn't in positions (race condition on double-expiry), this throws `KeyError`. Should use `.pop()`. | Potential crash |

### Situations Where Results Appear Correct But Are Wrong

1. **Single-equity backtests:** The equity-model accounting accidentally works correctly for stocks (`qty * price` is the correct position value). All smoke tests use equities, so they pass. The moment you add a STIR future, results are silently wrong.

2. **Sharpe ratio with synthetic data:** The synthetic feed generates small, normally-distributed returns. With enough bars, the `ddof=0` vs `ddof=1` difference is negligible (~0.5%). The error only becomes material with short lookback windows or in-sample/out-of-sample comparisons.

3. **Risk flatten appears safe in smoke tests:** The drawdown never breaches in the demo scripts, so the missing-import crash in `engine.py L106` is never triggered.

---

## Critical Issues — Ranked

### 🔴 Critical

1. **[engine.py L106](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L106): Missing imports `SignalDirection`, `OrderType`** — Runtime crash on risk breach. The primary safety mechanism is non-functional.

2. **[pnl.py L127-132](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L127-L132): Equity-model accounting for all instruments** — Produces wrong `total_equity` for futures, options, bonds. Cascades into wrong risk calculations, wrong sizing, wrong Sharpe ratios.

3. **[types.py L16](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/events/types.py#L16): Non-deterministic UUID event IDs** — Backtests are not reproducible.

### 🟠 High

4. **Look-ahead bias: same-bar signal + fill** — Orders generated from a bar's close price fill at that same close price within the same event cycle.

5. **[metrics.py L14](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L14): Population std in Sharpe** — Systematically wrong risk-adjusted returns.

6. **[bonds.py L19-23](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/pricing/bonds.py#L19-L23): Invalid bond pricing** — Duration-convexity approximation uses wrong reference yield.

### 🟡 Medium

7. **[pnl.py L50-53](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L50-L53): Decomposed leg cost basis** — First leg gets full price, others get zero.

8. **Daily loss limit never triggers** — `start_day()` is never called by the engine.

9. **[engine.py L76](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/core/engine.py#L76): `hasattr` duck-typing** — Non-OHLCV events still call `strategy.on_bar()`, potentially confusing strategies.

### 🟢 Low

10. **EventSerializer unbounded memory** — OOM risk at scale.
11. **WarmupWrapper dummy queue memory leak** — Accumulates trapped events forever.
12. **No logging module** — print-based diagnostics only.

---

## Mathematical Errors — Catalog

| File | Function | Issue | Correct Fix |
|---|---|---|---|
| [metrics.py L14](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L14) | `sharpe_ratio` | `np.std(returns)` uses ddof=0 (population std) | `np.std(returns, ddof=1)` |
| [metrics.py L14](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L14) | `sharpe_ratio` | `risk_free_rate` not deannualized | `(mean_return - risk_free_rate/periods)` |
| [metrics.py L32](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/analytics/metrics.py#L32) | `sortino_ratio` | Semi-deviation of negatives only, not proper downside deviation | `np.sqrt(np.mean(np.minimum(returns - rfr/periods, 0)**2))` |
| [vol_target.py L46](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/sizing/vol_target.py#L46) | `allocate` | Population std for vol estimation | `np.std(returns, ddof=1)` |
| [bonds.py L19](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/pricing/bonds.py#L19) | `get_value` | `dy = ytm - coupon_rate` is wrong reference point | Use proper discounted cash flow or `dy = ytm - reference_yield` |
| [pnl.py L130](file:///c:/Users/kanda/Desktop/can_backtest_new/src/backtester/portfolio/pnl.py#L130) | `_recalculate_account` | `qty * price` for non-equity instruments | Dispatch by instrument type: equity → qty×price; futures → variation margin |

---

## Production Risks

**What could cause incorrect backtest results:**

1. Any STIR, options, or bond position will produce wrong equity curves, wrong Sharpe ratios, and wrong drawdown calculations due to the equity-model accounting bug.
2. Multi-asset backtests with identical timestamps will have non-reproducible execution order.
3. Same-bar execution inflates strategy returns by eliminating the bid-ask spread and execution delay.
4. If a drawdown breach ever occurs in production, the engine crashes instead of flattening.
5. The daily loss limit is inert — it can never trigger, giving a false sense of safety.

---

## Hedge Fund Approval Assessment

| Purpose | Approved? | Why |
|---|---|---|
| Research | ❌ | Mathematical errors in core metrics; accounting bugs produce wrong PnL for non-equity instruments; non-deterministic replay |
| Strategy Development | ❌ | Look-ahead bias makes strategy performance unreliable; single-asset equity-only would be marginally acceptable with caveats |
| Risk Analysis | ❌ | Risk flatten mechanism crashes at runtime; margin is calculated but never enforced; daily loss limit is dead code |
| Portfolio Construction | ❌ | No factor model, no optimizer, no correlation/covariance framework, wrong multi-asset accounting |

---

## Final Verdict

### Classification: **Educational**

**Justification:**

The engine demonstrates a genuine understanding of event-driven backtesting architecture. The module decomposition is thoughtful, the ABC-based extension points are well-designed, and the STIR instrument hierarchy (outright → spread → butterfly with decomposition) shows real domain knowledge of rate futures trading. The `WarmupWrapper` decorator pattern and `Decomposable` mixin are pedagogically valuable patterns.

However, the implementation fails the bar for "Research Grade" on three grounds:

1. **Correctness:** The portfolio accounting layer applies equity-model assumptions to all instruments, producing silently wrong results for futures, options, and bonds. The risk flatten mechanism has a fatal missing-import bug. Mathematical formulas use population standard deviation.

2. **Reliability:** Event ordering is non-deterministic due to UUID-based tie-breaking. The daily loss limit is dead code. No meaningful test coverage validates any of these critical paths.

3. **Completeness:** Bonds and options are acknowledged stubs. No Greeks computation, no daily settlement, no dividend handling, no real data loaders, no benchmark analytics.

The codebase is an excellent **educational scaffold** — approximately 60-70% of the way to a legitimate research-grade engine. The architectural bones are sound, but the flesh needs significant work before it can be trusted for quantitative research.

| Classification | Match? |
|---|---|
| Toy Project | ❌ Too structured |
| **Educational** | ✅ **This one** |
| Research Grade | ❌ Mathematical/accounting errors prevent trust |
| Professional Grade | ❌ No test coverage, no logging, no real data |
| Institutional Grade | ❌ Missing entire subsystems (risk, settlement, corporate actions) |
