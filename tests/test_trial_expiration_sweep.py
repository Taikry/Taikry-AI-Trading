import datetime
from types import SimpleNamespace

from taikry.database.models import UserSubscription
from taikry.monitoring import engine as monitoring_engine


def test_trial_expiration_sweep_updates_subscription_records(monkeypatch):
    expired_subscription = SimpleNamespace(status="trial_active")
    session_state = {"model": None, "conditions": (), "commits": 0, "closed": False}

    class Query:
        def filter(self, *conditions):
            session_state["conditions"] = conditions
            return self

        def all(self):
            return [expired_subscription]

    class Session:
        def query(self, model):
            session_state["model"] = model
            return Query()

        def commit(self):
            session_state["commits"] += 1

        def close(self):
            session_state["closed"] = True

    monkeypatch.setattr("taikry.database.session.SessionLocal", Session)

    now = datetime.datetime(2026, 10, 30, 13, 0, tzinfo=datetime.timezone.utc)
    expired_count = monitoring_engine._expire_trial_subscriptions(now)

    assert expired_count == 1
    assert session_state["model"] is UserSubscription
    assert len(session_state["conditions"]) == 3
    assert expired_subscription.status == "trial_expired"
    assert session_state["commits"] == 1
    assert session_state["closed"] is True
