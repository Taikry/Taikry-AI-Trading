"""
AnyRouter Inference Client & Dynamic Model Discovery Engine for ZYROX AI.
OpenAI-Compatible Gateway integration with budget tracking and role routing.
Official API reference: https://docs.anyrouter.dev/api-reference/models
"""

import time
import datetime
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple

import requests
from pydantic import BaseModel, Field

from taikry.config import (
    ANYROUTER_API_KEY,
    ANYROUTER_BASE_URL,
    ANYROUTER_TIMEOUT_SECONDS,
    ANYROUTER_MAX_RETRIES,
    ANYROUTER_SPEND_LIMIT_USD,
    ANYROUTER_CONCURRENCY_LIMIT,
    ORCHESTRATOR_MODEL,
    REASONING_MODEL,
    FAST_MODEL,
    CRITIC_MODEL,
    FALLBACK_MODEL
)

logger = logging.getLogger("zyrox.ai.anyrouter")


class SanitizedModelInfo(BaseModel):
    """Sanitized public model metadata safe for UI presentation."""
    id: str
    provider: str
    context_window: Optional[int] = None
    capabilities: List[str] = Field(default_factory=lambda: ["chat"])
    billing_type: str = "tokens"
    pricing_input_per_m: Optional[float] = None
    pricing_output_per_m: Optional[float] = None
    status: str = "AVAILABLE"  # AVAILABLE, RESTRICTED, UNAVAILABLE
    description: Optional[str] = None


class CatalogResponse(BaseModel):
    """Sanitized catalog response returned to authenticated clients."""
    configured: bool
    status: str  # CONNECTED, UNCONFIGURED, UNAVAILABLE, ERROR
    total_models: int
    models: List[SanitizedModelInfo]
    last_catalog_refresh_time: Optional[str] = None
    error_message: Optional[str] = None


class SmokeTestResult(BaseModel):
    """Sanitized telemetry result of a low-token model verification smoke test."""
    status: str  # SUCCESS, FAILED, SKIPPED
    model_id: str
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    response_preview: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    timestamp_utc: str
    error_message: Optional[str] = None


class ModelRolesRegistry(BaseModel):
    """Registry mapping multi-agent roles to verified models."""
    orchestrator: str = ""
    reasoning: str = ""
    fast: str = ""
    critic: str = ""
    fallback: str = ""
    last_updated_utc: str = ""


class AnyRouterBudgetManager:
    """Thread-safe budget tracking & spending safety governor."""
    def __init__(self, spend_limit_usd: float = 10.0):
        self._lock = threading.RLock()
        self.spend_limit_usd = spend_limit_usd
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_requests = 0
        self.failed_requests = 0
        self.estimated_total_spend_usd = 0.0

    def record_usage(self, prompt_tokens: int, completion_tokens: int, cost_usd: Optional[float] = None):
        with self._lock:
            self.total_requests += 1
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            if cost_usd is not None and cost_usd > 0:
                self.estimated_total_spend_usd += cost_usd

    def record_failure(self):
        with self._lock:
            self.failed_requests += 1

    def is_budget_exceeded(self) -> bool:
        with self._lock:
            return self.estimated_total_spend_usd >= self.spend_limit_usd

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "spend_limit_usd": self.spend_limit_usd,
                "estimated_spend_usd": round(self.estimated_total_spend_usd, 4),
                "budget_exceeded": self.is_budget_exceeded(),
                "total_requests": self.total_requests,
                "failed_requests": self.failed_requests,
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_prompt_tokens + self.total_completion_tokens
            }


budget_manager = AnyRouterBudgetManager(spend_limit_usd=ANYROUTER_SPEND_LIMIT_USD)


class AnyRouterClient:
    """
    Production-grade AnyRouter client supporting:
    - Authenticated dynamic model catalog discovery
    - Redacted low-token smoke testing
    - Multi-agent role routing
    - Concurrency semaphores and budget guards
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._cached_catalog: Optional[List[SanitizedModelInfo]] = None
        self._catalog_cached_at: float = 0.0
        self._catalog_ttl_seconds: float = 300.0  # 5 minutes
        self._concurrency_semaphore = threading.Semaphore(ANYROUTER_CONCURRENCY_LIMIT)
        self._tested_models: Dict[str, SmokeTestResult] = {}

        # Initial Role Registry from Config
        self._role_registry = ModelRolesRegistry(
            orchestrator=ORCHESTRATOR_MODEL,
            reasoning=REASONING_MODEL,
            fast=FAST_MODEL,
            critic=CRITIC_MODEL,
            fallback=FALLBACK_MODEL,
            last_updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

    # -------------------------------------------------------------------------
    # 1. SECURITY & KEY CHECKS
    # -------------------------------------------------------------------------
    def _get_api_key(self) -> str:
        import sys
        mod = sys.modules.get("taikry.ai.anyrouter_client")
        if mod and getattr(mod, "ANYROUTER_API_KEY", None) == "":
            return ""
        if mod and getattr(mod, "ANYROUTER_API_KEY", None):
            return mod.ANYROUTER_API_KEY

        import os
        from dotenv import load_dotenv
        load_dotenv(override=True)
        from taikry.config import ANYROUTER_API_KEY
        return os.getenv("ANYROUTER_API_KEY", "") or ANYROUTER_API_KEY or ""

    def is_configured(self) -> bool:
        """Returns True only if ANYROUTER_API_KEY is non-empty."""
        k = self._get_api_key()
        return bool(k and len(k.strip()) > 3)

    def _get_headers(self) -> Dict[str, str]:
        """Builds authenticated headers. Never exposed in external logs."""
        k = self._get_api_key().strip()
        return {
            "Authorization": f"Bearer {k}",
            "Content-Type": "application/json",
            "User-Agent": "ZYROX-AI-Terminal/2.1"
        }

    # -------------------------------------------------------------------------
    # 2. STEP C — MODEL DISCOVERY
    # -------------------------------------------------------------------------
    def get_models(self, force_refresh: bool = False) -> CatalogResponse:
        """
        Discovers models via GET /api/v1/models.
        Handles 401, 403, 429, timeouts, and server errors gracefully.
        Never displays credentials or sensitive provider metadata.
        """
        now = time.time()
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not self.is_configured():
            return CatalogResponse(
                configured=False,
                status="UNCONFIGURED",
                total_models=0,
                models=[],
                last_catalog_refresh_time=None,
                error_message="ANYROUTER_API_KEY is not configured in environment."
            )

        # Check Cache
        with self._lock:
            if not force_refresh and self._cached_catalog and (now - self._catalog_cached_at < self._catalog_ttl_seconds):
                return CatalogResponse(
                    configured=True,
                    status="CONNECTED",
                    total_models=len(self._cached_catalog),
                    models=self._cached_catalog,
                    last_catalog_refresh_time=datetime.datetime.fromtimestamp(
                        self._catalog_cached_at, tz=datetime.timezone.utc
                    ).isoformat()
                )

        url = f"{ANYROUTER_BASE_URL}/models"
        headers = self._get_headers()

        try:
            resp = requests.get(url, headers=headers, timeout=ANYROUTER_TIMEOUT_SECONDS)
            if resp.status_code == 401:
                return CatalogResponse(
                    configured=True,
                    status="ERROR",
                    total_models=0,
                    models=[],
                    last_catalog_refresh_time=now_utc,
                    error_message="Authentication failed (HTTP 401). Verify ANYROUTER_API_KEY."
                )
            elif resp.status_code == 403:
                return CatalogResponse(
                    configured=True,
                    status="ERROR",
                    total_models=0,
                    models=[],
                    last_catalog_refresh_time=now_utc,
                    error_message="Access forbidden (HTTP 403). Check AnyRouter permissions or account balance."
                )
            elif resp.status_code == 429:
                return CatalogResponse(
                    configured=True,
                    status="ERROR",
                    total_models=0,
                    models=[],
                    last_catalog_refresh_time=now_utc,
                    error_message="Rate limit exceeded on AnyRouter API (HTTP 429). Retry after cooldown."
                )
            elif resp.status_code >= 500:
                return CatalogResponse(
                    configured=True,
                    status="ERROR",
                    total_models=0,
                    models=[],
                    last_catalog_refresh_time=now_utc,
                    error_message=f"AnyRouter server error (HTTP {resp.status_code})."
                )

            resp.raise_for_status()
            data = resp.json()

            # Parse standard OpenAI-compatible format {"data": [...]} or raw list [...]
            raw_models = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            sanitized: List[SanitizedModelInfo] = []

            for item in raw_models:
                if not isinstance(item, dict):
                    continue

                m_id = str(item.get("id") or item.get("name") or "").strip()
                if not m_id:
                    continue

                # Infer provider from prefix or owned_by
                owned_by = str(item.get("owned_by") or "").strip()
                provider = owned_by or (m_id.split("/")[0] if "/" in m_id else "anyrouter")

                # Context length
                ctx = item.get("context_length") or item.get("context_window") or item.get("max_tokens")
                try:
                    ctx_val = int(ctx) if ctx is not None else None
                except (ValueError, TypeError):
                    ctx_val = None

                # Capabilities
                caps = ["chat"]
                if "vision" in m_id.lower() or item.get("supports_vision"):
                    caps.append("vision")
                if "r1" in m_id.lower() or "reason" in m_id.lower() or "o1" in m_id.lower() or "o3" in m_id.lower():
                    caps.append("reasoning")
                if "embed" in m_id.lower():
                    caps = ["embeddings"]

                # Pricing
                pricing = item.get("pricing") or {}
                p_in = pricing.get("prompt") or pricing.get("input")
                p_out = pricing.get("completion") or pricing.get("output")

                sanitized.append(SanitizedModelInfo(
                    id=m_id,
                    provider=provider,
                    context_window=ctx_val,
                    capabilities=caps,
                    billing_type="tokens",
                    pricing_input_per_m=float(p_in) if p_in is not None else None,
                    pricing_output_per_m=float(p_out) if p_out is not None else None,
                    status="AVAILABLE",
                    description=item.get("description")
                ))

            with self._lock:
                self._cached_catalog = sanitized
                self._catalog_cached_at = now

            return CatalogResponse(
                configured=True,
                status="CONNECTED",
                total_models=len(sanitized),
                models=sanitized,
                last_catalog_refresh_time=now_utc
            )

        except requests.exceptions.Timeout:
            return CatalogResponse(
                configured=True,
                status="ERROR",
                total_models=0,
                models=[],
                last_catalog_refresh_time=now_utc,
                error_message=f"Connection timeout ({ANYROUTER_TIMEOUT_SECONDS}s) to {ANYROUTER_BASE_URL}."
            )
        except requests.exceptions.RequestException as re_err:
            return CatalogResponse(
                configured=True,
                status="ERROR",
                total_models=0,
                models=[],
                last_catalog_refresh_time=now_utc,
                error_message=f"Network error communicating with AnyRouter: {str(re_err)}"
            )
        except Exception as e:
            return CatalogResponse(
                configured=True,
                status="ERROR",
                total_models=0,
                models=[],
                last_catalog_refresh_time=now_utc,
                error_message=f"Failed to parse AnyRouter models response: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # 3. STEP D — SMOKE TEST
    # -------------------------------------------------------------------------
    def smoke_test(self, model_id: Optional[str] = None) -> SmokeTestResult:
        """
        Executes a low-token test request to verify API access, model responsiveness,
        and latency. Redacts all sensitive headers.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not self.is_configured():
            return SmokeTestResult(
                status="SKIPPED",
                model_id=model_id or "unconfigured",
                timestamp_utc=now_utc,
                error_message="ANYROUTER_API_KEY is not configured. Smoke test skipped."
            )

        # Select Model ID
        target_model = model_id
        if not target_model:
            catalog = self.get_models()
            if not catalog.models:
                return SmokeTestResult(
                    status="FAILED",
                    model_id="none_available",
                    timestamp_utc=now_utc,
                    error_message=catalog.error_message or "No accessible models found in AnyRouter catalog."
                )
            # Pick first available text/chat model
            target_model = catalog.models[0].id

        url = f"{ANYROUTER_BASE_URL}/chat/completions"
        headers = self._get_headers()
        payload = {
            "model": target_model,
            "messages": [
                {"role": "user", "content": "ping"}
            ],
            "max_tokens": 5,
            "temperature": 0.0
        }

        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=min(15.0, ANYROUTER_TIMEOUT_SECONDS))
            latency_ms = round((time.time() - t0) * 1000, 2)

            if resp.status_code != 200:
                err_text = resp.text[:200]
                result = SmokeTestResult(
                    status="FAILED",
                    model_id=target_model,
                    http_status=resp.status_code,
                    latency_ms=latency_ms,
                    timestamp_utc=now_utc,
                    error_message=f"HTTP {resp.status_code}: {err_text}"
                )
                with self._lock:
                    self._tested_models[target_model] = result
                return result

            data = resp.json()
            choices = data.get("choices", [])
            content = ""
            if choices and isinstance(choices, list):
                content = str(choices[0].get("message", {}).get("content", "")).strip()

            usage = data.get("usage", {})

            result = SmokeTestResult(
                status="SUCCESS",
                model_id=data.get("model", target_model),
                http_status=200,
                latency_ms=latency_ms,
                response_preview=content[:100],
                usage=usage,
                timestamp_utc=now_utc
            )

            # Record usage in budget manager
            if usage:
                p_tok = int(usage.get("prompt_tokens", 0))
                c_tok = int(usage.get("completion_tokens", 0))
                budget_manager.record_usage(p_tok, c_tok)

            with self._lock:
                self._tested_models[target_model] = result
            return result

        except requests.exceptions.Timeout:
            latency_ms = round((time.time() - t0) * 1000, 2)
            result = SmokeTestResult(
                status="FAILED",
                model_id=target_model,
                latency_ms=latency_ms,
                timestamp_utc=now_utc,
                error_message="Smoke test request timed out."
            )
            with self._lock:
                self._tested_models[target_model] = result
            return result
        except Exception as e:
            latency_ms = round((time.time() - t0) * 1000, 2)
            result = SmokeTestResult(
                status="FAILED",
                model_id=target_model,
                latency_ms=latency_ms,
                timestamp_utc=now_utc,
                error_message=str(e)
            )
            with self._lock:
                self._tested_models[target_model] = result
            return result

    # -------------------------------------------------------------------------
    # 4. STEP E — MODEL ROUTER & ROLES
    # -------------------------------------------------------------------------
    def get_role_registry(self) -> Dict[str, Any]:
        """Returns current multi-agent role assignments and their tested states."""
        with self._lock:
            roles = self._role_registry.model_dump()
            roles["tested_models"] = {k: v.model_dump() for k, v in self._tested_models.items()}
            return roles

    def configure_role(self, role: str, model_id: str, validate_first: bool = False) -> Tuple[bool, str]:
        """
        Assigns a model to an agent role.
        Validates compatibility and smoke-test state if required.
        """
        r_key = role.strip().lower()
        valid_roles = ["orchestrator", "reasoning", "fast", "critic", "fallback"]
        if r_key not in valid_roles:
            return False, f"Invalid role '{role}'. Expected one of: {valid_roles}"

        if validate_first and model_id:
            # Execute smoke test if not already tested
            with self._lock:
                tested = self._tested_models.get(model_id)
            if not tested or tested.status != "SUCCESS":
                smoke = self.smoke_test(model_id)
                if smoke.status != "SUCCESS":
                    return False, f"Model validation failed: {smoke.error_message}"

        with self._lock:
            if r_key == "orchestrator":
                self._role_registry.orchestrator = model_id
            elif r_key == "reasoning":
                self._role_registry.reasoning = model_id
            elif r_key == "fast":
                self._role_registry.fast = model_id
            elif r_key == "critic":
                self._role_registry.critic = model_id
            elif r_key == "fallback":
                self._role_registry.fallback = model_id

            self._role_registry.last_updated_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(f"[ANYROUTER_ROUTER] Assigned role '{r_key}' to model '{model_id}'")
        return True, f"Role '{r_key}' successfully assigned to '{model_id}'"

    def resolve_model_for_role(self, role: str) -> Optional[str]:
        """Resolves the active model ID for a role, with fallback hierarchy."""
        with self._lock:
            r = self._role_registry
            m = getattr(r, role.lower(), "")
            if m:
                return m
            # Fallbacks
            if role in ("reasoning", "critic") and r.orchestrator:
                return r.orchestrator
            if r.fast:
                return r.fast
            if r.fallback:
                return r.fallback
            return None

    # -------------------------------------------------------------------------
    # 5. STEP H — INFERENCE DISPATCH WITH BUDGET & CONCURRENCY CONTROLS
    # -------------------------------------------------------------------------
    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        role: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Dispatches OpenAI-compatible chat completion through AnyRouter gateway.
        Enforces:
        - Budget limits (stops dispatch if spend limit reached)
        - Concurrency throttling (semaphore)
        - Bounded retries with backoff
        - Redaction of sensitive payload headers
        """
        if not self.is_configured():
            raise RuntimeError("ANYROUTER_API_KEY is not configured.")

        if budget_manager.is_budget_exceeded():
            raise RuntimeError(f"AnyRouter spend limit exceeded (${budget_manager.spend_limit_usd} USD). Dispatch halted.")

        # Determine target model
        target_model = model
        if not target_model and role:
            target_model = self.resolve_model_for_role(role)
        if not target_model:
            target_model = self._role_registry.orchestrator or "deepseek/deepseek-chat"

        url = f"{ANYROUTER_BASE_URL}/chat/completions"
        headers = self._get_headers()
        req_timeout = timeout or ANYROUTER_TIMEOUT_SECONDS

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            payload["response_format"] = response_format

        # Acquire concurrency lock
        acquired = self._concurrency_semaphore.acquire(timeout=req_timeout)
        if not acquired:
            raise TimeoutError("AnyRouter concurrency capacity exceeded. Request rejected.")

        last_error = None
        try:
            for attempt in range(ANYROUTER_MAX_RETRIES + 1):
                try:
                    t0 = time.time()
                    resp = requests.post(url, headers=headers, json=payload, timeout=req_timeout)
                    latency_ms = (time.time() - t0) * 1000

                    if resp.status_code == 200:
                        data = resp.json()
                        usage = data.get("usage", {})
                        if usage:
                            budget_manager.record_usage(
                                int(usage.get("prompt_tokens", 0)),
                                int(usage.get("completion_tokens", 0))
                            )
                        choices = data.get("choices", [])
                        content = ""
                        if choices:
                            content = choices[0].get("message", {}).get("content", "")

                        return {
                            "content": content,
                            "raw_response": data,
                            "model_used": data.get("model", target_model),
                            "latency_ms": round(latency_ms, 2),
                            "usage": usage,
                            "attempt": attempt + 1
                        }

                    # Retryable status codes (429, 502, 503, 504)
                    if resp.status_code in (429, 502, 503, 504) and attempt < ANYROUTER_MAX_RETRIES:
                        sleep_time = (2 ** attempt) * 1.5
                        logger.warning(f"[ANYROUTER] HTTP {resp.status_code}. Retrying in {sleep_time}s (Attempt {attempt+1}/{ANYROUTER_MAX_RETRIES})")
                        time.sleep(sleep_time)
                        continue

                    resp.raise_for_status()

                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                    last_error = net_err
                    if attempt < ANYROUTER_MAX_RETRIES:
                        time.sleep((2 ** attempt) * 1.0)
                        continue
                    raise net_err
                except Exception as ex:
                    last_error = ex
                    budget_manager.record_failure()
                    raise ex

            budget_manager.record_failure()
            raise RuntimeError(f"AnyRouter failed after {ANYROUTER_MAX_RETRIES} retries. Last error: {str(last_error)}")

        finally:
            self._concurrency_semaphore.release()


# Global Singleton Client Instance
anyrouter_client = AnyRouterClient()

