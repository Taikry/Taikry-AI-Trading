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
import math
from typing import Dict, Any, Optional
import zoneinfo

from taikry.config import INITIAL_PAPER_BALANCE, LOCAL_TIMEZONE, MIN_RISK_REWARD_RATIO, RISK_PER_TRADE_PERCENT, get_symbol_config
from taikry.data.providers import market_data_engine
from taikry.data.validator import validate_dataframe, check_data_freshness
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
        simulated_equity: float = INITIAL_PAPER_BALANCE,
        open_positions_count: Optional[int] = None,
        preferred_llm: str = "quant",
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Executes complete multi-agent workflow.
        """
        import time
        t_start = time.time()
        cache_key = f"{symbol.upper()}:{preferred_llm or 'auto'}"
        now_ts = t_start
        if not force_refresh and cache_key in _ANALYSIS_CACHE:
            c_time, c_data = _ANALYSIS_CACHE[cache_key]
            if (now_ts - c_time) < 45.0:
                ret = dict(c_data)
                ret["performance"] = {
                    "parallel_execution": True,
                    "concurrency_level": 5,
                    "cached": True,
                    "latency_ms": round((time.time() - t_start) * 1000, 2)
                }
                return ret
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
        ts_utc_str = now_utc.isoformat()
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

        synthetic_timeframes = [
            tf for tf, frame in multi_tf_data.items()
            if frame is None or frame.empty or ("source" in frame.columns and frame["source"].astype(str).str.upper().str.contains("SYNTHETIC|DEMO").any())
        ]
        freshness = check_data_freshness(symbol, primary_df.iloc[-1].get("timestamp"), "M15")
        if synthetic_timeframes or not freshness.get("fresh") or any(marker in str(price_source).upper() for marker in ("SYNTHETIC", "DEMO", "UNAVAILABLE")):
            reason = "Synthetic or stale market data is not eligible for actionable analysis."
            return {
                "symbol": symbol,
                "verified_price": verified_price,
                "price_source": price_source,
                "timestamp_utc": ts_utc_str,
                "timestamp_cambodia": ts_kh_str,
                "market_bias": "NO TRADE",
                "setup_status": "NO TRADE",
                "proposed_direction": "NONE",
                "entry_price": None,
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "error": reason,
                "data_quality": {"synthetic_timeframes": synthetic_timeframes, "freshness": freshness},
                "report_english": f"TAIKRY AI MARKET INTELLIGENCE PRO\n\nSymbol: {symbol}\nStatus: NO TRADE ({reason})",
                "report_khmer": f"TAIKRY AI MARKET INTELLIGENCE PRO\n\nគូរូបិយវត្ថុ: {symbol}\nស្ថានភាព: គ្មានការជួញដូរ (ទិន្នន័យសិប្បនិម្មិត ឬចាស់ មិនអាចប្រើសម្រាប់សញ្ញាជួញដូរបានទេ)"
            }

        # 2. Run Agents 1, 2, 3, 8, and 9 Concurrently via Standardized Adapters & ThreadPool
        from concurrent.futures import ThreadPoolExecutor
        from taikry.agents.orderflow_sentiment_analyst import orderflow_sentiment_agent
        from taikry.agents.fractal_mtf_analyst import fractal_mtf_agent

        try:
            from taikry.agents.registry import agent_registry
        except ImportError:
            agent_registry = None

        if agent_registry:
            a1_ad = agent_registry.get_adapter("technical_analyst")
            a2_ad = agent_registry.get_adapter("ict_smc_analyst")
            a3_ad = agent_registry.get_adapter("macro_analyst")
            a8_ad = agent_registry.get_adapter("orderflow_sentiment_analyst")
            a9_ad = agent_registry.get_adapter("fractal_mtf_analyst")

            def _run_a1():
                return a1_ad.execute(symbol, multi_tf_data) if a1_ad else technical_analyst_agent.analyze(symbol, multi_tf_data)

            def _run_a2():
                return a2_ad.execute(symbol, multi_tf_data) if a2_ad else ict_smc_analyst_agent.analyze(symbol, multi_tf_data)

            def _run_a3():
                return a3_ad.execute(symbol) if a3_ad else macro_analyst_agent.analyze(symbol)

            def _run_a8():
                return a8_ad.execute(symbol=symbol, df_m15=primary_df, verified_price=verified_price) if a8_ad else orderflow_sentiment_agent.analyze(symbol, primary_df, verified_price)

            def _run_a9():
                return a9_ad.execute(symbol=symbol, multi_tf_data=multi_tf_data) if a9_ad else fractal_mtf_agent.analyze(symbol, multi_tf_data)

            with ThreadPoolExecutor(max_workers=5) as executor:
                fut1 = executor.submit(_run_a1)
                fut2 = executor.submit(_run_a2)
                fut3 = executor.submit(_run_a3)
                fut8 = executor.submit(_run_a8)
                fut9 = executor.submit(_run_a9)
                agent1_out = fut1.result()
                agent2_out = fut2.result()
                agent3_out = fut3.result()
                agent8_out = fut8.result()
                agent9_out = fut9.result()

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
            with ThreadPoolExecutor(max_workers=5) as executor:
                fut1 = executor.submit(technical_analyst_agent.analyze, symbol, multi_tf_data)
                fut2 = executor.submit(ict_smc_analyst_agent.analyze, symbol, multi_tf_data)
                fut3 = executor.submit(macro_analyst_agent.analyze, symbol)
                fut8 = executor.submit(orderflow_sentiment_agent.analyze, symbol, primary_df, verified_price)
                fut9 = executor.submit(fractal_mtf_agent.analyze, symbol, multi_tf_data)
                agent1_out = fut1.result()
                agent2_out = fut2.result()
                agent3_out = fut3.result()
                agent8_out = fut8.result()
                agent9_out = fut9.result()

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
        # Keep neutral and rejected analyses directionless.
        proposed_dir = risk_out.get("proposed_direction", "NONE")
        if proposed_dir not in ("LONG", "SHORT", "BUY", "SELL") or setup_status != "APPROVE":
            proposed_dir = "NONE"

        entry_price = risk_out.get("entry_price") if setup_status == "APPROVE" else None
        sl = risk_out.get("stop_loss") if setup_status == "APPROVE" else None
        tp1 = risk_out.get("take_profit_1") if setup_status == "APPROVE" else None
        tp2 = risk_out.get("take_profit_2") if setup_status == "APPROVE" else None
        rr_str = risk_out.get("calculated_rr", "N/A") if setup_status == "APPROVE" else "N/A"

        orderflow_dict = agent8_out.model_dump() if hasattr(agent8_out, "model_dump") else agent8_out
        fractal_dict = agent9_out.model_dump() if hasattr(agent9_out, "model_dump") else agent9_out

        for ag, name in [
            (agent1_out, "Agent 1 (Technical)"),
            (agent2_out, "Agent 2 (ICT/SMC)"),
            (agent3_out, "Agent 3 (Macro)"),
            (orderflow_dict, "Agent 8 (Order Flow)"),
            (fractal_dict, "Agent 9 (Fractal MTF)")
        ]:
            ag_bias = ag.get("bias") or ag.get("overall_direction", "NEUTRAL")
            if proposed_dir == "LONG" and "BEARISH" in str(ag_bias):
                dissenting.append(f"{name} holds dissenting BEARISH bias: {ag.get('rationale_en') or ag.get('rationale')}")
            elif proposed_dir == "SHORT" and "BULLISH" in str(ag_bias):
                dissenting.append(f"{name} holds dissenting BULLISH bias: {ag.get('rationale_en') or ag.get('rationale')}")

        if fractal_dict.get("trap_detected"):
            dissenting.append(f"Agent 9 (Fractal Defense): {fractal_dict.get('trap_description')}")

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
            synthesis_en = f"Consensus Confirmed: Technical momentum ({agent1_out.get('bias')}) and SMC market structure ({agent2_out.get('bias')}) exhibit directional confluence. Risk parameters verified against configured minimum R:R 1:{MIN_RISK_REWARD_RATIO} and maximum risk {RISK_PER_TRADE_PERCENT}%."
            synthesis_kh = f"ការស្រុះស្រួលគ្នាបានសម្រេច៖ សញ្ញាបច្ចេកទេស ({agent1_out.get('bias')}) និងរចនាសម្ព័ន្ធតម្លៃ ({agent2_out.get('bias')}) បង្ហាញទិសដៅស្របគ្នា។ ហានិភ័យត្រូវបានផ្ទៀងផ្ទាត់តាម R:R អប្បបរមា 1:{MIN_RISK_REWARD_RATIO} និងកម្រិតហានិភ័យអតិបរមា {RISK_PER_TRADE_PERCENT}%。"
        elif setup_status == "REJECT":
            synthesis_en = f"Capital Protection Triggered: {'; '.join(risk_causes)}. Execution blocked to safeguard portfolio."
            synthesis_kh = f"ប្រព័ន្ធការពារដើមទុនត្រូវបានដំណើរការ: {'; '.join(risk_causes)}។ បញ្ឈប់ការចូលជួញដូរជាបណ្តោះអាសន្នដើម្បីការពារសុវត្ថិភាពដើមទុន។"
        else:
            synthesis_en = f"Consolidation / Wait Phase: Inter-agent signals require higher timeframe confirmation before risk commitment."
            synthesis_kh = f"ដំណាក់កាលរង់ចាំការបញ្ជាក់: សញ្ញារវាងភ្នាក់ងារនៅមានភាពខ្វែងគំនិត ត្រូវរង់ចាំការបញ្ជាក់ទិសដៅច្បាស់លាស់ពីក្របខ័ណ្ឌពេលវេលាធំ។"

        # Real LLM Synthesis (Claude, OpenAI, Gemini, Manus AI)
        llm_meta = {
            "provider": "deterministic_multi_agent",
            "model": "python_technical_smc_macro_risk_agents",
            "status": "DETERMINISTIC_ONLY",
            "llm_call_made": False,
        }
        if llm_orchestrator and preferred_llm not in ["quant", "math", "fast"]:
            llm_meta = {
                "provider": "llm_orchestrator",
                "model": None,
                "status": "ATTEMPTED",
                "llm_call_made": True,
            }
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
                    llm_meta = {
                        **llm_meta,
                        **real_ai_res.get("_llm_meta", {"provider": prov_tag.lower(), "status": "SUCCESS"}),
                        "llm_call_made": True,
                    }
                else:
                    llm_meta["status"] = "UNAVAILABLE_OR_FALLBACK"
            except Exception as e:
                llm_meta["status"] = "ERROR"
                llm_meta["error_type"] = type(e).__name__

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

        # Report the weighted confidence actually returned by the contributing
        # agents. Do not add approval bonuses or floor scores into the alert band.
        from taikry.learning.self_trainer import agent_self_trainer
        dyn_weights = agent_self_trainer.get_current_agent_weights(symbol)
        confidence_terms = []
        for agent_id, agent_output in (
            ("technical_analyst", agent1_out),
            ("ict_smc_analyst", agent2_out),
            ("macro_analyst", agent3_out),
        ):
            try:
                confidence = float(agent_output.get("confidence"))
                weight = float(dyn_weights.get(agent_id, 1.0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(confidence) and 0 <= confidence <= 100 and math.isfinite(weight) and weight > 0:
                confidence_terms.append((confidence, weight))

        total_confidence_weight = sum(weight for _, weight in confidence_terms)
        ai_score = int(round(
            sum(confidence * weight for confidence, weight in confidence_terms) / total_confidence_weight
        )) if total_confidence_weight else 0

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
            "agent_3_summary": f"ទំនោរ: {agent3_out.get('bias')} | DXY: {agent3_out.get('usd_index', {}).get('dxy_price') if agent3_out.get('usd_index', {}).get('dxy_price') is not None else 'N/A'} | {agent3_out.get('rationale')}",
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
            "score_explanation": "Weighted mean of valid technical, SMC, and macro agent confidence inputs; heuristic score, not a calibrated win probability.",
            "setup_grade": "HIGH_CONVICTION" if ai_score >= 80 else "STANDARD",
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
                "agent_4_risk": risk_out,
                "agent_8_orderflow": orderflow_dict,
                "agent_9_fractal_mtf": fractal_dict
            },
            "agent_fleet_count": 9,
            "performance": {
                "parallel_execution": True,
                "concurrency_level": 5,
                "cached": False,
                "latency_ms": round((time.time() - t_start) * 1000, 2)
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
