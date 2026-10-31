"""Subscription and Telegram-link gates for automatic signal delivery."""
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from taikry.database.models import (
    Base,
    NotificationPreferences,
    SubscriptionPlan,
    TelegramSignalDailyQuotaModel,
    TelegramLink,
    User,
    UserSubscription,
)
from taikry.notifications.telegram_service import TelegramService
from taikry.saas.entitlement_service import get_telegram_signal_recipients
from taikry.saas.signal_quota_service import reserve_signal_alert_slot, release_signal_alert_slot
from unittest.mock import patch


def test_signal_recipients_require_active_plan_link_and_opt_in():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    now = datetime.datetime.now(datetime.timezone.utc)

    db.add_all([
        SubscriptionPlan(
            id="pro", name_en="Pro", name_kh="Pro", price_usd=29, amount=29,
            currency="USD", billing_interval="monthly", interval_count=1,
            trial_days=0, max_ai_scans_per_day=50, max_deep_analysis_per_day=20,
            signal_alerts_target_min_per_day=5, max_signal_alerts_per_day=10,
            max_watchlists=25, backtesting_enabled=True, telegram_alerts_enabled=True,
            agent_debate_enabled=True, is_active=True,
        ),
        SubscriptionPlan(
            id="no_telegram", name_en="No Telegram", name_kh="No Telegram",
            price_usd=10, amount=10, currency="USD", billing_interval="monthly",
            interval_count=1, trial_days=0, telegram_alerts_enabled=False,
            is_active=True,
        ),
    ])
    db.flush()

    users = [
        User(email=f"signal-{index}@example.test", hashed_password="hash", salt="salt")
        for index in range(4)
    ]
    db.add_all(users)
    db.flush()

    for index, user in enumerate(users):
        plan_id = "no_telegram" if index == 1 else "pro"
        expires = now + datetime.timedelta(days=30) if index != 3 else now - datetime.timedelta(days=1)
        db.add(UserSubscription(
            user_id=user.id,
            plan_id=plan_id,
            status="active_paid",
            current_period_starts_at=now - datetime.timedelta(days=1),
            current_period_expires_at=expires,
        ))
        db.add(TelegramLink(
            user_id=user.id,
            telegram_chat_id=str(1000 + index),
            is_linked=True,
            linked_at=now,
        ))
    db.add(NotificationPreferences(user_id=users[2].id, signal_generated=False))
    db.commit()

    try:
        recipients = get_telegram_signal_recipients(db)
        assert recipients == [{
            "user_id": users[0].id,
            "chat_id": "1000",
            "plan_id": "pro",
            "signal_alerts_target_min_per_day": 5,
            "max_signal_alerts_per_day": 10,
        }]
    finally:
        db.close()
        engine.dispose()


def test_signal_fanout_uses_a_separate_persistent_delivery_per_chat():
    service = TelegramService()
    service.enabled = True
    service.token = "unit-test-token"
    recipients = [
        {"user_id": 1, "chat_id": "101", "plan_id": "pro", "max_signal_alerts_per_day": 10},
        {"user_id": 2, "chat_id": "202", "plan_id": "premium", "max_signal_alerts_per_day": 15},
    ]
    with patch("taikry.notifications.telegram_service.SessionLocal") as session_factory, patch(
        "taikry.saas.entitlement_service.get_telegram_signal_recipients", return_value=recipients
    ), patch.object(
        service, "_dispatch_persistent_message", return_value=(True, "44", None, "SENT")
    ) as dispatch, patch(
        "taikry.saas.signal_quota_service.reserve_signal_alert_slot",
        return_value=(True, "RESERVED"),
    ):
        session_factory.return_value.close = lambda: None
        session_factory.return_value.query.return_value.filter.return_value.first.return_value = None
        delivered, eligible = service._fanout_plan_signal(
            "<b>Approved signal</b>",
            source_key="SIG-FANOUT-TEST",
            notification_type="SIGNAL",
            signal_id="SIG-FANOUT-TEST",
            symbol="EURUSD",
            direction="BUY",
            timeframe="M15",
            reply_markup=None,
            exclude_chat_id="101",
        )

    assert (delivered, eligible) == (1, 1)
    dispatch.assert_called_once()
    assert dispatch.call_args.kwargs["chat_id"] == "202"
    assert dispatch.call_args.kwargs["idempotency_key"].startswith("plan-signal:")


def test_signal_daily_quota_is_idempotent_capped_and_releasable():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(email="quota@example.test", hashed_password="hash", salt="salt")
    db.add(user)
    db.commit()
    day = "2026-10-31"

    try:
        assert reserve_signal_alert_slot(db, user.id, day, 2, "signal-a") == (True, "RESERVED")
        assert reserve_signal_alert_slot(db, user.id, day, 2, "signal-a") == (True, "ALREADY_RESERVED")
        assert reserve_signal_alert_slot(db, user.id, day, 2, "signal-b") == (True, "RESERVED")
        assert reserve_signal_alert_slot(db, user.id, day, 2, "signal-c") == (False, "DAILY_CAP_REACHED")
        assert db.query(TelegramSignalDailyQuotaModel).one().reserved_count == 2

        assert release_signal_alert_slot(db, "signal-a") is True
        assert reserve_signal_alert_slot(db, user.id, day, 2, "signal-c") == (True, "RESERVED")
        assert db.query(TelegramSignalDailyQuotaModel).one().reserved_count == 2
    finally:
        db.close()
        engine.dispose()
