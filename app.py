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
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - 180 * 14_400_000

    tests = [
        {"label": "NVDA 4h",  "coin": "NVDA",     "interval": "4h"},
        {"label": "BTC 4h",   "coin": "BTC",       "interval": "4h"},
        {"label": "NVDA 4H",  "coin": "NVDA",      "interval": "4H"},
        {"label": "kNVDA 4h", "coin": "kNVDA",     "interval": "4h"},
    ]

    for t in tests:
        try:
            resp = requests.post(
                'https://api.hyperliquid.xyz/info',
                json={'type': 'candleSnapshot', 'req': {
                    'coin': t['coin'],
                    'interval': t['interval'],
                    'startTime': start_ms,
                    'endTime': end_ms
                }},
                timeout=10
            )
            st.write(f"**{t['label']}** → Status: {resp.status_code} | Response: `{resp.text[:100]}`")
        except Exception as e:
            st.error(f"{t['label']} error: {e}")    except Exception as e:
        st.error(f"API error: {e}")
