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
        force_refresh: bool = False,
        trade_style: str = "INTRADAY"
    ) -> Dict[str, Any]:
        """
        Executes complete multi-agent workflow.
        """
        import time
        t_start = time.time()
        trade_style = str(trade_style or "INTRADAY").strip().upper()
        if trade_style not in {"INTRADAY", "SWING"}:
            raise ValueError("trade_style must be INTRADAY or SWING")
        cache_key = f"{symbol.upper()}:{preferred_llm or 'auto'}" + (":SWING" if trade_style == "SWING" else "")
        now_ts = t_start
        if not force_refresh and cache_key in _ANALYSIS_CACHE:
            c_time, c_data = _ANALYSIS_CACHE[cache_key]
            if (now_ts - c_time) < 45.0:
                ret = dict(c_data)
                ret["performance"] = {
                    "parallel_execution": True,
                    "concurrency_level": 9,
                    "cached": True,
                    "latency_ms": round((time.time() - t_start) * 1000, 2)
                }
                return ret
        # 1. Fetch & Validate Market Data
        timeframes = ["W1", "D1", "H4", "H1", "M15", "M5"]
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(symbol, timeframes)

        setup_timeframe = "H4" if trade_style == "SWING" else "M15"
        primary_df = multi_tf_data.get(setup_timeframe)
        if primary_df is None or primary_df.empty:
            primary_df = multi_tf_data.get("M5") if trade_style == "INTRADAY" else None

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
        required_timeframes = ["W1", "D1", "H4", "H1"] if trade_style == "SWING" else ["D1", "H4", "H1", "M15", "M5"]
        required_synthetic = [tf for tf in required_timeframes if tf in synthetic_timeframes]
        freshness = check_data_freshness(symbol, primary_df.iloc[-1].get("timestamp"), setup_timeframe)
        if required_synthetic or not freshness.get("fresh") or any(marker in str(price_source).upper() for marker in ("SYNTHETIC", "DEMO", "UNAVAILABLE")):
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
                "trade_style": trade_style,
                "data_quality": {"synthetic_timeframes": required_synthetic, "freshness": freshness},
                "report_english": f"TAIKRY AI MARKET INTELLIGENCE PRO\n\nSymbol: {symbol}\nStatus: NO TRADE ({reason})",
                "report_khmer": f"TAIKRY AI MARKET INTELLIGENCE PRO\n\nគូរូបិយវត្ថុ: {symbol}\nស្ថានភាព: គ្មានការជួញដូរ (ទិន្នន័យសិប្បនិម្មិត ឬចាស់ មិនអាចប្រើសម្រាប់សញ្ញាជួញដូរបានទេ)"
            }

        # 2. Run the data guardian and all eight directional analysts on this
        # exact snapshot. Candidate-dependent specialists run after a plan exists.
        from concurrent.futures import ThreadPoolExecutor
        from taikry.agents.data_quality_agent import data_quality_agent
        from taikry.agents.orderflow_sentiment_analyst import orderflow_sentiment_agent
        from taikry.agents.fractal_mtf_analyst import fractal_mtf_agent
        from taikry.agents.regime_detection_agent import regime_detection_agent
        from taikry.agents.quantitative_research_agent import quantitative_research_agent
        from taikry.agents.ml_forecast_agent import ml_forecast_agent
        from taikry.agents.concept_recommender import concept_recommender

        try:
            from taikry.agents.registry import agent_registry
        except ImportError:
            agent_registry = None
        if agent_registry is None:
            raise RuntimeError("Agent registry is required for role-aware consensus execution.")

        if agent_registry:
            dq_ad = agent_registry.get_adapter("data_quality_agent")
            a1_ad = agent_registry.get_adapter("technical_analyst")
            a2_ad = agent_registry.get_adapter("ict_smc_analyst")
            a3_ad = agent_registry.get_adapter("macro_analyst")
            a8_ad = agent_registry.get_adapter("orderflow_sentiment_analyst")
            a9_ad = agent_registry.get_adapter("fractal_mtf_analyst")
            regime_ad = agent_registry.get_adapter("regime_detection_agent")
            quant_ad = agent_registry.get_adapter("quantitative_research_agent")
            ml_ad = agent_registry.get_adapter("ml_forecast_agent")
            concept_ad = agent_registry.get_adapter("concept_recommender")

            def _run_dq():
                return dq_ad.execute(
                    symbol=symbol,
                    timeframe=setup_timeframe,
                    market_snapshot={
                        "multi_tf_data": multi_tf_data,
                        "verified_price": verified_price,
                        "price_timestamp": price_ts,
                        "price_source": price_source,
                    },
                ) if dq_ad else data_quality_agent.analyze(
                    symbol=symbol,
                    timeframe=setup_timeframe,
                    market_snapshot={
                        "multi_tf_data": multi_tf_data,
                        "verified_price": verified_price,
                        "price_timestamp": price_ts,
                        "price_source": price_source,
                    },
                )

            def _run_a1():
                if trade_style == "SWING":
                    return a1_ad.execute(symbol, multi_tf_data, setup_timeframe=setup_timeframe) if a1_ad else technical_analyst_agent.analyze(symbol, multi_tf_data, setup_timeframe=setup_timeframe)
                return a1_ad.execute(symbol, multi_tf_data) if a1_ad else technical_analyst_agent.analyze(symbol, multi_tf_data)

            def _run_a2():
                if trade_style == "SWING":
                    return a2_ad.execute(symbol, multi_tf_data, setup_timeframe=setup_timeframe) if a2_ad else ict_smc_analyst_agent.analyze(symbol, multi_tf_data, setup_timeframe=setup_timeframe)
                return a2_ad.execute(symbol, multi_tf_data) if a2_ad else ict_smc_analyst_agent.analyze(symbol, multi_tf_data)

            def _run_a3():
                return a3_ad.execute(symbol) if a3_ad else macro_analyst_agent.analyze(symbol)

            def _run_a8():
                return a8_ad.execute(symbol=symbol, df_m15=primary_df, verified_price=verified_price) if a8_ad else orderflow_sentiment_agent.analyze(symbol, primary_df, verified_price)

            def _run_a9():
                return a9_ad.execute(symbol=symbol, multi_tf_data=multi_tf_data) if a9_ad else fractal_mtf_agent.analyze(symbol, multi_tf_data)

            def _run_regime():
                return regime_ad.execute(symbol=symbol, multi_tf_data=multi_tf_data) if regime_ad else regime_detection_agent.analyze(symbol, multi_tf_data)

            def _run_quant():
                return quant_ad.execute(symbol=symbol, multi_tf_data=multi_tf_data) if quant_ad else quantitative_research_agent.analyze(symbol, multi_tf_data)

            def _run_ml():
                return ml_ad.execute(symbol=symbol, multi_tf_data=multi_tf_data) if ml_ad else ml_forecast_agent.analyze(symbol, multi_tf_data)

            with ThreadPoolExecutor(max_workers=9) as executor:
                fut_dq = executor.submit(_run_dq)
                fut1 = executor.submit(_run_a1)
                fut2 = executor.submit(_run_a2)
                fut3 = executor.submit(_run_a3)
                fut8 = executor.submit(_run_a8)
                fut9 = executor.submit(_run_a9)
                fut_regime = executor.submit(_run_regime)
                fut_quant = executor.submit(_run_quant)
                fut_ml = executor.submit(_run_ml)
                data_quality_out = fut_dq.result()
                agent1_out = fut1.result()
                agent2_out = fut2.result()
                agent3_out = fut3.result()
                agent8_out = fut8.result()
                agent9_out = fut9.result()
                regime_out = fut_regime.result()
                quant_out = fut_quant.result()
                ml_out = fut_ml.result()

            # Agent outputs can be dictionaries or Pydantic models. Preserve
            # adapter fallback and source status instead of marking every return
            # as a healthy vote.
            def _as_report(output):
                if isinstance(output, dict):
                    return dict(output)
                if hasattr(output, "model_dump"):
                    return output.model_dump()
                if hasattr(output, "dict"):
                    return output.dict()
                raise TypeError(f"Unsupported agent report: {type(output).__name__}")

            def _track_report(agent_id, output):
                report = _as_report(output)
                source_status = str(report.get("status", "")).upper()
                execution_status = "FALLBACK" if report.get("_fallback_applied") else (
                    "DEGRADED" if source_status in {"ERROR", "FAILED", "UNAVAILABLE", "NOT_AVAILABLE", "DEGRADED", "STALE", "INVALID"} else "SUCCESS"
                )
                report["source_status"] = report.get("status")
                report["execution_status"] = execution_status
                report["agent_id"] = agent_id
                return report

            agent_reports = {
                "data_quality_agent": _track_report("data_quality_agent", data_quality_out),
                "technical_analyst": _track_report("technical_analyst", agent1_out),
                "ict_smc_analyst": _track_report("ict_smc_analyst", agent2_out),
                "macro_analyst": _track_report("macro_analyst", agent3_out),
                "orderflow_sentiment_analyst": _track_report("orderflow_sentiment_analyst", agent8_out),
                "fractal_mtf_analyst": _track_report("fractal_mtf_analyst", agent9_out),
                "regime_detection_agent": _track_report("regime_detection_agent", regime_out),
                "quantitative_research_agent": _track_report("quantitative_research_agent", quant_out),
                "ml_forecast_agent": _track_report("ml_forecast_agent", ml_out),
            }

            # Normalize specialist-specific labels into comparable signal votes.
            for agent_id, report in agent_reports.items():
                bias = str(report.get("bias", "NEUTRAL") or "NEUTRAL").upper().replace("_", " ")
                confidence = report.get("confidence", 50)
                if agent_id == "regime_detection_agent":
                    regime = str(report.get("regime", "UNKNOWN")).upper()
                    bias = "BULLISH" if "BULLISH" in regime else ("BEARISH" if "BEARISH" in regime else "NEUTRAL")
                    confidence = 65 if bias != "NEUTRAL" else 50
                elif agent_id == "quantitative_research_agent":
                    bias = "BULLISH" if bias in {"LONG", "BUY"} else ("BEARISH" if bias in {"SHORT", "SELL"} else "NEUTRAL")
                    confidence = report.get("mean_reversion_probability", 50) if bias != "NEUTRAL" else 50
                elif agent_id == "ml_forecast_agent":
                    predicted = str(report.get("predicted_direction", bias)).upper()
                    bias = "BULLISH" if predicted in {"BULLISH", "BUY", "LONG"} else ("BEARISH" if predicted in {"BEARISH", "SELL", "SHORT"} else "NEUTRAL")
                    confidence = report.get("confidence", confidence)
                elif agent_id == "fractal_mtf_analyst":
                    direction = str(report.get("overall_direction", "WAIT")).upper()
                    bias = "BULLISH" if direction in {"BUY", "BULLISH", "LONG"} else ("BEARISH" if direction in {"SELL", "BEARISH", "SHORT"} else "NEUTRAL")
                    confidence = report.get("confidence", confidence)
                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    confidence = 0.0
                if not math.isfinite(confidence):
                    confidence = 0.0
                report["bias"] = bias
                report["confidence"] = max(0.0, min(100.0, confidence))
                report["contributes_to_consensus"] = (
                    agent_id in {
                        "technical_analyst", "ict_smc_analyst", "macro_analyst",
                        "orderflow_sentiment_analyst", "fractal_mtf_analyst",
                        "regime_detection_agent", "quantitative_research_agent", "ml_forecast_agent",
                    }
                    and report["execution_status"] == "SUCCESS"
                )

            if (
                str(agent_reports["data_quality_agent"].get("feed_status", "")).upper() != "HEALTHY"
                or agent_reports["data_quality_agent"].get("is_fresh") is not True
            ):
                agent_reports["data_quality_agent"]["execution_status"] = "DEGRADED"

            data_quality_out = agent_reports["data_quality_agent"]
            agent1_out = agent_reports["technical_analyst"]
            agent2_out = agent_reports["ict_smc_analyst"]
            agent3_out = agent_reports["macro_analyst"]
            orderflow_dict = agent_reports["orderflow_sentiment_analyst"]
            fractal_dict = agent_reports["fractal_mtf_analyst"]
            regime_out = agent_reports["regime_detection_agent"]
            quant_out = agent_reports["quantitative_research_agent"]
            ml_out = agent_reports["ml_forecast_agent"]

            # The concept recommender consumes the completed analyst reports.
            if concept_ad:
                concept_out = concept_ad.execute(
                    symbol=symbol,
                    regime_data=regime_out,
                    technical_data=agent1_out,
                    smc_data=agent2_out,
                    quant_data=quant_out,
                    ml_data=ml_out,
                )
            else:
                concept_out = concept_recommender.evaluate_concepts(
                    symbol=symbol,
                    regime_data=regime_out,
                    technical_data=agent1_out,
                    smc_data=agent2_out,
                    quant_data=quant_out,
                    ml_data=ml_out,
                )
            concept_out = _track_report("concept_recommender", concept_out)

            # 3. Challenge with Agent 4 (Risk Validator) via Adapter
            a4_ad = agent_registry.get_adapter("risk_validator")
            risk_quote_fields = self._risk_quote_fields(data_quality_out)
            if a4_ad:
                risk_out = a4_ad.execute(
                    symbol=symbol,
                    verified_price=verified_price,
                    price_timestamp=price_ts,
                    agent1_report=agent1_out,
                    agent2_report=agent2_out,
                    agent3_report=agent3_out,
                    simulated_equity=simulated_equity,
                    open_positions_count=open_positions_count,
                    **risk_quote_fields
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
                    open_positions_count=open_positions_count,
                    **risk_quote_fields
                )
            risk_out = _track_report("risk_validator", risk_out)
        # 4. Synthesize weighted eight-agent consensus and enforce data-quality quorum.
        from taikry.learning.self_trainer import agent_self_trainer
        learned_weights = agent_self_trainer.get_current_agent_weights(symbol)
        base_vote_weights = {
            "technical_analyst": 0.22,
            "ict_smc_analyst": 0.30,
            "macro_analyst": 0.14,
            "orderflow_sentiment_analyst": 0.08,
            "fractal_mtf_analyst": 0.08,
            "regime_detection_agent": 0.06,
            "quantitative_research_agent": 0.06,
            "ml_forecast_agent": 0.06,
        }
        for agent_id in ("technical_analyst", "ict_smc_analyst", "macro_analyst", "orderflow_sentiment_analyst", "fractal_mtf_analyst"):
            try:
                learned = float(learned_weights.get(agent_id, base_vote_weights[agent_id]))
            except (TypeError, ValueError):
                learned = base_vote_weights[agent_id]
            if math.isfinite(learned) and learned > 0:
                base_vote_weights[agent_id] = learned
        base_weight_total = sum(base_vote_weights.values()) or 1.0
        vote_weights = {agent_id: weight / base_weight_total for agent_id, weight in base_vote_weights.items()}

        voter_ids = tuple(vote_weights)
        eligible_voters = len(voter_ids)
        participating_reports = []
        for agent_id in voter_ids:
            report = agent_reports.get(agent_id, {})
            if report.get("contributes_to_consensus") is not True:
                continue
            try:
                confidence = float(report.get("confidence"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(confidence) or not 0 <= confidence <= 100 or not isinstance(report.get("bias"), str):
                continue
            participating_reports.append((agent_id, report, confidence))

        vote_coverage = len(participating_reports) / float(eligible_voters)
        buy_weight = 0.0
        sell_weight = 0.0
        neutral_weight = 0.0
        total_vote_weight = 0.0
        for agent_id, report, confidence in participating_reports:
            weight = vote_weights[agent_id]
            total_vote_weight += weight
            bias = report["bias"].upper()
            if "BULLISH" in bias or "BUY" in bias or bias == "LONG":
                buy_weight += weight * confidence / 100.0
            elif "BEARISH" in bias or "SELL" in bias or bias == "SHORT":
                sell_weight += weight * confidence / 100.0
            else:
                neutral_weight += weight * max(0.10, 1.0 - confidence / 100.0)

        stronger_weight = max(buy_weight, sell_weight)
        weaker_weight = min(buy_weight, sell_weight)
        material_conflict = stronger_weight > 0 and weaker_weight >= 0.35 * stronger_weight
        consensus_direction = "BUY" if buy_weight > sell_weight else ("SELL" if sell_weight > buy_weight else "NONE")
        directional_total = buy_weight + sell_weight + neutral_weight
        directional_share = stronger_weight / directional_total if directional_total > 0 else 0.0
        measured_support = (stronger_weight / total_vote_weight * 100.0) if total_vote_weight > 0 else 0.0
        ai_score = min(95, max(0, int(round(measured_support))))

        if buy_weight > sell_weight:
            market_bias = "STRONG BULLISH" if directional_share >= 0.75 else "BULLISH"
        elif sell_weight > buy_weight:
            market_bias = "STRONG BEARISH" if directional_share >= 0.75 else "BEARISH"
        else:
            market_bias = "NEUTRAL"

        setup_status = str(risk_out.get("decision", "REJECT")).upper()
        proposed_dir = str(risk_out.get("proposed_direction", "NONE")).upper()
        proposed_vote = "BUY" if proposed_dir in {"LONG", "BUY"} else ("SELL" if proposed_dir in {"SHORT", "SELL"} else "NONE")
        data_quality_ok = (
            data_quality_out.get("execution_status") == "SUCCESS"
            and str(data_quality_out.get("feed_status", "")).upper() == "HEALTHY"
            and data_quality_out.get("is_fresh") is True
        )
        required_voters_ok = all(
            agent_reports.get(agent_id, {}).get("contributes_to_consensus") is True
            for agent_id in ("technical_analyst", "ict_smc_analyst", "macro_analyst")
        )
        review_reasons = []
        if not data_quality_ok:
            review_reasons.append("Data quality agent did not confirm a fresh, healthy market feed.")
        if vote_coverage < 0.60:
            review_reasons.append(f"Directional agent coverage is {vote_coverage:.0%}; at least 60% is required.")
        if not required_voters_ok:
            review_reasons.append("A required technical, structure, or macro report is unavailable.")
        if material_conflict:
            review_reasons.append("Material bullish and bearish vote conflict; wait for clearer confluence.")
        if setup_status == "APPROVE" and (consensus_direction == "NONE" or proposed_vote != consensus_direction or directional_share < 0.55):
            review_reasons.append("The independent risk direction does not have sufficient eight-agent consensus support.")
            setup_status = "WAIT"
        if review_reasons and setup_status == "APPROVE":
            setup_status = "REJECT" if any("unavailable" in reason.lower() or "data quality" in reason.lower() for reason in review_reasons) else "WAIT"
        if setup_status == "APPROVE" and ai_score < 80:
            review_reasons.append("Weighted eight-agent support is below the 80/100 dispatch threshold.")
            setup_status = "WAIT"

        # Required feeds and quorum veto any approval before a candidate is exposed.
        if setup_status in {"REJECT", "WAIT", "NO TRADE"}:
            proposed_dir = "NONE"
        elif proposed_vote != consensus_direction:
            proposed_dir = "NONE"

        # Candidate-stage specialists are only run for an approved, sufficiently
        # scored plan. Portfolio and execution reviewers can veto; the critic is advisory.
        candidate_review_reports = {}
        if setup_status == "APPROVE" and 80 <= ai_score <= 95:
            from taikry.agents.registry import agent_registry
            from taikry.config import COMMISSION_PER_LOT, get_symbol_config
            counter_ad = agent_registry.get_adapter("counter_analysis_agent")
            portfolio_ad = agent_registry.get_adapter("portfolio_analysis_agent")
            execution_ad = agent_registry.get_adapter("execution_simulation_agent")
            if not counter_ad or not portfolio_ad or not execution_ad:
                review_reasons.append("Counter, portfolio, or execution reviewer is unavailable.")
                setup_status = "REJECT"
                proposed_dir = "NONE"
            else:
                candidate_entry = risk_out.get("entry_price")
                candidate_sl = risk_out.get("stop_loss")
                candidate_tp1 = risk_out.get("take_profit_1")
                def _review(adapter, **kwargs):
                    value = adapter.execute(**kwargs)
                    return _as_report(value)
                try:
                    candidate_review_reports["counter_analysis_agent"] = _review(
                        counter_ad,
                        symbol=symbol,
                        proposed_direction=proposed_vote,
                        entry_price=candidate_entry,
                        stop_loss=candidate_sl,
                        take_profit_1=candidate_tp1,
                        technical_report=agent1_out,
                        smc_report=agent2_out,
                        macro_report=agent3_out,
                    )
                    candidate_review_reports["portfolio_analysis_agent"] = _review(
                        portfolio_ad,
                        proposed_symbol=symbol,
                        proposed_risk_pct=RISK_PER_TRADE_PERCENT,
                    )
                    symbol_cfg = get_symbol_config(symbol)
                    lot_size = float(symbol_cfg.get("lot_size") or 100000)
                    commission_per_unit = COMMISSION_PER_LOT / lot_size if lot_size > 0 else 0.0
                    candidate_review_reports["execution_simulation_agent"] = _review(
                        execution_ad,
                        symbol=symbol,
                        direction=proposed_vote,
                        entry_price=candidate_entry,
                        stop_loss=candidate_sl,
                        take_profit_1=candidate_tp1,
                        current_spread_points=data_quality_out.get("spread_points") or symbol_cfg.get("spread_estimate", 0.25),
                        volatility_state=regime_out.get("volatility_state", "NORMAL_LIQUIDITY"),
                        commission_per_unit=commission_per_unit,
                    )
                except Exception as exc:
                    candidate_review_reports["candidate_review_error"] = {"error": str(exc), "_fallback_applied": True}
                portfolio_ok = candidate_review_reports.get("portfolio_analysis_agent", {}).get("is_approved") is True
                execution_ok = candidate_review_reports.get("execution_simulation_agent", {}).get("is_execution_viable") is True
                review_failed = any(
                    candidate_review_reports.get(agent_id, {}).get("_fallback_applied")
                    for agent_id in ("portfolio_analysis_agent", "execution_simulation_agent")
                )
                if not portfolio_ok or not execution_ok or review_failed:
                    review_reasons.append("Portfolio exposure or post-cost execution review rejected the candidate.")
                    setup_status = "REJECT"
                    proposed_dir = "NONE"
                    risk_out = dict(risk_out)
                    risk_out["decision"] = "REJECT"
                    risk_out["reasons"] = list(risk_out.get("reasons", [])) + review_reasons

        if review_reasons and setup_status in {"WAIT", "REJECT"}:
            risk_out = dict(risk_out)
            risk_out["reasons"] = list(risk_out.get("reasons", [])) + [reason for reason in review_reasons if reason not in risk_out.get("reasons", [])]
            if setup_status == "REJECT":
                risk_out["decision"] = "REJECT"

        for agent_id, report in candidate_review_reports.items():
            if isinstance(report, dict):
                report.setdefault("agent_id", agent_id)
                report.setdefault("execution_status", "FALLBACK" if report.get("_fallback_applied") else "SUCCESS")

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

        for ag, name in [
            (agent1_out, "Agent 1 (Technical)"),
            (agent2_out, "Agent 2 (ICT/SMC)"),
            (agent3_out, "Agent 3 (Macro)"),
            (orderflow_dict, "Agent 8 (Order Flow)"),
            (fractal_dict, "Agent 9 (Fractal MTF)"),
            (regime_out, "Market Regime"),
            (quant_out, "Quantitative Research"),
            (ml_out, "ML Forecast"),
        ]:
            ag_bias = ag.get("bias") or ag.get("overall_direction", "NEUTRAL")
            if proposed_dir == "LONG" and "BEARISH" in str(ag_bias):
                dissenting.append(f"{name} holds dissenting BEARISH bias: {ag.get('rationale_en') or ag.get('rationale')}")
            elif proposed_dir == "SHORT" and "BULLISH" in str(ag_bias):
                dissenting.append(f"{name} holds dissenting BULLISH bias: {ag.get('rationale_en') or ag.get('rationale')}")

        if fractal_dict.get("trap_detected"):
            dissenting.append(f"Agent 9 (Fractal Defense): {fractal_dict.get('trap_description')}")
        for agent_id, report in (("regime_detection_agent", regime_out), ("quantitative_research_agent", quant_out), ("ml_forecast_agent", ml_out)):
            if report.get("execution_status") != "SUCCESS":
                dissenting.append(f"{agent_id} did not contribute a verified directional vote ({report.get('execution_status')}).")

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
            synthesis_en = f"Eight-agent consensus confirms {proposed_dir}: technical ({agent1_out.get('bias')}), SMC ({agent2_out.get('bias')}), order flow, fractal, regime, quantitative, and ML reports support the plan. Risk and portfolio/execution checks passed with configured minimum R:R 1:{MIN_RISK_REWARD_RATIO} and maximum risk {RISK_PER_TRADE_PERCENT}%."
            synthesis_kh = f"ភ្នាក់ងារវិភាគទិសដៅ ៨ បានគាំទ្រ {proposed_dir}: បច្ចេកទេស ({agent1_out.get('bias')}), SMC ({agent2_out.get('bias')}), Order Flow, Fractal, Regime, Quantitative និង ML បានពិនិត្យផែនការ។ ការត្រួតពិនិត្យហានិភ័យ ផលប័ត្រ និងថ្លៃប្រតិបត្តិការបានឆ្លងកាត់តាម R:R អប្បបរមា 1:{MIN_RISK_REWARD_RATIO} និងហានិភ័យអតិបរមា {RISK_PER_TRADE_PERCENT}%。"
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
                "risk_reward_confluence": chk_rr,
                "data_quality_confluence": data_quality_ok,
                "eight_agent_vote_coverage": vote_coverage,
                "directional_share": round(directional_share, 4),
            }
        }

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
            "trade_style": trade_style,
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

        agent_statuses = {
            agent_id: report.get("execution_status", "UNKNOWN")
            for agent_id, report in agent_reports.items()
        }
        agent_statuses.update({
            "concept_recommender": concept_out.get("execution_status", "UNKNOWN"),
            "risk_validator": risk_out.get("execution_status", "FALLBACK" if risk_out.get("_fallback_applied") else "SUCCESS"),
            "consensus_engine": "SUCCESS",
            "debate_engine": "DEFERRED",
            "self_trainer": "DEFERRED",
            "counter_analysis_agent": "PENDING_CANDIDATE",
            "portfolio_analysis_agent": "PENDING_CANDIDATE",
            "execution_simulation_agent": "PENDING_CANDIDATE",
        })
        for agent_id, report in candidate_review_reports.items():
            if agent_id in agent_statuses and isinstance(report, dict):
                agent_statuses[agent_id] = "FALLBACK" if report.get("_fallback_applied") else "SUCCESS"
        agent_statuses["consensus_engine"] = "SUCCESS"
        agent_run_summary = {
            "registered_agents_reported": len(agent_statuses),
            "status_counts": {
                status: sum(1 for current in agent_statuses.values() if current == status)
                for status in set(agent_statuses.values())
            },
            "agent_statuses": agent_statuses,
            "voting_agents": len(voter_ids),
            "voting_agents_participated": len(participating_reports),
            "voting_coverage": round(vote_coverage, 4),
        }

        out_dict = {
            "symbol": symbol,
            "trade_style": trade_style,
            "setup_timeframe": setup_timeframe,
            "verified_price": verified_price,
            "price_source": price_source,
            "data_quality": {
                "synthetic_timeframes": synthetic_timeframes,
                "freshness": freshness,
            },
            "timestamp_utc": ts_utc_str,
            "timestamp_cambodia": ts_kh_str,
            "market_bias": market_bias,
            "setup_status": setup_status,
            "proposed_direction": proposed_dir,
            "ai_score": ai_score,
            "confidence_score": ai_score,
            "score_explanation": "Weighted directional support from all available signal-voting agents; heuristic score, not a calibrated win probability.",
            "setup_grade": "HIGH_CONVICTION" if ai_score >= 80 else "STANDARD",
            "entry_price": entry_price,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_ratio": rr_str,
            "invalidation_rules": agent1_out.get("invalidation_level") or agent2_out.get("invalidation_level"),
            "smart_analysis": smart_analysis,
            "agent_run_summary": agent_run_summary,
            "agents": {
                "agent_1_technical": agent1_out,
                "agent_2_ict_smc": agent2_out,
                "agent_3_macro": agent3_out,
                "agent_4_risk": risk_out,
                "data_quality_agent": data_quality_out,
                "agent_8_orderflow": orderflow_dict,
                "agent_9_fractal_mtf": fractal_dict,
                "regime_detection_agent": regime_out,
                "quantitative_research_agent": quant_out,
                "ml_forecast_agent": ml_out,
                "concept_recommender": concept_out,
                "counter_analysis_agent": candidate_review_reports.get("counter_analysis_agent", {"execution_status": "PENDING_CANDIDATE"}),
                "portfolio_analysis_agent": candidate_review_reports.get("portfolio_analysis_agent", {"execution_status": "PENDING_CANDIDATE"}),
                "execution_simulation_agent": candidate_review_reports.get("execution_simulation_agent", {"execution_status": "PENDING_CANDIDATE"}),
            },
            "agent_fleet_count": len(agent_statuses),
            "performance": {
                "parallel_execution": True,
                "concurrency_level": 9,
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

    @staticmethod
    def _risk_quote_fields(report: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Return only spread and executable sides from the audited fresh quote."""
        if not isinstance(report, dict) or report.get("is_fresh") is not True:
            return {"spread_price": None, "bid_price": None, "ask_price": None}
        if str(report.get("feed_status", "")).upper() != "HEALTHY":
            return {"spread_price": None, "bid_price": None, "ask_price": None}
        try:
            bid = float(report.get("bid_price"))
            ask = float(report.get("ask_price"))
        except (TypeError, ValueError):
            return {"spread_price": None, "bid_price": None, "ask_price": None}
        if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask <= bid:
            return {"spread_price": None, "bid_price": None, "ask_price": None}
        return {"spread_price": round(ask - bid, 8), "bid_price": bid, "ask_price": ask}

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
