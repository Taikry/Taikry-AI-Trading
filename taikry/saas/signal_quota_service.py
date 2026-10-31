"""Atomic daily quotas for subscription signal notifications."""
import datetime
import hashlib
from typing import Optional, Tuple

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from taikry.database.models import (
    TelegramSignalDailyQuotaModel,
    TelegramSignalQuotaReservationModel,
)


def cambodia_date_str(now: Optional[datetime.datetime] = None) -> str:
    """Return the business date in Phnom Penh (UTC+7)."""
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=datetime.timezone.utc)
    return (current.astimezone(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d")


def signal_quota_idempotency_key(user_id: int, business_date: str, source_key: str) -> str:
    digest = hashlib.sha256(
        f"{int(user_id)}:{business_date}:{source_key}".encode("utf-8")
    ).hexdigest()
    return f"plan-signal-quota:{digest}"


def reserve_signal_alert_slot(
    db,
    user_id: int,
    business_date: str,
    daily_limit: int,
    idempotency_key: str,
) -> Tuple[bool, str]:
    """Atomically reserve one per-user slot, idempotently for a signal/chat pair."""
    daily_limit = max(0, int(daily_limit or 0))
    if daily_limit == 0:
        return False, "DAILY_CAP_DISABLED"
    if not idempotency_key:
        return False, "MISSING_IDEMPOTENCY_KEY"

    dialect = db.bind.dialect.name
    values = {
        "idempotency_key": idempotency_key[:160],
        "user_id": int(user_id),
        "cambodia_date": business_date,
    }
    if dialect == "postgresql":
        insert_reservation = postgresql_insert(TelegramSignalQuotaReservationModel).values(**values).on_conflict_do_nothing(
            index_elements=[TelegramSignalQuotaReservationModel.idempotency_key]
        )
        insert_daily = postgresql_insert(TelegramSignalDailyQuotaModel).values(
            user_id=int(user_id),
            cambodia_date=business_date,
            reserved_count=0,
            updated_at=datetime.datetime.utcnow(),
        ).on_conflict_do_nothing(
            index_elements=[
                TelegramSignalDailyQuotaModel.user_id,
                TelegramSignalDailyQuotaModel.cambodia_date,
            ]
        )
    elif dialect == "sqlite":
        insert_reservation = sqlite_insert(TelegramSignalQuotaReservationModel).values(**values).on_conflict_do_nothing(
            index_elements=[TelegramSignalQuotaReservationModel.idempotency_key]
        )
        insert_daily = sqlite_insert(TelegramSignalDailyQuotaModel).values(
            user_id=int(user_id),
            cambodia_date=business_date,
            reserved_count=0,
            updated_at=datetime.datetime.utcnow(),
        ).on_conflict_do_nothing(
            index_elements=[
                TelegramSignalDailyQuotaModel.user_id,
                TelegramSignalDailyQuotaModel.cambodia_date,
            ]
        )
    else:
        return False, f"UNSUPPORTED_DATABASE_DIALECT:{dialect}"

    try:
        reservation_result = db.execute(insert_reservation)
        if reservation_result.rowcount == 0:
            db.commit()
            return True, "ALREADY_RESERVED"

        db.execute(insert_daily)
        changed = db.query(TelegramSignalDailyQuotaModel).filter(
            TelegramSignalDailyQuotaModel.user_id == int(user_id),
            TelegramSignalDailyQuotaModel.cambodia_date == business_date,
            TelegramSignalDailyQuotaModel.reserved_count < daily_limit,
        ).update({
            "reserved_count": TelegramSignalDailyQuotaModel.reserved_count + 1,
            "updated_at": datetime.datetime.utcnow(),
        }, synchronize_session=False)
        if changed != 1:
            db.query(TelegramSignalQuotaReservationModel).filter(
                TelegramSignalQuotaReservationModel.idempotency_key == values["idempotency_key"]
            ).delete(synchronize_session=False)
            db.commit()
            return False, "DAILY_CAP_REACHED"

        db.commit()
        return True, "RESERVED"
    except Exception:
        db.rollback()
        raise


def release_signal_alert_slot(db, idempotency_key: str) -> bool:
    """Release a reservation only after Telegram definitively rejects delivery."""
    try:
        reservation = db.query(TelegramSignalQuotaReservationModel).filter(
            TelegramSignalQuotaReservationModel.idempotency_key == idempotency_key
        ).first()
        if not reservation:
            return False
        user_id = reservation.user_id
        business_date = reservation.cambodia_date
        deleted = db.query(TelegramSignalQuotaReservationModel).filter(
            TelegramSignalQuotaReservationModel.idempotency_key == idempotency_key
        ).delete(synchronize_session=False)
        if deleted:
            db.query(TelegramSignalDailyQuotaModel).filter(
                TelegramSignalDailyQuotaModel.user_id == user_id,
                TelegramSignalDailyQuotaModel.cambodia_date == business_date,
                TelegramSignalDailyQuotaModel.reserved_count > 0,
            ).update({
                "reserved_count": TelegramSignalDailyQuotaModel.reserved_count - 1,
                "updated_at": datetime.datetime.utcnow(),
            }, synchronize_session=False)
        db.commit()
        return bool(deleted)
    except Exception:
        db.rollback()
        raise
