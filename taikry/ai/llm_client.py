"""
TAIKRY AI Real LLM Orchestrator
Integrated Frontier LLMs:
1. Anthropic Claude (Claude 3.7 Sonnet / Claude 3.5 Sonnet / Claude 3.5 Haiku / Opus)
2. OpenAI (o3-mini / o1 / o1-mini / GPT-4o / GPT-4o-mini)
3. Google Gemini (Gemini 2.5 Pro / 2.5 Flash / 2.0 Flash / 1.5 Pro)
4. DeepSeek (DeepSeek-V3 671B MoE / DeepSeek-R1 Reasoner)
5. Manus AI (Manus Agent API / Autonomous Multi-Step Reasoning)
"""
import datetime
import json
import logging
import re
import time
from typing import Dict, Any, Optional, List, Tuple

import requests

from taikry.config import (
    FREELLMAPI_ENABLED,
    FREELLMAPI_BASE_URL,
    FREELLMAPI_DEFAULT_MODEL,
    CLAUDE_API_KEY,
    CLAUDE_BASE_URL,
    CLAUDE_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    ANYROUTER_API_KEY,
    GEMINI_API_KEY,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    OPENROUTER_API_KEY,
    GROQ_API_KEY,
    MANUS_API_KEY,
    MANUS_API_URL,
    ORCAROUTER_API_KEY,
    ORCAROUTER_BASE_URL,
    ORCAROUTER_MODEL,
    AI_PROVIDER
)

logger = logging.getLogger("taikry.ai.llm_client")

# Institutional Multi-Agent Prompt with Global News & Khmer Analysis Mandate
LLM_SYSTEM_PROMPT = """You are the Institutional Lead Consensus Orchestrator for TAIKRY AI MARKET INTELLIGENCE PRO.
You summarize the analysis supplied in the request:
1. Technical Momentum Agent: Evaluates EMA 20/50/200 multi-timeframe alignment, RSI momentum/divergence, MACD expansion, ATR volatility.
2. Institutional SMC / ICT Agent: Analyzes Buy-side/Sell-side liquidity (BSL/SSL) sweeps, Fair Value Gaps (FVG), Optimal Trade Entry (OTE 61.8%-78.6%), Dealing Range (Premium vs Discount), and Killzone timing.
3. Macroeconomic & Global News Agent: Uses only the economic events, news, and US Dollar Index (DXY) evidence explicitly supplied in the request. Treasury yield data is not assumed to be available.
4. Risk & Capital Protection Guardian: Validates the configured minimum Risk-to-Reward ratio, configured per-trade risk cap, available news-calendar checks, and structural invalidation levels. Use risk values provided in context; never assume a default percentage or ratio.

CRITICAL INSTRUCTIONS:
1. Use only evidence included in the request. You do not have live market, calendar, news, DXY, or yield access unless a value is explicitly supplied.
2. Never invent agent calls, headlines, event schedules, prices, indicators, yields, or risk checks. Mark unavailable evidence as unavailable.
3. Provide a concise synthesis in BOTH English and Natural Khmer ("synthesis_summary_kh"). Do not claim that an event or macro factor caused a move unless the supplied evidence supports it.
4. The deterministic server-side risk validator is authoritative. Do not approve a trade from language-model reasoning alone.
5. If the context does not contain a current approved setup with verified levels, or if required evidence is missing or conflicting, action must be "HOLD" and levels must remain "LOCKED".

You must respond ONLY with a valid, parseable JSON object matching this exact schema:
{
  "smart_analysis": {
    "synthesis_summary_en": "<deep causal synthesis explaining WHY this market structure exists and news impact>",
    "synthesis_summary_kh": "<វិភាគមូលហេតុលម្អិតជាភាសាខ្មែរ ពន្យល់ពីហេតុផលបច្ចេកទេស រចនាសម្ព័ន្ធស្ថាប័ន និងឥទ្ធិពលព័ត៌មាន FOMC/PPI/CPI លើមាស និងរូបិយប័ណ្ណ>",
    "technical_causes": [
      "<specific technical causes, EMA alignment, RSI momentum, ATR volatility>"
    ],
    "smc_causes": [
      "<institutional ICT/SMC causes: liquidity sweeps, FVG, OTE 61.8%-78.6%, order blocks>"
    ],
    "macro_causes": [
      "<macroeconomic, global news & DXY causes: FOMC/PPI/CPI analysis, dollar trend, interest rates>"
    ],
    "risk_causes": [
      "<risk audit causes, configured R:R check, news-calendar status, capital protection rules>"
    ],
    "checklist": {
      "multi_agent_consensus": true,
      "institutional_liquidity_clear": true,
      "macro_dxy_aligned": true,
      "risk_reward_viable": true
    }
  },
  "trade_execution": {
    "action": "BUY" | "SELL" | "HOLD",
    "status": "APPROVED" | "REJECTED_LOCKED",
    "confidence": <integer 0-100>,
    "entry_price": <number or "LOCKED">,
    "stop_loss": <number or "LOCKED">,
    "take_profit_1": <number or "LOCKED">,
    "take_profit_2": <number or "LOCKED">,
    "risk_reward_ratio": <string, e.g. "1:2.0" or "LOCKED">,
    "invalidation_level": <number or string>
  }
}
"""

def _extract_json_from_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts JSON from raw LLM output even if surrounded by markdown fences."""
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # Match first '{' to last '}'
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except Exception:
            pass

    return None


def call_claude(symbol_info: Dict[str, Any], timeframe: str, metrics: Dict[str, Any], timeout: int = 35) -> Optional[Dict[str, Any]]:
    """
    Calls Anthropic Claude API with latest Frontier models:
    - Claude 3.7 Sonnet (claude-3-7-sonnet-20250219)
    - Claude 3.5 Sonnet (claude-3-5-sonnet-latest / claude-3-5-sonnet-20241022)
    - Claude 3.5 Haiku (claude-3-5-haiku-latest)
    - Claude 3 Opus
    """
    if not CLAUDE_API_KEY:
        # Fallback to OpenRouter or AnyRouter if available
        if OPENROUTER_API_KEY:
            try:
                t0 = time.time()
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "anthropic/claude-3.5-sonnet",
                        "messages": [
                            {"role": "system", "content": LLM_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=timeout
                )
                if resp.status_code == 200:
                    raw_text = resp.json()["choices"][0]["message"]["content"]
                    parsed = _extract_json_from_response(raw_text)
                    if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                        lat = int((time.time() - t0) * 1000)
                        parsed["_llm_meta"] = {"provider": "claude (via openrouter)", "model": "anthropic/claude-3.5-sonnet", "latency_ms": lat, "status": "SUCCESS"}
                        return parsed
            except Exception as e:
                logger.warning(f"Claude via OpenRouter notice: {e}")
        from taikry.config import ANYROUTER_API_KEY
        if ANYROUTER_API_KEY:
            try:
                from taikry.ai.anyrouter_client import anyrouter_client
                res = anyrouter_client.generate_chat_completion(
                    messages=[{"role": "system", "content": LLM_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                    model="anyrouter/free",
                    response_format={"type": "json_object"}
                )
                parsed = _extract_json_from_response(res.get("content", ""))
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    parsed["_llm_meta"] = {"provider": "claude (via anyrouter)", "model": res.get("model", "anyrouter/free"), "latency_ms": res.get("latency_ms", 1500), "status": "SUCCESS"}
                    return parsed
            except Exception as e:
                logger.warning(f"Claude via AnyRouter notice: {e}")
        return None

    models = []
    if CLAUDE_MODEL:
        models.append(CLAUDE_MODEL)
    for m in [
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-latest",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest"
    ]:
        if m not in models:
            models.append(m)

    base_endpoint = (CLAUDE_BASE_URL or "https://api.anthropic.com/v1").rstrip("/")
    if base_endpoint.endswith("/v1"):
        url = f"{base_endpoint}/messages"
    else:
        url = f"{base_endpoint}/v1/messages"

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "Authorization": f"Bearer {CLAUDE_API_KEY}",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    for model in models:
        payload = {
            "model": model,
            "max_tokens": 2000,
            "system": LLM_SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                text_content = ""
                for part in res_data.get("content", []):
                    if part.get("type") == "text":
                        text_content += part.get("text", "")
                parsed = _extract_json_from_response(text_content)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    latency = int((time.time() - t0) * 1000)
                    parsed["_llm_meta"] = {
                        "provider": "claude",
                        "model": model,
                        "latency_ms": latency,
                        "status": "SUCCESS"
                    }
                    return parsed
            elif resp.status_code in [401, 403]:
                logger.warning(f"Claude API key unauthorized ({resp.status_code}). Skipping Claude models.")
                break
            else:
                logger.warning(f"Claude API ({model}) returned HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"Claude API ({model}) error: {e}")
            break

    return None


def call_openai(symbol_info: Dict[str, Any], timeframe: str, metrics: Dict[str, Any], timeout: int = 35) -> Optional[Dict[str, Any]]:
    """
    Calls OpenAI API with latest Frontier models:
    - o3-mini (reasoning frontier)
    - o1 / o1-mini
    - GPT-4o
    - GPT-4o-mini
    - GPT-4-turbo
    """
    if not OPENAI_API_KEY:
        # Fallback to OpenRouter or AnyRouter if available
        if OPENROUTER_API_KEY:
            try:
                t0 = time.time()
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "openai/gpt-4o",
                        "messages": [
                            {"role": "system", "content": LLM_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=timeout
                )
                if resp.status_code == 200:
                    raw_text = resp.json()["choices"][0]["message"]["content"]
                    parsed = _extract_json_from_response(raw_text)
                    if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                        lat = int((time.time() - t0) * 1000)
                        parsed["_llm_meta"] = {"provider": "openai (via openrouter)", "model": "openai/gpt-4o", "latency_ms": lat, "status": "SUCCESS"}
                        return parsed
            except Exception as e:
                logger.warning(f"OpenAI via OpenRouter notice: {e}")
        from taikry.config import ANYROUTER_API_KEY
        if ANYROUTER_API_KEY:
            try:
                from taikry.ai.anyrouter_client import anyrouter_client
                res = anyrouter_client.generate_chat_completion(
                    messages=[{"role": "system", "content": LLM_SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                    model="anyrouter/free",
                    response_format={"type": "json_object"}
                )
                parsed = _extract_json_from_response(res.get("content", ""))
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    parsed["_llm_meta"] = {"provider": "openai (via anyrouter)", "model": res.get("model", "anyrouter/free"), "latency_ms": res.get("latency_ms", 1500), "status": "SUCCESS"}
                    return parsed
            except Exception as e:
                logger.warning(f"OpenAI via AnyRouter notice: {e}")
        return None

    # Priority models (supports TryAI, official OpenAI, and frontier relays)
    models = []
    if OPENAI_MODEL:
        models.append(OPENAI_MODEL)
    for m in ["gpt-5.6-sol", "gpt-6-sol", "gpt-6.1-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-6-astra", "gpt-6-luna", "gpt-4o", "gpt-4o-mini", "o3-mini", "o1", "o1-mini", "gpt-4-turbo"]:
        if m not in models:
            models.append(m)

    base_endpoint = (OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    if base_endpoint.endswith("/v1"):
        url = f"{base_endpoint}/chat/completions"
    else:
        url = f"{base_endpoint}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    for model in models:
        # Check if model is reasoning model (o1, o3-mini) which doesn't support custom temperature or system role in standard format
        is_reasoning_model = model.startswith("o1") or model.startswith("o3")

        if is_reasoning_model:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": f"{LLM_SYSTEM_PROMPT}\n\n{user_prompt}"}
                ],
                "response_format": {"type": "json_object"}
            }
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }

        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_text = res_data["choices"][0]["message"]["content"]
                parsed = _extract_json_from_response(raw_text)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    latency = int((time.time() - t0) * 1000)
                    parsed["_llm_meta"] = {
                        "provider": "openai",
                        "model": model,
                        "latency_ms": latency,
                        "status": "SUCCESS"
                    }
                    return parsed
            elif resp.status_code in [401, 403]:
                logger.warning(f"OpenAI API key unauthorized ({resp.status_code}). Skipping OpenAI models.")
                break
            else:
                logger.warning(f"OpenAI API ({model}) returned HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"OpenAI API ({model}) error: {e}")
            break

    return None


def call_gemini(symbol_info: Dict[str, Any], timeframe: str, metrics: Dict[str, Any], timeout: int = 35) -> Optional[Dict[str, Any]]:
    """
    Calls Google Gemini API with latest Frontier models:
    - Gemini 2.5 Pro
    - Gemini 2.5 Flash
    - Gemini 2.0 Flash
    - Gemini 1.5 Pro
    - Gemini 1.5 Flash
    """
    if not GEMINI_API_KEY:
        return None

    models = [
        "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-2.5-flash",
        "gemini-1.5-flash"
    ]
    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": LLM_SYSTEM_PROMPT + "\n\n" + user_prompt}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = _extract_json_from_response(raw_text)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    latency = int((time.time() - t0) * 1000)
                    parsed["_llm_meta"] = {
                        "provider": "gemini",
                        "model": model,
                        "latency_ms": latency,
                        "status": "SUCCESS"
                    }
                    return parsed
            elif resp.status_code in [400, 401, 403]:
                logger.warning(f"Gemini API returned {resp.status_code}. Key or access restricted.")
                break
            else:
                logger.warning(f"Gemini API ({model}) returned HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"Gemini API ({model}) error: {e}")
            break

    return None


def call_groq(symbol_info: Dict[str, Any], timeframe: str, metrics: Dict[str, Any], timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Calls Groq Cloud API (Ultra-High Speed LPU Inference):
    - openai/gpt-oss-120b
    - qwen/qwen3.8-27b
    - openai/gpt-oss-20b
    - llama-3.3-70b-versatile
    """
    if not GROQ_API_KEY:
        return None

    models = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "deepseek-r1-distill-llama-70b"
    ]
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_text = res_data["choices"][0]["message"]["content"]
                parsed = _extract_json_from_response(raw_text)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    latency = int((time.time() - t0) * 1000)
                    parsed["_llm_meta"] = {
                        "provider": "groq",
                        "model": model,
                        "latency_ms": latency,
                        "status": "SUCCESS"
                    }
                    return parsed
            elif resp.status_code in [401, 403]:
                logger.warning(f"Groq API key unauthorized ({resp.status_code}).")
                break
        except Exception as e:
            logger.warning(f"Groq API ({model}) error: {e}")
            break

    return None


def call_deepseek(symbol_info: Dict[str, Any], timeframe: str, metrics: Dict[str, Any], timeout: int = 35) -> Optional[Dict[str, Any]]:
    """
    Calls DeepSeek API with Frontier reasoning and chat models:
    - meta-llama/llama-3.3-70b-instruct
    - deepseek-reasoner (DeepSeek-R1)
    - deepseek-chat (DeepSeek-V3 671B MoE)
    Supports direct DeepSeek API, or OpenRouter Free/Paid Tier.
    """
    api_key = DEEPSEEK_API_KEY or OPENROUTER_API_KEY
    if not api_key:
        return None

    if DEEPSEEK_API_KEY:
        base = (DEEPSEEK_BASE_URL or "https://api.deepseek.com").rstrip("/")
        if base.endswith("/chat/completions"):
            url = base
        else:
            url = f"{base}/chat/completions"

        models = []
        if DEEPSEEK_MODEL:
            models.append(DEEPSEEK_MODEL)
        for m in ["deepseek/deepseek-v4-pro-0813", "deepseek-reasoner", "deepseek-chat"]:
            if m not in models:
                models.append(m)
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"
        models = [
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat",
            "deepseek/deepseek-r1:free"
        ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_text = res_data["choices"][0]["message"]["content"]
                parsed = _extract_json_from_response(raw_text)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    latency = int((time.time() - t0) * 1000)
                    parsed["_llm_meta"] = {
                        "provider": "deepseek",
                        "model": model,
                        "latency_ms": latency,
                        "status": "SUCCESS"
                    }
                    return parsed
            elif resp.status_code == 402:
                logger.warning(f"DeepSeek ({model}) insufficient quota / payment required (HTTP 402): {resp.text[:120]}")
                continue
            elif resp.status_code in [401, 403]:
                logger.warning(f"DeepSeek API key unauthorized ({resp.status_code}). Skipping DeepSeek models.")
                break
            else:
                logger.warning(f"DeepSeek API ({model}) returned HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"DeepSeek API ({model}) error: {e}")
            break

    return None


def call_manus(symbol_info: Dict[str, Any], timeframe: str, metrics: Dict[str, Any], timeout: int = 35) -> Optional[Dict[str, Any]]:
    """
    Calls Manus AI Agent API (manus.ai / manus.im).
    Supports task-based agent endpoints and OpenAI-compatible inference completions.
    """
    if not MANUS_API_KEY:
        return None

    base_url = MANUS_API_URL.rstrip("/")
    chat_url = f"{base_url}/chat/completions"
    tasks_url = f"{base_url}/tasks"

    headers = {
        "Authorization": f"Bearer {MANUS_API_KEY}",
        "Content-Type": "application/json"
    }

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    # 1. Attempt chat endpoint first
    try:
        t0 = time.time()
        payload = {
            "model": "manus-agent-pro",
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
        resp = requests.post(chat_url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            res_data = resp.json()
            raw_text = res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _extract_json_from_response(raw_text)
            if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                latency = int((time.time() - t0) * 1000)
                parsed["_llm_meta"] = {
                    "provider": "manus",
                    "model": "manus-agent-pro",
                    "latency_ms": latency,
                    "status": "SUCCESS"
                }
                return parsed
    except Exception as e:
        logger.warning(f"Manus AI chat endpoint failed: {e}")

    # 2. Attempt task planning endpoint
    try:
        t0 = time.time()
        payload = {
            "task": f"Synthesize institutional multi-agent market intelligence for {symbol_info.get('symbol')}. Produce JSON output matching schema.",
            "context": {
                "system_prompt": LLM_SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "metrics": metrics
            }
        }
        resp = requests.post(tasks_url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code in [200, 201]:
            res_data = resp.json()
            output = res_data.get("output") or res_data.get("result") or json.dumps(res_data)
            parsed = _extract_json_from_response(str(output))
            if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                latency = int((time.time() - t0) * 1000)
                parsed["_llm_meta"] = {
                    "provider": "manus",
                    "model": "manus-task-agent",
                    "latency_ms": latency,
                    "status": "SUCCESS"
                }
                return parsed
    except Exception as e:
        logger.warning(f"Manus AI task endpoint failed: {e}")

    return None



def call_orcarouter(
    symbol_info: Dict[str, Any],
    timeframe: str,
    metrics: Dict[str, Any],
    model: Optional[str] = None,
    timeout: int = 35
) -> Optional[Dict[str, Any]]:
    """Calls OrcaRouter OpenAI-compatible API gateway (https://api.orcarouter.ai/v1)."""
    if not ORCAROUTER_API_KEY:
        return None

    url = f"{ORCAROUTER_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {ORCAROUTER_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""

    models_to_try = []
    if model:
        models_to_try.append(model)
    elif ORCAROUTER_MODEL:
        models_to_try.append(ORCAROUTER_MODEL)
    for m in ["deepseek/deepseek-v4-pro-0813", "orcarouter/auto", "orcarouter/free"]:
        if m not in models_to_try:
            models_to_try.append(m)

    for m in models_to_try:
        payload = {
            "model": m,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                raw_text = res_data["choices"][0]["message"]["content"]
                parsed = _extract_json_from_response(raw_text)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    latency = int((time.time() - t0) * 1000)
                    parsed["_llm_meta"] = {
                        "provider": "orcarouter",
                        "model": m,
                        "latency_ms": latency,
                        "status": "SUCCESS"
                    }
                    return parsed
            elif resp.status_code == 402:
                logger.warning(f"OrcaRouter ({m}) out of credits / payment required (HTTP 402): {resp.text[:120]}")
            elif resp.status_code == 403:
                logger.warning(f"OrcaRouter ({m}) model access denied (HTTP 403): {resp.text[:120]}")
            else:
                logger.warning(f"OrcaRouter ({m}) returned HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"OrcaRouter ({m}) error: {e}")

    return None


def call_freellmapi(
    symbol_info: Dict[str, Any],
    timeframe: str,
    metrics: Dict[str, Any],
    model: Optional[str] = None,
    timeout: int = 8
) -> Optional[Dict[str, Any]]:
    """
    Calls FreeLLMAPI: open-source free-tier proxy from GitHub (https://github.com/tashfeenahmed/freellmapi).
    Aggregates free tiers of DeepSeek R1, Llama 3.3 70B, Gemini 2.0 Flash, Qwen 2.5.
    """
    from taikry.ai.freellmapi_client import freellmapi_client
    target_model = model or freellmapi_client.default_model or "deepseek-r1"

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON.
"""
    messages = [
        {"role": "system", "content": LLM_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    try:
        t0 = time.time()
        res = freellmapi_client.chat_completion(
            messages=messages,
            model=target_model,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        if res.get("success"):
            raw_text = res.get("content", "")
            parsed = _extract_json_from_response(raw_text)
            if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                lat = int((time.time() - t0) * 1000)
                parsed["_llm_meta"] = {
                    "provider": "freellmapi",
                    "model": res.get("model", target_model),
                    "latency_ms": lat,
                    "status": "SUCCESS"
                }
                return parsed
    except Exception as e:
        logger.warning(f"FreeLLMAPI call notice: {e}")

    return None



def call_anyrouter(
    symbol_info: Dict[str, Any],
    timeframe: str,
    metrics: Dict[str, Any],
    model: Optional[str] = None,
    timeout: int = 15
) -> Optional[Dict[str, Any]]:
    """
    Calls AnyRouter Gateway (OpenAI-compatible inference).
    Routes dynamically to anyrouter/free, anyrouter/auto, or assigned multi-agent roles.
    """
    from taikry.ai.anyrouter_client import anyrouter_client
    if not anyrouter_client.is_configured():
        return None

    target_model = model or anyrouter_client.resolve_model_for_role("orchestrator") or "anyrouter/free"

    user_prompt = f"""Asset: {symbol_info.get('name', 'Asset')} ({symbol_info.get('symbol', 'UNKNOWN')})
Category: {symbol_info.get('category', 'Trading')}
Timeframe: {timeframe}
Market Indicators, Macro News & Metrics:
{json.dumps(metrics, indent=2)}

Perform institutional multi-agent causal analysis first (English & Natural Khmer), incorporating global economic catalysts (FOMC, PPI, CPI, NFP), then output trade execution strictly in JSON matching the schema.
"""
    messages = [
        {"role": "system", "content": LLM_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    try:
        t0 = time.time()
        res = anyrouter_client.generate_chat_completion(
            messages=messages,
            model=target_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=timeout
        )
        raw_text = res.get("content", "")
        parsed = _extract_json_from_response(raw_text)
        if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
            lat = int((time.time() - t0) * 1000)
            parsed["_llm_meta"] = {
                "provider": "anyrouter",
                "model": res.get("model", target_model),
                "latency_ms": lat,
                "status": "SUCCESS"
            }
            return parsed
    except Exception as e:
        logger.warning(f"AnyRouter call notice: {e}")

    return None

class LLMOrchestrator:
    """
    Lead Multi-LLM Orchestrator that unifies Frontier AI models:
    Claude 3.7/3.5, OpenAI o3/o1/GPT-4o, Gemini 2.5/2.0, DeepSeek V3/R1, and Manus AI.
    Features:
    - Configurable routing policy without code changes
    - Per-provider circuit breakers with automatic cooldown
    - Detailed model provenance recording (tracking attempted models, latencies, and fallback reasons)
    - Zero fabrication: returns None when models fail so deterministic Python analysis takes over cleanly
    """

    def __init__(self):
        self.routing_policy: Dict[str, Any] = {
            "prefer_local": True,
            "priority_order": ["anyrouter", "orcarouter", "groq", "gemini", "deepseek", "claude", "openai", "freellmapi", "manus"],
            "circuit_breaker_max_fails": 3,
            "circuit_breaker_cooldown_sec": 60.0
        }
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {
            p: {"fails": 0, "last_fail": 0.0}
            for p in ["groq", "gemini", "deepseek", "openrouter", "claude", "openai", "manus", "freellmapi", "anyrouter", "orcarouter"]
        }

    def get_routing_policy(self) -> Dict[str, Any]:
        """Returns the active model routing configuration."""
        return dict(self.routing_policy)

    def update_routing_policy(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates model routing policy dynamically at runtime."""
        if "prefer_local" in updates:
            self.routing_policy["prefer_local"] = bool(updates["prefer_local"])
        if "priority_order" in updates and isinstance(updates["priority_order"], list):
            self.routing_policy["priority_order"] = [str(x).lower() for x in updates["priority_order"]]
        if "circuit_breaker_max_fails" in updates:
            self.routing_policy["circuit_breaker_max_fails"] = int(updates["circuit_breaker_max_fails"])
        if "circuit_breaker_cooldown_sec" in updates:
            self.routing_policy["circuit_breaker_cooldown_sec"] = float(updates["circuit_breaker_cooldown_sec"])
        return dict(self.routing_policy)

    def is_provider_available(self, provider: str) -> bool:
        """Checks if provider circuit breaker is closed or cooldown has expired."""
        cb = self.circuit_breakers.get(provider)
        if not cb:
            return True
        max_fails = self.routing_policy.get("circuit_breaker_max_fails", 3)
        cooldown = self.routing_policy.get("circuit_breaker_cooldown_sec", 60.0)
        if cb["fails"] >= max_fails:
            if (time.time() - cb["last_fail"]) < cooldown:
                return False
            # Cooldown expired: half-open probe allowed
            cb["fails"] = max_fails - 1
        return True

    def record_provider_result(self, provider: str, success: bool):
        """Records provider execution outcome for circuit breaking."""
        cb = self.circuit_breakers.setdefault(provider, {"fails": 0, "last_fail": 0.0})
        if success:
            cb["fails"] = 0
        else:
            cb["fails"] += 1
            cb["last_fail"] = time.time()

    def get_status(self) -> Dict[str, Any]:
        """Reports key configuration and circuit state without claiming a live provider ping."""
        def provider_status(provider: str, configured: bool) -> str:
            if not configured:
                return "NOT_CONFIGURED"
            if not self.is_provider_available(provider):
                return "CIRCUIT_BROKEN"
            return "CONFIGURED_NOT_PROBED"

        return {
            "groq": {
                "name": "Groq Cloud",
                "configured": bool(GROQ_API_KEY),
                "status": provider_status("groq", bool(GROQ_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "Provider plan and usage limits apply",
                "frontier_models": ["deepseek-r1-distill-llama-70b", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
            },
            "openrouter": {
                "name": "OpenRouter (Free Tier Models)",
                "configured": bool(OPENROUTER_API_KEY),
                "status": provider_status("openrouter", bool(OPENROUTER_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "FREE",
                "frontier_models": ["deepseek/deepseek-r1:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-exp:free"]
            },
            "gemini": {
                "name": "Google Gemini 2.0 / 1.5 Flash (Free Tier)",
                "configured": bool(GEMINI_API_KEY),
                "status": provider_status("gemini", bool(GEMINI_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "FREE",
                "frontier_models": ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.5-pro"]
            },
            "deepseek": {
                "name": "DeepSeek V3 / R1 Reasoner",
                "configured": bool(DEEPSEEK_API_KEY or OPENROUTER_API_KEY),
                "status": provider_status("deepseek", bool(DEEPSEEK_API_KEY or OPENROUTER_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "FREE_WITH_OPENROUTER",
                "frontier_models": ["deepseek-r1", "deepseek-v3"]
            },
            "claude": {
                "name": "Anthropic Claude 3.7 / 3.5 Sonnet",
                "configured": bool(CLAUDE_API_KEY),
                "status": provider_status("claude", bool(CLAUDE_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "PRO",
                "frontier_models": ["claude-3-7-sonnet", "claude-3-5-sonnet", "claude-3-5-haiku"]
            },
            "openai": {
                "name": "OpenAI GPT-4o / o3-mini / o1",
                "configured": bool(OPENAI_API_KEY),
                "status": provider_status("openai", bool(OPENAI_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "PRO",
                "frontier_models": ["o3-mini", "o1", "gpt-4o", "gpt-4o-mini"]
            },
            "manus": {
                "name": "Manus AI Agent Pro",
                "configured": bool(MANUS_API_KEY),
                "status": provider_status("manus", bool(MANUS_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "PRO",
                "frontier_models": ["manus-agent-pro"]
            },
            "orcarouter": {
                "name": "OrcaRouter Gateway",
                "configured": bool(ORCAROUTER_API_KEY),
                "status": provider_status("orcarouter", bool(ORCAROUTER_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "GATEWAY",
                "frontier_models": ["orcarouter/auto", "orcarouter/free", "orcarouter/fusion", "deepseek/deepseek-v4-pro-0813"],
                "docs_url": "https://orcarouter.ai"
            },
            "anyrouter": {
                "name": "AnyRouter Multi-Agent Gateway",
                "configured": bool(ANYROUTER_API_KEY),
                "status": provider_status("anyrouter", bool(ANYROUTER_API_KEY)),
                "reachability": "NOT_PROBED",
                "tier": "GATEWAY",
                "frontier_models": ["anyrouter/free", "anyrouter/auto", "anyrouter/decision", "deepseek/deepseek-flash-latest"],
                "docs_url": "https://docs.anyrouter.dev"
            },
            "freellmapi": {
                "name": "FreeLLMAPI Unified Free Aggregator",
                "configured": bool(FREELLMAPI_ENABLED and FREELLMAPI_BASE_URL),
                "status": "DISABLED" if not FREELLMAPI_ENABLED else provider_status("freellmapi", bool(FREELLMAPI_BASE_URL)),
                "reachability": "NOT_PROBED",
                "tier": "100% FREE",
                "frontier_models": ["deepseek-r1", "llama-3.3-70b-versatile", "gemini-2.0-flash", "qwen-2.5-72b"],
                "github_url": "https://github.com/tashfeenahmed/freellmapi"
            },
            "active_mode": AI_PROVIDER,
            "routing_policy": self.get_routing_policy()
        }

    def analyze(
        self,
        symbol_info: Dict[str, Any],
        timeframe: str,
        metrics: Dict[str, Any],
        preferred_provider: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Dispatches analysis according to hybrid model routing policy with circuit breaking
        and full model provenance tracking.
        """
        provider = (preferred_provider or AI_PROVIDER).lower()

        # Built-in mathematical multi-agent mode: return immediately without remote HTTP calls
        if provider in ["quant", "math", "fast", "builtin", "local"]:
            return None

        caller_map = {
            "groq": call_groq,
            "gemini": call_gemini,
            "deepseek": call_deepseek,
            "openrouter": call_deepseek,
            "claude": call_claude,
            "openai": call_openai,
            "manus": call_manus,
            "freellmapi": call_freellmapi,
            "anyrouter": call_anyrouter,
            "orcarouter": call_orcarouter
        }

        provenance_log: List[Dict[str, Any]] = []

        # 1. Direct target provider requested
        if provider in caller_map:
            caller_func = caller_map[provider]
            if not self.is_provider_available(provider):
                logger.warning(f"Target provider {provider} circuit-broken. Cascading to fallback priority.")
                provenance_log.append({
                    "provider": provider,
                    "status": "CIRCUIT_BROKEN",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
            else:
                t0 = time.time()
                res = caller_func(symbol_info, timeframe, metrics)
                lat = int((time.time() - t0) * 1000)
                if res:
                    self.record_provider_result(provider, True)
                    provenance_log.append({
                        "provider": provider,
                        "model": res.get("_llm_meta", {}).get("model", provider),
                        "status": "SUCCESS",
                        "latency_ms": lat,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    })
                    if "_llm_meta" not in res:
                        res["_llm_meta"] = {}
                    res["_llm_meta"]["provenance"] = provenance_log
                    res["_llm_meta"]["fallback_occurred"] = False
                    return res
                else:
                    self.record_provider_result(provider, False)
                    provenance_log.append({
                        "provider": provider,
                        "status": "UNAVAILABLE_OR_FAILED",
                        "latency_ms": lat,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    })

        # 2. Configured Priority Cascade across Frontier LLMs
        priority_order = self.routing_policy.get(
            "priority_order",
            ["groq", "gemini", "deepseek", "claude", "openai", "manus"]
        )

        for prov_name in priority_order:
            if prov_name not in caller_map:
                continue
            if not self.is_provider_available(prov_name):
                provenance_log.append({
                    "provider": prov_name,
                    "status": "SKIPPED_CIRCUIT_OPEN",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                continue

            caller_func = caller_map[prov_name]
            t0 = time.time()
            res = caller_func(symbol_info, timeframe, metrics)
            lat = int((time.time() - t0) * 1000)

            if res:
                self.record_provider_result(prov_name, True)
                provenance_log.append({
                    "provider": prov_name,
                    "model": res.get("_llm_meta", {}).get("model", prov_name),
                    "status": "SUCCESS",
                    "latency_ms": lat,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                if "_llm_meta" not in res:
                    res["_llm_meta"] = {}
                res["_llm_meta"]["provenance"] = provenance_log
                res["_llm_meta"]["fallback_occurred"] = (len(provenance_log) > 1)
                if len(provenance_log) > 1:
                    res["_llm_meta"]["fallback_reason"] = f"Cascade switch to {prov_name} after preceding providers were unavailable."
                logger.info(f"Analysis successfully executed by real Frontier LLM: {prov_name} (Provenance: {len(provenance_log)} steps)")
                return res
            else:
                self.record_provider_result(prov_name, False)
                provenance_log.append({
                    "provider": prov_name,
                    "status": "UNAVAILABLE_OR_FAILED",
                    "latency_ms": lat,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })

        return None


# Global singleton instance
llm_orchestrator = LLMOrchestrator()

def get_llm_status() -> Dict[str, Any]:
    return llm_orchestrator.get_status()


# =========================================================================
# REAL MULTIMODAL AI & VISION ORCHESTRATION (PHONE & PC TERMINAL CHAT)
# =========================================================================

VISION_SYSTEM_PROMPT = """You are TAIKRY AI Institutional Vision & Multi-Agent Market Analyst.
You are inspecting an actual candlestick chart screenshot or market photo uploaded by a professional trader from their PC or mobile phone.
Analyze the chart with institutional Smart Money Concepts (SMC) & ICT methodologies:
1. Detect Market Structure: Trends, Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), Lower Lows (LL), Break of Structure (BOS), Change of Character (CHoCH).
2. Locate Order Blocks (OB), Fair Value Gaps (FVG), Inversion FVGs, and Liquidity Sweeps (Buy-side Liquidity BSL, Sell-side Liquidity SSL).
3. Evaluate Multi-Timeframe Alignment & Momentum (RSI, EMA 20/50/200, Volume).
4. Provide a Concrete Institutional Trade Setup:
   - Action: BUY, SELL, or HOLD
   - Entry Price (exact level or tight range)
   - Stop Loss (SL) (placed safely beyond structural swing high/low or invalidation)
   - Take Profit 1 (TP1) based on a measured target that meets the configured risk/reward floor
   - Take Profit 2 (TP2) (runner target at major structural swing)
   - Risk-to-Reward Ratio (must meet the configured minimum provided in context)
   - Confidence (0-100%)
5. Provide deep natural Khmer analysis (វិភាគមើលជាភាសាខ្មែរ) explaining:
   - ការវិភាគរចនាសម្ព័ន្ធទីផ្សារ (Market Structure)
   - តំបន់ FVG និង Order Block
   - ចំណុចចូល (Entry), កាត់ខាត (SL), យកចំណេញ (TP1, TP2)
   - ការគ្រប់គ្រងហានិភ័យតាមកម្រិតដែលបានកំណត់ក្នុងបរិបទ

You must respond ONLY with a valid parseable JSON object matching this schema:
{
  "smart_analysis": {
    "synthesis_summary_en": "<deep institutional analysis of the uploaded chart in English>",
    "synthesis_summary_kh": "<ការវិភាគមើលលម្អិតជាភាសាខ្មែរ ពន្យល់ពីរចនាសម្ព័ន្ធទីផ្សារ FVG Order Block និន្នាការ និងយុទ្ធសាស្ត្រជួញដូរ>",
    "chart_observations": [
      "<observation 1, e.g. Bearish FVG identified between 4048 and 4052>",
      "<observation 2, e.g. Liquidity sweep of Asian session high at 4055>"
    ],
    "smc_causes": [
      "<specific institutional cause 1>",
      "<specific institutional cause 2>"
    ]
  },
  "trade_execution": {
    "action": "BUY" | "SELL" | "HOLD",
    "entry_price": <number>,
    "stop_loss": <number>,
    "take_profit_1": <number>,
    "take_profit_2": <number>,
    "risk_reward_ratio": "<string e.g. 1:2.5>",
    "confidence": <integer 0-100>,
    "invalidation_level": <number or string>
  }
}
"""


def call_multimodal_vision(
    image_base64: str,
    prompt: Optional[str] = None,
    symbol: str = "XAUUSD",
    timeframe: str = "15m",
    market_context: Optional[Dict[str, Any]] = None,
    timeout: int = 15
) -> Optional[Dict[str, Any]]:
    """
    Multimodal Vision analyzer for chart screenshots and photos uploaded from phone or PC.
    Directly inspects candlesticks, order blocks, fair value gaps (FVG), swing levels, and momentum.
    Uses Google Gemini (gemini-3-flash-preview / gemini-flash-latest) with inline_data,
    with fallback to OpenRouter multimodal vision.
    """
    if not image_base64:
        return None

    # Parse mime type and extract raw base64 data
    mime_type = "image/png"
    clean_b64 = image_base64.strip()
    if clean_b64.startswith("data:"):
        parts = clean_b64.split(",", 1)
        if len(parts) == 2:
            header, clean_b64 = parts
            if ";" in header and ":" in header:
                mime_type = header.split(";")[0].replace("data:", "").strip()

    ctx_text = ""
    if market_context:
        ctx_text = f"\nMarket Reference Context:\n- Verified Price: {market_context.get('price', 'N/A')}\n- Asset: {symbol}\n- Timeframe: {timeframe}\n- Technical Bias: {market_context.get('bias', 'N/A')}\n"

    full_prompt = f"""Asset: {symbol}
Timeframe: {timeframe}
Trader Query / Note: {prompt or 'Analyze this chart thoroughly with institutional SMC/ICT rules, provide Entry, SL, TP, and វិភាគមើលជាភាសាខ្មែរ.'}
{ctx_text}
Perform institutional visual chart analysis:
1. Identify market trend, swing highs/lows, BOS, and CHoCH.
2. Locate Fair Value Gaps (FVG) and Order Blocks (OB).
3. Formulate a trade decision only from provided evidence and configured risk rules; otherwise return HOLD with no price levels.
4. Provide deep Natural Khmer analysis (វិភាគមើលជាភាសាខ្មែរ) explaining the structure and reason for entry.
Respond ONLY with valid JSON matching the schema.
"""

    # 1. Try Google Gemini Multimodal Vision first
    if GEMINI_API_KEY:
        gemini_models = ["gemini-3-flash-preview", "gemini-flash-latest", "gemini-pro-latest"]
        for g_model in gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": VISION_SYSTEM_PROMPT + "\n\n" + full_prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": clean_b64
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2
                }
            }
            try:
                t0 = time.time()
                resp = requests.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        parsed = _extract_json_from_response(raw_text)
                        if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                            lat = int((time.time() - t0) * 1000)
                            parsed["_llm_meta"] = {
                                "provider": "gemini",
                                "model": g_model,
                                "type": "MULTIMODAL_VISION",
                                "latency_ms": lat,
                                "status": "SUCCESS"
                            }
                            return parsed
                else:
                    logger.warning(f"Gemini vision ({g_model}) returned {resp.status_code}: {resp.text[:120]}")
            except Exception as e:
                logger.warning(f"Gemini vision ({g_model}) exception: {e}")

    # 2. Try OpenRouter multimodal vision fallback
    if OPENROUTER_API_KEY:
        or_models = ["google/gemma-3-27b-it", "google/gemini-2.5-flash-image", "qwen/qwen2.5-vl-72b-instruct"]
        for or_m in or_models:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": or_m,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_SYSTEM_PROMPT + "\n\n" + full_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{clean_b64}"}}
                    ]
                }],
                "temperature": 0.2
            }
            try:
                t0 = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    raw_text = resp.json()["choices"][0]["message"]["content"]
                    parsed = _extract_json_from_response(raw_text)
                    if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                        lat = int((time.time() - t0) * 1000)
                        parsed["_llm_meta"] = {
                            "provider": "openrouter",
                            "model": or_m,
                            "type": "MULTIMODAL_VISION",
                            "latency_ms": lat,
                            "status": "SUCCESS"
                        }
                        return parsed
            except Exception as e:
                logger.warning(f"OpenRouter vision ({or_m}) exception: {e}")

    return None


def chat_with_real_ai(
    query: str,
    symbol: str = "XAUUSD",
    timeframe: str = "15m",
    provider: str = "auto",
    image_base64: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for Real AI Chat in Web UI (no simulated mock data).
    Integrates:
    - Real multimodal vision if image/photo is sent from phone or PC.
    - Real Frontier LLMs (Groq 120B, Gemini 3 Flash, OpenRouter Llama 3.3 70B, Claude, OpenAI).
    - Real-time verified market prices & technical SMC levels.
    - Trade decision and any measured levels must conform to configured risk rules and verified data.
    - វិភាគមើលជាភាសាខ្មែរ (Market Structure, FVG, Order Blocks, Liquidity, Trend).
    """
    sym = (symbol or "XAUUSD").upper().replace("/", "").replace("-", "")
    tf = timeframe or "15m"
    prov = (provider or "auto").lower()

    # Get live verified market data for context
    price_val = None
    price_src = "N/A"
    try:
        from taikry.data.providers import market_data_engine, REFERENCE_BASE_PRICES
        p, src, _ = market_data_engine.get_verified_price(sym)
        if p and p > 0:
            price_val = round(p, 2)
            price_src = src
    except Exception:
        pass

    market_ctx = {
        "price": price_val,
        "price_source": price_src,
        "symbol": sym,
        "timeframe": tf
    }

    t_start = time.time()

    # CASE A: Photo / Screenshot Uploaded
    if image_base64:
        logger.info(f"Processing multimodal chart photo analysis for {sym} ({len(image_base64)} chars)")
        vision_res = call_multimodal_vision(
            image_base64=image_base64,
            prompt=query,
            symbol=sym,
            timeframe=tf,
            market_context=market_ctx
        )
        if vision_res:
            latency = int((time.time() - t_start) * 1000)
            meta = vision_res.get("_llm_meta", {})
            return {
                "status": "SUCCESS",
                "has_photo": True,
                "provider": meta.get("provider", "gemini"),
                "model": meta.get("model", "gemini-3-flash-preview"),
                "latency_ms": meta.get("latency_ms", latency),
                "symbol": sym,
                "timeframe": tf,
                "smart_analysis": vision_res.get("smart_analysis", {}),
                "trade_execution": {
                    "setup_status": "NO_APPROVED_SETUP",
                    "action": "HOLD",
                    "entry_price": None,
                    "stop_loss": None,
                    "take_profit_1": None,
                    "take_profit_2": None,
                    "risk_reward_ratio": "N/A",
                    "confidence": None
                }
            }

    # CASE B: Real LLM Text Analysis (Groq 120B / Gemini / OpenRouter)
    # Fast market context retrieval (instantaneous cache lookup)
    live_bias = "NEUTRAL"
    live_dir = "HOLD"
    live_entry = live_sl = live_tp1 = live_tp2 = None
    live_rr = "N/A"
    live_conf = None
    approved_setup = None

    try:
        from taikry.agents.consensus_engine import _ANALYSIS_CACHE
        for k, v in list(_ANALYSIS_CACHE.items()):
            if k.startswith(f"{sym}:") and isinstance(v, (tuple, list)) and len(v) > 1:
                cached = v[1]
                if not isinstance(cached, dict) or cached.get("setup_status") != "APPROVE":
                    continue
                if not cached.get("timestamp_utc"):
                    continue
                direction = str(cached.get("proposed_direction") or "").upper()
                score = cached.get("confidence_score", cached.get("ai_score"))
                try:
                    entry = float(cached.get("entry_price"))
                    stop = float(cached.get("stop_loss"))
                    target_1 = float(cached.get("take_profit_1"))
                    score = float(score)
                except (TypeError, ValueError):
                    continue
                from taikry.data.validator import check_data_freshness
                freshness = check_data_freshness(sym, cached.get("timestamp_utc"), "M15")
                source = str(cached.get("price_source", "")).upper()
                direction_valid = (
                    direction in ("LONG", "BUY") and stop < entry < target_1
                ) or (
                    direction in ("SHORT", "SELL") and stop > entry > target_1
                )
                if not direction_valid or not freshness.get("fresh") or "DEMO_SYNTHETIC" in source or not 80 <= score <= 95:
                    continue
                live_bias = cached.get("market_bias", "NEUTRAL")
                live_dir = "BUY" if direction in ("LONG", "BUY") else "SELL"
                live_entry, live_sl, live_tp1 = entry, stop, target_1
                try:
                    candidate_tp2 = float(cached.get("take_profit_2"))
                    live_tp2 = candidate_tp2 if (candidate_tp2 > target_1 if live_dir == "BUY" else candidate_tp2 < target_1) else None
                except (TypeError, ValueError):
                    live_tp2 = None
                live_rr = cached.get("risk_reward_ratio") or "N/A"
                live_conf = score
                approved_setup = cached
                break
    except Exception:
        pass

    deep_research_data = None
    try:
        from taikry.agents.deep_research_engine import deep_research_engine
        dr_res = deep_research_engine.run_deep_research(sym, timeframe=tf)
        deep_research_data = dr_res.get("sections")
    except Exception as e:
        logger.debug(f"Deep research engine notice: {e}")

    macro_note = ""
    cal_note = ""
    if deep_research_data:
        cal = deep_research_data.get("C_upcoming_news_calendar", {})
        macro = deep_research_data.get("D_macro_impact", {})
        cal_note = f"Upcoming Catalyst: {cal.get('event_name')} ({cal.get('currency')}) at {cal.get('event_time_utc')} | Forecast: {cal.get('forecast')} | Previous: {cal.get('previous')} | Blackout: {cal.get('blackout_status')}"
        macro_note = f"DXY Index: {macro.get('dxy_index')} ({macro.get('dxy_trend')}) | Monetary Regime: {macro.get('monetary_policy_regime')}"

    llm_prompt = f"""Trader Query: {query}
Asset: {sym}
Execution Timeframe: {tf}
Live Market Context:
- Current Verified Price: {price_val} ({price_src})
- Multi-Agent Direction Bias: {live_dir} ({live_bias})
- Macro & Calendar Context: {cal_note} | {macro_note}
- Approved consensus setup: {"Entry=" + str(live_entry) + ", SL=" + str(live_sl) + ", TP1=" + str(live_tp1) + ", TP2=" + str(live_tp2) + ", R:R=" + str(live_rr) if approved_setup else "None; no approved fresh setup is available"}

Perform full institutional trade analysis and answer the trader's query:
1. Provide deep smart causal analysis in English (synthesis_summary_en) explaining technical indicators, SMC order block / FVG mitigation, and global news impact.
2. Provide clear Natural Khmer analysis (synthesis_summary_kh / វិភាគមើលជាភាសាខ្មែរ) explaining the evidence, uncertainty, and configured capital-protection rules. Do not invent a risk percentage.
3. If an approved consensus setup is shown above, copy its exact action and price levels into trade_execution without changing them. If no approved setup is shown, action must be "HOLD" and all price levels must be null, risk_reward_ratio "N/A", and confidence null. Never invent entry, stop, target, direction, or confidence values.
Respond strictly in JSON matching the schema.
"""

    llm_res = None
    used_provider = "groq"
    used_model = "openai/gpt-oss-120b"

    # FreeLLMAPI execution if requested or available
    if not llm_res and (prov in ["freellmapi", "auto"]):
        from taikry.ai.freellmapi_client import freellmapi_client
        if prov == "freellmapi" or (not GROQ_API_KEY and not GEMINI_API_KEY and not OPENROUTER_API_KEY):
            try:
                fl_res = freellmapi_client.chat_completion(
                    messages=[
                        {"role": "system", "content": LLM_SYSTEM_PROMPT},
                        {"role": "user", "content": llm_prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                if fl_res.get("success"):
                    raw = fl_res.get("content", "")
                    parsed = _extract_json_from_response(raw)
                    if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                        llm_res = parsed
                        used_provider = "freellmapi"
                        used_model = fl_res.get("model", "deepseek-r1")
            except Exception as e:
                logger.warning(f"FreeLLMAPI chat notice: {e}")

    # Direct Groq call if auto or groq
    if not llm_res and prov in ["groq", "auto"]:
        if GROQ_API_KEY:
            for g_mod in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
                try:
                    t0 = time.time()
                    resp = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": g_mod,
                            "messages": [
                                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                                {"role": "user", "content": llm_prompt}
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.2
                        },
                        timeout=8
                    )
                    if resp.status_code == 200:
                        raw = resp.json()["choices"][0]["message"]["content"]
                        parsed = _extract_json_from_response(raw)
                        if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                            llm_res = parsed
                            used_provider = "groq"
                            used_model = g_mod
                            break
                except Exception as e:
                    logger.warning(f"Groq chat ({g_mod}) failed: {e}")

    # Fallback to Gemini if Groq didn't succeed or if provider is gemini
    if not llm_res and (prov in ["gemini", "auto"]) and GEMINI_API_KEY:
        for m in ["gemini-3-flash-preview", "gemini-flash-latest", "gemini-pro-latest"]:
            try:
                t0 = time.time()
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": LLM_SYSTEM_PROMPT + "\n\n" + llm_prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}
                    },
                    timeout=8
                )
                if resp.status_code == 200:
                    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = _extract_json_from_response(raw)
                    if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                        llm_res = parsed
                        used_provider = "gemini"
                        used_model = m
                        break
            except Exception as e:
                logger.warning(f"Gemini chat ({m}) failed: {e}")

    # Fallback to OpenRouter (Llama 3.3 70B)
    if not llm_res and OPENROUTER_API_KEY:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct",
                    "messages": [
                        {"role": "system", "content": LLM_SYSTEM_PROMPT},
                        {"role": "user", "content": llm_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                },
                timeout=8
            )
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"]
                parsed = _extract_json_from_response(raw)
                if parsed and ("smart_analysis" in parsed or "trade_execution" in parsed):
                    llm_res = parsed
                    used_provider = "openrouter"
                    used_model = "meta-llama/llama-3.3-70b-instruct"
        except Exception as e:
            logger.warning(f"OpenRouter chat failed: {e}")

    total_lat = int((time.time() - t_start) * 1000)

    # If LLM succeeded:
    if llm_res:
        smart_analysis = llm_res.get("smart_analysis", {})
        if approved_setup:
            trade_execution = {
                "setup_status": "APPROVE",
                "action": live_dir,
                "entry_price": live_entry,
                "stop_loss": live_sl,
                "take_profit_1": live_tp1,
                "take_profit_2": live_tp2,
                "risk_reward_ratio": live_rr,
                "confidence": live_conf
            }
        else:
            trade_execution = {
                "setup_status": "NO_APPROVED_SETUP",
                "action": "HOLD",
                "entry_price": None,
                "stop_loss": None,
                "take_profit_1": None,
                "take_profit_2": None,
                "risk_reward_ratio": "N/A",
                "confidence": None
            }

        return {
            "status": "SUCCESS",
            "has_photo": bool(image_base64),
            "provider": used_provider,
            "model": used_model,
            "latency_ms": total_lat,
            "symbol": sym,
            "timeframe": tf,
            "smart_analysis": smart_analysis,
            "trade_execution": trade_execution,
            "deep_research": deep_research_data
        }

    # Safe response when no configured language model returns a result.
    if approved_setup:
        fallback_en = f"A fresh approved {live_dir} setup is available for {sym} at the validated levels shown in trade_execution. Review the source and risk before acting."
        fallback_kh = f"មានសញ្ញា {live_dir} ដែលបានអនុម័តថ្មីសម្រាប់ {sym}។ សូមពិនិត្យតម្លៃ និងហានិភ័យក្នុង trade_execution មុនធ្វើសកម្មភាព។"
    else:
        fallback_en = f"No fresh approved trade setup is available for {sym}. Wait for a new scan with valid market data."
        fallback_kh = f"មិនមានសញ្ញាជួញដូរដែលបានអនុម័តថ្មីសម្រាប់ {sym} ទេ។ សូមរង់ចាំការស្កេនថ្មីដែលមានទិន្នន័យត្រឹមត្រូវ។"
    return {
        "status": "SUCCESS",
        "has_photo": bool(image_base64),
        "provider": "institutional_consensus",
        "model": "quant_engine",
        "latency_ms": total_lat,
        "symbol": sym,
        "timeframe": tf,
        "smart_analysis": {
            "synthesis_summary_en": fallback_en,
            "synthesis_summary_kh": fallback_kh
        },
        "trade_execution": {
            "action": live_dir,
            "setup_status": "APPROVE" if approved_setup else "NO_APPROVED_SETUP",
            "entry_price": live_entry,
            "stop_loss": live_sl,
            "take_profit_1": live_tp1,
            "take_profit_2": live_tp2,
            "risk_reward_ratio": live_rr,
            "confidence": live_conf
        },
        "deep_research": deep_research_data
    }

