import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from analysis import get_full_analysis, SYMBOLS

st.set_page_config(page_title="Hyperliquid Quantum V2", layout="wide", page_icon="⚡")
st.title("⚡ Hyperliquid 4H Quantum V2 Analyzer")
st.caption("Advanced ICT + Quantum Weighted Confluence")

st.sidebar.header("Symbol")
default_idx = SYMBOLS.index("xyz:NVDA") if "xyz:NVDA" in SYMBOLS else 0
selected = st.sidebar.selectbox("Select symbol", SYMBOLS, index=default_idx)
custom = st.sidebar.text_input("Or enter custom symbol (e.g. BTC)", "")

symbol = custom.strip() if custom.strip() else selected

if st.button("🔥 ANALYZE NOW", type="primary", use_container_width=True):
    with st.spinner("Running Quantum V2 Analysis..."):
        result = get_full_analysis(symbol)
    
    if result.get("df") is None:
        st.error("No data")
        st.stop()
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader(f"{symbol} • 4H Chart")
        # Placeholder chart
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", height=600)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Quantum V2 Analysis")
        
        bias_color = "🟢" if result['bias'] == 'bullish' else "🔴"
        st.metric("Bias", f"{bias_color} {result['bias'].upper()}", f"{result['confidence']}%")
        
        st.write("**Structure:**", f"{result.get('structure', 0)} ({result.get('structure_tag', '')})")
        
        if result.get('ote_flag'):
            st.success("⚡ OTE ZONE — Optimal Trade Entry")
        
        st.write("**Liquidity:**", result.get('liquidity', 0))
        st.write("**Order Block:**", result.get('order_block', 0))
        st.write("**FVG:**", result.get('fvg', 0))
        st.write("**Displacement:**", result.get('displacement', 0))
        st.write("**EMA:**", result.get('ema', 0))
        st.write("**Volume:**", result.get('volume', 0))
        
        st.write("**Entanglement:**", f"×{result.get('entanglement_multiplier', 1.0)}")
        
        if result.get('hte_aligned'):
            st.write("**HTF:** ✅ Daily Aligned")
        else:
            st.write("**HTF:** ⚠️ Against Daily")
        
        st.write("**Premium/Discount:**", result.get('premium_discount', ''))
        
        st.metric("Target", result.get('target', 0))
        st.metric("Stop Loss", result.get('sl', 0))
        
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M')}")
