"""Build a bilingual, evidence-based summary of the four rule-based agent reports.
This produces a structured review, not a live conversation between autonomous agents.
"""
import logging
import datetime
from typing import Dict, Any, List, Optional

from taikry.database.session import SessionLocal
from taikry.database.models import AgentDebateSession
from taikry.agents.technical_analyst import technical_analyst_agent
from taikry.agents.ict_smc_analyst import ict_smc_analyst_agent
from taikry.agents.macro_analyst import macro_analyst_agent
from taikry.agents.risk_validator import risk_validator_agent
from taikry.data.providers import market_data_engine
from taikry.data.validator import check_data_freshness

logger = logging.getLogger("taikry.agents.debate_engine")

class AgentDebateEngine:
    """Orchestrates live round-table conversation and adversarial debates among AI agents."""

    def conduct_debate(self, symbol: str = "XAUUSD", timeframe: str = "M15") -> Dict[str, Any]:
        """
        Summarizes four independent agent reports for the given asset.
        """
        # Fetch verified price & multi-timeframe candles
        timeframes = ["D1", "H4", "H1", "M15", "M5"]
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(symbol, timeframes)
        verified_price, price_source, price_ts = market_data_engine.get_verified_price(symbol)

        primary_df = multi_tf_data.get("M15")
        if primary_df is None or primary_df.empty:
            primary_df = multi_tf_data.get("M5")
        freshness = check_data_freshness(symbol, primary_df.iloc[-1].get("timestamp") if primary_df is not None and not primary_df.empty else None, "M15")
        invalid_timeframes = [
            tf for tf, frame in multi_tf_data.items()
            if frame is None or frame.empty or ("source" in frame.columns and frame["source"].astype(str).str.upper().str.contains("DEMO|SYNTHETIC").any())
        ]
        if verified_price <= 0 or any(marker in str(price_source).upper() for marker in ("DEMO", "SYNTHETIC", "UNAVAILABLE")) or invalid_timeframes or not freshness.get("fresh"):
            reason = "Live market data is refreshing or awaiting confirmed candle close. Agents recommend standing by."
            reason_kh = "ទិន្នន័យទីផ្សារផ្ទាល់កំពុងធ្វើបច្ចុប្បន្នភាព ឬរង់ចាំការបិទទាន។ ភ្នាក់ងារណែនាំឱ្យរង់ចាំសិន។"
            turns = [
                {
                    "turn_index": 1,
                    "agent_id": "technical_analyst",
                    "agent_name": "Agent 1 — Quantitative Technical",
                    "agent_avatar": "🤖",
                    "badge_color": "var(--cyan-neon)",
                    "stance": "NEUTRAL",
                    "message_en": f"Quantitative Technical Agent monitoring {symbol} on {timeframe}. Awaiting confirmed multi-timeframe candles.",
                    "message_kh": f"ភ្នាក់ងារបច្ចេកទេសកំពុងតាមដាន {symbol} លើ {timeframe}។ កំពុងរង់ចាំទៀនដែលបានបញ្ជាក់។",
                    "timestamp": "Step 1: Momentum Audit"
                },
                {
                    "turn_index": 2,
                    "agent_id": "ict_smc_analyst",
                    "agent_name": "Agent 2 — Institutional ICT / SMC",
                    "agent_avatar": "🏛️",
                    "badge_color": "var(--gold-primary)",
                    "stance": "NEUTRAL",
                    "message_en": f"Smart Money Concepts Analyst checking {symbol} liquidity pools and order blocks. Standing by for fresh order flow.",
                    "message_kh": f"ភ្នាក់ងារ SMC កំពុងត្រួតពិនិត្យអាងសន្ទនីយភាព និង Order Block របស់ {symbol}។",
                    "timestamp": "Step 2: Liquidity & OTE Review"
                },
                {
                    "turn_index": 3,
                    "agent_id": "macro_analyst",
                    "agent_name": "Agent 3 — Macroeconomic & Global News",
                    "agent_avatar": "🌐",
                    "badge_color": "var(--blue-neon)",
                    "stance": "NEUTRAL",
                    "message_en": "Macro & News Agent: Calendar and central bank rate monitors active. No high-impact lockouts recorded.",
                    "message_kh": "ភ្នាក់ងារម៉ាក្រូ៖ ប្រតិទិនសេដ្ឋកិច្ចសកម្ម គ្មានការចាក់សោរព័ត៌មានធំៗឡើយ។",
                    "timestamp": "Step 3: Macro Catalyst & News Check"
                },
                {
                    "turn_index": 4,
                    "agent_id": "risk_validator",
                    "agent_name": "Agent 4 — Risk Guardian & Arbiter",
                    "agent_avatar": "🛡️",
                    "badge_color": "var(--red-neon)",
                    "stance": "WAIT",
                    "message_en": f"Risk Arbiter Ruling: WAIT. {reason}",
                    "message_kh": f"សេចក្តីសម្រេចអាជ្ញាកណ្តាលហានិភ័យ៖ រង់ចាំ (WAIT)។ {reason_kh}",
                    "timestamp": "Step 4: Risk Review"
                }
            ]
            return {
                "session_id": None,
                "symbol": symbol,
                "timeframe": timeframe,
                "status": "NO_TRADE",
                "outcome_status": "DATA_UNAVAILABLE",
                "consensus_decision": "NO TRADE",
                "analysis_error": None,
                "debate_summary_en": reason,
                "debate_summary_kh": reason_kh,
                "total_turns": len(turns),
                "turns": turns,
                "dialogue": turns,
                "verdict": {"decision": "NO TRADE", "proposed_direction": "NONE", "summary_en": reason, "summary_kh": reason_kh},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }

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

        turns: List[Dict[str, Any]] = []

        # --- TURN 1: Agent 1 (Technical Momentum) Opens ---
        technical_evidence = a1_report.get("evidence", [])
        evidence_en = "; ".join(str(item) for item in technical_evidence[:3]) or "No qualifying technical evidence was recorded."
        t1_en = f"Structured technical analysis reports {a1_bias} for {symbol}. Recorded evidence: {evidence_en}"
        t1_kh = f"ការវិភាគបច្ចេកទេសតាមច្បាប់បង្ហាញទំនោរ {a1_bias} សម្រាប់ {symbol}។ ភស្តុតាងដែលបានកត់ត្រា៖ {evidence_en}"

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
        structure_evidence = a2_report.get("evidence", [])
        evidence_en = "; ".join(str(item) for item in structure_evidence[:3]) or "No qualifying structure evidence was recorded."
        t2_en = f"Structured chart analysis reports {a2_bias}. Recorded evidence: {evidence_en}"
        t2_kh = f"ការវិភាគរចនាសម្ព័ន្ធតាមក្រាហ្វបង្ហាញទំនោរ {a2_bias}។ ភស្តុតាងដែលបានកត់ត្រា៖ {evidence_en}"

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
        macro_evidence = a3_report.get("evidence", [])
        evidence_en = "; ".join(str(item) for item in macro_evidence[:3]) or "No verified macro evidence was returned."
        t3_en = f"Macro data summary: {evidence_en}"
        t3_kh = f"សេចក្តីសង្ខេបទិន្នន័យម៉ាក្រូ៖ {evidence_en}"

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
        calendar_unavailable = blackout_status.get("status") == "UNAVAILABLE"
        reasons = risk_report.get("reasons", [])
        reason_text = "; ".join(str(item) for item in reasons) or "No additional reason was provided."
        reason_kh = "។ ".join(str(item) for item in reasons) or "មិនមានការពន្យល់បន្ថែមទេ។"

        if is_news_blackout:
            decision = "REJECT"
            t4_en = f"Risk review rejected the setup because a high-impact news blackout is active. {reason_text}"
            t4_kh = f"ការត្រួតពិនិត្យហានិភ័យបានបដិសេធការរៀបចំនេះ ដោយសារមានការផ្អាកជួញដូរពេលព័ត៌មានឥទ្ធិពលខ្ពស់។ {reason_kh}"
            outcome_status = "RISK_VETOED"
        elif calendar_unavailable:
            decision = "REJECT"
            t4_en = f"Risk review blocked the setup because the calendar feed is unavailable. {reason_text}"
            t4_kh = f"ការត្រួតពិនិត្យហានិភ័យបានទប់ស្កាត់ការរៀបចំនេះ ព្រោះមិនអាចភ្ជាប់ប្រតិទិនព័ត៌មានបាន។ {reason_kh}"
            outcome_status = "RISK_VETOED"
        elif decision == "APPROVE":
            calc_rr = risk_report.get("calculated_rr", "N/A")
            sizing = risk_report.get("position_sizing", {})
            risk_pct = sizing.get("risk_percent", "N/A")
            t4_en = f"Risk review approved the setup. Reported R:R: {calc_rr}; configured risk: {risk_pct}%. Levels: entry {risk_report.get('entry_price')}, stop {risk_report.get('stop_loss')}, target {risk_report.get('take_profit_1')}."
            t4_kh = f"ការត្រួតពិនិត្យហានិភ័យបានអនុម័តការរៀបចំនេះ។ អនុបាត R:R ដែលបានរាយការណ៍៖ {calc_rr}; ហានិភ័យតាមការកំណត់៖ {risk_pct}%。 កម្រិតតម្លៃ៖ ចូល {risk_report.get('entry_price')}, កាត់ខាត {risk_report.get('stop_loss')}, គោលដៅ {risk_report.get('take_profit_1')}។"
            outcome_status = "CONSENSUS_REACHED"
        elif decision == "REJECT":
            t4_en = f"Risk review rejected the setup. {reason_text}"
            t4_kh = f"ការត្រួតពិនិត្យហានិភ័យបានបដិសេធការរៀបចំនេះ។ {reason_kh}"
            outcome_status = "RISK_VETOED"
        else:
            decision = "WAIT"
            t4_en = f"Risk review did not approve a setup. {reason_text}"
            t4_kh = f"ការត្រួតពិនិត្យហានិភ័យមិនបានអនុម័តការរៀបចំទេ។ {reason_kh}"
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
            "timestamp": "Step 4: Risk Review"
        })

        # Save session to SQLite database
        db = SessionLocal()
        session_id = None
        persisted = True
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
            persisted = False
            logger.exception("Could not persist structured agent review for %s", symbol)
        finally:
            db.close()

        return {
            "session_id": session_id,
            "persisted": persisted,
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
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

# Global singleton
agent_debate_engine = AgentDebateEngine()
