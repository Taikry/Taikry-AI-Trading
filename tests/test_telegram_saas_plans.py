from unittest.mock import patch
from types import SimpleNamespace

from taikry.notifications.telegram_service import TelegramService


def test_telegram_plan_catalog_matches_website_tiers_and_limits():
    service = TelegramService()
    plans = [
        {
            "id": "premium", "price_usd": 79, "billing_interval": "monthly",
            "signal_alerts_target_min_per_day": 10, "max_signal_alerts_per_day": 15,
            "max_ai_scans_per_day": 200, "max_deep_analysis_per_day": 100,
            "max_watchlists": 100, "agent_debate_enabled": True,
        },
        {
            "id": "pro", "price_usd": 29, "billing_interval": "monthly",
            "signal_alerts_target_min_per_day": 5, "max_signal_alerts_per_day": 10,
            "max_ai_scans_per_day": 50, "max_deep_analysis_per_day": 20,
            "max_watchlists": 25, "agent_debate_enabled": True,
        },
        {
            "id": "free_trial", "price_usd": 0, "billing_interval": "trial",
            "signal_alerts_target_min_per_day": 2, "max_signal_alerts_per_day": 4,
            "max_ai_scans_per_day": 10, "max_deep_analysis_per_day": 3,
            "max_watchlists": 5, "agent_debate_enabled": False,
        },
    ]
    with patch("taikry.notifications.telegram_service.SessionLocal"), patch(
        "taikry.saas.entitlement_service.get_all_plans", return_value=plans
    ):
        message, keyboard = service.build_saas_plan_catalog_message()

    assert message.index("NORMAL / 14-Day Trial") < message.index("<b>PRO</b>") < message.index("<b>PREMIUM</b>")
    assert "2–4/day target, 4 max" in message
    assert "5–10/day target, 10 max" in message
    assert "10–15/day target, 15 max" in message
    assert "not guaranteed minimums" in message
    assert keyboard["inline_keyboard"][-1][0]["callback_data"] == "account:myplan"


def test_telegram_my_plan_shows_linked_tier_usage_and_preferences():
    service = TelegramService()
    entitlement = {
        "is_active": True,
        "subscription_status": "active_paid",
        "telegram_signal_notifications_enabled": True,
        "plan": {"id": "pro", "name_en": "Pro Trader Tier"},
        "quotas": {
            "max_signal_alerts_per_day": 10,
            "signal_alerts_target_min_per_day": 5,
            "signal_alerts_reserved_today": 3,
            "signal_alerts_remaining_today": 7,
            "standard_scans_used_today": 12,
            "max_ai_scans_per_day": 50,
            "deep_analysis_used_today": 4,
            "max_deep_analysis_per_day": 20,
            "max_watchlists": 25,
            "backtesting_enabled": True,
            "agent_debate_enabled": True,
            "telegram_alerts_enabled": True,
        },
    }
    with patch.object(service, "_load_linked_saas_entitlement", return_value=entitlement):
        message, _keyboard = service.build_saas_plan_status_message("12345")

    assert "PRO" in message
    assert "3/10 allocated · 7 remaining" in message
    assert "12/50 used" in message
    assert "20 used" in message
    assert "notification preference:</b> On" in message


def test_main_telegram_menu_exposes_site_plans_and_legacy_vip_separately():
    service = TelegramService()
    callbacks = [
        button.get("callback_data")
        for row in service.build_main_menu_keyboard()["inline_keyboard"]
        for button in row
    ]

    assert "account:plans" in callbacks
    assert "account:myplan" in callbacks
    assert "sub:plans" in callbacks


def test_linked_telegram_scan_consumes_account_scan_quota():
    service = TelegramService()
    linked = SimpleNamespace(user_id=44)
    with patch.object(service, "_is_telegram_admin", return_value=False), patch(
        "taikry.notifications.telegram_service.SessionLocal"
    ) as session_factory, patch(
        "taikry.saas.entitlement_service.get_user_entitlement",
        return_value={"is_active": True, "quotas": {"agent_debate_enabled": True}},
    ), patch(
        "taikry.saas.entitlement_service.check_and_consume_quota",
        return_value=(False, "Daily AI market scan quota reached", {}),
    ) as consume_quota:
        session_factory.return_value.query.return_value.filter.return_value.first.return_value = linked
        message = service._consume_linked_plan_analysis_quota(7, "12345", "standard_scan", "EURUSD")

    assert "Plan quota reached" in message
    consume_quota.assert_called_once()
    assert consume_quota.call_args.args[1:3] == (44, "standard_scan")


def test_normal_tier_cannot_run_debate_when_feature_is_not_included():
    service = TelegramService()
    linked = SimpleNamespace(user_id=45)
    with patch.object(service, "_is_telegram_admin", return_value=False), patch(
        "taikry.notifications.telegram_service.SessionLocal"
    ) as session_factory, patch(
        "taikry.saas.entitlement_service.get_user_entitlement",
        return_value={"is_active": True, "quotas": {"agent_debate_enabled": False}},
    ), patch("taikry.saas.entitlement_service.check_and_consume_quota") as consume_quota:
        session_factory.return_value.query.return_value.filter.return_value.first.return_value = linked
        message = service._consume_linked_plan_analysis_quota(7, "12345", "deep_analysis", "XAUUSD")

    assert "not included in your current tier" in message
    consume_quota.assert_not_called()
