"""
Support Ticketing Engine for ZYROX AI SaaS Platform.
Implements:
- Authenticated user ticket creation and tracking
- Categories: account, trial, billing, telegram, ai_analysis, technical
- Ticket ID format: TICK-YYYYMMDD-XXXX
- Admin reply and status resolution workflows
"""

import secrets
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from taikry.database.models import User, SupportTicket, AuditLog

VALID_CATEGORIES = ["account", "trial", "billing", "telegram", "ai_analysis", "technical"]
VALID_PRIORITIES = ["LOW", "NORMAL", "HIGH", "URGENT"]
VALID_STATUSES = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]


def create_support_ticket(
    db: Session,
    user_id: int,
    category: str,
    subject: str,
    message: str,
    priority: str = "NORMAL"
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Creates a new authenticated support ticket."""
    cat = category.strip().lower()
    if cat not in VALID_CATEGORIES:
        return False, f"Invalid category. Must be one of: {VALID_CATEGORIES}", None

    subj = subject.strip()
    if not subj or len(subj) < 4:
        return False, "Subject must be at least 4 characters long.", None

    msg = message.strip()
    if not msg or len(msg) < 10:
        return False, "Message must provide at least 10 characters describing the issue.", None

    prio = priority.upper() if priority.upper() in VALID_PRIORITIES else "NORMAL"

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    date_str = now_utc.strftime("%Y%m%d")
    random_suffix = secrets.token_hex(2).upper()
    ticket_id = f"TICK-{date_str}-{random_suffix}"

    ticket = SupportTicket(
        id=ticket_id,
        user_id=user_id,
        category=cat,
        subject=subj[:250],
        message=msg,
        status="OPEN",
        priority=prio,
        created_at=now_utc
    )
    db.add(ticket)

    audit = AuditLog(
        actor_user_id=user_id,
        action="SUPPORT_TICKET_CREATED",
        target_type="support_ticket",
        target_id=ticket_id,
        details={"category": cat, "priority": prio}
    )
    db.add(audit)
    db.commit()

    return True, "Support ticket submitted successfully.", {
        "id": ticket.id,
        "ticket_id": ticket.id,
        "ticket_number": ticket.id,
        "category": ticket.category,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at_utc": ticket.created_at.isoformat()
    }


def get_user_tickets(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Retrieves all tickets opened by the user."""
    tickets = db.query(SupportTicket).filter(
        SupportTicket.user_id == user_id
    ).order_by(SupportTicket.created_at.desc()).all()

    return [
        {
            "id": t.id,
            "category": t.category,
            "subject": t.subject,
            "message": t.message,
            "status": t.status,
            "priority": t.priority,
            "admin_response": t.admin_response,
            "resolved_at_utc": t.resolved_at.isoformat() if t.resolved_at else None,
            "created_at_utc": t.created_at.isoformat()
        }
        for t in tickets
    ]


def admin_list_all_tickets(db: Session, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves tickets for administrative review."""
    query = db.query(SupportTicket, User.email).join(User, SupportTicket.user_id == User.id)
    if status_filter and status_filter.upper() in VALID_STATUSES:
        query = query.filter(SupportTicket.status == status_filter.upper())
    
    results = query.order_by(SupportTicket.created_at.desc()).limit(100).all()
    return [
        {
            "id": t.id,
            "user_id": t.user_id,
            "user_email": email,
            "category": t.category,
            "subject": t.subject,
            "message": t.message,
            "status": t.status,
            "priority": t.priority,
            "admin_response": t.admin_response,
            "created_at_utc": t.created_at.isoformat()
        }
        for t, email in results
    ]


def admin_reply_ticket(
    db: Session,
    ticket_id: str,
    response_text: str,
    new_status: str = "RESOLVED",
    admin_user_id: Optional[int] = None
) -> Tuple[bool, str]:
    """Applies an administrative response and updates ticket status."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id.strip()).first()
    if not ticket:
        return False, "Ticket not found."

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ticket.admin_response = response_text.strip()
    ticket.status = new_status.upper() if new_status.upper() in VALID_STATUSES else "RESOLVED"
    if ticket.status in ("RESOLVED", "CLOSED"):
        ticket.resolved_at = now_utc

    audit = AuditLog(
        actor_user_id=admin_user_id,
        action="SUPPORT_TICKET_REPLIED",
        target_type="support_ticket",
        target_id=ticket.id,
        details={"status": ticket.status}
    )
    db.add(audit)
    db.commit()
    return True, f"Ticket {ticket.id} updated to {ticket.status}."
