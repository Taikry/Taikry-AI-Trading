"""
TAIKRY Real AI LLM Integration Package
Supports Groq (Free), OpenRouter/DeepSeek (Free), Gemini (Free), Claude, OpenAI, and Manus AI.
"""
from taikry.ai.llm_client import (
    llm_orchestrator,
    call_groq,
    call_deepseek,
    call_gemini,
    call_claude,
    call_openai,
    call_manus,
    get_llm_status
)

__all__ = [
    "llm_orchestrator",
    "call_groq",
    "call_deepseek",
    "call_gemini",
    "call_claude",
    "call_openai",
    "call_manus",
    "get_llm_status"
]
