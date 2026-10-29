"""
AGENT 3 — MACROECONOMIC & GLOBAL NEWS ANALYST
Analyzes:
- Federal Reserve Monetary Policy Stance & FOMC Meetings
- Real-time High-Impact Economic Events: FOMC, PPI, CPI, NFP, GDP
- US Dollar Index (DXY) momentum when a verified feed is available
- Live Breaking Financial News (Investing.com / MarketWatch RSS)
- Multi-Asset Macroeconomic Impact Mapping (Gold, Forex, Crypto)
- Bilingual Synthesis (English & Natural Khmer)
Rule: Uses timestamped and verified sources; never invents events or headlines.
"""
from typing import Dict, Any, List
from taikry.data.economic_calendar import economic_calendar_provider
from taikry.config import get_symbol_config

class MacroAnalystAgent:
    """Agent 3: Macroeconomic & Global Sentiment Specialist."""
    AGENT_ID = "macro_analyst"
    AGENT_NAME = "Agent 3 — Macroeconomic & Fundamental Analyst"

    def analyze(self, symbol: str) -> Dict[str, Any]:
        cfg = get_symbol_config(symbol)
        category = cfg.get("category", "Forex")

        # 1. Fetch DXY context
        dxy_data = economic_calendar_provider.get_usd_strength_context()
        dxy_price = dxy_data.get("dxy_price")
        dxy_change = dxy_data.get("dxy_change_pts")
        usd_bias = dxy_data.get("usd_bias", "UNAVAILABLE")

        # 2. Fetch verified high-impact economic calendar & countdowns
        events = economic_calendar_provider.get_upcoming_high_impact_events()

        # 3. Fetch live breaking macro headlines
        live_news = economic_calendar_provider.get_live_macro_news(limit=4)

        # 4. Check news blackout status
        blackout_info = economic_calendar_provider.check_news_blackout(symbol)

        evidence = []
        evidence_kh = []
        if dxy_price is not None and dxy_change is not None:
            evidence.append(f"US Dollar Index (DXY) at {dxy_price} (Change: {dxy_change:+} pts). Bias: {usd_bias}.")
            evidence_kh.append(f"សន្ទស្សន៍ប្រាក់ដុល្លារអាមេរិក (DXY) ស្ថិតនៅ {dxy_price} (បម្រែបម្រួល {dxy_change:+} pts)។ ទំនោរ: {usd_bias}។")
        else:
            evidence.append("US Dollar Index data is unavailable; no DXY direction is inferred.")
            evidence_kh.append("មិនមានទិន្នន័យសន្ទស្សន៍ប្រាក់ដុល្លារ DXY ទេ ដូច្នេះមិនសន្និដ្ឋានទិសដៅពី DXY ឡើយ។")

        # Macro Bias mapping based on asset class
        if symbol == "XAUUSD" or category == "Commodities":
            # This rule uses DXY only; no yield series is loaded here.
            if usd_bias == "BULLISH_USD":
                macro_bias = "BEARISH"
                confidence = 65
                gold_impact = "The available DXY direction is a headwind for Gold; yield data was not assessed."
                gold_impact_kh = "ទិសដៅ DXY ដែលមានបង្ហាញជាកត្តាសម្ពាធលើមាស។ ទិន្នន័យទិន្នផលសញ្ញាប័ណ្ណមិនត្រូវបានវាយតម្លៃទេ។"
            elif usd_bias == "BEARISH_USD":
                macro_bias = "BULLISH"
                confidence = 65
                gold_impact = "The available DXY direction may support Gold; yield data was not assessed."
                gold_impact_kh = "ទិសដៅ DXY ដែលមានអាចគាំទ្រតម្លៃមាស។ ទិន្នន័យទិន្នផលសញ្ញាប័ណ្ណមិនត្រូវបានវាយតម្លៃទេ។"
            else:
                macro_bias = "NEUTRAL"
                confidence = 0 if usd_bias == "UNAVAILABLE" else 50
                gold_impact = "DXY unavailable; macro direction cannot be assessed." if usd_bias == "UNAVAILABLE" else "DXY direction is neutral in the available feed."
                gold_impact_kh = "DXY មិនអាចប្រើបាន ដូច្នេះមិនអាចវាយតម្លៃទិសដៅម៉ាក្រូបានទេ។" if usd_bias == "UNAVAILABLE" else "ទិន្នន័យ DXY ដែលមានបង្ហាញទិសដៅអព្យាក្រឹត។"
            evidence.append(gold_impact)
            evidence_kh.append(gold_impact_kh)

        elif category == "Forex":
            if usd_bias == "UNAVAILABLE":
                macro_bias, confidence = "NEUTRAL", 0
                evidence.append("DXY data is unavailable; FX macro direction is unverified.")
                evidence_kh.append("មិនមានទិន្នន័យ DXY ទេ ដូច្នេះទិសដៅម៉ាក្រូ FX មិនទាន់បានផ្ទៀងផ្ទាត់។")
            else:
                if symbol.startswith("USD"):
                    macro_bias = "BULLISH" if usd_bias == "BULLISH_USD" else ("BEARISH" if usd_bias == "BEARISH_USD" else "NEUTRAL")
                else:
                    macro_bias = "BEARISH" if usd_bias == "BULLISH_USD" else ("BULLISH" if usd_bias == "BEARISH_USD" else "NEUTRAL")
                confidence = 65 if macro_bias != "NEUTRAL" else 50
                evidence.append(f"Macro correlation aligns {macro_bias} against US Dollar trend.")
                evidence_kh.append(f"ទំនាក់ទំនងម៉ាក្រូសេដ្ឋកិច្ចស្របទៅនឹងទំនោរ {macro_bias} ធៀបនឹងប្រាក់ដុល្លារ។")

        elif category == "Crypto":
            if usd_bias == "BEARISH_USD":
                macro_bias = "BULLISH"
                confidence = 70
                evidence.append("Weakening USD increases institutional risk-on appetite for digital assets.")
                evidence_kh.append("ប្រាក់ដុល្លារចុះខ្សោយបង្កើនចំណង់ទិញទ្រព្យសកម្មឌីជីថលពីស្ថាប័នធំៗ។")
            elif usd_bias == "BULLISH_USD":
                macro_bias = "BEARISH"
                confidence = 60
                evidence.append("Dollar strength tightens financial conditions, exerting pressure on risk assets.")
                evidence_kh.append("កម្លាំងដុល្លាររឹតបន្តឹងលក្ខខណ្ឌហិរញ្ញវត្ថុ ដាក់សម្ពាធលើទ្រព្យគ្រីបតូ។")
            else:
                macro_bias = "NEUTRAL"
                confidence = 0 if usd_bias == "UNAVAILABLE" else 50
                evidence.append("DXY data is unavailable; no USD-driven crypto view is inferred." if usd_bias == "UNAVAILABLE" else "DXY direction is neutral in the available feed.")
                evidence_kh.append("មិនមានទិន្នន័យ DXY ទេ ដូច្នេះមិនសន្និដ្ឋានទិសដៅគ្រីបតូដោយផ្អែកលើ USD ឡើយ។" if usd_bias == "UNAVAILABLE" else "ទិន្នន័យ DXY ដែលមានបង្ហាញទិសដៅអព្យាក្រឹត។")
        else:
            macro_bias = "NEUTRAL"
            confidence = 50

        # Summarize upcoming calendar risks
        risk_warnings = []
        risk_warnings_kh = []

        if blackout_info.get("is_blackout"):
            risk_warnings.append(blackout_info["advisory_en"])
            risk_warnings_kh.append(blackout_info["advisory_kh"])
        elif blackout_info.get("status") == "UNAVAILABLE":
            risk_warnings.append(blackout_info["advisory_en"])
            risk_warnings_kh.append(blackout_info["advisory_kh"])

        for ev in events[:4]:
            t_en = ev.get("title", "")
            t_kh = ev.get("title_kh", "")
            time_u = ev.get("time_until", "")
            evidence.append(f"High-Impact Catalyst: {t_en} ({ev.get('country')}) — {time_u}")
            evidence_kh.append(f"ព្រឹត្តិការណ៍ឥទ្ធិពលខ្ពស់៖ {t_kh} ({ev.get('country')}) — {time_u}")

        # Add breaking headlines
        for n in live_news[:2]:
            evidence.append(f"Live Macro Feed: [{n.get('source')}] {n.get('title')}")

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "bias": macro_bias,
            "confidence": confidence,
            "confidence_basis": "rule_based_heuristic_not_calibrated_probability",
            "setup_eligible": usd_bias != "UNAVAILABLE",
            "usd_index": {
                "dxy_price": dxy_price,
                "dxy_change": dxy_change,
                "usd_bias": usd_bias
            },
            "high_impact_events": events,
            "live_news": live_news,
            "blackout_status": blackout_info,
            "evidence": evidence,
            "evidence_kh": evidence_kh,
            "risk_warnings": risk_warnings,
            "risk_warnings_kh": risk_warnings_kh,
            "rationale": f"Fundamental direction driven by {usd_bias} with DXY at {dxy_price}." if dxy_price is not None else "DXY data is unavailable; no USD-driven macro direction is inferred.",
            "rationale_kh": f"ទិសដៅម៉ាក្រូសេដ្ឋកិច្ចត្រូវបានដឹកនាំដោយទំនោរ {usd_bias} ជាមួយ DXY ស្ថិតនៅ {dxy_price}។" if dxy_price is not None else "មិនមានទិន្នន័យ DXY ទេ ដូច្នេះមិនសន្និដ្ឋានទិសដៅម៉ាក្រូដោយផ្អែកលើ USD ឡើយ។"
        }

macro_analyst_agent = MacroAnalystAgent()
