"""
AGENT 2 — ICT / SMC ANALYST
Institutional Price Action & Market Structure Specialist.
Analyzes:
- Buy-Side & Sell-Side Liquidity Sweeps
- Fair Value Gaps (FVG) and Mitigation
- Order Blocks (OB)
- Break of Structure (BOS) & Change of Character (CHOCH)
- Premium and Discount Pricing
- Institutional Session Context (London, NY, Asian)
Note: Does not claim to know actual institutional orders or intent from price charts alone.
"""
from typing import Dict, Any, List
import pandas as pd
from taikry.indicators.ict_smc import extract_ict_smc_summary

class IctSmcAnalystAgent:
    """Agent 2: Smart Money Concepts & Institutional Structure."""
    AGENT_ID = "ict_smc"
    AGENT_NAME = "Agent 2 — ICT / SMC Structure Analyst"

    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        df_m15 = multi_tf_data.get("M15")
        if df_m15 is None or df_m15.empty:
            df_m15 = multi_tf_data.get("M5")
        if df_m15 is None or df_m15.empty or len(df_m15) < 20:
            return {
                "agent_id": self.AGENT_ID,
                "agent_name": self.AGENT_NAME,
                "bias": "NO TRADE",
                "confidence": 0,
                "setup_eligible": False,
                "evidence": ["Insufficient candles for ICT structure extraction"],
                "rationale": "Need at least 20 bars to map liquidity, FVGs, and order blocks."
            }

        curr_price = float(df_m15["close"].iloc[-1])
        smc = extract_ict_smc_summary(df_m15)

        sweeps = smc.get("liquidity_sweeps", [])
        fvgs = smc.get("unmitigated_fvgs", [])
        obs = smc.get("recent_order_blocks", [])
        breakers = smc.get("breaker_blocks", [])
        bos = smc.get("structure_break")
        choch = smc.get("change_of_character")
        prem_disc = smc.get("premium_discount", {})
        ote = smc.get("optimal_trade_entry", {})
        killzones = smc.get("killzones", {})
        amd = smc.get("amd_status", {})
        session = smc.get("session_context", {})
        vol_profile = smc.get("volume_profile", {})
        ifvgs = smc.get("inversion_fvgs", {})

        bull_evidence = []
        bear_evidence = []
        bull_score = 0
        bear_score = 0

        # 0. Fixed Range Volume Profile (POC / VAH / VAL)
        vp_pos = vol_profile.get("current_position", "")
        poc = vol_profile.get("poc")
        vah = vol_profile.get("vah")
        val = vol_profile.get("val")
        if vp_pos == "BELOW_VAL" and val:
            bull_score += 25
            bull_evidence.append(f"📊 Volume Profile: Discounted BELOW VAL ({val}) -> Institutional accumulation targeting POC ({poc})")
        elif vp_pos == "ABOVE_VAH" and vah:
            bear_score += 25
            bear_evidence.append(f"📊 Volume Profile: Overextended ABOVE VAH ({vah}) -> Premium mean-reversion targeting POC ({poc})")
        elif vp_pos == "AT_POC" and poc:
            bull_score += 10
            bear_score += 10
            bull_evidence.append(f"📊 Volume Profile: Testing Point of Control (POC: {poc}) — High volume balance anchor")

        # 0b. Inversion Fair Value Gaps (IFVG) & Balanced Price Ranges (BPR)
        active_retest = ifvgs.get("active_retest")
        if active_retest:
            if active_retest.get("type") == "BULLISH_INVERSION_FVG":
                bull_score += 30
                bull_evidence.append(f"🔄 {active_retest.get('description_en')}")
            elif active_retest.get("type") == "BEARISH_INVERSION_FVG":
                bear_score += 30
                bear_evidence.append(f"🔄 {active_retest.get('description_en')}")
            elif "BPR" in active_retest.get("description_en", ""):
                bull_score += 15
                bear_score += 15
                bull_evidence.append(f"🧲 {active_retest.get('description_en')}")

        # 1. Optimal Trade Entry (OTE 62% - 79% Fibonacci Sweet Spot)
        if ote.get("in_ote_zone"):
            if ote.get("impulse_direction") == "BULLISH":
                bull_score += 35
                bull_evidence.append(
                    f"🎯 Price is inside ICT Bullish OTE Zone (Fib 62%-79%) at {curr_price} with 0.705 sweet spot at {ote.get('fib_705_sweet_spot')}"
                )
            elif ote.get("impulse_direction") == "BEARISH":
                bear_score += 35
                bear_evidence.append(
                    f"🎯 Price is inside ICT Bearish OTE Zone (Fib 62%-79%) at {curr_price} with 0.705 sweet spot at {ote.get('fib_705_sweet_spot')}"
                )

        # 2. Breaker Blocks (Broken Order Blocks Flipping Polarity)
        for brk in breakers:
            if brk.get("type") == "BULLISH_BREAKER":
                bull_score += 25
                bull_evidence.append(f"🧱 Retesting Bullish Breaker Support at {brk['low']} - {brk['high']}")
            elif brk.get("type") == "BEARISH_BREAKER":
                bear_score += 25
                bear_evidence.append(f"🧱 Retesting Bearish Breaker Resistance at {brk['low']} - {brk['high']}")

        # 3. AMD / Power of 3 & Judas Swing Traps
        judas = amd.get("judas_swing")
        if judas:
            if judas["type"] == "BULLISH_JUDAS_SWING":
                bull_score += 30
                bull_evidence.append(f"⚡ {judas['details']}")
            elif judas["type"] == "BEARISH_JUDAS_SWING":
                bear_score += 30
                bear_evidence.append(f"⚡ {judas['details']}")

        # 4. Liquidity sweeps (BSL / SSL)
        for sw in sweeps:
            if sw["type"] == "SELL_SIDE_LIQUIDITY_SWEEP":
                bull_score += 30
                bull_evidence.append(f"💧 SSL Swept at {sw['swept_level']} with strong rejection wick (potential accumulation)")
            elif sw["type"] == "BUY_SIDE_LIQUIDITY_SWEEP":
                bear_score += 30
                bear_evidence.append(f"💧 BSL Swept at {sw['swept_level']} with sharp rejection (potential distribution)")

        # 5. Structure Breaks (BOS / CHOCH)
        if choch:
            if choch["type"] == "BULLISH_CHOCH":
                bull_score += 25
                bull_evidence.append(f"🔄 Bullish Change of Character (CHOCH) above {choch['level']}")
            elif choch["type"] == "BEARISH_CHOCH":
                bear_score += 25
                bear_evidence.append(f"🔄 Bearish Change of Character (CHOCH) below {choch['level']}")
        elif bos:
            if bos["type"] == "BULLISH_BOS":
                bull_score += 20
                bull_evidence.append(f"📈 Bullish Break of Structure (BOS) continuing above {bos['level']}")
            elif bos["type"] == "BEARISH_BOS":
                bear_score += 20
                bear_evidence.append(f"📉 Bearish Break of Structure (BOS) continuing below {bos['level']}")

        # 6. Fair Value Gaps (FVG)
        for f in fvgs:
            if f["type"] == "BULLISH_FVG" and curr_price >= f["bottom"]:
                bull_score += 15
                bull_evidence.append(f"🕳️ Unmitigated Bullish FVG active between {f['bottom']} and {f['top']}")
            elif f["type"] == "BEARISH_FVG" and curr_price <= f["top"]:
                bear_score += 15
                bear_evidence.append(f"🕳️ Unmitigated Bearish FVG active between {f['bottom']} and {f['top']}")

        # 7. Premium / Discount Pricing
        current_zone = prem_disc.get("current_zone", "EQUILIBRIUM")
        if current_zone == "DISCOUNT":
            bull_score += 15
            bull_evidence.append(f"Price is in DISCOUNT zone ({prem_disc.get('position_percent')}%), favorable for Longs")
        elif current_zone == "PREMIUM":
            bear_score += 15
            bear_evidence.append(f"Price is in PREMIUM zone ({prem_disc.get('position_percent')}%), favorable for Shorts")

        # 8. ICT Killzones & Silver Bullet Timing Confluence
        if killzones.get("is_silver_bullet"):
            bull_score += 25
            bear_score += 25
            session_note = "⚡ ICT SILVER BULLET WINDOW ACTIVE (NY 10:00-11:00 AM EST) — High probability displacement."
        elif killzones.get("active_killzones"):
            bull_score += 10
            bear_score += 10
            session_note = f"🟢 Active Killzone: {', '.join(killzones.get('active_killzones'))}."
        else:
            session_note = f"⚪ Standby. Next: {killzones.get('next_killzone', 'Interbank Range')}"

        # Decision Matrix - Enhanced to actively identify ICT/SMC institutional order flow
        if (bull_score >= 35 and bull_score >= bear_score) or (bull_score > bear_score and bull_score >= 25):
            bias = "BULLISH"
            confidence = max(55, min(92, bull_score))
            setup_eligible = True
            evidence = bull_evidence or ["Bullish order block accumulation in discount"]
            entry = curr_price
            candidate_sl = ote.get("fib_786") if (ote.get("impulse_direction") == "BULLISH" and ote.get("fib_786", 0) < curr_price) else prem_disc.get("range_low", curr_price * 0.995)
            if not candidate_sl or candidate_sl >= curr_price:
                candidate_sl = curr_price * 0.995
            sl = round(candidate_sl, 4)
            sl_dist = curr_price - sl
            tp1 = round(curr_price + (sl_dist * 2.2), 4)
            tp2 = round(curr_price + (sl_dist * 3.5), 4)
            invalidation = f"Clean close below OTE 0.786 boundary / discount support at {sl}"
            rationale = "ICT Bullish structure confirmed via OTE sweet spot, liquidity sweep, or FVG confluence."
        elif (bear_score >= 35 and bear_score > bull_score) or (bear_score > bull_score and bear_score >= 25):
            bias = "BEARISH"
            confidence = max(55, min(92, bear_score))
            setup_eligible = True
            evidence = bear_evidence or ["Bearish order block distribution in premium"]
            entry = curr_price
            candidate_sl = ote.get("fib_786") if (ote.get("impulse_direction") == "BEARISH" and ote.get("fib_786", 0) > curr_price) else prem_disc.get("range_high", curr_price * 1.005)
            if not candidate_sl or candidate_sl <= curr_price:
                candidate_sl = curr_price * 1.005
            sl = round(candidate_sl, 4)
            sl_dist = sl - curr_price
            tp1 = round(curr_price - (sl_dist * 2.2), 4)
            tp2 = round(curr_price - (sl_dist * 3.5), 4)
            invalidation = f"Clean close above OTE 0.786 boundary / premium resistance at {sl}"
            rationale = "ICT Bearish structure confirmed via OTE sweet spot, liquidity sweep, or FVG confluence."
        else:
            # Resolves dealing range tilt: Discount (< Eq) -> Buy dip; Premium (>= Eq) -> Sell rally
            eq = prem_disc.get("equilibrium", curr_price)
            is_discount = curr_price <= eq
            bias = "BULLISH" if is_discount else "BEARISH"
            confidence = 54
            setup_eligible = True
            evidence = bull_evidence + bear_evidence
            entry = curr_price
            if is_discount:
                sl = round(prem_disc.get("range_low", curr_price * 0.995), 4)
                if sl >= curr_price: sl = round(curr_price * 0.995, 4)
                sl_dist = curr_price - sl
                tp1 = round(curr_price + (sl_dist * 2.2), 4)
                tp2 = round(curr_price + (sl_dist * 3.5), 4)
                invalidation = f"Break of dealing range low at {sl}"
                rationale = "Dealing Range Discount: Institutional accumulation favorable near range low."
            else:
                sl = round(prem_disc.get("range_high", curr_price * 1.005), 4)
                if sl <= curr_price: sl = round(curr_price * 1.005, 4)
                sl_dist = sl - curr_price
                tp1 = round(curr_price - (sl_dist * 2.2), 4)
                tp2 = round(curr_price - (sl_dist * 3.5), 4)
                invalidation = f"Break of dealing range high at {sl}"
                rationale = "Dealing Range Premium: Institutional distribution favorable near range high."

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "bias": bias,
            "confidence": confidence,
            "setup_eligible": setup_eligible,
            "evidence": evidence,
            "key_price_zones": {
                "current_price": curr_price,
                "dealing_range_high": prem_disc.get("range_high"),
                "dealing_range_low": prem_disc.get("range_low"),
                "equilibrium_50pct": prem_disc.get("equilibrium"),
                "current_zone": current_zone,
                "suggested_entry": entry,
                "suggested_stop_loss": sl,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "ote_sweet_spot": ote.get("fib_705_sweet_spot"),
                "in_ote_zone": ote.get("in_ote_zone", False),
                "unmitigated_fvgs": fvgs,
                "recent_order_blocks": obs,
                "breaker_blocks": breakers,
                "killzone_status": killzones.get("current_label"),
                "is_silver_bullet": killzones.get("is_silver_bullet", False),
                "volume_profile": {
                    "poc": vol_profile.get("poc"),
                    "vah": vol_profile.get("vah"),
                    "val": vol_profile.get("val"),
                    "current_position": vol_profile.get("current_position"),
                    "summary_en": vol_profile.get("summary_en"),
                    "summary_kh": vol_profile.get("summary_kh"),
                    "profile_bars": vol_profile.get("profile_bars", [])
                },
                "inversion_fvgs": ifvgs.get("inversion_fvgs", []),
                "balanced_price_ranges": ifvgs.get("balanced_price_ranges", [])
            },
            "session_context": session_note,
            "invalidation_level": invalidation,
            "methodology_disclaimer": "Analysis derived strictly from price chart geometry; no actual order-book or institutional intent is claimed.",
            "rationale": rationale
        }

ict_smc_analyst_agent = IctSmcAnalystAgent()
