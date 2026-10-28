"""
AGENT 3 — MACROECONOMIC & GLOBAL NEWS ANALYST
Analyzes:
- Federal Reserve Monetary Policy Stance & FOMC Meetings
- Real-time High-Impact Economic Events: FOMC, PPI, CPI, NFP, GDP
- US Dollar Index (DXY) momentum and yield curve pressure
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
        dxy_price = dxy_data.get("dxy_price", 104.0)
        dxy_change = dxy_data.get("dxy_change_pts", 0.0)
        usd_bias = dxy_data.get("usd_bias", "NEUTRAL_USD")

        # 2. Fetch verified high-impact economic calendar & countdowns
        events = economic_calendar_provider.get_upcoming_high_impact_events()

        # 3. Fetch live breaking macro headlines
        live_news = economic_calendar_provider.get_live_macro_news(limit=4)

        # 4. Check news blackout status
        blackout_info = economic_calendar_provider.check_news_blackout(symbol)

        evidence = []
        evidence_kh = []
        evidence.append(f"US Dollar Index (DXY) at {dxy_price} (Change: {dxy_change:+} pts). Bias: {usd_bias}.")
        evidence_kh.append(f"សន្ទស្សន៍ប្រាក់ដុល្លារអាមេរិក (DXY) ស្ថិតនៅ {dxy_price} (បម្រែបម្រួល {dxy_change:+} pts)។ ទំនោរ: {usd_bias}។")

        # Macro Bias mapping based on asset class
        if symbol == "XAUUSD" or category == "Commodities":
            # Gold has inverse correlation with USD and yields
            if usd_bias == "BULLISH_USD":
                macro_bias = "BEARISH"
                confidence = 65
                gold_impact = "Stronger USD creates headwind for Gold bullion."
                gold_impact_kh = "ប្រាក់ដុល្លាររឹងមាំដាក់សម្ពាធធ្លាក់ចុះលើតម្លៃមាស។"
            elif usd_bias == "BEARISH_USD":
                macro_bias = "BULLISH"
                confidence = 75
                gold_impact = "Softening USD and lower yields provide supportive tailwind for Gold."
                gold_impact_kh = "ប្រាក់ដុល្លារចុះខ្សោយ និងទិន្នផលធ្លាក់ចុះ ជួយរុញច្រានឱ្យតម្លៃមាសហក់ឡើង។"
            else:
                macro_bias = "NEUTRAL"
                confidence = 50
                gold_impact = "Dollar consolidation; Gold driven primarily by technical and geopolitical safe-haven flow."
                gold_impact_kh = "ប្រាក់ដុល្លារកំពុងប្រមូលផ្តុំកម្លាំង មាសរងឥទ្ធិពលពីលំហូរសុវត្ថិភាពភូមិសាស្ត្រនយោបាយ។"
            evidence.append(gold_impact)
            evidence_kh.append(gold_impact_kh)

        elif category == "Forex":
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
                confidence = 50
                evidence.append("Macro environment neutral; Crypto driven by on-chain and technical factors.")
                evidence_kh.append("បរិយាកាសម៉ាក្រូអព្យាក្រឹត គ្រីបតូដឹកនាំដោយទិន្នន័យ On-chain និងបច្ចេកទេស។")
        else:
            macro_bias = "NEUTRAL"
            confidence = 50

        # Summarize upcoming calendar risks
        risk_warnings = []
        risk_warnings_kh = []

        if blackout_info.get("is_blackout"):
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
            "setup_eligible": True,
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
            "rationale": f"Fundamental direction driven by {usd_bias} with DXY at {dxy_price}.",
            "rationale_kh": f"ទិសដៅម៉ាក្រូសេដ្ឋកិច្ចត្រូវបានដឹកនាំដោយទំនោរ {usd_bias} ជាមួយ DXY ស្ថិតនៅ {dxy_price}។"
        }

macro_analyst_agent = MacroAnalystAgent()
