import streamlit as st
import requests
import time
from analysis import SYMBOLS

st.set_page_config(page_title="Hyperliquid Quantum V2", layout="wide", page_icon="⚡")
st.title("⚡ Debug — API Test")

st.sidebar.header("Symbol")
default_idx = SYMBOLS.index("xyz:NVDA") if "xyz:NVDA" in SYMBOLS else 0
selected = st.sidebar.selectbox("Select symbol", SYMBOLS, index=default_idx)
custom = st.sidebar.text_input("Or enter custom symbol", "")
symbol = custom.strip() if custom.strip() else selected

if st.button("🔥 TEST API", type="primary", use_container_width=True):
    coin = symbol.replace('xyz:', '')
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - 180 * 14_400_000

    st.write("Coin:", coin)
    st.write("Start:", start_ms, "End:", end_ms)

    try:
        resp = requests.post(
            'https://api.hyperliquid.xyz/info',
            json={'type': 'candleSnapshot', 'req': {
                'coin': coin,
                'interval': '4h',
                'startTime': start_ms,
                'endTime': end_ms
            }},
            timeout=10
        )
        st.write("Status code:", resp.status_code)
        st.write("Raw response (first 500 chars):")
        st.code(resp.text[:500])
    except Exception as e:
        st.error(f"API error: {e}")
