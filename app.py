import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Options Flow Analyzer", layout="wide", page_icon="📊")
st.title("📊 Weekly Options Flow Analyzer")
st.caption("Max Pain · IV Skew · GEX · Options Levels")

SYMBOLS = ['NVDA', 'INTC', 'AMD', 'AAPL', 'AMZN', 'GOOGL', 'MSFT', 'PLTR', 'HOOD', 'ORCL', 'MU']

# ── Sidebar ───────────────────────────────────
st.sidebar.header("Symbol")
selected = st.sidebar.selectbox("Select symbol", SYMBOLS)
custom   = st.sidebar.text_input("Or enter custom ticker (e.g. TSLA)", "")
symbol   = custom.strip().upper() if custom.strip() else selected

# ── Calculations ──────────────────────────────

def calc_max_pain(calls, puts):
    all_strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
    min_pain, max_pain_strike = float('inf'), all_strikes[0]
    for s in all_strikes:
        call_loss = ((s - calls['strike']) * calls['openInterest'] * 100).clip(lower=0).sum()
        put_loss  = ((puts['strike'] - s)  * puts['openInterest']  * 100).clip(lower=0).sum()
        total     = call_loss + put_loss
        if total < min_pain:
            min_pain          = total
            max_pain_strike   = s
    return max_pain_strike

def calc_iv_skew(calls, puts, price):
    # ATM = closest strike to current price
    atm = min(calls['strike'].tolist(), key=lambda x: abs(x - price))

    call_iv = calls[calls['strike'] == atm]['impliedVolatility'].values
    put_iv  = puts[puts['strike']  == atm]['impliedVolatility'].values

    if len(call_iv) == 0 or len(put_iv) == 0:
        return None, None, None

    skew = round((put_iv[0] - call_iv[0]) * 100, 2)
    return round(call_iv[0] * 100, 2), round(put_iv[0] * 100, 2), skew

def calc_gex(calls, puts):
    # GEX = gamma × OI × 100 × spot² × 0.01
    # Positive GEX = dealer long gamma = suppresses volatility
    # Negative GEX = dealer short gamma = amplifies volatility
    call_gex = (calls['gamma'] * calls['openInterest'] * 100).fillna(0)
    put_gex  = (puts['gamma']  * puts['openInterest']  * 100 * -1).fillna(0)

    calls = calls.copy()
    puts  = puts.copy()
    calls['gex'] = call_gex
    puts['gex']  = put_gex

    # Find highest positive and negative GEX strikes
    all_gex = {}
    for _, row in calls.iterrows():
        all_gex[row['strike']] = all_gex.get(row['strike'], 0) + row['gex']
    for _, row in puts.iterrows():
        all_gex[row['strike']] = all_gex.get(row['strike'], 0) + row['gex']

    sorted_gex    = sorted(all_gex.items(), key=lambda x: x[1], reverse=True)
    top_pos_gex   = sorted_gex[0]   if sorted_gex else None
    top_neg_gex   = sorted_gex[-1]  if sorted_gex else None

    return all_gex, top_pos_gex, top_neg_gex

# ── Analyze ───────────────────────────────────
if st.button("🔥 ANALYZE OPTIONS", type="primary", use_container_width=True):
    with st.spinner("Fetching options chain..."):
        try:
            ticker   = yf.Ticker(symbol)
            expiries = ticker.options
            if not expiries:
                st.error("No options data found.")
                st.stop()

            expiry = expiries[0]
            chain  = ticker.option_chain(expiry)
            calls  = chain.calls
            puts   = chain.puts

            info  = ticker.fast_info
            price = round(info.last_price, 2)

        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    # Filter ±20% of current price
    lower = price * 0.80
    upper = price * 1.20
    calls_f = calls[(calls['strike'] >= lower) & (calls['strike'] <= upper)].copy()
    puts_f  = puts[(puts['strike']  >= lower) & (puts['strike']  <= upper)].copy()

    if calls_f.empty or puts_f.empty:
        st.error("No contracts found within ±20% of current price.")
        st.stop()

    # ── Core calculations ─────────────────────
    call_row    = calls_f.loc[calls_f['openInterest'].idxmax()]
    put_row     = puts_f.loc[puts_f['openInterest'].idxmax()]
    call_strike = call_row['strike']
    put_strike  = put_row['strike']
    call_oi     = int(call_row['openInterest'])
    put_oi      = int(put_row['openInterest'])
    mid         = round((call_strike + put_strike) / 2, 2)

    max_pain                    = calc_max_pain(calls_f, puts_f)
    call_iv, put_iv, iv_skew    = calc_iv_skew(calls_f, puts_f, price)
    all_gex, top_pos, top_neg   = calc_gex(calls_f, puts_f)

    # ── Row 1: Core metrics ───────────────────
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Current Price",      f"${price}")
    c2.metric("📈 Max Call OI Strike", f"${call_strike}", f"{call_oi:,} contracts")
    c3.metric("📉 Max Put OI Strike",  f"${put_strike}",  f"{put_oi:,} contracts")
    c4.metric("⚖️ Midpoint",           f"${mid}")

    # ── Row 2: Max Pain + IV Skew + GEX ──────
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("🎯 Max Pain",  f"${max_pain}",
              f"{'▼' if max_pain < price else '▲'} {abs(round(max_pain - price, 2))} from price")

    if iv_skew is not None:
        skew_label = "⚠️ Puts expensive — hedging" if iv_skew > 3 else ("✅ Balanced" if abs(iv_skew) <= 3 else "Calls expensive")
        c6.metric("📐 IV Skew (Put-Call)", f"{iv_skew}%", skew_label)
        c7.metric("📊 ATM Call IV / Put IV", f"{call_iv}% / {put_iv}%")

    if top_pos and top_neg:
        c8.metric("⚡ GEX Wall",
                  f"${top_pos[0]} (+) / ${top_neg[0]} (-)",
                  "Positive = magnet | Negative = accelerator")

    # ── Bias ─────────────────────────────────
    st.divider()
    bias_signals = []
    if price > mid:               bias_signals.append(1)
    else:                         bias_signals.append(-1)
    if max_pain > price:          bias_signals.append(1)
    else:                         bias_signals.append(-1)
    if iv_skew is not None:
        if iv_skew > 3:           bias_signals.append(-1)
        elif iv_skew < -3:        bias_signals.append(1)
    if top_pos and top_pos[0] > price: bias_signals.append(1)
    else:                         bias_signals.append(-1)

    score = sum(bias_signals)
    if score >= 2:
        st.success(f"📈 BULLISH — {score}/{len(bias_signals)} signals aligned | Target: ${call_strike} | Max Pain pull: ${max_pain}")
    elif score <= -2:
        st.error(f"📉 BEARISH — {abs(score)}/{len(bias_signals)} signals aligned | Target: ${put_strike} | Max Pain pull: ${max_pain}")
    else:
        st.info(f"⚖️ NEUTRAL — Mixed signals | Max Pain: ${max_pain} | Watch GEX wall at ${top_pos[0] if top_pos else 'N/A'}")

    st.divider()

    # ── Chart 1: OI Distribution ──────────────
    st.subheader(f"Open Interest by Strike — Expiry: {expiry}")
    fig1 = go.Figure()

    fig1.add_trace(go.Bar(x=calls_f['strike'], y=calls_f['openInterest'],
        name='Calls', marker_color='#26a69a', opacity=0.8))
    fig1.add_trace(go.Bar(x=puts_f['strike'],  y=puts_f['openInterest'],
        name='Puts',  marker_color='#ef5350',  opacity=0.8))

    for level, color, label in [
        (call_strike, '#26a69a', f"Max Call OI ${call_strike}"),
        (put_strike,  '#ef5350', f"Max Put OI ${put_strike}"),
        (max_pain,    '#ffeb3b', f"Max Pain ${max_pain}"),
        (price,       '#ffffff', f"Price ${price}"),
    ]:
        fig1.add_vline(x=level, line=dict(color=color, width=1.5, dash='dash'),
            annotation_text=label, annotation_font_size=10)

    fig1.update_layout(template="plotly_dark", height=400,
        xaxis_title="Strike", yaxis_title="Open Interest",
        barmode='overlay', margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig1, use_container_width=True)

    # ── Chart 2: GEX by Strike ────────────────
    if all_gex:
        st.subheader("Gamma Exposure (GEX) by Strike")
        gex_strikes = sorted(all_gex.keys())
        gex_vals    = [all_gex[s] for s in gex_strikes]
        colors      = ['#26a69a' if v >= 0 else '#ef5350' for v in gex_vals]

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=gex_strikes, y=gex_vals,
            marker_color=colors, name='GEX'))
        fig2.add_vline(x=price, line=dict(color='white', width=1.5, dash='dot'),
            annotation_text=f"Price ${price}", annotation_font_size=10)
        fig2.add_hline(y=0, line=dict(color='gray', width=1))
        fig2.update_layout(template="plotly_dark", height=350,
            xaxis_title="Strike", yaxis_title="GEX",
            margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    st.caption(f"Expiry: {expiry} | Updated: {datetime.now().strftime('%H:%M:%S')}")
