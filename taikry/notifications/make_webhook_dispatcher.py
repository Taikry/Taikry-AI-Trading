"""
Make.com Webhook Dispatcher for TAIKRY AI MARKET INTELLIGENCE PRO
Handles resilient event dispatching to Make scenarios (S01 - S07)
Includes retry with exponential backoff, latency metrics, and delivery auditing.
"""
import time
import requests
from typing import Dict, Any, Optional

from taikry.config import (
    MAKE_WEBHOOK_URL,
    MAKE_CRITICAL_ALERT_WEBHOOK,
    MAKE_PAPER_TRADE_WEBHOOK,
    MAX_RETRIES,
    BACKOFF_BASE_SECONDS,
)
from taikry.database.session import SessionLocal
from taikry.database.models import NotificationAudit

def dispatch_to_make(
    payload: Dict[str, Any],
    webhook_url: Optional[str] = None,
    event_type: str = "market_report_15m"
) -> Dict[str, Any]:
    """
    Dispatches a structured JSON payload to Make.com webhook endpoint.
    """
    event_targets = {
        "critical_market_alert": MAKE_CRITICAL_ALERT_WEBHOOK,
        "signal_lifecycle_transition": MAKE_CRITICAL_ALERT_WEBHOOK,
        "paper_trade": MAKE_PAPER_TRADE_WEBHOOK,
        "paper_trade_update": MAKE_PAPER_TRADE_WEBHOOK,
    }
    target_url = webhook_url or event_targets.get(event_type) or MAKE_WEBHOOK_URL
    if not target_url:
        return {"success": False, "status_code": 0, "error": "No Make webhook URL configured."}

    headers = {"Content-Type": "application/json"}
    status_code = None
    error_msg = None
    t0 = time.time()

    attempts = max(1, int(MAX_RETRIES))
    for attempt in range(attempts):
        try:
            res = requests.post(target_url, json=payload, headers=headers, timeout=10)
            status_code = res.status_code
            latency_ms = int((time.time() - t0) * 1000)

            if status_code in [200, 201, 202]:
                _audit_notification("webhook", event_type, payload, "SENT", status_code, None)
                return {
                    "success": True,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "response": res.text[:200]
                }
            else:
                error_msg = f"HTTP {status_code}: {res.text[:100]}"
                # Retry transient upstream failures; fail fast for permanent client errors.
                if status_code < 500 and status_code != 429 and status_code != 408:
                    break
        except Exception as e:
            error_msg = str(e).replace(target_url, "[REDACTED_WEBHOOK_URL]")

        if attempt + 1 < attempts:
            time.sleep(BACKOFF_BASE_SECONDS * (attempt + 1))

    latency_ms = int((time.time() - t0) * 1000)
    _audit_notification("webhook", event_type, payload, "FAILED", status_code, error_msg)
    return {
        "success": False,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "error": error_msg
    }

def _audit_notification(channel, event_type, payload, status, code, err):
    db = None
    try:
        db = SessionLocal()
        summary = {
            "symbol": payload.get("symbol"),
            "bias": payload.get("market_bias") or payload.get("action"),
            "status": payload.get("setup_status")
        }
        rec = NotificationAudit(
            channel=channel,
            event_type=event_type,
            payload_summary=summary,
            status=status,
            response_code=code,
            error=err
        )
        db.add(rec)
        db.commit()
    except Exception:
        pass
    finally:
        if db is not None:
            db.close()
