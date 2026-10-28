"""
AI AGENTS INTER-AGENT DEBATE & ROUND-TABLE DIALOGUE ENGINE
("AI Agents និយាយគ្នាវិភាគ ទៅវិញទៅមក")
Simulates dynamic, adversarial, multi-turn dialogue among the 4 institutional AI agents:
1. Agent 1: Quantitative Technical Analyst (Momentum, EMAs, RSI, ATR)
2. Agent 2: Institutional ICT / SMC Analyst (Liquidity sweeps, FVG, OTE, Order Blocks)
3. Agent 3: Macroeconomic & DXY Analyst (Dollar index, yield curve, macro events)
4. Agent 4: Independent Risk Validator & Arbiter (R:R audit, invalidation rules, capital safety)
"""
import datetime
from typing import Dict, Any, List, Optional

from taikry.database.session import SessionLocal
from taikry.database.models import AgentDebateSession
from taikry.agents.technical_analyst import technical_analyst_agent
from taikry.agents.ict_smc_analyst import ict_smc_analyst_agent
from taikry.agents.macro_analyst import macro_analyst_agent
from taikry.agents.risk_validator import risk_validator_agent
from taikry.data.providers import market_data_engine

class AgentDebateEngine:
    """Orchestrates live round-table conversation and adversarial debates among AI agents."""

    def conduct_debate(self, symbol: str = "XAUUSD", timeframe: str = "M15") -> Dict[str, Any]:
        """
        Executes a 4-turn adversarial debate and consensus dialogue for the given asset.
        Produces full English and Natural Khmer dialogue turns.
        """
        # Fetch verified price & multi-timeframe candles
        timeframes = ["D1", "H4", "H1", "M15", "M5"]
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(symbol, timeframes)
        verified_price, price_source, price_ts = market_data_engine.get_verified_price(symbol)

        a1_report = technical_analyst_agent.analyze(symbol, multi_tf_data)
        a2_report = ict_smc_analyst_agent.analyze(symbol, multi_tf_data)
        a3_report = macro_analyst_agent.analyze(symbol)

        risk_report = risk_validator_agent.validate(
            symbol=symbol,
            verified_price=verified_price,
            price_timestamp=price_ts,
            agent1_report=a1_report,
            agent2_report=a2_report,
            agent3_report=a3_report
        )

        a1_bias = a1_report.get("bias", "NEUTRAL")
        a2_bias = a2_report.get("bias", "NEUTRAL")
        a3_bias = a3_report.get("bias", "NEUTRAL")
        decision = risk_report.get("decision", "HOLD")
        proposed_dir = risk_report.get("proposed_direction", "NONE")

        m15_levels = a1_report.get("key_price_levels", {})
        rsi = m15_levels.get("rsi", 50.0)
        atr = m15_levels.get("atr", 8.0)
        ote_info = a2_report.get("key_price_zones", {})
        eq = ote_info.get("equilibrium_50pct", verified_price)
        zone = ote_info.get("current_zone", "EQUILIBRIUM")
        in_ote = ote_info.get("in_ote_zone", False)
        dxy_data = a3_report.get("usd_index", {})
        dxy_val = dxy_data.get("dxy_price", 104.2)
        dxy_bias = dxy_data.get("dxy_bias", "NEUTRAL")

        turns: List[Dict[str, Any]] = []

        # --- TURN 1: Agent 1 (Technical Momentum) Opens ---
        if "BULLISH" in a1_bias:
            t1_en = f"I am opening with a strong BULLISH stance on {symbol} at {verified_price}. Price is trading firmly above EMA 21 and EMA 50 on M15. RSI is at {rsi}, showing sustained buying volume without overbought exhaustion. The momentum favors immediate upside expansion."
            t1_kh = f"ខ្ញុំសូមបើកការពិភាក្សាជាមួយជំហរទិញ (BULLISH) យ៉ាងរឹងមាំលើ {symbol} ក្នុងតម្លៃ {verified_price}។ តម្លៃកំពុងស្ថិតនៅពីលើបន្ទាត់មធ្យម EMA 21 និង EMA 50 លើ M15។ សន្ទុះ RSI ស្ថិតនៅ {rsi} បង្ហាញពីកម្លាំងទិញបន្តបន្ទាប់ដោយគ្មានការអស់កម្លាំងឡើយ។"
        elif "BEARISH" in a1_bias:
            t1_en = f"I am opening with a BEARISH thesis on {symbol} at {verified_price}. Market structure has formed lower highs and lower lows below EMA 21 and EMA 50. RSI is at {rsi}, showing clear bearish continuation pressure."
            t1_kh = f"ខ្ញុំសូមបើកកិច្ចពិភាក្សាជាមួយទស្សនៈលក់ (BEARISH) លើ {symbol} នៅតម្លៃ {verified_price}។ រចនាសម្ព័ន្ធទីផ្សារកំពុងបង្កើត Lower Highs និង Lower Lows ក្រោម EMA 21 និង EMA 50។ សន្ទុះ RSI ({rsi}) បង្ហាញពីសម្ពាធធ្លាក់ចុះច្បាស់លាស់។"
        else:
            t1_en = f"Technical indicators on {symbol} are currently mixed around {verified_price}. Price is compressing near EMA 21 with RSI at {rsi}. We are in a consolidation band awaiting volume breakout."
            t1_kh = f"សូចនាករបច្ចេកទេសលើ {symbol} កំពុងមានសញ្ញាចម្រុះជុំវិញតម្លៃ {verified_price}។ តម្លៃកំពុងប្រមូលផ្តុំជិត EMA 21 ជាមួយ RSI {rsi} ក្នុងសភាពរង់ចាំការទម្លុះទិសដៅ។"

        turns.append({
            "turn_index": 1,
            "agent_id": "technical_analyst",
            "agent_name": "Agent 1 — Quantitative Technical",
            "agent_avatar": "🤖",
            "badge_color": "var(--cyan-neon)",
            "stance": a1_bias,
            "message_en": t1_en,
            "message_kh": t1_kh,
            "timestamp": "Step 1: Momentum Audit"
        })

        # --- TURN 2: Agent 2 (ICT / SMC) Challenges & Evaluates Liquidity ---
        if in_ote and "DISCOUNT" in zone:
            t2_en = f"Agent 1, I support your upside view, but let's be institutionally precise. Price has dropped into the 61.8%-78.6% Optimal Trade Entry (OTE) sweet spot inside the Institutional Discount zone below EQ ({round(eq, 2)}). Sell-side liquidity (SSL) has been swept. Smart money is accumulating long contracts here."
            t2_kh = f"Agent 1 ខ្ញុំគាំទ្រទស្សនៈឡើងរបស់អ្នក ប៉ុន្តែយើងត្រូវពិនិត្យរចនាសម្ព័ន្ធស្ថាប័នឱ្យច្បាស់លាស់។ តម្លៃបានធ្លាក់ចុះមកដល់តំបន់មាស OTE (61.8%-78.6%) ក្នុងតំបន់ Discount ក្រោម EQ ({round(eq, 2)})។ សន្ទនីយភាព SSL ត្រូវបានស្រូបទាញរួចហើយ ស្ថាប័នធំៗកំពុងប្រមូលកុងត្រាទិញនៅទីនេះ។"
        elif "PREMIUM" in zone:
            t2_en = f"Careful, Agent 1! Price is trading at {verified_price}, inside the Institutional Premium zone (Dealing Range High is above EQ {round(eq, 2)}). Entering long here risks buying into institutional distribution. We have overhead Buy-Side Liquidity (BSL) waiting to be swept before any reversal."
            t2_kh = f"សូមប្រយ័ត្ន Agent 1! តម្លៃបច្ចុប្បន្ន {verified_price} ស្ថិតក្នុងតំបន់ Premium របស់ស្ថាប័ន (លើសពី EQ {round(eq, 2)})។ ការចូលទិញនៅត្រង់នេះប្រឈមនឹងការទិញចំពេលស្ថាប័នកំពុងបញ្ចេញទំនិញ (Distribution)។ យើងមានសន្ទនីយភាព BSL នៅខាងលើដែលត្រូវតែប្រយ័ត្ន។"
        else:
            t2_en = f"I am observing fair value gap (FVG) mitigations around equilibrium ({round(eq, 2)}). Institutional order flow is rebalancing orders across the dealing range. We should confirm breaker block defense before commiting large sizing."
            t2_kh = f"ខ្ញុំកំពុងសង្កេតឃើញការបំពេញចន្លោះប្រហោង Fair Value Gap (FVG) ជុំវិញចំណុចកណ្តាល Equilibrium ({round(eq, 2)})។ លំហូរទុនស្ថាប័នកំពុងថ្លឹងថ្លែងឡើងវិញ យើងគួររង់ចាំការបញ្ជាក់លើ Breaker Block ជាមុនសិន។"

        turns.append({
            "turn_index": 2,
            "agent_id": "ict_smc_analyst",
            "agent_name": "Agent 2 — Institutional ICT / SMC",
            "agent_avatar": "🏛️",
            "badge_color": "var(--gold-primary)",
            "stance": a2_bias,
            "message_en": t2_en,
            "message_kh": t2_kh,
            "timestamp": "Step 2: Liquidity & OTE Review"
        })

        # --- TURN 3: Agent 3 (Macro & DXY) Cross-Examines External Drivers & Global News ---
        high_impact_events = a3_report.get("high_impact_events", [])
        blackout_status = a3_report.get("blackout_status", {})
        top_event = high_impact_events[0] if high_impact_events else None

        news_context_en = ""
        news_context_kh = ""
        if top_event:
            ev_title = top_event.get("title", "")
            ev_title_kh = top_event.get("title_kh", "")
            ev_time = top_event.get("time_until", "")
            ev_fc = top_event.get("forecast", "N/A")
            ev_prev = top_event.get("previous", "N/A")
            news_context_en = f" High-impact catalyst alert: '{ev_title}' ({top_event.get('country')}) scheduled {ev_time} [Forecast: {ev_fc} vs Prev: {ev_prev}]. {top_event.get('gold_impact_en')}"
            news_context_kh = f" ការប្រុងប្រយ័ត្នព័ត៌មានឥទ្ធិពលខ្លាំង៖ '{ev_title_kh}' ({top_event.get('country')}) នឹងចេញផ្សាយ {ev_time} [ការព្យាករណ៍: {ev_fc} ធៀបមុន: {ev_prev}]។ {top_event.get('gold_impact_kh')}"

        if "XAU" in symbol or "GOLD" in symbol:
            if "BEARISH" in dxy_bias:
                t3_en = f"Macro perspective confirms the setup: The US Dollar Index (DXY) is softening around {dxy_val}, facing overhead resistance. Benchmark yields are pulling back, lowering the opportunity cost of holding non-yielding bullion.{news_context_en} Macro winds favor safe-haven expansion."
                t3_kh = f"កត្តាម៉ាក្រូសេដ្ឋកិច្ចសូមបញ្ជាក់បន្ថែម៖ សន្ទស្សន៍ប្រាក់ដុល្លារអាមេរិក (DXY) កំពុងចុះខ្សោយជុំវិញ {dxy_val} ដោយសារជួបនឹងរនាំងធន់នៅខាងលើ។ ទិន្នផលមូលបត្របំណុលកំពុងថមថយ ដែលជាកត្តាជំរុញឱ្យតម្លៃមាសហក់ឡើងយ៉ាងរឹងមាំ។{news_context_kh}"
            else:
                t3_en = f"Macro caution alert: The US Dollar Index (DXY) is holding firm at {dxy_val}. Recent central bank rate commentary maintains a cautious stance.{news_context_en} Even if the chart looks technical, macroeconomic dollar resilience could cap upside momentum."
                t3_kh = f"ការព្រមានពីកត្តាម៉ាក្រូ៖ សន្ទស្សន៍ប្រាក់ដុល្លារ (DXY) នៅតែរឹងមាំនៅកម្រិត {dxy_val}។ ជំហរអត្រាការប្រាក់របស់ធនាគារកណ្តាលនៅតែប្រយ័ត្នប្រយែង។{news_context_kh} ទោះបីជាបច្ចេកទេសល្អ ក៏កម្លាំងដុល្លារអាចរារាំងការឡើងថ្លៃផងដែរ។"
        elif "BTC" in symbol or "CRYPTO" in symbol or "ETH" in symbol:
            t3_en = f"Crypto macro environment: Global liquidity conditions and institutional ETF inflows create a solid foundation.{news_context_en} Systemic leverage remains moderate."
            t3_kh = f"ស្ថានភាពម៉ាក្រូគ្រីបតូ៖ លំហូរសន្ទនីយភាពសកល និងការហូរចូលនៃមូលនិធិ Spot ETF កំពុងបង្កើតកម្រាលទ្រទ្រង់យ៉ាងរឹងមាំ។{news_context_kh} មិនទាន់មានហានិភ័យ Leverage ហួសហេតុឡើយ។"
        else:
            t3_en = f"Forex macro cross-check: Currency yield differentials and upcoming central bank rate decisions are priced in.{news_context_en} Volatility risk elevated."
            t3_kh = f"ការផ្ទៀងផ្ទាត់ម៉ាក្រូប្តូរប្រាក់៖ គម្លាតអត្រាការប្រាក់រវាងរូបិយប័ណ្ណត្រូវបានទីផ្សារគណនារួចរាល់។{news_context_kh} កម្រិតបម្រែបម្រួលអាចកើនឡើងខ្លាំង។"

        turns.append({
            "turn_index": 3,
            "agent_id": "macro_analyst",
            "agent_name": "Agent 3 — Macroeconomic & Global News",
            "agent_avatar": "🌐",
            "badge_color": "var(--blue-neon)",
            "stance": a3_bias,
            "message_en": t3_en,
            "message_kh": t3_kh,
            "timestamp": "Step 3: Macro Catalyst & News Check"
        })

        # --- TURN 4: Agent 4 (Risk Arbiter) Challenges, Validates & Gives Ruling ---
        is_news_blackout = blackout_status.get("is_blackout", False)

        if is_news_blackout:
            blackout_title = blackout_status.get("event_title", "High-Impact Catalyst")
            blackout_title_kh = blackout_status.get("event_title_kh", "ព័ត៌មានឥទ្ធិពលខ្លាំង")
            mins_rem = blackout_status.get("minutes_remaining", 0)
            t4_en = f"EMERGENCY NEWS LOCKOUT: VETO TRIGGERED. Setup REJECTED. High-impact event '{blackout_title}' is releasing within {mins_rem} minutes. Spread widening, slippage spikes, and severe broker liquidity gaps make entering suicidal. Execution levels strictly LOCKED to preserve capital."
            t4_kh = f"បំរាមជួញដូរពេលចេញព័ត៌មាន (News Lockout)៖ ការប្រើសិទ្ធិវេតូ (VETO) បដិសេធការជួញដូរ! ព្រឹត្តិការណ៍ឥទ្ធិពលខ្លាំង '{blackout_title_kh}' នឹងចេញផ្សាយក្នុងរយៈពេល {mins_rem} នាទីទៀត។ គម្លាត Spread នឹងឡើងខ្ពស់ និងមាន Slippage ខ្លាំង។ ចំណុចប្រតិបត្តិការត្រូវបានចាក់សោរ (LOCKED) ដើម្បីការពារដើមទុនដាច់ខាត។"
            outcome_status = "RISK_VETOED"
            decision = "REJECT"
        elif decision == "APPROVE":
            calc_rr = risk_report.get("calculated_rr", "1:2.0")
            entry_p = risk_report.get("entry_price")
            sl_p = risk_report.get("stop_loss")
            tp1_p = risk_report.get("take_profit_1")
            t4_en = f"I have audited all three theses. Directional confluence achieved between Technical ({a1_bias}) and SMC ({a2_bias}). No news blackout conflicts. Calculated Risk-to-Reward is {calc_rr} to TP1, exceeding our institutional minimum of 1:2.0. Proposed Entry: {entry_p}, SL: {sl_p}, TP1: {tp1_p}. Position size is strictly capped at 0.5% portfolio equity. SETUP APPROVED."
            t4_kh = f"ខ្ញុំបានធ្វើសវនកម្មលើទស្សនៈទាំង ៣ របស់អ្នករួចរាល់។ មានការស្រុះស្រួលគ្នារវាងបច្ចេកទេស ({a1_bias}) និងស្ថាប័ន SMC ({a2_bias}) ដោយគ្មានការរំខានពីបំរាមព័ត៌មានឡើយ។ អនុបាត R:R គឺ {calc_rr} ទៅកាន់ TP1 លើសពីកម្រិតកំណត់អប្បបរមា 1:2.0។ តម្លៃចូលជួញដូរ: {entry_p}, SL: {sl_p}, TP1: {tp1_p}។ ហានិភ័យត្រូវបានកម្រិតត្រឹម ០.៥% នៃដើមទុន។ ការរៀបចំជួញដូរត្រូវបានអនុម័ត (APPROVED)។"
            outcome_status = "CONSENSUS_REACHED"
        elif decision == "REJECT":
            reasons = "; ".join(risk_report.get("reasons", ["Risk-to-Reward insufficient"]))
            t4_en = f"VETO TRIGGERED: Setup REJECTED. Reasoning: {reasons}. The trade does not satisfy our mandatory 1:2.0 Risk-to-Reward rule or has inter-agent conflict. Trade execution levels remain LOCKED to protect portfolio capital."
            t4_kh = f"ការប្រើសិទ្ធិវេតូ (VETO): ការរៀបចំជួញដូរត្រូវបានបដិសេធ (REJECTED)។ មូលហេតុ៖ {reasons}។ ការជួញដូរមិនគ្រប់អនុបាត R:R 1:2.0 ឬមានជម្លោះរវាងភ្នាក់ងារ។ ចំណុចប្រតិបត្តិការត្រូវបានចាក់សោរ (LOCKED) ដើម្បីការពារដើមទុន។"
            outcome_status = "RISK_VETOED"
        else:
            t4_en = f"STAND ASIDE: Setup placed on WAIT / HOLD status. The market is consolidating or awaiting session liquidity. We preserve capital until clean OTE confirmation."
            t4_kh = f"ផ្អាកសិន (WAIT): ស្ថានភាពស្ថិតក្នុងភាពរង់ចាំ។ ទីផ្សារកំពុងប្រមូលផ្តុំ ឬរង់ចាំសន្ទនីយភាពក្នុង Session ថ្មី។ យើងការពារដើមទុនរហូតដល់មានការបញ្ជាក់ច្បាស់លាស់ពី OTE។"
            outcome_status = "DISSENT_RESOLVED"

        turns.append({
            "turn_index": 4,
            "agent_id": "risk_validator",
            "agent_name": "Agent 4 — Risk Guardian & Arbiter",
            "agent_avatar": "🛡️",
            "badge_color": "var(--green-neon)" if decision == "APPROVE" else "var(--red-neon)",
            "stance": decision,
            "message_en": t4_en,
            "message_kh": t4_kh,
            "timestamp": "Step 4: Final Binding Ruling"
        })

        # Save session to SQLite database
        db = SessionLocal()
        try:
            debate_record = AgentDebateSession(
                symbol=symbol,
                timeframe=timeframe,
                status=outcome_status,
                dialogue_json=turns,
                consensus_summary_en=t4_en,
                consensus_summary_kh=t4_kh,
                created_at=datetime.datetime.utcnow()
            )
            db.add(debate_record)
            db.commit()
            db.refresh(debate_record)
            session_id = debate_record.id
        except Exception:
            db.rollback()
            session_id = 1
        finally:
            db.close()

        return {
            "session_id": session_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "status": outcome_status,
            "outcome_status": outcome_status,
            "consensus_decision": decision,
            "debate_summary_en": t4_en,
            "debate_summary_kh": t4_kh,
            "total_turns": len(turns),
            "turns": turns,
            "dialogue": turns,
            "verdict": {
                "decision": decision,
                "proposed_direction": proposed_dir,
                "summary_en": t4_en,
                "summary_kh": t4_kh
            },
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

# Global singleton
agent_debate_engine = AgentDebateEngine()
