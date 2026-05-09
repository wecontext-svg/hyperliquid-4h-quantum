import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from analysis import get_full_analysis, SYMBOLS

st.set_page_config(page_title="Hyperliquid Quantum V2", layout="wide", page_icon="⚡")
st.title("⚡ Hyperliquid 4H Quantum V2 Analyzer")
st.caption("Advanced ICT + Quantum Weighted Confluence")

# ── Sidebar ──────────────────────────────────────────────
st.sidebar.header("Symbol")
default_idx = SYMBOLS.index("xyz:NVDA") if "xyz:NVDA" in SYMBOLS else 0
selected = st.sidebar.selectbox("Select symbol", SYMBOLS, index=default_idx)
custom = st.sidebar.text_input("Or enter custom symbol (e.g. BTC)", "")
symbol = custom.strip() if custom.strip() else selected

# ── Analyze ───────────────────────────────────────────────
if st.button("🔥 ANALYZE NOW", type="primary", use_container_width=True):
    with st.spinner("Running Quantum V2 Analysis..."):
        r = get_full_analysis(symbol)

    df = r.get("df")
    has_data = df is not None and not df.empty

    if r.get("error"):
        st.error(f"⚠️ {r['error']}")

    col1, col2 = st.columns([3, 2])

    # ── Chart ─────────────────────────────────────────────
    with col1:
        st.subheader(f"{symbol} • 4H Chart")
        fig = go.Figure()

        if has_data:
            fig.add_trace(go.Candlestick(
                x=df['time'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="Price",
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ))

            if 'ema50' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['time'], y=df['ema50'],
                    line=dict(color='orange', width=1.5),
                    name="EMA50"
                ))

            for h in r.get('swing_highs', [])[-8:]:
                fig.add_hline(y=h['price'],
                    line=dict(color='rgba(239,83,80,0.5)', width=1, dash='dash'),
                    annotation_text="Sell Liq", annotation_font_size=9)

            for l in r.get('swing_lows', [])[-8:]:
                fig.add_hline(y=l['price'],
                    line=dict(color='rgba(38,166,154,0.5)', width=1, dash='dash'),
                    annotation_text="Buy Liq", annotation_font_size=9)

            ob = r.get('order_block_zone')
            if ob:
                fig.add_hrect(y0=ob['bottom'], y1=ob['top'],
                    fillcolor='rgba(255,165,0,0.15)', line_width=0,
                    annotation_text="Order Block", annotation_font_size=9)

            fvg = r.get('fvg_zone')
            if fvg:
                fig.add_hrect(y0=fvg['bottom'], y1=fvg['top'],
                    fillcolor='rgba(100,149,237,0.15)', line_width=0,
                    annotation_text="FVG", annotation_font_size=9)

            if r.get('sl'):
                fig.add_hline(y=r['sl'],
                    line=dict(color='#ef5350', width=1.5, dash='dot'),
                    annotation_text=f"SL {r['sl']}", annotation_font_size=10)

            if r.get('target'):
                fig.add_hline(y=r['target'],
                    line=dict(color='#26a69a', width=1.5, dash='dot'),
                    annotation_text=f"Target {r['target']}", annotation_font_size=10)
        else:
            fig.add_annotation(text="No chart data yet — stub mode",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font=dict(size=16, color="gray"))

        fig.update_layout(
            template="plotly_dark", height=600,
            xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Analysis Panel ────────────────────────────────────
    with col2:
        st.subheader("Quantum V2 Analysis")

        # Bias + Confidence
        bias = r.get('bias', 'neutral')
        conf = r.get('confidence', 0)
        score = r.get('score', 0)
        bias_icon = "🟢" if bias == 'bullish' else "🔴" if bias == 'bearish' else "⚪"

        if conf >= 85:
            conf_label = "HIGH CONVICTION"
            conf_color = "normal"
        elif conf >= 72:
            conf_label = "VALID SETUP"
            conf_color = "normal"
        elif conf >= 51:
            conf_label = "DEVELOPING"
            conf_color = "off"
        else:
            conf_label = "WEAK / NO SETUP"
            conf_color = "inverse"

        st.metric("Bias", f"{bias_icon} {bias.upper()}", f"Q-Score: {score}  |  {conf}% — {conf_label}")

        st.divider()

        # OTE flag
        if r.get('ote_flag'):
            st.success("⚡ OTE ZONE — Optimal Trade Entry")

        # HTF alignment
        if r.get('hte_aligned'):
            st.markdown("**HTF:** ✅ Daily Aligned")
        else:
            st.markdown("**HTF:** ⚠️ Against Daily Structure")

        # Premium / Discount
        pd_raw = r.get('premium_discount', '')
        st.markdown(f"**Entry Zone:** {pd_raw}")

        st.divider()

        # Factor scores
        st.markdown("**Factor Breakdown**")
        factors = [
            ("Structure",     r.get('structure', 0),     r.get('structure_tag', '')),
            ("Liquidity",     r.get('liquidity', 0),     ""),
            ("Order Block",   r.get('order_block', 0),   ""),
            ("FVG",           r.get('fvg', 0),           ""),
            ("Displacement",  r.get('displacement', 0),  ""),
            ("EMA",           r.get('ema', 0),           ""),
            ("Volume",        r.get('volume', 0),        ""),
        ]

        for name, val, tag in factors:
            bar = int(val / 10)
            filled = "█" * bar
            empty = "░" * (10 - bar)
            color = "🟢" if val >= 75 else "🟡" if val >= 50 else "🔴"
            label = f" ({tag})" if tag else ""
            st.markdown(f"{color} **{name}{label}** {filled}{empty} `{val}`")

        st.markdown(f"**Entanglement:** ×{r.get('entanglement_multiplier', 1.0)}")

        st.divider()

        # Levels
        cp = r.get('current_price', 0)
        tgt = r.get('target', 0)
        sl = r.get('sl', 0)

        if cp and tgt and sl:
            reward = round(tgt - cp, 2) if bias == 'bullish' else round(cp - tgt, 2)
            risk   = round(cp - sl, 2)  if bias == 'bullish' else round(sl - cp, 2)
            rr     = round(reward / risk, 2) if risk > 0 else 0
        else:
            reward = risk = rr = 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Entry",  f"{cp}")
        c2.metric("Target", f"{tgt}", f"+{reward}" if bias == 'bullish' else f"-{reward}")
        c3.metric("SL",     f"{sl}",  f"-{risk}"   if bias == 'bullish' else f"+{risk}")

        rr_color = "✅" if rr >= 2 else "⚠️"
        st.markdown(f"**R:R** {rr_color} `{rr}:1`")

        st.divider()

        st.caption(f"Reason: {r.get('reason', '')}")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
