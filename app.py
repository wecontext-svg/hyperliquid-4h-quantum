import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Options Flow Analyzer", layout="wide", page_icon="📊")
st.title("📊 Weekly Options Flow Analyzer")
st.caption("Max Call / Put OI Strike Levels — Yahoo Finance")

SYMBOLS = ['NVDA', 'INTC', 'AMD', 'AAPL', 'AMZN', 'GOOGL', 'MSFT', 'PLTR', 'HOOD', 'ORCL', 'MU']

# ── Sidebar ───────────────────────────────────
st.sidebar.header("Symbol")
selected = st.sidebar.selectbox("Select symbol", SYMBOLS)
custom   = st.sidebar.text_input("Or enter custom ticker (e.g. TSLA)", "")
symbol   = custom.strip().upper() if custom.strip() else selected

# ── Analyze ───────────────────────────────────
if st.button("🔥 ANALYZE OPTIONS", type="primary", use_container_width=True):
    with st.spinner("Fetching options chain..."):
        try:
            ticker  = yf.Ticker(symbol)
            expiries = ticker.options
            if not expiries:
                st.error("No options data found for this symbol.")
                st.stop()

            # Pick nearest weekly expiry
            expiry = expiries[0]
            chain  = ticker.option_chain(expiry)
            calls  = chain.calls
            puts   = chain.puts

        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    # Filter to ±20% of current price
    lower = price * 0.80
    upper = price * 1.20
    calls = calls[(calls['strike'] >= lower) & (calls['strike'] <= upper)]
    puts  = puts[(puts['strike'] >= lower)  & (puts['strike'] <= upper)]

    if calls.empty or puts.empty:
        st.error("No contracts found within ±20% of current price.")
        st.stop()

    # Max OI strikes
    call_row    = calls.loc[calls['openInterest'].idxmax()]
    put_row     = puts.loc[puts['openInterest'].idxmax()]
    call_strike = call_row['strike']
    put_strike  = put_row['strike']
    call_oi     = int(call_row['openInterest'])
    put_oi      = int(put_row['openInterest'])

    # Current price
    info  = ticker.fast_info
    price = round(info.last_price, 2)

    # ── Metrics ───────────────────────────────
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Current Price",     f"${price}")
    col2.metric("📈 Max Call OI Strike", f"${call_strike}", f"{call_oi:,} contracts")
    col3.metric("📉 Max Put OI Strike",  f"${put_strike}",  f"{put_oi:,} contracts")
    mid = round((call_strike + put_strike) / 2, 2)
    col4.metric("⚖️ Midpoint",           f"${mid}")

    # Bias based on price vs midpoint
    if price > mid:
        st.success(f"📈 Price above midpoint — Bullish bias toward ${call_strike}")
    elif price < mid:
        st.warning(f"📉 Price below midpoint — Bearish bias toward ${put_strike}")
    else:
        st.info("⚖️ Price at midpoint — Neutral")

    st.divider()

    # ── OI Bar Chart ──────────────────────────
    st.subheader(f"Open Interest by Strike — Expiry: {expiry}")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=calls['strike'], y=calls['openInterest'],
        name='Calls', marker_color='#26a69a', opacity=0.8
    ))

    fig.add_trace(go.Bar(
        x=puts['strike'], y=puts['openInterest'],
        name='Puts', marker_color='#ef5350', opacity=0.8
    ))

    fig.add_vline(x=call_strike,
        line=dict(color='#26a69a', width=2, dash='dash'),
        annotation_text=f"Max Call OI ${call_strike}",
        annotation_font_size=11)

    fig.add_vline(x=put_strike,
        line=dict(color='#ef5350', width=2, dash='dash'),
        annotation_text=f"Max Put OI ${put_strike}",
        annotation_font_size=11)

    fig.add_vline(x=price,
        line=dict(color='white', width=1.5, dash='dot'),
        annotation_text=f"Price ${price}",
        annotation_font_size=11)

    fig.update_layout(
        template="plotly_dark", height=500,
        xaxis_title="Strike Price",
        yaxis_title="Open Interest",
        barmode='overlay',
        margin=dict(l=0, r=0, t=30, b=0)
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── All expiries ──────────────────────────
    st.caption(f"Available expiries: {', '.join(expiries[:8])}")
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
