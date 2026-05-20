import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Options Flow Analyzer", layout="wide", page_icon="📊")
st.title("📊 Weekly Options Flow Analyzer")
st.caption("Max Call / Put OI Strike Levels")

SYMBOLS = ['NVDA', 'INTC', 'AMD', 'AAPL', 'AMZN', 'GOOGL', 'MSFT', 'PLTR', 'HOOD', 'ORCL', 'MU', 'SNDK']

# ── Sidebar ───────────────────────────────────
st.sidebar.header("Symbol")
selected = st.sidebar.selectbox("Select symbol", SYMBOLS)
custom   = st.sidebar.text_input("Or enter custom ticker (e.g. TSLA)", "")
symbol   = custom.strip().upper() if custom.strip() else selected

# ── Fetch Options Chain ───────────────────────
def get_weekly_expiry():
    today      = datetime.utcnow()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

def fetch_options(ticker, contract_type, expiry, api_key):
    url    = f"https://api.massive.com/v1/snapshot/options/{ticker}/chain"
    params = {'expiration_date': expiry, 'contract_type': contract_type, 'limit': 250}
    headers = {'Authorization': f'Bearer {api_key}'}
    resp   = requests.get(url, params=params, headers=headers, timeout=10)
    return resp.json().get('results', [])

def find_max_oi(contracts):
    if not contracts:
        return None, None
    best = max(contracts, key=lambda x: x.get('open_interest', 0))
    strike = best.get('details', {}).get('strike_price')
    oi     = best.get('open_interest', 0)
    return strike, oi

# ── Analyze ───────────────────────────────────
if st.button("🔥 ANALYZE OPTIONS", type="primary", use_container_width=True):
    api_key = st.secrets.get("MASSIVE_API_KEY", "")
    if not api_key:
        st.error("MASSIVE_API_KEY not found in Streamlit secrets.")
        st.stop()

    expiry = get_weekly_expiry()
    st.caption(f"Weekly expiry: {expiry}")

    with st.spinner("Fetching options chain..."):
        try:
            calls = fetch_options(symbol, 'call', expiry, api_key)
            puts  = fetch_options(symbol, 'put',  expiry, api_key)
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    if not calls and not puts:
        st.error("No options data returned. Check ticker or API key.")
        st.stop()

    call_strike, call_oi = find_max_oi(calls)
    put_strike,  put_oi  = find_max_oi(puts)

    # ── Metrics ───────────────────────────────
    st.divider()
    col1, col2, col3 = st.columns(3)

    col1.metric("📈 Max Call OI Strike", f"${call_strike}" if call_strike else "N/A", f"{call_oi:,} contracts" if call_oi else "")
    col2.metric("📉 Max Put OI Strike",  f"${put_strike}"  if put_strike  else "N/A", f"{put_oi:,} contracts"  if put_oi  else "")
    if call_strike and put_strike:
        mid = round((call_strike + put_strike) / 2, 2)
        col3.metric("⚖️ Midpoint", f"${mid}", "Expected range center")

    st.divider()

    # ── OI Bar Chart ──────────────────────────
    st.subheader("Open Interest by Strike")

    all_contracts = []
    for c in calls:
        strike = c.get('details', {}).get('strike_price')
        oi     = c.get('open_interest', 0)
        if strike and oi:
            all_contracts.append({'strike': strike, 'oi': oi, 'type': 'call'})
    for p in puts:
        strike = p.get('details', {}).get('strike_price')
        oi     = p.get('open_interest', 0)
        if strike and oi:
            all_contracts.append({'strike': strike, 'oi': oi, 'type': 'put'})

    if all_contracts:
        call_data = sorted([x for x in all_contracts if x['type'] == 'call'], key=lambda x: x['strike'])
        put_data  = sorted([x for x in all_contracts if x['type'] == 'put'],  key=lambda x: x['strike'])

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=[x['strike'] for x in call_data],
            y=[x['oi']     for x in call_data],
            name='Calls', marker_color='#26a69a', opacity=0.8
        ))

        fig.add_trace(go.Bar(
            x=[x['strike'] for x in put_data],
            y=[x['oi']     for x in put_data],
            name='Puts', marker_color='#ef5350', opacity=0.8
        ))

        if call_strike:
            fig.add_vline(x=call_strike,
                line=dict(color='#26a69a', width=2, dash='dash'),
                annotation_text=f"Max Call OI ${call_strike}",
                annotation_font_size=11)

        if put_strike:
            fig.add_vline(x=put_strike,
                line=dict(color='#ef5350', width=2, dash='dash'),
                annotation_text=f"Max Put OI ${put_strike}",
                annotation_font_size=11)

        fig.update_layout(
            template="plotly_dark",
            height=500,
            xaxis_title="Strike Price",
            yaxis_title="Open Interest",
            barmode='overlay',
            margin=dict(l=0, r=0, t=30, b=0)
        )

        st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Expiry: {expiry}")
