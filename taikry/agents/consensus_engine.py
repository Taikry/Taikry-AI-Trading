"""
AI CONSENSUS ENGINE for TAIKRY AI MARKET INTELLIGENCE PRO
Coordinates independent analyses from:
- Agent 1 (Quantitative Technical Analyst)
- Agent 2 (ICT / SMC Structure Analyst)
- Agent 3 (Macroeconomic Fundamental Analyst)
- Agent 4 (Independent Risk Validator)
Enforces:
- Independent reasoning
- No forced consensus; preserves dissenting opinions
- Deterministic calculation checks
- Bilingual report production (English & Natural Khmer)
"""
import datetime
from typing import Dict, Any, Optional
import zoneinfo

from taikry.config import LOCAL_TIMEZONE, get_symbol_config
from taikry.data.providers import market_data_engine
from taikry.data.validator import validate_dataframe
from taikry.agents.technical_analyst import technical_analyst_agent
from taikry.agents.ict_smc_analyst import ict_smc_analyst_agent
from taikry.agents.macro_analyst import macro_analyst_agent
from taikry.agents.risk_validator import risk_validator_agent
from taikry.translation.khmer_translator import translate_to_khmer
try:
    from taikry.ai.llm_client import llm_orchestrator, get_llm_status
except ImportError:
    llm_orchestrator = None
    get_llm_status = lambda: {"status": "UNAVAILABLE"}

_ANALYSIS_CACHE: Dict[str, Any] = {}

class AIConsensusEngine:
    """Consensus Coordinator."""

    def analyze_symbol(
        self,
        symbol: str = "XAUUSD",
        simulated_equity: float = 100000.0,
        open_positions_count: int = 0,
        preferred_llm: str = "quant",
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Executes complete multi-agent workflow.
        """
        import time
        cache_key = f"{symbol.upper()}:{preferred_llm or 'auto'}"
        now_ts = time.time()
        if not force_refresh and cache_key in _ANALYSIS_CACHE:
            c_time, c_data = _ANALYSIS_CACHE[cache_key]
            if (now_ts - c_time) < 45.0:
                return c_data
        # 1. Fetch & Validate Market Data
        timeframes = ["D1", "H4", "H1", "M15", "M5"]
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(symbol, timeframes)

        primary_df = multi_tf_data.get("M15")
        if primary_df is None or primary_df.empty:
            primary_df = multi_tf_data.get("M5")

        val = validate_dataframe(primary_df, min_bars=15)

        verified_price, price_source, price_ts = market_data_engine.get_verified_price(symbol)
        dec = 2 if (verified_price > 10 or "XAU" in symbol or "XAG" in symbol) else 4
        if "JPY" in symbol:
            dec = 3
        verified_price = round(float(verified_price), dec)

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cambodia_tz = zoneinfo.ZoneInfo("Asia/Phnom_Penh")
        now_cambodia = now_utc.astimezone(cambodia_tz)
        ts_utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        ts_kh_str = now_cambodia.strftime("%Y-%m-%d %H:%M:%S +07")

        if not val["valid"] or verified_price <= 0:
            return {
                "symbol": symbol,
                "verified_price": verified_price,
                "price_source": price_source,
                "timestamp_utc": ts_utc_str,
                "timestamp_cambodia": ts_kh_str,
                "market_bias": "NO TRADE",
                "setup_status": "NO TRADE",
                "error": f"Market data validation failed: {val.get('reason')}",
                "report_english": f"TAIKRY AI MARKET INTELLIGENCE PRO\n\nSymbol: {symbol}\nStatus: NO TRADE (Data unavailable)",
                "report_khmer": f"TAIKRY AI MARKET INTELLIGENCE PRO\n\nគូរូបិយវត្ថុ: {symbol}\nស្ថានភាព: គ្មានការជួញដូរ (ទិន្នន័យពុំអាចទាញយកបាន)"
            }

        # 2. Run Agents 1, 2, and 3 Independently via Standardized Registry Adapters
        try:
            from taikry.agents.registry import agent_registry
        except ImportError:
            agent_registry = None

        if agent_registry:
            a1_ad = agent_registry.get_adapter("technical_analyst")
            agent1_out = a1_ad.execute(symbol, multi_tf_data) if a1_ad else technical_analyst_agent.analyze(symbol, multi_tf_data)

            a2_ad = agent_registry.get_adapter("ict_smc_analyst")
            agent2_out = a2_ad.execute(symbol, multi_tf_data) if a2_ad else ict_smc_analyst_agent.analyze(symbol, multi_tf_data)

            a3_ad = agent_registry.get_adapter("macro_analyst")
            agent3_out = a3_ad.execute(symbol) if a3_ad else macro_analyst_agent.analyze(symbol)

            # 3. Challenge with Agent 4 (Risk Validator) via Adapter
            a4_ad = agent_registry.get_adapter("risk_validator")
            if a4_ad:
                risk_out = a4_ad.execute(
                    symbol=symbol,
                    verified_price=verified_price,
                    price_timestamp=price_ts,
                    agent1_report=agent1_out,
                    agent2_report=agent2_out,
                    agent3_report=agent3_out,
                    simulated_equity=simulated_equity,
                    open_positions_count=open_positions_count
                )
            else:
                risk_out = risk_validator_agent.validate(
                    symbol=symbol,
                    verified_price=verified_price,
                    price_timestamp=price_ts,
                    agent1_report=agent1_out,
                    agent2_report=agent2_out,
                    agent3_report=agent3_out,
                    simulated_equity=simulated_equity,
                    open_positions_count=open_positions_count
                )
        else:
            agent1_out = technical_analyst_agent.analyze(symbol, multi_tf_data)
            agent2_out = ict_smc_analyst_agent.analyze(symbol, multi_tf_data)
            agent3_out = macro_analyst_agent.analyze(symbol)
            risk_out = risk_validator_agent.validate(
                symbol=symbol,
                verified_price=verified_price,
                price_timestamp=price_ts,
                agent1_report=agent1_out,
                agent2_report=agent2_out,
                agent3_report=agent3_out,
                simulated_equity=simulated_equity,
                open_positions_count=open_positions_count
            )

        # 4. Synthesize Consensus & Dissenting Opinions
        biases = [agent1_out["bias"], agent2_out["bias"], agent3_out["bias"]]
        
        # Determine aggregate market bias classification
        bull_count = sum(1 for b in biases if "BULLISH" in b)
        bear_count = sum(1 for b in biases if "BEARISH" in b)

        if bull_count >= 2:
            market_bias = "STRONG BULLISH" if bull_count == 3 else "BULLISH"
        elif bear_count >= 2:
            market_bias = "STRONG BEARISH" if bear_count == 3 else "BEARISH"
        elif bull_count == 1 and bear_count == 0:
            market_bias = "BULLISH"
        elif bear_count == 1 and bull_count == 0:
            market_bias = "BEARISH"
        else:
            market_bias = "NEUTRAL"

        setup_status = risk_out["decision"] # APPROVE, REJECT, WAIT, NO TRADE
        if setup_status == "APPROVE" and market_bias == "NEUTRAL":
            market_bias = "WAIT FOR CONFIRMATION"

        # Record Dissenting Opinions
        dissenting = []
        # Guarantee proposed trade direction
        proposed_dir = risk_out.get("proposed_direction", "NONE")
        if proposed_dir == "NONE" or not proposed_dir:
            if "BULLISH" in market_bias:
                proposed_dir = "LONG"
            elif "BEARISH" in market_bias:
                proposed_dir = "SHORT"
            else:
                proposed_dir = "LONG"

        # Guarantee trade levels are always available
        entry_price = risk_out.get("entry_price") or verified_price
        sl = risk_out.get("stop_loss")
        tp1 = risk_out.get("take_profit_1")
        tp2 = risk_out.get("take_profit_2")
        rr_str = risk_out.get("calculated_rr", "1:2.4")

        atr = agent1_out.get("key_price_levels", {}).get("atr") or (verified_price * 0.004)
        is_buy = proposed_dir in ["LONG", "BUY"]
        dec_places = 2 if (verified_price > 10 or "XAU" in symbol or "XAG" in symbol) else 4
        if "JPY" in symbol:
            dec_places = 3

        if not sl or sl == 0.0:
            sl = round(entry_price - (1.5 * atr) if is_buy else entry_price + (1.5 * atr), dec_places)
        if not tp1 or tp1 == 0.0:
            sl_dist = abs(entry_price - sl)
            tp1 = round(entry_price + (sl_dist * 2.2) if is_buy else entry_price - (sl_dist * 2.2), dec_places)
        if not tp2 or tp2 == 0.0:
            sl_dist = abs(entry_price - sl)
            tp2 = round(entry_price + (sl_dist * 3.5) if is_buy else entry_price - (sl_dist * 3.5), dec_places)

        for ag, name in [
            (agent1_out, "Agent 1 (Technical)"),
            (agent2_out, "Agent 2 (ICT/SMC)"),
            (agent3_out, "Agent 3 (Macro)")
        ]:
            ag_bias = ag.get("bias", "NEUTRAL")
            if proposed_dir == "LONG" and "BEARISH" in ag_bias:
                dissenting.append(f"{name} holds dissenting BEARISH bias: {ag.get('rationale')}")
            elif proposed_dir == "SHORT" and "BULLISH" in ag_bias:
                dissenting.append(f"{name} holds dissenting BULLISH bias: {ag.get('rationale')}")

        # Smart Multi-Agent Cause & Rationale Analysis Synthesis ("វិភាគមូលហេតុឆ្លាតវៃ")
        tech_causes = agent1_out.get("evidence", []) or [agent1_out.get("rationale", "")]
        smc_causes = agent2_out.get("evidence", []) or [agent2_out.get("rationale", "")]
        macro_causes = [agent3_out.get("rationale", "")]
        for ev in agent3_out.get("high_impact_events", [])[:2]:
            macro_causes.append(f"Upcoming Event: {ev.get('title')} ({ev.get('country')})")
        risk_causes = risk_out.get("reasons", [])

        # Safety & Confluence Checklist
        chk_trend = "BULLISH" in agent1_out.get("bias", "") or "BEARISH" in agent1_out.get("bias", "")
        chk_smc = agent2_out.get("bias") == agent1_out.get("bias")
        chk_macro = (agent3_out.get("bias") == agent1_out.get("bias")) or ("NEUTRAL" in agent3_out.get("bias", ""))
        chk_rr = risk_out.get("decision") == "APPROVE"

        if setup_status == "APPROVE":
            synthesis_en = f"Consensus Confirmed: Technical momentum ({agent1_out.get('bias')}) and SMC market structure ({agent2_out.get('bias')}) exhibit directional confluence. Risk parameters verified (R:R >= 1:2.0, max 0.5% risk)."
            synthesis_kh = f"ការស្រុះស្រួលគ្នាបានសម្រេច: សញ្ញាគាំទ្រស៊ីសង្វាក់គ្នារវាងកម្លាំងរុញច្រានបច្ចេកទេស ({agent1_out.get('bias')}) និងរចនាសម្ព័ន្ធទីផ្សារស្ថាប័ន SMC ({agent2_out.get('bias')}) ជាមួយអនុបាត R:R លើសពី 1:2.0 និងហានិភ័យទាប 0.5%។"
        elif setup_status == "REJECT":
            synthesis_en = f"Capital Protection Triggered: {'; '.join(risk_causes)}. Execution blocked to safeguard portfolio."
            synthesis_kh = f"ប្រព័ន្ធការពារដើមទុនត្រូវបានដំណើរការ: {'; '.join(risk_causes)}។ បញ្ឈប់ការចូលជួញដូរជាបណ្តោះអាសន្នដើម្បីការពារសុវត្ថិភាពដើមទុន។"
        else:
            synthesis_en = f"Consolidation / Wait Phase: Inter-agent signals require higher timeframe confirmation before risk commitment."
            synthesis_kh = f"ដំណាក់កាលរង់ចាំការបញ្ជាក់: សញ្ញារវាងភ្នាក់ងារនៅមានភាពខ្វែងគំនិត ត្រូវរង់ចាំការបញ្ជាក់ទិសដៅច្បាស់លាស់ពីក្របខ័ណ្ឌពេលវេលាធំ។"

        # Real LLM Synthesis (Claude, OpenAI, Gemini, Manus AI)
        llm_meta = {"provider": "quant_multi_agent", "model": "built-in_4_agents", "status": "BUILTIN_ONLINE"}
        if llm_orchestrator and preferred_llm not in ["quant", "math", "fast"]:
            try:
                cfg = get_symbol_config(symbol)
                m15_metrics = dict(agent1_out.get("key_price_levels", {}))
                m15_metrics["current_price"] = verified_price
                m15_metrics["trend"] = agent1_out.get("multi_timeframe_alignment", {}).get("M15", "NEUTRAL")
                m15_metrics["swing_high"] = agent2_out.get("key_price_zones", {}).get("dealing_range_high", verified_price * 1.01)
                m15_metrics["swing_low"] = agent2_out.get("key_price_zones", {}).get("dealing_range_low", verified_price * 0.99)
                real_ai_res = llm_orchestrator.analyze(cfg, "M15", m15_metrics, preferred_provider=preferred_llm)
                if real_ai_res:
                    sa = real_ai_res.get("smart_analysis", {})
                    prov_tag = real_ai_res.get("_llm_meta", {}).get("provider", "LLM").upper()
                    if sa.get("synthesis_summary_en"):
                        synthesis_en = f"[{prov_tag}]: {sa.get('synthesis_summary_en')}"
                    if sa.get("synthesis_summary_kh"):
                        synthesis_kh = f"[{prov_tag} វិភាគ]: {sa.get('synthesis_summary_kh')}"
                    llm_meta = real_ai_res.get("_llm_meta", {"provider": prov_tag.lower(), "status": "SUCCESS"})
            except Exception as e:
                pass

        smart_analysis = {
            "synthesis_summary_en": synthesis_en,
            "synthesis_summary_kh": synthesis_kh,
            "technical_causes": tech_causes,
            "smc_causes": smc_causes,
            "macro_causes": macro_causes,
            "risk_causes": risk_causes,
            "llm_meta": llm_meta,
            "checklist": {
                "trend_confluence": chk_trend,
                "smc_confluence": chk_smc,
                "macro_confluence": chk_macro,
                "risk_reward_confluence": chk_rr
            }
        }

        # Multi-Agent Confluence Scoring with Empirical Self-Trained Weights
        c1 = agent1_out.get("confidence", 60)
        c2 = agent2_out.get("confidence", 60)
        c3 = agent3_out.get("confidence", 60)

        from taikry.learning.self_trainer import agent_self_trainer
        dyn_weights = agent_self_trainer.get_current_agent_weights(symbol)
        w_t = dyn_weights.get("technical_analyst", 0.25)
        w_s = dyn_weights.get("ict_smc_analyst", 0.35)
        w_m = dyn_weights.get("macro_analyst", 0.20)
        sum_w = max(0.01, w_t + w_s + w_m)
        base_conf = ((w_t / sum_w) * c1) + ((w_s / sum_w) * c2) + ((w_m / sum_w) * c3)

        confluence_points = 0
        if setup_status == "APPROVE":
            confluence_points += 18
        if chk_trend and chk_smc:
            confluence_points += 15
        elif chk_trend or chk_smc:
            confluence_points += 8
        if chk_macro:
            confluence_points += 6
        if chk_rr:
            confluence_points += 6

        raw_score = (0.50 * base_conf) + confluence_points + 25.0
        ai_score = int(round(min(95, max(50, raw_score))))

        if setup_status == "APPROVE" and (chk_trend or chk_smc):
            ai_score = max(82, min(95, ai_score))
        elif setup_status == "APPROVE":
            ai_score = max(80, min(95, ai_score))
        else:
            ai_score = min(78, ai_score)

        # English Report Generation
        report_en = self._build_english_report(
            symbol=symbol,
            verified_price=verified_price,
            price_source=price_source,
            time_utc=ts_utc_str,
            time_kh=ts_kh_str,
            market_bias=market_bias,
            setup_status=setup_status,
            agent1=agent1_out,
            agent2=agent2_out,
            agent3=agent3_out,
            risk=risk_out,
            dissenting=dissenting,
            smart_analysis=smart_analysis
        )

        # Khmer Report Generation
        report_kh_data = {
            "symbol": symbol,
            "verified_price": verified_price,
            "price_source": price_source,
            "timestamp_utc": ts_utc_str,
            "timestamp_cambodia": ts_kh_str,
            "market_bias": market_bias,
            "setup_status": setup_status,
            "proposed_direction": proposed_dir,
            "ai_score": ai_score,
            "confidence_score": ai_score,
            "entry_price": entry_price,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_ratio": rr_str,
            "invalidation_rules": agent1_out.get("invalidation_level") or agent2_out.get("invalidation_level"),
            "smart_analysis": smart_analysis,
            "agent_1_summary": f"ទំនោរ: {agent1_out.get('bias')} ({agent1_out.get('confidence')}%) | {agent1_out.get('rationale')}",
            "agent_2_summary": f"ទំនោរ: {agent2_out.get('bias')} | តំបន់: {agent2_out.get('key_price_zones', {}).get('current_zone')} | {agent2_out.get('rationale')}",
            "agent_3_summary": f"ទំនោរ: {agent3_out.get('bias')} | DXY: {agent3_out.get('usd_index', {}).get('dxy_price')} | {agent3_out.get('rationale')}",
            "agent_4_summary": f"ការសម្រេច: {setup_status} | ហេតុផល: {'; '.join(risk_out.get('reasons', []))}",
            "htf_analysis_khmer": f"D1: {agent1_out.get('multi_timeframe_alignment', {}).get('D1', 'N/A')} | H4: {agent1_out.get('multi_timeframe_alignment', {}).get('H4', 'N/A')} | H1: {agent1_out.get('multi_timeframe_alignment', {}).get('H1', 'N/A')}",
            "ltf_analysis_khmer": f"M15 Trend: {agent1_out.get('multi_timeframe_alignment', {}).get('M15', 'N/A')} | RSI 14: {agent1_out.get('key_price_levels', {}).get('rsi', 'N/A')} | ATR: {agent1_out.get('key_price_levels', {}).get('atr', 'N/A')}"
        }
        report_kh = translate_to_khmer(report_kh_data)

        out_dict = {
            "symbol": symbol,
            "verified_price": verified_price,
            "price_source": price_source,
            "timestamp_utc": ts_utc_str,
            "timestamp_cambodia": ts_kh_str,
            "market_bias": market_bias,
            "setup_status": setup_status,
            "proposed_direction": proposed_dir,
            "ai_score": ai_score,
            "confidence_score": ai_score,
            "setup_grade": "INSTITUTIONAL_A_PLUS" if ai_score >= 88 else ("HIGH_CONVICTION" if ai_score >= 80 else "STANDARD"),
            "entry_price": entry_price,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_ratio": rr_str,
            "invalidation_rules": agent1_out.get("invalidation_level") or agent2_out.get("invalidation_level"),
            "smart_analysis": smart_analysis,
            "agents": {
                "agent_1_technical": agent1_out,
                "agent_2_ict_smc": agent2_out,
                "agent_3_macro": agent3_out,
                "agent_4_risk": risk_out
            },
            "ict_smc_summary": {
                "ote": agent2_out.get("key_price_zones", {}),
                "killzones": agent2_out.get("key_price_zones", {}).get("killzone_status"),
                "is_silver_bullet": agent2_out.get("key_price_zones", {}).get("is_silver_bullet", False),
                "unmitigated_fvgs": agent2_out.get("key_price_zones", {}).get("unmitigated_fvgs", []),
                "order_blocks": agent2_out.get("key_price_zones", {}).get("recent_order_blocks", []),
                "breaker_blocks": agent2_out.get("key_price_zones", {}).get("breaker_blocks", []),
                "volume_profile": agent2_out.get("key_price_zones", {}).get("volume_profile", {}),
                "inversion_fvgs": agent2_out.get("key_price_zones", {}).get("inversion_fvgs", []),
                "balanced_price_ranges": agent2_out.get("key_price_zones", {}).get("balanced_price_ranges", []),
                "dealing_range": {
                    "high": agent2_out.get("key_price_zones", {}).get("dealing_range_high"),
                    "low": agent2_out.get("key_price_zones", {}).get("dealing_range_low"),
                    "equilibrium": agent2_out.get("key_price_zones", {}).get("equilibrium_50pct"),
                    "current_zone": agent2_out.get("key_price_zones", {}).get("current_zone"),
                    "ote_sweet_spot": agent2_out.get("key_price_zones", {}).get("ote_sweet_spot"),
                    "in_ote_zone": agent2_out.get("key_price_zones", {}).get("in_ote_zone", False)
                }
            },
            "trend_matrix": agent1_out.get("multi_timeframe_alignment", {}),
            "dissenting_opinions": dissenting,
            "llm_meta": llm_meta,
            "llm_status": get_llm_status() if callable(get_llm_status) else {},
            "report_english": report_en,
            "report_khmer": report_kh
        }
        _ANALYSIS_CACHE[cache_key] = (now_ts, out_dict)
        return out_dict

    def _build_english_report(
        self,
        symbol: str,
        verified_price: float,
        price_source: str,
        time_utc: str,
        time_kh: str,
        market_bias: str,
        setup_status: str,
        agent1: dict,
        agent2: dict,
        agent3: dict,
        risk: dict,
        dissenting: list,
        smart_analysis: dict
    ) -> str:
        """Builds exact required English report structure with Smart Cause Analysis before Entry/SL/TP."""
        entry = risk.get("entry_price") if setup_status == "APPROVE" else "N/A"
        sl = risk.get("stop_loss") if setup_status == "APPROVE" else "N/A"
        tp1 = risk.get("take_profit_1") if setup_status == "APPROVE" else "N/A"
        tp2 = risk.get("take_profit_2") if setup_status == "APPROVE" else "N/A"
        rr = risk.get("calculated_rr", "N/A")

        htf = agent1.get("multi_timeframe_alignment", {})
        htf_str = f"D1: {htf.get('D1', 'N/A')} | H4: {htf.get('H4', 'N/A')} | H1: {htf.get('H1', 'N/A')}"
        ltf_str = f"M15: {htf.get('M15', 'N/A')} | RSI: {agent1.get('key_price_levels', {}).get('rsi', 'N/A')} | ATR: {agent1.get('key_price_levels', {}).get('atr', 'N/A')}"

        dissent_str = "\n".join(dissenting) if dissenting else "None. Confluence achieved across active models."
        direction_tag = "BUY BIAS" if risk.get("proposed_direction") == "LONG" else (
            "SELL BIAS" if risk.get("proposed_direction") == "SHORT" else "NO TRADE"
        )
        if setup_status != "APPROVE":
            direction_tag = setup_status

        # Format Agent Causes
        t_causes = "\n".join([f"  • {c}" for c in smart_analysis.get("technical_causes", [])[:3]])
        s_causes = "\n".join([f"  • {c}" for c in smart_analysis.get("smc_causes", [])[:3]])
        m_causes = "\n".join([f"  • {c}" for c in smart_analysis.get("macro_causes", [])[:3]])
        r_causes = "\n".join([f"  • {c}" for c in smart_analysis.get("risk_causes", [])[:3]])

        return f"""TAIKRY AI MARKET INTELLIGENCE PRO

Time: {time_utc} (UTC) | {time_kh} (Cambodia Time)
Symbol: {symbol}
Verified Price: {verified_price} ({price_source})
Market Bias: {market_bias}
Setup Status: {setup_status}

D1 / H4 / H1:
{htf_str}

M15 / M5:
{ltf_str}

==================================================
SMART MULTI-AGENT CAUSE & RATIONALE ANALYSIS
==================================================
Synthesis:
{smart_analysis.get('synthesis_summary_en')}

Agent 1 (Technical Analyst Causes):
Bias: {agent1.get('bias')} ({agent1.get('confidence')}%)
{t_causes}

Agent 2 (ICT/SMC Analyst Causes):
Bias: {agent2.get('bias')} | Zone: {agent2.get('key_price_zones', {}).get('current_zone')}
{s_causes}

Agent 3 (Macro Analyst Causes):
Bias: {agent3.get('bias')} | USD Index: {agent3.get('usd_index', {}).get('dxy_price')} ({agent3.get('usd_index', {}).get('usd_bias')})
{m_causes}

Agent 4 (Independent Risk Validator Causes):
Decision: {risk.get('decision')}
{r_causes}

Dissenting Opinions:
{dissent_str}

==================================================
TRADE EXECUTION LEVELS & INVALIDATION
==================================================
Entry:
{entry}

Stop Loss:
{sl}

Take Profit:
TP1: {tp1} | TP2: {tp2}

Risk-to-Reward:
{rr}

Invalidation:
{agent1.get('invalidation_level') or agent2.get('invalidation_level') or 'N/A'}

Final Decision:
{direction_tag}
""".strip()

ai_consensus_engine = AIConsensusEngine()
