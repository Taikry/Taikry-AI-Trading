"""
ICT / SMC (Smart Money Concepts) Analytical Engine
Institutional Price Action Analysis:
- Liquidity Sweeps (BSL / SSL)
- Fair Value Gaps (FVG) & Mitigation status
- Order Blocks (OB)
- Break of Structure (BOS) & Change of Character (CHOCH)
- Displacement Momentum
- Premium / Discount Equilibrium (50%)
- Session Context (London, New York, Asian)
"""
from typing import Dict, Any, List, Optional
import datetime
import pandas as pd
import numpy as np

def identify_swing_points(df: pd.DataFrame, left: int = 3, right: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    """
    Identifies fractal swing highs and swing lows.
    """
    if len(df) < left + right + 1:
        return {"swing_highs": [], "swing_lows": []}

    highs = []
    lows = []

    for i in range(left, len(df) - right):
        curr_h = df["high"].iloc[i]
        curr_l = df["low"].iloc[i]

        is_high = True
        for offset in range(-left, right + 1):
            if offset == 0:
                continue
            if df["high"].iloc[i + offset] >= curr_h:
                is_high = False
                break

        if is_high:
            highs.append({
                "index": i,
                "price": float(curr_h),
                "timestamp": df["timestamp"].iloc[i]
            })

        is_low = True
        for offset in range(-left, right + 1):
            if offset == 0:
                continue
            if df["low"].iloc[i + offset] <= curr_l:
                is_low = False
                break

        if is_low:
            lows.append({
                "index": i,
                "price": float(curr_l),
                "timestamp": df["timestamp"].iloc[i]
            })

    return {"swing_highs": highs, "swing_lows": lows}

def detect_fair_value_gaps(df: pd.DataFrame, lookback: int = 30) -> List[Dict[str, Any]]:
    """
    Detects 3-candle Fair Value Gaps (FVG) and verifies mitigation status.
    - Bullish FVG: high[i-2] < low[i]
    - Bearish FVG: low[i-2] > high[i]
    """
    if len(df) < 5:
        return []

    fvgs = []
    start_idx = max(2, len(df) - lookback)

    for i in range(start_idx, len(df)):
        c0_h = df["high"].iloc[i - 2]
        c0_l = df["low"].iloc[i - 2]
        c2_h = df["high"].iloc[i]
        c2_l = df["low"].iloc[i]

        # Bullish FVG (Imbalance between c0 high and c2 low)
        if c2_l > c0_h:
            gap_top = float(c2_l)
            gap_bottom = float(c0_h)
            # Check subsequent candles for mitigation
            mitigated = False
            for j in range(i + 1, len(df)):
                if df["low"].iloc[j] <= gap_top:
                    mitigated = True
                    break

            fvgs.append({
                "type": "BULLISH_FVG",
                "top": round(gap_top, 4),
                "bottom": round(gap_bottom, 4),
                "mitigated": mitigated,
                "timestamp": df["timestamp"].iloc[i - 1]
            })

        # Bearish FVG (Imbalance between c0 low and c2 high)
        elif c2_h < c0_l:
            gap_top = float(c0_l)
            gap_bottom = float(c2_h)
            mitigated = False
            for j in range(i + 1, len(df)):
                if df["high"].iloc[j] >= gap_bottom:
                    mitigated = True
                    break

            fvgs.append({
                "type": "BEARISH_FVG",
                "top": round(gap_top, 4),
                "bottom": round(gap_bottom, 4),
                "mitigated": mitigated,
                "timestamp": df["timestamp"].iloc[i - 1]
            })

    return fvgs

def detect_order_blocks(df: pd.DataFrame, lookback: int = 30) -> List[Dict[str, Any]]:
    """
    Detects valid Order Blocks preceding significant displacement:
    - Bullish OB: Last down-close candle before a sharp upward impulse.
    - Bearish OB: Last up-close candle before a sharp downward impulse.
    """
    if len(df) < 5:
        return []

    obs = []
    start_idx = max(2, len(df) - lookback)

    for i in range(start_idx, len(df) - 1):
        c_curr = df.iloc[i]
        c_next = df.iloc[i + 1]

        body_curr = abs(c_curr["close"] - c_curr["open"])
        body_next = abs(c_next["close"] - c_next["open"])

        # Bullish OB: current candle was bearish, next is aggressive bullish displacement
        if c_curr["close"] < c_curr["open"] and c_next["close"] > c_next["open"]:
            if body_next > 1.4 * body_curr and c_next["close"] > c_curr["high"]:
                obs.append({
                    "type": "BULLISH_ORDER_BLOCK",
                    "high": round(float(c_curr["high"]), 4),
                    "low": round(float(c_curr["low"]), 4),
                    "timestamp": c_curr["timestamp"]
                })

        # Bearish OB: current candle was bullish, next is aggressive bearish displacement
        elif c_curr["close"] > c_curr["open"] and c_next["close"] < c_next["open"]:
            if body_next > 1.4 * body_curr and c_next["close"] < c_curr["low"]:
                obs.append({
                    "type": "BEARISH_ORDER_BLOCK",
                    "high": round(float(c_curr["high"]), 4),
                    "low": round(float(c_curr["low"]), 4),
                    "timestamp": c_curr["timestamp"]
                })

    return obs

def detect_liquidity_sweeps(df: pd.DataFrame, swings: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Detects liquidity sweeps where price wicks beyond a recent swing high/low but closes inside.
    """
    if len(df) < 5:
        return []

    sweeps = []
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Check Buy-side Liquidity (BSL) Sweeps (Wick above swing high, close below)
    for sh in swings.get("swing_highs", [])[-5:]:
        sh_price = sh["price"]
        if latest["high"] > sh_price and latest["close"] < sh_price:
            sweeps.append({
                "type": "BUY_SIDE_LIQUIDITY_SWEEP",
                "swept_level": round(sh_price, 4),
                "bias_implication": "BEARISH_REVERSAL",
                "details": f"Price swept BSL at {sh_price} and rejected back below."
            })

    # Check Sell-side Liquidity (SSL) Sweeps (Wick below swing low, close above)
    for sl in swings.get("swing_lows", [])[-5:]:
        sl_price = sl["price"]
        if latest["low"] < sl_price and latest["close"] > sl_price:
            sweeps.append({
                "type": "SELL_SIDE_LIQUIDITY_SWEEP",
                "swept_level": round(sl_price, 4),
                "bias_implication": "BULLISH_REVERSAL",
                "details": f"Price swept SSL at {sl_price} and rejected back above."
            })

    return sweeps

def detect_structure_breaks(df: pd.DataFrame, swings: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Detects Break of Structure (BOS) and Change of Character (CHOCH).
    """
    if len(df) < 10:
        return {"bos": None, "choch": None}

    latest = df.iloc[-1]
    curr_c = latest["close"]

    shs = swings.get("swing_highs", [])
    sls = swings.get("swing_lows", [])

    bos = None
    choch = None

    if len(shs) >= 2:
        last_sh = shs[-1]["price"]
        prev_sh = shs[-2]["price"]
        if curr_c > last_sh:
            bos = {"type": "BULLISH_BOS", "level": round(last_sh, 4)}

    if len(sls) >= 2:
        last_sl = sls[-1]["price"]
        prev_sl = sls[-2]["price"]
        if curr_c < last_sl:
            bos = {"type": "BEARISH_BOS", "level": round(last_sl, 4)}

    # CHOCH: Reversal against previous established trend
    if len(shs) >= 1 and len(sls) >= 1:
        if curr_c > shs[-1]["price"] and (sls[-1]["price"] < (sls[-2]["price"] if len(sls) >= 2 else sls[-1]["price"])):
            choch = {"type": "BULLISH_CHOCH", "level": round(shs[-1]["price"], 4)}
        elif curr_c < sls[-1]["price"] and (shs[-1]["price"] > (shs[-2]["price"] if len(shs) >= 2 else shs[-1]["price"])):
            choch = {"type": "BEARISH_CHOCH", "level": round(sls[-1]["price"], 4)}

    return {"bos": bos, "choch": choch}

def compute_premium_discount(df: pd.DataFrame, lookback: int = 50) -> Dict[str, Any]:
    """
    Calculates Dealing Range Equilibrium (50%), Premium (>50%), and Discount (<50%) zones.
    """
    if len(df) < 10:
        return {}

    window = df.tail(lookback)
    range_high = float(window["high"].max())
    range_low = float(window["low"].min())
    curr_price = float(df["close"].iloc[-1])

    equilibrium = (range_high + range_low) / 2.0
    zone = "PREMIUM" if curr_price > equilibrium else ("DISCOUNT" if curr_price < equilibrium else "EQUILIBRIUM")
    pct_range = ((curr_price - range_low) / (range_high - range_low + 1e-10)) * 100.0

    return {
        "range_high": round(range_high, 4),
        "range_low": round(range_low, 4),
        "equilibrium": round(equilibrium, 4),
        "current_zone": zone,
        "position_percent": round(pct_range, 1)
    }

def detect_breaker_blocks(df: pd.DataFrame, obs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detects Breaker Blocks (failed Order Blocks that flip polarity):
    - Bullish Breaker: A Bearish Order Block that price violently broke above;
      now flips into high-conviction support.
    - Bearish Breaker: A Bullish Order Block that price violently broke below;
      now flips into high-conviction resistance.
    """
    if len(df) < 5 or not obs:
        return []

    breakers = []
    latest_c = float(df["close"].iloc[-1])

    for ob in obs:
        ob_type = ob.get("type", "")
        ob_high = ob.get("high", 0.0)
        ob_low = ob.get("low", 0.0)

        # Bullish Breaker: Previous Bearish OB broken upwards
        if ob_type == "BEARISH_ORDER_BLOCK":
            # Check if any subsequent candle closed above the OB high
            if latest_c > ob_high:
                breakers.append({
                    "type": "BULLISH_BREAKER",
                    "high": ob_high,
                    "low": ob_low,
                    "role": "INSTITUTIONAL_SUPPORT",
                    "description": f"Bearish OB at {ob_low}-{ob_high} broken above. Flipped to Bullish Breaker Support."
                })

        # Bearish Breaker: Previous Bullish OB broken downwards
        elif ob_type == "BULLISH_ORDER_BLOCK":
            # Check if any subsequent candle closed below the OB low
            if latest_c < ob_low:
                breakers.append({
                    "type": "BEARISH_BREAKER",
                    "high": ob_high,
                    "low": ob_low,
                    "role": "INSTITUTIONAL_RESISTANCE",
                    "description": f"Bullish OB at {ob_low}-{ob_high} broken below. Flipped to Bearish Breaker Resistance."
                })

    return breakers[-3:]

def compute_optimal_trade_entry(df: pd.DataFrame, swings: Dict[str, List[Dict[str, Any]]], lookback: int = 50) -> Dict[str, Any]:
    """
    Computes ICT Optimal Trade Entry (OTE) based on the 0.618 - 0.786 Fibonacci sweet spot.
    - Equilibrium: 0.50
    - OTE Entrance: 0.618
    - OTE Sweet Spot: 0.705 (Optimal Institutional Fill)
    - OTE Invalidation Boundary: 0.786
    """
    if len(df) < 10:
        return {}

    curr_price = float(df["close"].iloc[-1])
    shs = swings.get("swing_highs", [])
    sls = swings.get("swing_lows", [])

    if not shs or not sls:
        window = df.tail(lookback)
        swing_h = float(window["high"].max())
        swing_l = float(window["low"].min())
    else:
        recent_sh = max(shs[-3:], key=lambda x: x["price"])
        recent_sl = min(sls[-3:], key=lambda x: x["price"])
        swing_h = float(recent_sh["price"])
        swing_l = float(recent_sl["price"])

    range_span = swing_h - swing_l
    if range_span <= 0:
        return {}

    equilibrium = swing_l + 0.50 * range_span

    # Determine dominant impulse direction
    # If price is closer to the high or latest swing was low, evaluate bullish retracement into discount
    is_bullish_impulse = (shs[-1]["index"] > sls[-1]["index"]) if (shs and sls) else (curr_price >= equilibrium)

    if is_bullish_impulse:
        # Bullish OTE: Retracement down from swing_h into discount (61.8% to 78.6% pullbacks)
        fib_618 = swing_h - 0.618 * range_span
        fib_705 = swing_h - 0.705 * range_span
        fib_786 = swing_h - 0.786 * range_span
        in_ote = (fib_786 <= curr_price <= fib_618)
        ote_status = "BULLISH_OTE_ACTIVE" if in_ote else ("DISCOUNT_UNDER_OTE" if curr_price < fib_786 else "PREMIUM_ABOVE_OTE")
    else:
        # Bearish OTE: Retracement up from swing_l into premium (61.8% to 78.6% rallies)
        fib_618 = swing_l + 0.618 * range_span
        fib_705 = swing_l + 0.705 * range_span
        fib_786 = swing_l + 0.786 * range_span
        in_ote = (fib_618 <= curr_price <= fib_786)
        ote_status = "BEARISH_OTE_ACTIVE" if in_ote else ("PREMIUM_ABOVE_OTE" if curr_price > fib_786 else "DISCOUNT_UNDER_OTE")

    return {
        "impulse_direction": "BULLISH" if is_bullish_impulse else "BEARISH",
        "swing_high": round(swing_h, 4),
        "swing_low": round(swing_l, 4),
        "equilibrium_50": round(equilibrium, 4),
        "fib_618": round(fib_618, 4),
        "fib_705_sweet_spot": round(fib_705, 4),
        "fib_786": round(fib_786, 4),
        "in_ote_zone": in_ote,
        "ote_status": ote_status,
        "current_price": round(curr_price, 4)
    }

def get_ict_killzones(check_time: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Returns live ICT Institutional Killzones and Silver Bullet status (UTC):
    - Asian Range: 00:00 - 05:00 UTC (Accumulation)
    - London Open Killzone: 07:00 - 10:00 UTC (02:00 - 05:00 EST)
    - New York AM Killzone: 12:00 - 15:00 UTC (07:00 - 10:00 EST)
    - ICT Silver Bullet (NY AM): 14:00 - 15:00 UTC (10:00 - 11:00 EST) -> High probability FVG entry
    - London Close Killzone: 15:00 - 17:00 UTC (10:00 - 12:00 EST)
    """
    if check_time is None:
        check_time = datetime.datetime.now(datetime.timezone.utc)
    elif check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=datetime.timezone.utc)

    hour = check_time.hour
    minute = check_time.minute
    total_minutes = hour * 60 + minute

    active_kz = []
    is_silver_bullet = False

    # 1. Asian Range
    if 0 <= hour < 5:
        active_kz.append("Asian Range (Accumulation)")

    # 2. London Open Killzone (07:00 - 10:00 UTC)
    if 7 <= hour < 10:
        active_kz.append("London Open Killzone")

    # 3. New York AM Killzone (12:00 - 15:00 UTC)
    if 12 <= hour < 15:
        active_kz.append("New York AM Killzone")

    # 4. ICT Silver Bullet (14:00 - 15:00 UTC / 10:00 - 11:00 AM EST)
    if 14 <= hour < 15:
        is_silver_bullet = True
        active_kz.append("ICT Silver Bullet (10-11 AM EST)")

    # 5. London Close Killzone (15:00 - 17:00 UTC)
    if 15 <= hour < 17:
        active_kz.append("London Close Killzone")

    # Determine primary status label
    if is_silver_bullet:
        kz_label = "⚡ SILVER BULLET ACTIVE (NY 10-11 AM)"
        kz_color = "green"
    elif active_kz:
        kz_label = f"🟢 ACTIVE: {active_kz[0]}"
        kz_color = "gold"
    else:
        kz_label = "⚪ STANDBY (Interbank Range)"
        kz_color = "neutral"

    # Next killzone schedule
    if hour < 7:
        next_kz = "London Open Killzone at 07:00 UTC (14:00 KH)"
    elif hour < 12:
        next_kz = "New York AM Killzone at 12:00 UTC (19:00 KH)"
    elif hour < 14:
        next_kz = "ICT Silver Bullet at 14:00 UTC (21:00 KH)"
    elif hour < 15:
        next_kz = "London Close Killzone at 15:00 UTC (22:00 KH)"
    else:
        next_kz = "Asian Range at 00:00 UTC (07:00 KH tomorrow)"

    return {
        "active_killzones": active_kz,
        "is_silver_bullet": is_silver_bullet,
        "current_label": kz_label,
        "status_color": kz_color,
        "next_killzone": next_kz,
        "current_utc_time": check_time.strftime("%H:%M UTC")
    }

def get_current_session(check_time: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Returns active institutional trading session (UTC), backward compatible.
    """
    kz = get_ict_killzones(check_time)
    sessions = kz.get("active_killzones", [])
    is_overlap = any("New York" in s or "Silver Bullet" in s for s in sessions)
    return {
        "active_sessions": sessions,
        "is_london_ny_overlap": is_overlap,
        "volatility_context": "PEAK_INSTITUTIONAL_VOLUME" if kz.get("is_silver_bullet") else ("ACTIVE" if sessions else "OFF_HOURS"),
        "killzone_details": kz
    }

def detect_amd_judas_swing(df: pd.DataFrame, swings: Dict[str, List[Dict[str, Any]]], check_time: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    ICT Power of 3 (AMD): Accumulation -> Manipulation (Judas Swing) -> Distribution.
    Detects if London Open or NY Open swept the Asian Range extreme and rejected (Judas Swing).
    """
    if len(df) < 20:
        return {"phase": "ACCUMULATION", "judas_swing": None, "details": "Insufficient data"}

    curr_p = float(df["close"].iloc[-1])
    recent_high = float(df["high"].tail(24).max())
    recent_low = float(df["low"].tail(24).min())

    shs = swings.get("swing_highs", [])
    sls = swings.get("swing_lows", [])

    # Check for Judas Swing: Fakeout beyond extreme followed by immediate displacement
    judas = None
    phase = "DISTRIBUTION"

    if shs and sls:
        last_sh = shs[-1]["price"]
        last_sl = sls[-1]["price"]

        # Swept high but closed back below -> Bearish Judas Swing
        if df["high"].iloc[-2] > last_sh and curr_p < last_sh:
            judas = {
                "type": "BEARISH_JUDAS_SWING",
                "swept_extreme": round(last_sh, 4),
                "implication": "MANIPULATION_COMPLETE_BEARISH_EXPANSION",
                "details": f"Price swept liquidity high at {last_sh} and displaced downwards (Judas Swing trap)."
            }
            phase = "MANIPULATION"
        # Swept low but closed back above -> Bullish Judas Swing
        elif df["low"].iloc[-2] < last_sl and curr_p > last_sl:
            judas = {
                "type": "BULLISH_JUDAS_SWING",
                "swept_extreme": round(last_sl, 4),
                "implication": "MANIPULATION_COMPLETE_BULLISH_EXPANSION",
                "details": f"Price swept liquidity low at {last_sl} and displaced upwards (Judas Swing trap)."
            }
            phase = "MANIPULATION"

    return {
        "phase": phase,
        "judas_swing": judas,
        "range_high": round(recent_high, 4),
        "range_low": round(recent_low, 4)
    }

def compute_volume_profile(df: pd.DataFrame, num_bins: int = 24, lookback: int = 50) -> Dict[str, Any]:
    """
    Computes Fixed-Range Institutional Volume Profile:
    - POC (Point of Control): Highest traded volume price level
    - VAH (Value Area High): Upper boundary of 70% traded volume area
    - VAL (Value Area Low): Lower boundary of 70% traded volume area
    - Profile distribution histogram for UI visualization
    - Current price relationship (ABOVE_VAH, INSIDE_VALUE_AREA, BELOW_VAL, AT_POC)
    """
    if len(df) < 10:
        return {
            "poc": 0.0, "vah": 0.0, "val": 0.0,
            "current_position": "UNKNOWN", "total_volume": 0.0,
            "profile_bars": [], "summary_en": "Insufficient data", "summary_kh": "ទិន្នន័យមិនគ្រប់គ្រាន់"
        }

    sub_df = df.tail(lookback).copy()
    p_min = float(sub_df["low"].min())
    p_max = float(sub_df["high"].max())
    curr_price = float(sub_df["close"].iloc[-1])

    if p_max <= p_min:
        return {
            "poc": curr_price, "vah": curr_price, "val": curr_price,
            "current_position": "INSIDE_VALUE_AREA", "total_volume": 0.0,
            "profile_bars": [], "summary_en": "Flat range", "summary_kh": "ជួរតម្លៃរាបស្មើ"
        }

    bins = np.linspace(p_min, p_max, num_bins + 1)
    vols = np.zeros(num_bins)

    has_vol = "volume" in sub_df.columns and sub_df["volume"].sum() > 0

    for i in range(len(sub_df)):
        row = sub_df.iloc[i]
        c_low = float(row["low"])
        c_high = float(row["high"])
        c_vol = float(row["volume"]) if has_vol else 100.0

        c_bins = np.where((bins[:-1] >= c_low) & (bins[1:] <= c_high))[0]
        if len(c_bins) > 0:
            vols[c_bins] += c_vol / len(c_bins)
        else:
            typ = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3.0
            idx = min(num_bins - 1, max(0, int((typ - p_min) / (p_max - p_min) * num_bins)))
            vols[idx] += c_vol

    total_vol = float(vols.sum())
    if total_vol <= 0:
        total_vol = 1.0

    poc_idx = int(np.argmax(vols))
    poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2.0

    # Steidlmayer 70% Value Area algorithm
    target_vol = total_vol * 0.70
    included = {poc_idx}
    cum_vol = vols[poc_idx]
    up = poc_idx + 1
    down = poc_idx - 1

    while cum_vol < target_vol and (up < num_bins or down >= 0):
        vol_up = vols[up] if up < num_bins else -1.0
        vol_down = vols[down] if down >= 0 else -1.0
        if vol_up >= vol_down and vol_up >= 0:
            included.add(up)
            cum_vol += vol_up
            up += 1
        elif vol_down >= 0:
            included.add(down)
            cum_vol += vol_down
            down -= 1
        else:
            break

    min_idx = min(included)
    max_idx = max(included)
    val_price = (bins[min_idx] + bins[min_idx + 1]) / 2.0
    vah_price = (bins[max_idx] + bins[max_idx + 1]) / 2.0

    # Current price position relative to Value Area
    price_tolerance = (p_max - p_min) * 0.015
    if abs(curr_price - poc_price) <= price_tolerance:
        pos = "AT_POC"
        summary_en = f"Price is testing Point of Control (POC: {poc_price:.2f}) — Institutional Fair Value Anchor."
        summary_kh = f"តម្លៃកំពុងតេស្តកម្រិត POC ({poc_price:.2f}) — ចំណុចប្រជុំបរិមាណជួញដូរធំបំផុតរបស់ស្ថាប័ន។"
    elif curr_price > vah_price:
        pos = "ABOVE_VAH"
        summary_en = f"Price is extended ABOVE Value Area High (VAH: {vah_price:.2f}) — Premium expansion zone; potential mean-reversion target back to POC ({poc_price:.2f})."
        summary_kh = f"តម្លៃកំពុងឡើងផុត VAH ({vah_price:.2f}) — តំបន់ថ្លៃខ្ពស់ (Premium); អាចនឹងទាញត្រឡប់មករក POC ({poc_price:.2f}) វិញ។"
    elif curr_price < val_price:
        pos = "BELOW_VAL"
        summary_en = f"Price is discounted BELOW Value Area Low (VAL: {val_price:.2f}) — Discount value zone; potential institutional accumulation targeting POC ({poc_price:.2f})."
        summary_kh = f"តម្លៃកំពុងធ្លាក់ក្រោម VAL ({val_price:.2f}) — តំបន់បញ្ចុះតម្លៃ (Discount); អាចជាឱកាសទិញឡើងទៅកាន់ POC ({poc_price:.2f})។"
    else:
        pos = "INSIDE_VALUE_AREA"
        summary_en = f"Price is trading INSIDE 70% Value Area ({val_price:.2f} - {vah_price:.2f}) around POC ({poc_price:.2f}) — Balanced rotation."
        summary_kh = f"តម្លៃកំពុងជួញដូរក្នុងតំបន់ Value Area ({val_price:.2f} - {vah_price:.2f}) ក្បែរ POC ({poc_price:.2f}) — ទីផ្សារមានតុល្យភាព។"

    # Profile bars for UI
    max_vol = float(vols.max()) if vols.max() > 0 else 1.0
    profile_bars = []
    for b_idx in range(num_bins):
        b_p = (bins[b_idx] + bins[b_idx + 1]) / 2.0
        profile_bars.append({
            "price": round(b_p, 2 if b_p > 10 else 4),
            "volume": round(float(vols[b_idx]), 1),
            "percentage": round(float(vols[b_idx] / max_vol * 100), 1),
            "is_poc": (b_idx == poc_idx),
            "in_value_area": (b_idx in included)
        })

    dec = 2 if poc_price > 10 else 4
    return {
        "poc": round(poc_price, dec),
        "vah": round(vah_price, dec),
        "val": round(val_price, dec),
        "current_position": pos,
        "total_volume": round(total_vol, 1),
        "profile_bars": profile_bars,
        "summary_en": summary_en,
        "summary_kh": summary_kh
    }


def detect_inversion_fair_value_gaps(df: pd.DataFrame, lookback: int = 40) -> Dict[str, Any]:
    """
    Detects Institutional Inversion Fair Value Gaps (IFVG) and Balanced Price Ranges (BPR):
    - Bullish IFVG: A Bearish FVG that got breached and closed ABOVE, flipping into Support.
    - Bearish IFVG: A Bullish FVG that got breached and closed BELOW, flipping into Resistance.
    - Balanced Price Range (BPR): Overlapping Bullish and Bearish FVGs forming an institutional magnet.
    """
    if len(df) < 6:
        return {"inversion_fvgs": [], "balanced_price_ranges": [], "active_retest": None}

    sub_df = df.tail(lookback).reset_index(drop=True)
    n = len(sub_df)
    curr_price = float(sub_df["close"].iloc[-1])

    bull_fvgs = []
    bear_fvgs = []

    # 1. Identify all 3-candle imbalances
    for i in range(2, n):
        c0_h = float(sub_df["high"].iloc[i - 2])
        c0_l = float(sub_df["low"].iloc[i - 2])
        c2_h = float(sub_df["high"].iloc[i])
        c2_l = float(sub_df["low"].iloc[i])

        # Bullish imbalance: c2_low > c0_high
        if c2_l > c0_h:
            bull_fvgs.append({
                "candle_idx": i - 1,
                "top": c2_l,
                "bottom": c0_h,
                "timestamp": sub_df["timestamp"].iloc[i - 1]
            })
        # Bearish imbalance: c2_high < c0_low
        elif c2_h < c0_l:
            bear_fvgs.append({
                "candle_idx": i - 1,
                "top": c0_l,
                "bottom": c2_h,
                "timestamp": sub_df["timestamp"].iloc[i - 1]
            })

    inversion_fvgs = []
    # 2. Check for Bullish Inversion FVGs: Bearish FVGs closed above
    for bf in bear_fvgs:
        idx = bf["candle_idx"]
        breached = False
        breach_idx = -1
        for j in range(idx + 1, n):
            if sub_df["close"].iloc[j] > bf["top"]:
                breached = True
                breach_idx = j
                break
        if breached:
            # Once closed above, it flips to Bullish Support
            is_retesting = bf["bottom"] <= curr_price <= bf["top"] * 1.001
            inversion_fvgs.append({
                "type": "BULLISH_INVERSION_FVG",
                "role": "SUPPORT_FLIP",
                "top": round(bf["top"], 2 if bf["top"] > 10 else 4),
                "bottom": round(bf["bottom"], 2 if bf["bottom"] > 10 else 4),
                "breached_at": str(sub_df["timestamp"].iloc[breach_idx]),
                "is_retesting": is_retesting,
                "description_en": f"Bearish FVG [{bf['bottom']:.2f} - {bf['top']:.2f}] breached upward -> Flipped into Institutional Bullish Support.",
                "description_kh": f"Bearish FVG [{bf['bottom']:.2f} - {bf['top']:.2f}] ត្រូវបានទម្លុះឡើងលើ -> ប្រែជាតំបន់គាំទ្រ Bullish Support (IFVG)។"
            })

    # 3. Check for Bearish Inversion FVGs: Bullish FVGs closed below
    for bf in bull_fvgs:
        idx = bf["candle_idx"]
        breached = False
        breach_idx = -1
        for j in range(idx + 1, n):
            if sub_df["close"].iloc[j] < bf["bottom"]:
                breached = True
                breach_idx = j
                break
        if breached:
            # Once closed below, it flips to Bearish Resistance
            is_retesting = bf["bottom"] * 0.999 <= curr_price <= bf["top"]
            inversion_fvgs.append({
                "type": "BEARISH_INVERSION_FVG",
                "role": "RESISTANCE_FLIP",
                "top": round(bf["top"], 2 if bf["top"] > 10 else 4),
                "bottom": round(bf["bottom"], 2 if bf["bottom"] > 10 else 4),
                "breached_at": str(sub_df["timestamp"].iloc[breach_idx]),
                "is_retesting": is_retesting,
                "description_en": f"Bullish FVG [{bf['bottom']:.2f} - {bf['top']:.2f}] breached downward -> Flipped into Institutional Bearish Resistance.",
                "description_kh": f"Bullish FVG [{bf['bottom']:.2f} - {bf['top']:.2f}] ត្រូវបានទម្លុះចុះក្រោម -> ប្រែជាតំបន់រារាំង Bearish Resistance (IFVG)។"
            })

    # 4. Balanced Price Range (BPR): Overlapping Bullish and Bearish FVGs
    balanced_price_ranges = []
    for b_up in bull_fvgs:
        for b_down in bear_fvgs:
            # Check overlap
            overlap_bottom = max(b_up["bottom"], b_down["bottom"])
            overlap_top = min(b_up["top"], b_down["top"])
            if overlap_top > overlap_bottom:
                is_testing = overlap_bottom <= curr_price <= overlap_top
                balanced_price_ranges.append({
                    "top": round(overlap_top, 2 if overlap_top > 10 else 4),
                    "bottom": round(overlap_bottom, 2 if overlap_bottom > 10 else 4),
                    "is_testing": is_testing,
                    "description_en": f"Balanced Price Range (BPR) at [{overlap_bottom:.2f} - {overlap_top:.2f}] — High-speed volume magnet.",
                    "description_kh": f"តំបន់តម្លៃតុល្យភាព BPR [{overlap_bottom:.2f} - {overlap_top:.2f}] — កន្លែងស្រូបទាញតម្លៃរបស់ស្ថាប័ន។"
                })

    active_retest = next((f for f in inversion_fvgs if f.get("is_retesting")), None)
    if not active_retest:
        active_retest = next((b for b in balanced_price_ranges if b.get("is_testing")), None)

    return {
        "inversion_fvgs": inversion_fvgs[-4:],
        "balanced_price_ranges": balanced_price_ranges[-2:],
        "active_retest": active_retest,
        "total_active_ifvgs": len(inversion_fvgs)
    }


def extract_ict_smc_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extracts full ICT / SMC institutional market structure summary:
    - OTE (Optimal Trade Entry 62% - 79% Fibonacci)
    - Fixed-Range Volume Profile (POC, VAH, VAL)
    - Inversion FVGs (IFVG) & Balanced Price Ranges (BPR)
    - ICT Killzones & Silver Bullet 10-11 AM window
    - Breaker Blocks & Order Blocks
    - Fair Value Gaps (FVG)
    - Liquidity Sweeps (BSL / SSL)
    - Break of Structure (BOS) & Change of Character (CHOCH)
    - Power of 3 (AMD) & Judas Swing
    - Premium / Discount Equilibrium (50%)
    """
    if len(df) < 15:
        return {}

    swings = identify_swing_points(df, left=2, right=2)
    fvgs = detect_fair_value_gaps(df, lookback=25)
    unmitigated_fvgs = [f for f in fvgs if not f.get("mitigated")]
    obs = detect_order_blocks(df, lookback=25)
    breakers = detect_breaker_blocks(df, obs)
    sweeps = detect_liquidity_sweeps(df, swings)
    structure = detect_structure_breaks(df, swings)
    prem_disc = compute_premium_discount(df, lookback=40)
    ote = compute_optimal_trade_entry(df, swings, lookback=40)
    killzones = get_ict_killzones()
    amd = detect_amd_judas_swing(df, swings)
    vol_profile = compute_volume_profile(df, lookback=min(60, len(df)))
    ifvgs = detect_inversion_fair_value_gaps(df, lookback=min(40, len(df)))

    return {
        "unmitigated_fvgs": unmitigated_fvgs[-3:],
        "recent_order_blocks": obs[-3:],
        "breaker_blocks": breakers,
        "liquidity_sweeps": sweeps,
        "structure_break": structure.get("bos"),
        "change_of_character": structure.get("choch"),
        "premium_discount": prem_disc,
        "optimal_trade_entry": ote,
        "killzones": killzones,
        "amd_status": amd,
        "session_context": killzones,
        "volume_profile": vol_profile,
        "inversion_fvgs": ifvgs
    }

