import os, requests, time
from concurrent.futures import ThreadPoolExecutor
from analysis import get_full_analysis, SYMBOLS
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alert(symbol: str, analysis: dict):
    if analysis["confidence"] < 72: return
    emoji = "🟢⚡" if analysis["bias"] == "bullish" else "🔴⚡"
    msg = f"""
🚨 <b>QUANTUM 4H SIGNAL</b> {emoji}
<b>{symbol}</b> • Q-Score: <b>{analysis.get('quantum_score',0)}</b>
Bias: <b>{analysis['bias'].upper()}</b> | Confidence <b>{analysis['confidence']}%</b>
{analysis['reason']}
Price: <code>{analysis['current_price']}</code>
Target: <code>{analysis['target']}</code>
SL: <code>{analysis['sl']}</code>
Chart → https://app.hyperliquid.xyz/trade/{symbol}
    """.strip()
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
    print(f"✅ Alert sent → {symbol}")

if __name__ == "__main__":
    print(f"⚡ Quantum scan started @ {datetime.now()}")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda s: (s, get_full_analysis(s)), SYMBOLS))
    for sym, res in results:
        if res: send_alert(sym, res)
    print("✅ Scan complete")
