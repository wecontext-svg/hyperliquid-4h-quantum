import pandas as pd
import numpy as np
import time
import json
from pathlib import Path
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants

SYMBOLS = [
    "xyz:SP500", "xyz:MU", "xyz:SNDK", "xyz:NVDA", "xyz:INTC",
    "xyz:GOOGL", "xyz:AMD", "xyz:AAPL", "xyz:AMZN", "xyz:ORCL",
    "xyz:HOOD", "xyz:MSFT", "xyz:PLTR", "xyz:EWY"
]

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 720

def _get_cache_file(symbol: str) -> Path:
    safe_name = symbol.replace(":", "_").replace("/", "_")
    return CACHE_DIR / f"{safe_name}_4h.json"

def fetch_candles(symbol: str, num_candles: int = 180) -> pd.DataFrame:
    cache_file = _get_cache_file(symbol)
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cached = json.load(f)
            if time.time() - cached["timestamp"] < CACHE_TTL:
                return pd.DataFrame(cached["data"])
        except:
            pass  # ignore bad cache

    try:
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        end_time = int(time.time() * 1000)
        interval_ms = 4 * 60 * 60 * 1000
        start_time = end_time - (num_candles + 50) * interval_ms

        raw = info.candles_snapshot(
            name=symbol,
            interval="4h",
            startTime=start_time,
            endTime=end_time
        )

        if not raw or len(raw) == 0:
            raise Exception(f"Hyperliquid returned ZERO candles for {symbol}. This symbol may have no 4H history yet.")

        df = pd.DataFrame([{
            'timestamp': pd.to_datetime(c['t'], unit='ms'),
            'open': float(c['o']), 'high': float(c['h']),
            'low': float(c['l']), 'close': float(c['c']),
            'volume': float(c.get('v', 0))
        } for c in raw])

        df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)
        df = df.tail(num_candles).reset_index(drop=True)

        with open(cache_file, "w") as f:
            json.dump({"timestamp": time.time(), "data": df.to_dict(orient="records")}, f)

        return df

    except Exception as e:
        error_msg = str(e)
        print(f"❌ DEBUG ERROR for {symbol}: {error_msg}")
        df = pd.DataFrame()
        df.attrs['error'] = error_msg
        return df

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 60: return df
    df = df.copy()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    tr = pd.concat([df['high']-df['low'], (df['high']-df['close'].shift()).abs(), (df['low']-df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    return df

def detect_swings(df: pd.DataFrame, strength: int = 5):
    highs, lows = [], []
    for i in range(strength, len(df) - strength):
        if df['high'].iloc[i] == df['high'].iloc[i-strength:i+strength+1].max():
            highs.append({'time': df['timestamp'].iloc[i], 'price': float(df['high'].iloc[i])})
        if df['low'].iloc[i] == df['low'].iloc[i-strength:i+strength+1].min():
            lows.append({'time': df['timestamp'].iloc[i], 'price': float(df['low'].iloc[i])})
    return highs[-8:], lows[-8:]

def quantum_weighted_confluence(df: pd.DataFrame) -> dict:
    if len(df) < 60 or df.empty:
        error = df.attrs.get('error', 'No candles returned') if hasattr(df, 'attrs') else "Insufficient data"
        return {"bias": "neutral", "confidence": 0, "reason": f"ERROR: {error}", "target": None, "sl": None}
    # ... (quantum logic unchanged)
    df = add_indicators(df)
    current_price = float(df['close'].iloc[-1])
    ema50 = float(df['ema50'].iloc[-1])
    atr = float(df['atr'].iloc[-1]) if not pd.isna(df['atr'].iloc[-1]) else 1.0
    swing_highs, swing_lows = detect_swings(df)
    sell_liq = [h['price'] for h in swing_highs if h['price'] > current_price][-3:] or [current_price * 1.02]
    buy_liq = [l['price'] for l in swing_lows if l['price'] < current_price][-3:] or [current_price * 0.98]
    recent = df.tail(8).reset_index(drop=True)
    hh, hl = recent['high'].iloc[-1] > recent['high'].iloc[-2], recent['low'].iloc[-1] > recent['low'].iloc[-2]
    lh, ll = recent['high'].iloc[-1] < recent['high'].iloc[-2], recent['low'].iloc[-1] < recent['low'].iloc[-2]
    last, prev = df.iloc[-1], df.iloc[-2]
    body = abs(last['close'] - last['open'])
    pinbar_bull = (last['low'] - min(last['open'], last['close'])) > 2 * body and last['close'] > last['open']
    pinbar_bear = (max(last['open'], last['close']) - last['high']) > 2 * body and last['close'] < last['open']
    engulf_bull = last['close'] > prev['high'] and last['open'] < prev['close']
    engulf_bear = last['close'] < prev['low'] and last['open'] > prev['close']
    factors = {
        "structure": 90 if (hh and hl) else 10 if (lh and ll) else 50,
        "liquidity": 95 if (last['low'] < buy_liq[0] and last['close'] > buy_liq[0]) else 95 if (last['high'] > sell_liq[0] and last['close'] < sell_liq[0]) else 40,
        "ema": 85 if current_price > ema50 else 15,
        "pattern": 90 if (pinbar_bull or engulf_bull) else 90 if (pinbar_bear or engulf_bear) else 45,
        "volatility": min(100, int(atr / current_price * 10000))
    }
    weights = np.array([0.40, 0.30, 0.15, 0.10, 0.05])
    amplitudes = np.sqrt(np.array(list(factors.values())) / 100.0)
    raw_score = np.dot(amplitudes**2, weights) * 100
    entanglement = 1.25 if sum(1 for v in factors.values() if v > 80) >= 3 else 1.0
    quantum_score = int(raw_score * entanglement)
    bias = "bullish" if quantum_score > 65 else "bearish" if quantum_score < 35 else "neutral"
    confidence = max(40, min(98, quantum_score))
    if bias == "bullish":
        target = current_price + 3 * atr
        sl = min(buy_liq) - 0.5 * atr
    elif bias == "bearish":
        target = current_price - 3 * atr
        sl = max(sell_liq) + 0.5 * atr
    else:
        target = sl = current_price
    reasons = [f"{k.capitalize()}:{v}" for k, v in factors.items() if v > 60][:4]
    reason_str = " | ".join(reasons) + f" | Entangle×{entanglement:.2f}"
    return {
        "bias": bias, "confidence": confidence, "reason": reason_str,
        "target": round(target, 2), "sl": round(sl, 2),
        "current_price": round(current_price, 2), "ema50": round(ema50, 2),
        "buy_liquidity": [round(x, 2) for x in buy_liq],
        "sell_liquidity": [round(x, 2) for x in sell_liq],
        "quantum_score": quantum_score
    }

def get_full_analysis(symbol: str):
    df = fetch_candles(symbol)
    if df.empty:
        return None
    analysis = quantum_weighted_confluence(df)
    analysis["symbol"] = symbol
    analysis["df"] = df
    return analysis
