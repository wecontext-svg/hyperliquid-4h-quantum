import streamlit as st
import plotly.graph_objects as go
from analysis import get_full_analysis, SYMBOLS
from datetime import datetime

st.set_page_config(page_title="Hyperliquid Quantum Analyzer", layout="wide", page_icon="⚡")
st.title("⚡ Hyperliquid 4H Quantum Weighted Analyzer")
st.caption("Quantum Confluence Engine • Lightning Fast • Pure SMC/ICT")

st.sidebar.header("⚡ Choose Symbol")
default_idx = SYMBOLS.index("xyz:NVDA")
selected = st.sidebar.selectbox("Select", SYMBOLS, index=default_idx)
custom = st.sidebar.text_input("Or type custom symbol", "")

symbol = custom.strip() or selected

@st.cache_data(ttl=300, show_spinner=False)
def cached_analysis(s: str):
    return get_full_analysis(s)

if st.button("🔥 ANALYZE NOW", type="primary", use_container_width=True):
    with st.spinner("Fetching data + running quantum analysis..."):
        result = cached_analysis(symbol)
    if not result or result.get("df") is None:
        st.error("No data received")
        st.stop()
    df = result["df"]
    a = {k: v for k, v in result.items() if k != "df"}
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader(f"{symbol} • 4H Chart")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close']))
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema50'], line=dict(color='orange', width=3), name="EMA50"))
        for lvl in a["buy_liquidity"]: fig.add_hline(y=lvl, line_dash="dash", line_color="lime", annotation_text="BUY LIQ")
        for lvl in a["sell_liquidity"]: fig.add_hline(y=lvl, line_dash="dash", line_color="red", annotation_text="SELL LIQ")
        fig.update_layout(template="plotly_dark", height=680)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("🔥 Quantum Analysis")
        color = "🟢" if a["bias"] == "bullish" else "🔴"
        st.metric("Bias", f"{color} {a['bias'].upper()}", f"Confidence: {a['confidence']}%")
        st.write("**Reason:**", a["reason"])
        st.code(f"Price: {a['current_price']}\nTarget: {a['target']}\nSL: {a['sl']}")
        st.link_button("📊 Open Hyperliquid Chart", f"https://app.hyperliquid.xyz/trade/{symbol}", use_container_width=True)
