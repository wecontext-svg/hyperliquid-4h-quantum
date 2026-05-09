import pandas as pd
import numpy as np
import requests
import time

SYMBOLS = [
    'xyz:SP500', 'xyz:MU', 'xyz:SNDK', 'xyz:NVDA', 'xyz:INTC',
    'xyz:GOOGL', 'xyz:AMD', 'xyz:AAPL', 'xyz:AMZN', 'xyz:ORCL',
    'xyz:HOOD', 'xyz:MSFT', 'xyz:PLTR', 'xyz:EWY'
]

INTERVAL_MS = {'4h': 14_400_000, '1d': 86_400_000}

# ─────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────

def fetch_candles(symbol, interval='4h', limit=180):
    coin = symbol.replace('xyz:', '')
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - limit * INTERVAL_MS.get(interval, 14_400_000)
    try:
        resp = requests.post(
            'https://api.hyperliquid.xyz/info',
            json={'type': 'candleSnapshot', 'req': {
                'coin': coin, 'interval': interval,
                'startTime': start_ms, 'endTime': end_ms
            }},
            timeout=10
        )
        data = resp.json()
        if not data:
            return pd.DataFrame()
        rows = [{
            'time':   pd.to_datetime(c['t'], unit='ms'),
            'open':   float(c['o']),
            'high':   float(c['h']),
            'low':    float(c['l']),
            'close':  float(c['c']),
            'volume': float(c.get('v', 0))
        } for c in data]
        df = pd.DataFrame(rows).sort_values('time').reset_index(drop=True)
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['atr']   = _atr(df)
        return df
    except Exception as e:
        print(f"fetch_candles error: {e}")
        return pd.DataFrame()


def _atr(df, period=14):
    h, l, pc = df['high'], df['low'], df['close'].shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ─────────────────────────────────────────────
# SWING DETECTION
# ─────────────────────────────────────────────

def detect_swings(df, strength=5):
    highs, lows = [], []
    for i in range(strength, len(df) - strength):
        w_h = df['high'].iloc[i - strength:i + strength + 1]
        w_l = df['low'].iloc[i  - strength:i + strength + 1]
        if df['high'].iloc[i] >= w_h.max():
            highs.append({'index': i, 'price': df['high'].iloc[i], 'time': df['time'].iloc[i]})
        if df['low'].iloc[i] <= w_l.min():
            lows.append({'index': i, 'price': df['low'].iloc[i],  'time': df['time'].iloc[i]})
    return highs, lows

# ─────────────────────────────────────────────
# FACTOR 1 — STRUCTURE  (25%)
# ─────────────────────────────────────────────

def score_structure(df, swing_highs, swing_lows):
    last = df.iloc[-1]
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 50, 'Neutral'

    last_sh, prev_sh = swing_highs[-1]['price'], swing_highs[-2]['price']
    last_sl, prev_sl = swing_lows[-1]['price'],  swing_lows[-2]['price']

    hh = last_sh > prev_sh
    hl = last_sl > prev_sl
    lh = last_sh < prev_sh
    ll = last_sl < prev_sl

    if last['close'] > last_sh:  return 90, 'Bullish BOS'
    if last['close'] < last_sl:  return 10, 'Bearish BOS'
    if lh and hl:                return 75, 'Bullish CHOCH'
    if hh and ll:                return 25, 'Bearish CHOCH'
    if hh and hl:                return 65, 'Bullish Trend'
    if lh and ll:                return 35, 'Bearish Trend'
    return 50, 'Neutral'

# ─────────────────────────────────────────────
# FACTOR 2 — ORDER BLOCK  (20%)
# ─────────────────────────────────────────────

def score_order_block(df, struct_tag, atr):
    if not any(x in struct_tag for x in ['BOS', 'CHOCH', 'Trend']):
        return 10, None

    bullish = 'Bullish' in struct_tag
    ob_zone, ob_idx = None, 0

    for i in range(len(df) - 2, max(len(df) - 40, 0), -1):
        c = df.iloc[i]
        is_bear = c['close'] < c['open']
        is_bull = c['close'] > c['open']
        if (bullish and is_bear) or (not bullish and is_bull):
            ob_zone = {'top': max(c['open'], c['close']), 'bottom': min(c['open'], c['close'])}
            ob_idx  = i
            break

    if ob_zone is None:
        return 10, None

    current      = df.iloc[-1]['close']
    candles_ago  = len(df) - 1 - ob_idx

    if ob_zone['bottom'] <= current <= ob_zone['top']:
        score = 95
    elif ob_zone['bottom'] - 0.5*atr <= current <= ob_zone['top'] + 0.5*atr:
        score = 75
    else:
        score = 20

    if   candles_ago > 40: score = int(score * 0.50)
    elif candles_ago > 20: score = int(score * 0.75)

    return score, ob_zone

# ─────────────────────────────────────────────
# FACTOR 3 — LIQUIDITY  (20%)
# ─────────────────────────────────────────────

def score_liquidity(df, swing_highs, swing_lows, atr):
    last    = df.iloc[-1]
    current = last['close']

    buy_liq  = [l['price'] for l in swing_lows  if l['price'] < current]
    sell_liq = [h['price'] for h in swing_highs if h['price'] > current]

    bull_raid = bool(buy_liq  and last['low']  < buy_liq[-1]  and last['close'] > buy_liq[-1])
    bear_raid = bool(sell_liq and last['high'] > sell_liq[0]  and last['close'] < sell_liq[0])

    if not bull_raid and not bear_raid:
        return 20, None

    raid_level = buy_liq[-1] if bull_raid else sell_liq[0]

    # A: level significance
    all_prices = sorted(set([s['price'] for s in swing_highs + swing_lows]))
    idx = next((i for i, p in enumerate(all_prices) if p == raid_level), -1)
    neighbors = []
    if idx > 0:               neighbors.append(abs(raid_level - all_prices[idx-1]))
    if idx < len(all_prices)-1: neighbors.append(abs(raid_level - all_prices[idx+1]))
    avg_dist = np.mean(neighbors) if neighbors else atr
    score_a = 90 if avg_dist > 1.5 * atr else 55

    # B: wick quality
    body_bot = min(last['open'], last['close'])
    body_top = max(last['open'], last['close'])
    if bull_raid:
        wick_size  = body_bot - last['low']
        fully_back = last['close'] > raid_level
    else:
        wick_size  = last['high'] - body_top
        fully_back = last['close'] < raid_level

    if fully_back and wick_size > 0.3 * atr: score_b = 95
    elif fully_back:                          score_b = 65
    else:                                     score_b = 25

    # C: multi-level sweep
    swept = sum(1 for p in (buy_liq if bull_raid else sell_liq)
                if (last['low'] < p if bull_raid else last['high'] > p))
    score_c = 90 if swept >= 2 else 60

    return int(score_a*0.4 + score_b*0.4 + score_c*0.2), raid_level

# ─────────────────────────────────────────────
# FACTOR 4 — FAIR VALUE GAP  (15%)
# ─────────────────────────────────────────────

def score_fvg(df, struct_tag, atr):
    bullish = 'Bullish' in struct_tag
    fvgs    = []

    for i in range(2, len(df) - 1):
        c0, c2 = df.iloc[i-2], df.iloc[i]
        if bullish and c0['high'] < c2['low']:
            gap = {'top': c2['low'], 'bottom': c0['high'], 'index': i}
            mid = (gap['top'] + gap['bottom']) / 2
            later = df.iloc[i+1:]
            if not (not later.empty and (later['low'] <= mid).any()):
                fvgs.append(gap)
        elif not bullish and c0['low'] > c2['high']:
            gap = {'top': c0['low'], 'bottom': c2['high'], 'index': i}
            mid = (gap['top'] + gap['bottom']) / 2
            later = df.iloc[i+1:]
            if not (not later.empty and (later['high'] >= mid).any()):
                fvgs.append(gap)

    if not fvgs:
        return 10, None

    fvg       = fvgs[-1]
    current   = df.iloc[-1]['close']
    gap_size  = fvg['top'] - fvg['bottom']
    candles_ago = len(df) - 1 - fvg['index']

    if fvg['bottom'] <= current <= fvg['top']:
        score = 95
    elif (abs(current - fvg['bottom']) < 0.5*atr or
          abs(current - fvg['top'])    < 0.5*atr):
        score = 75
    else:
        score = 50

    if gap_size > atr:        score = min(100, score + 10)
    elif gap_size < 0.3*atr:  score = max(0,   score - 10)
    if candles_ago <= 5:      score = min(100, score + 10)

    return score, fvg

# ─────────────────────────────────────────────
# FACTOR 5 — DISPLACEMENT  (10%)
# ─────────────────────────────────────────────

def score_displacement(df, raid_level, atr, bullish):
    if raid_level is None or atr <= 0:
        return 10

    last = df.iloc[-1]
    body = abs(last['close'] - last['open'])
    ratio = body / atr
    rng   = last['high'] - last['low']

    correct_dir = (bullish and last['close'] > last['open']) or \
                  (not bullish and last['close'] < last['open'])
    if not correct_dir:
        return 10

    close_pos = ((last['close'] - last['low']) / rng if bullish
                 else (last['high'] - last['close']) / rng) if rng > 0 else 0

    if ratio > 1.5 and close_pos > 0.75: return 95
    if ratio > 1.0:                       return 75
    if ratio > 0.5:                       return 50
    return 20

# ─────────────────────────────────────────────
# FACTOR 6 — EMA INTERACTION  (7%)
# ─────────────────────────────────────────────

def score_ema(df):
    if 'ema50' not in df.columns or len(df) < 2:
        return 50
    last, prev = df.iloc[-1], df.iloc[-2]
    ema     = last['ema50']
    price   = last['close']
    atr     = last['atr'] if 'atr' in df.columns else (last['high'] - last['low'])

    bounced   = prev['low']   <= ema * 1.003 and price > ema * 1.005
    reclaimed = prev['close'] < prev['ema50'] and price > ema

    if bounced:   return 95
    if reclaimed: return 80
    if price > ema: return 70 if abs(price-ema)/ema*100 < 1 else 65
    return 30 if abs(price-ema)/ema*100 < 1 else 20

# ─────────────────────────────────────────────
# FACTOR 7 — VOLUME  (3%)
# ─────────────────────────────────────────────

def score_volume(df, raid_level):
    if raid_level is None or len(df) < 22:
        return 50
    avg      = df['volume'].iloc[-20:].mean()
    disp_vol = df.iloc[-1]['volume']
    raid_vol = df.iloc[-2]['volume']

    if raid_vol > 1.5*avg and disp_vol > 1.5*avg: return 95
    if disp_vol > 1.5*avg:                         return 75
    if raid_vol > avg and disp_vol > avg:          return 60
    if disp_vol > avg:                             return 50
    return 25

# ─────────────────────────────────────────────
# PREMIUM / DISCOUNT MODIFIER
# ─────────────────────────────────────────────

def calc_premium_discount(df, bias):
    hi  = df['high'].iloc[-20:].max()
    lo  = df['low'].iloc[-20:].min()
    cur = df.iloc[-1]['close']
    rng = hi - lo
    if rng == 0:
        return 50, f"50% — Fair Value"

    pos = int((cur - lo) / rng * 100)

    if bias == 'bullish':
        if pos < 35:   label = f"{pos}% — Buying Cheap ✅"
        elif pos > 65: label = f"{pos}% — Buying Expensive ⚠️"
        else:          label = f"{pos}% — Buying Fair Value"
    else:
        if pos > 65:   label = f"{pos}% — Selling Expensive ✅"
        elif pos < 35: label = f"{pos}% — Selling Cheap ⚠️"
        else:          label = f"{pos}% — Selling Fair Value"

    return pos, label

# ─────────────────────────────────────────────
# HTF DAILY GATE
# ─────────────────────────────────────────────

def htf_aligned(symbol, bias):
    df_d = fetch_candles(symbol, interval='1d', limit=30)
    if df_d.empty or len(df_d) < 3:
        return True
    last, prev = df_d.iloc[-1], df_d.iloc[-2]
    daily_bull = last['close'] > prev['high']
    daily_bear = last['close'] < prev['low']
    if bias == 'bullish' and daily_bear: return False
    if bias == 'bearish' and daily_bull: return False
    return True

# ─────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────

def quantum_weighted_confluence(df, symbol):
    atr     = df['atr'].iloc[-1]
    atr     = atr if not pd.isna(atr) else (df['high'].iloc[-1] - df['low'].iloc[-1])
    current = df.iloc[-1]['close']

    swing_highs, swing_lows = detect_swings(df, strength=5)

    # ── Factor scores ──────────────────────────
    struct_score, struct_tag = score_structure(df, swing_highs, swing_lows)
    ob_score,    ob_zone     = score_order_block(df, struct_tag, atr)
    liq_score,   raid_level  = score_liquidity(df, swing_highs, swing_lows, atr)
    fvg_score,   fvg_data    = score_fvg(df, struct_tag, atr)
    
    bullish   = struct_score >= 50
    disp_score = score_displacement(df, raid_level, atr, bullish)
    ema_score  = score_ema(df)
    vol_score  = score_volume(df, raid_level)

    # ── HTF penalty applied to structure ───────
    bias_prelim = 'bullish' if bullish else 'bearish'
    aligned     = htf_aligned(symbol, bias_prelim)
    if not aligned:
        struct_score = int(struct_score * 0.65)

    # ── Weighted score (linear — no square root) ─
    raw = (struct_score * 0.25 +
           ob_score     * 0.20 +
           liq_score    * 0.20 +
           fvg_score    * 0.15 +
           disp_score   * 0.10 +
           ema_score    * 0.07 +
           vol_score    * 0.03)

    # ── Entanglement multiplier ─────────────────
    scores       = [struct_score, ob_score, liq_score, fvg_score, disp_score, ema_score, vol_score]
    strong_count = sum(1 for s in scores if s > 75)
    has_bos      = any(x in struct_tag for x in ['BOS', 'CHOCH'])

    if disp_score < 40:
        multiplier = 0.90
    elif strong_count >= 5:
        multiplier = 1.35
    elif strong_count >= 3 and has_bos:
        multiplier = 1.25
    else:
        multiplier = 1.00

    quantum_score = min(100, raw * multiplier)

    # ── Premium / Discount modifier ─────────────
    bias_prelim  = 'bullish' if quantum_score >= 50 else 'bearish'
    pd_pos, pd_label = calc_premium_discount(df, bias_prelim)

    if bias_prelim == 'bullish':
        if pd_pos < 35:   quantum_score = min(100, quantum_score * 1.10)
        elif pd_pos > 65: quantum_score *= 0.80
    else:
        if pd_pos > 65:   quantum_score = min(100, quantum_score * 1.10)
        elif pd_pos < 35: quantum_score *= 0.80

    quantum_score = round(quantum_score, 1)

    # ── Final bias ──────────────────────────────
    if quantum_score > 65:   bias_str = 'bullish'
    elif quantum_score < 35: bias_str = 'bearish'
    else:                    bias_str = 'neutral'

    # ── OTE flag ────────────────────────────────
    price_ok = (pd_pos < 40) if bias_str == 'bullish' else (pd_pos > 60)
    ote_flag = (ob_score >= 75 and fvg_score >= 75 and
                liq_score >= 60 and has_bos and price_ok)

    # ── SL & Target ─────────────────────────────
    raid_candle = df.iloc[-2] if raid_level is not None else df.iloc[-1]
    sell_above  = [h['price'] for h in swing_highs if h['price'] > current]
    buy_below   = [l['price'] for l in swing_lows  if l['price'] < current]

    if bias_str == 'bullish':
        sl          = round(raid_candle['low']  - 0.1 * atr, 4)
        min_target  = round(current + (current - sl) * 2, 4)
        valid       = [p for p in sell_above if p >= min_target]
        target      = round(valid[0] if valid else min_target, 4)
    else:
        sl          = round(raid_candle['high'] + 0.1 * atr, 4)
        min_target  = round(current - (sl - current) * 2, 4)
        valid       = [p for p in buy_below if p <= min_target]
        target      = round(valid[-1] if valid else min_target, 4)

    risk   = abs(current - sl)
    reward = abs(target  - current)
    rr     = round(reward / risk, 2) if risk > 0 else 0

    # ── Reason string ───────────────────────────
    named = [('Structure', struct_score), ('OB', ob_score), ('Liquidity', liq_score),
             ('FVG', fvg_score), ('Displacement', disp_score), ('EMA', ema_score)]
    top4  = sorted(named, key=lambda x: x[1], reverse=True)[:4]
    reason = ' | '.join(f"{n}:{s}" for n, s in top4)
    if multiplier != 1.0:
        reason += f' | Entangle×{multiplier}'

    fvg_zone = ({'top': fvg_data['top'], 'bottom': fvg_data['bottom']}
                if fvg_data else None)

    return {
        'df':                   df,
        'bias':                 bias_str,
        'confidence':           quantum_score,
        'score':                quantum_score,
        'structure':            struct_score,
        'structure_tag':        struct_tag,
        'liquidity':            liq_score,
        'order_block':          ob_score,
        'order_block_zone':     ob_zone,
        'fvg':                  fvg_score,
        'fvg_zone':             fvg_zone,
        'displacement':         disp_score,
        'ema':                  ema_score,
        'volume':               vol_score,
        'entanglement_multiplier': multiplier,
        'ote_flag':             ote_flag,
        'hte_aligned':          aligned,
        'premium_discount':     pd_label,
        'current_price':        round(current, 4),
        'target':               target,
        'sl':                   sl,
        'rr':                   rr,
        'reason':               reason,
        'raid_candle_low':      round(raid_candle['low'], 4),
        'swing_highs':          swing_highs,
        'swing_lows':           swing_lows,
    }


def get_full_analysis(symbol):
    df = fetch_candles(symbol, interval='4h', limit=180)
    if df.empty:
        return {'df': None, 'error': 'No data fetched'}
    return quantum_weighted_confluence(df, symbol)
