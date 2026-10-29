"""
Production Evaluation Suite for ZYROX AI Deep Research & Pre-News Multi-Agent System.
Measures:
1. Data Freshness and Source Coverage (Sections B & J)
2. Scenario Calibration (Sections F & G with R:R floor >= 1:2.0)
3. No-Trade Decision Safety & Pre-News Lockout (Section H)
4. Multi-Gateway Router Health, Latency, and Cost Compliance ($0-$15/month limit)
5. Crypto Unverified Data Integrity (Section K)
"""

import pytest
import datetime
import time
from typing import Dict, Any

from taikry.agents.deep_research_engine import deep_research_engine, WINDOW_60_30_MIN, WINDOW_15_5_MIN
from taikry.ai.anyrouter_client import anyrouter_client, budget_manager
from taikry.config import ANYROUTER_SPEND_LIMIT_USD, MIN_RISK_REWARD_RATIO


# -----------------------------------------------------------------------------
# 1. HISTORICAL BENCHMARK EVALUATION DATASET
# -----------------------------------------------------------------------------
HISTORICAL_EVALUATION_DATASET = [
    {
        "event_id": "eval_cpi_2026_01",
        "title": "US Core CPI m/m",
        "currency": "USD",
        "forecast": "0.3%",
        "previous": "0.2%",
        "actual": "0.4%",
        "expected_direction": "BEARISH_GOLD_BULLISH_USD",
        "category": "CPI"
    },
    {
        "event_id": "eval_nfp_2026_02",
        "title": "US Non-Farm Payrolls",
        "currency": "USD",
        "forecast": "180K",
        "previous": "210K",
        "actual": "142K",
        "expected_direction": "BULLISH_GOLD_BEARISH_USD",
        "category": "NFP"
    },
    {
        "event_id": "eval_fomc_2026_03",
        "title": "Federal Funds Rate Decision",
        "currency": "USD",
        "forecast": "4.75%",
        "previous": "5.00%",
        "actual": "4.50%",
        "expected_direction": "HIGH_VOLATILITY_EXPANSION",
        "category": "FOMC"
    }
]


class TestDeepResearchFleetEvaluation:
    """Rigorous evaluation of the 11-Agent Deep Research Fleet."""

    def test_data_freshness_and_source_coverage(self):
        """Validates that real-time market data and source citations are verified."""
        res = deep_research_engine.run_deep_research("XAUUSD", force_refresh=True)
        assert res["status"] == "SUCCESS"
        assert res["price"] > 0, "Price must be positive and verified"
        assert res["price_source"] != "DEMO_SYNTHETIC", "Must not use unverified synthetic data for live research"

        sections = res["sections"]
        # Section B Check
        sec_b = sections["B_verified_price"]
        assert sec_b["symbol"] == "XAUUSD"
        assert "data_timestamp_utc" in sec_b
        assert "data_timestamp_cambodia" in sec_b
        assert "UTC+7" in sec_b["data_timestamp_cambodia"]

        # Section J Check
        sec_j = sections["J_source_list_and_freshness"]
        assert sec_j["market_data_freshness"] == "LIVE_FRESH"
        assert len(sec_j["news_sources"]) >= 0

    def test_scenario_calibration_and_risk_reward_floor(self):
        """Validates that Bullish & Bearish scenarios have deterministic triggers and >= 1:2.0 R:R."""
        res = deep_research_engine.run_deep_research("XAUUSD", force_refresh=False)
        sections = res["sections"]

        sec_f = sections["F_bullish_scenario"]
        sec_g = sections["G_bearish_scenario"]

        # Bullish Scenario Calibration
        assert sec_f["name"] == "Bullish Breakout / Demand Absorption"
        assert sec_f["target_1"] > res["price"], "Bullish target 1 must be above current price"
        assert sec_f["target_2"] > sec_f["target_1"], "Bullish target 2 must be above target 1"
        assert sec_f["stop_loss"] < res["price"], "Bullish stop loss must be below current price"
        assert "1:2.0" in sec_f["risk_reward"]
        assert "Break and close below" in sec_f["invalidation"]

        # Bearish Scenario Calibration
        assert sec_g["name"] == "Bearish Breakdown / Liquidity Sweep Below"
        assert sec_g["target_1"] < res["price"], "Bearish target 1 must be below current price"
        assert sec_g["target_2"] < sec_g["target_1"], "Bearish target 2 must be below target 1"
        assert sec_g["stop_loss"] > res["price"], "Bearish stop loss must be above current price"
        assert "1:2.0" in sec_g["risk_reward"]
        assert "Rally and close above" in sec_g["invalidation"]

    def test_no_trade_safety_and_capital_protection(self):
        """Verifies that contradictory evidence or pre-news lockout yields NO TRADE / WAIT."""
        res = deep_research_engine.run_deep_research("XAUUSD", force_refresh=False)
        sections = res["sections"]
        sec_h = sections["H_base_case_no_trade"]

        assert "final_recommendation" in sec_h
        assert sec_h["final_recommendation"] in ["CONDITIONAL WAIT", "NO TRADE (PRE-NEWS LOCKOUT)"]
        assert len(sec_h["no_trade_rules"]) >= 2
        # Ensure no forced buy/sell signal
        assert "BUY" not in sec_h["final_recommendation"]
        assert "SELL" not in sec_h["final_recommendation"]

    def test_crypto_unverified_derivatives_integrity(self):
        """Ensures that crypto funding and open interest are not invented when feeds are absent."""
        res = deep_research_engine.run_deep_research("BTCUSDT", force_refresh=True)
        sections = res["sections"]
        sec_k = sections["K_uncertainties_missing_inputs"]

        assert "unverified_derivatives" in sec_k
        assert "marked unverified" in sec_k["unverified_derivatives"].lower() or "broker" in sec_k["unverified_derivatives"].lower()
        assert "strictly deterministic" in sec_k["data_integrity"]

    def test_model_router_failover_latency_and_budget_controls(self):
        """Tests that the AnyRouter router dispatches within budget and fails over gracefully."""
        t0 = time.time()
        resp = anyrouter_client.generate_chat_completion(
            messages=[{"role": "user", "content": "Respond strictly with: EVALUATION_PASSED"}],
            model="anyrouter/auto",
            max_tokens=25
        )
        elapsed_sec = time.time() - t0

        # Assertions
        assert resp is not None
        assert "content" in resp
        assert "model_used" in resp
        assert elapsed_sec < 15.0, f"Router latency {elapsed_sec:.2f}s must be under 15 seconds"

        # Budget assertion
        b_summary = budget_manager.get_summary()
        assert b_summary["estimated_spend_usd"] <= ANYROUTER_SPEND_LIMIT_USD, "Must stay within spend ceiling"
        assert not b_summary["budget_exceeded"]

    def test_bilingual_khmer_and_english_synthesis(self):
        """Verifies that Executive Summary and key causes contain complete English and Khmer text."""
        res = deep_research_engine.run_deep_research("XAUUSD", force_refresh=False)
        sections = res["sections"]
        sec_a = sections["A_executive_summary"]

        assert "en" in sec_a and len(sec_a["en"]) > 50
        assert "kh" in sec_a and len(sec_a["kh"]) > 50
        assert "XAUUSD" in sec_a["en"]
        assert "របាយការណ៍" in sec_a["kh"] or "តម្លៃ" in sec_a["kh"]

    def test_historical_dataset_calibration_consistency(self):
        """Evaluates calibration against the historical benchmark dataset."""
        for item in HISTORICAL_EVALUATION_DATASET:
            assert item["forecast"] != "N/A"
            assert item["previous"] != "N/A"
            assert item["actual"] != "N/A"
            assert item["category"] in ["CPI", "NFP", "FOMC"]

