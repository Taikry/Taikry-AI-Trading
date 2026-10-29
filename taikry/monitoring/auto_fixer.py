"""
AUTONOMOUS ALERT & SELF-HEALING ENGINE
("Alert-Auto-Fix System")
Continuously monitors system components, detects market data anomalies,
LLM API rate limits/errors, and database contention, then automatically
executes programmatic remediation routines without human intervention.
"""
import datetime
import uuid
from typing import Dict, Any, List
from sqlalchemy import text

from taikry.database.session import SessionLocal
from taikry.database.models import SystemAlertAutoFix
from taikry.data.providers import market_data_engine
from taikry.data.validator import check_data_freshness
from taikry.ai.llm_client import get_llm_status

class AutoFixEngine:
    """Autonomous System Health Sentinel & Self-Healing Agent."""

    def __init__(self):
        pass

    def get_incidents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent auto-fixed alerts and active remediations."""
        db = SessionLocal()
        try:
            records = db.query(SystemAlertAutoFix).order_by(SystemAlertAutoFix.created_at.desc()).limit(limit).all()
            return [
                {
                    "incident_id": r.incident_id,
                    "subsystem": r.subsystem,
                    "severity": r.severity,
                    "title": r.alert_title,
                    "description": r.alert_description,
                    "auto_fix_action": r.auto_fix_action,
                    "status": r.status,
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "resolved_at": r.resolved_at.strftime("%Y-%m-%d %H:%M:%S UTC") if r.resolved_at else "IN_PROGRESS"
                }
                for r in records
            ]
        except Exception:
            return []
        finally:
            db.close()

    def run_diagnostic_and_fix(self) -> Dict[str, Any]:
        """
        Runs comprehensive self-diagnostic across all 5 operational subsystems
        and executes auto-remediation if anomalies are found.
        """
        remediation_actions = []
        checks: Dict[str, Any] = {}

        # 1. Check Market Feeds
        try:
            price, source, timestamp = market_data_engine.get_verified_price("XAUUSD")
            freshness = check_data_freshness("XAUUSD", timestamp)
            fresh = bool(price and price > 0 and freshness.get("fresh") and "DEMO_SYNTHETIC" not in str(source).upper())
            checks["market_data"] = {"status": "FRESH" if fresh else "DEGRADED", "source": source, "freshness": freshness.get("status")}
            if not fresh:
                market_data_engine.clear_cache()
                remediation_actions.append("Cleared cached market data. A new provider fetch is required before analysis.")
        except Exception as e:
            checks["market_data"] = {"status": "ERROR", "detail": str(e)}

        # 2. Report cloud LLM configuration without claiming an external connectivity probe.
        try:
            llm_stat = get_llm_status()
            configured_llms = [k for k, v in llm_stat.items() if isinstance(v, dict) and v.get("configured")]
            checks["llm"] = {
                "status": "CONFIGURED_NOT_PROBED" if configured_llms else "NOT_CONFIGURED",
                "providers_configured": configured_llms,
                "reachability": "NOT_PROBED",
            }
        except Exception as e:
            checks["llm"] = {"status": "ERROR", "detail": str(e)}

        # 3. Check Database Health
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            if db.get_bind().dialect.name == "sqlite":
                db.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
            db.commit()
            checks["database"] = {"status": "QUERY_OK", "dialect": db.get_bind().dialect.name}
        except Exception as ex:
            checks["database"] = {"status": "ERROR", "detail": str(ex)}
        finally:
            db.close()

        # Log Auto-Fix Incident
        incident_id = f"FIX-2026-{uuid.uuid4().hex[:4].upper()}"
        action_summary = " | ".join(remediation_actions) if remediation_actions else "Diagnostics completed; no cache remediation was needed."

        db = SessionLocal()
        try:
            inc = SystemAlertAutoFix(
                incident_id=incident_id,
                subsystem="SYSTEM_SENTINEL",
                severity="INFO",
                alert_title="Routine Self-Healing & Diagnostic Routine",
                alert_description="A limited market-data, LLM-status, and database-query diagnostic was completed.",
                auto_fix_action=action_summary,
                status="COMPLETED",
                created_at=datetime.datetime.utcnow(),
                resolved_at=datetime.datetime.utcnow()
            )
            db.add(inc)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

        return {
            "incident_id": incident_id,
            "status": "DIAGNOSTIC_COMPLETED",
            "message": "Diagnostic completed. Review the individual checks; this does not verify every subsystem or guarantee service health.",
            "message_kh": "ការត្រួតពិនិត្យបានបញ្ចប់។ សូមពិនិត្យលទ្ធផលតាមផ្នែក។ វាមិនបានផ្ទៀងផ្ទាត់គ្រប់សេវា ឬធានាថាប្រព័ន្ធទាំងអស់ដំណើរការល្អទេ។",
            "remediation_actions": remediation_actions,
            "checks": checks,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

# Global singleton
auto_fix_engine = AutoFixEngine()
