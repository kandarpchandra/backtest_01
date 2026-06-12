import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from pathlib import Path

st.set_page_config(page_title="can_backtest Dashboard", layout="wide")

st.title("📈 Backtest Analysis Dashboard")

RESULTS_DIR = Path(__file__).parent.parent / "results"

@st.cache_data
def load_data():
    metrics = {}
    if (RESULTS_DIR / "metrics.json").exists():
        with open(RESULTS_DIR / "metrics.json", "r") as f:
            metrics = json.load(f)
            
    equity_df = pd.DataFrame()
    if (RESULTS_DIR / "equity.csv").exists():
        equity_df = pd.read_csv(RESULTS_DIR / "equity.csv")
        
    events_df = pd.DataFrame()
    if (RESULTS_DIR / "event_log.parquet").exists():
        events_df = pd.read_parquet(RESULTS_DIR / "event_log.parquet")
        
    return metrics, equity_df, events_df

metrics, equity_df, events_df = load_data()

if events_df.empty:
    st.warning(f"No backtest data found in {RESULTS_DIR}. Please run `python scripts/smoke_test_full.py` first.")
    st.stop()

# Helper to calculate drawdowns
def calculate_drawdown(equity_series):
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max
    return drawdown * 100

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Performance Summary", 
    "🕯️ Market Action", 
    "🧾 Trade Ledger", 
    "🔍 Raw Events"
])

# ==========================================
# TAB 1: PERFORMANCE SUMMARY
# ==========================================
with tab1:
    st.header("Key Performance Indicators")
    cols = st.columns(6)
    
    # Extract metrics safely
    final_eq = metrics.get("Final Equity", 0)
    realized_pnl = metrics.get("Realized PnL", 0)
    commissions = metrics.get("Total Commission", 0)
    sharpe = metrics.get("Sharpe Ratio", 0)
    sortino = metrics.get("Sortino Ratio", 0)
    max_dd = metrics.get("Max Drawdown", 0)
    
    cols[0].metric("Final Equity", f"${final_eq:,.2f}")
    cols[1].metric("Realized PnL", f"${realized_pnl:,.2f}")
    cols[2].metric("Commissions", f"${commissions:,.2f}")
    cols[3].metric("Sharpe Ratio", f"{sharpe:.2f}")
    cols[4].metric("Sortino Ratio", f"{sortino:.2f}")
    cols[5].metric("Max Drawdown", f"{max_dd:.2f}%")
    
    if not equity_df.empty:
        st.subheader("Equity Curve & Drawdown")
        
        eq = equity_df['equity']
        dd = calculate_drawdown(eq)
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Scatter(x=equity_df['timestamp'], y=eq, name="Equity", line=dict(color='blue')),
            secondary_y=False,
        )
        
        fig.add_trace(
            go.Scatter(x=equity_df['timestamp'], y=dd, name="Drawdown %", fill='tozeroy', line=dict(color='red', width=0), opacity=0.3),
            secondary_y=True,
        )
        
        fig.update_layout(height=500, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified")
        fig.update_yaxes(title_text="Total Equity ($)", secondary_y=False)
        fig.update_yaxes(title_text="Drawdown (%)", secondary_y=True, range=[-abs(dd.min()) * 1.5, 0])
        
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 2: MARKET ACTION
# ==========================================
with tab2:
    st.header("Market Action & Executions")
    
    bars = events_df[events_df['event_type'] == 'TradeBarEvent'].copy()
    fills = events_df[events_df['event_type'] == 'FillEvent'].copy()
    
    if bars.empty:
        st.info("No market data bars found in the event log.")
    else:
        symbols = bars['symbol'].unique()
        selected_symbol = st.selectbox("Select Symbol", symbols)
        
        sym_bars = bars[bars['symbol'] == selected_symbol]
        sym_fills = fills[fills['symbol'] == selected_symbol]
        
        fig = go.Figure()
        
        # Candlesticks
        fig.add_trace(go.Candlestick(
            x=sym_bars['timestamp'],
            open=sym_bars['open'],
            high=sym_bars['high'],
            low=sym_bars['low'],
            close=sym_bars['close'],
            name=f"{selected_symbol} OHLC"
        ))
        
        # Overlay Fills
        if not sym_fills.empty:
            buys = sym_fills[sym_fills['direction'].astype(str).str.contains('LONG|BUY')]
            sells = sym_fills[sym_fills['direction'].astype(str).str.contains('SHORT|SELL|FLAT')]
            
            fig.add_trace(go.Scatter(
                x=buys['timestamp'], y=buys['fill_price'],
                mode='markers', name='Buy Fill',
                marker=dict(symbol='triangle-up', size=12, color='green', line=dict(width=1, color='darkgreen')),
                text=buys['quantity'], hovertemplate="Price: %{y}<br>Qty: %{text}"
            ))
            
            fig.add_trace(go.Scatter(
                x=sells['timestamp'], y=sells['fill_price'],
                mode='markers', name='Sell Fill',
                marker=dict(symbol='triangle-down', size=12, color='red', line=dict(width=1, color='darkred')),
                text=sells['quantity'], hovertemplate="Price: %{y}<br>Qty: %{text}"
            ))
            
        fig.update_layout(
            height=600, 
            title=f"{selected_symbol} Price Chart",
            xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 3: TRADE LEDGER
# ==========================================
with tab3:
    st.header("Trade Ledger (Fills)")
    fills = events_df[events_df['event_type'] == 'FillEvent'].copy()
    
    if fills.empty:
        st.info("No fills recorded.")
    else:
        # Simplify display
        display_cols = ['timestamp', 'symbol', 'direction', 'quantity', 'fill_price', 'commission']
        existing_cols = [c for c in display_cols if c in fills.columns]
        
        st.dataframe(fills[existing_cols].sort_values('timestamp'), use_container_width=True)
        
        # Note: Implementing a full FIFO/LIFO round-trip matcher in Pandas is complex and 
        # usually belongs in the backtester engine itself. For this dashboard, we show fills.
        st.info("Note: The above table shows individual fills. Round-trip trade matching requires an explicit Trade object from the engine.")

# ==========================================
# TAB 4: RAW EVENTS
# ==========================================
with tab4:
    st.header("Raw Event Log Inspector")
    
    col1, col2 = st.columns(2)
    with col1:
        event_types = ["ALL"] + list(events_df['event_type'].unique())
        selected_event = st.selectbox("Filter by Event Type", event_types)
    with col2:
        # Some events might not have a symbol
        if 'symbol' in events_df.columns:
            symbols = ["ALL"] + list(events_df['symbol'].dropna().unique())
            selected_sym = st.selectbox("Filter by Symbol", symbols)
        else:
            selected_sym = "ALL"
            
    filtered_df = events_df.copy()
    if selected_event != "ALL":
        filtered_df = filtered_df[filtered_df['event_type'] == selected_event]
    if selected_sym != "ALL" and 'symbol' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['symbol'] == selected_sym]
        
    st.dataframe(filtered_df.sort_values('timestamp' if 'timestamp' in filtered_df.columns else filtered_df.index), use_container_width=True)
