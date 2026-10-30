import datetime

import requests

from taikry.data.economic_calendar import EconomicCalendarProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _future_utc(minutes=90):
    return (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=minutes)
    ).replace(microsecond=0).isoformat()


def test_showmytrades_calendar_is_normalized_and_countdowns_are_cached(monkeypatch):
    provider = EconomicCalendarProvider()
    requests_seen = []

    def fake_get(url, **kwargs):
        requests_seen.append((url, kwargs))
        return FakeResponse({
            "generated_at": "2026-10-30T10:00:00Z",
            "events": [{
                "id": "usd-cpi.20261110T1330",
                "time": _future_utc(),
                "currency": "USD",
                "impact": "high",
                "title": "US CPI Report",
                "forecast": "0.2%",
                "previous": "0.3%",
                "actual": "",
                "confidence": "official",
            }],
        })

    monkeypatch.setattr("taikry.data.economic_calendar.requests.get", fake_get)

    events = provider.get_upcoming_high_impact_events(force_refresh=True)
    assert len(events) == 1
    assert events[0]["id"] == "usd-cpi.20261110T1330"
    assert events[0]["country"] == "USD"
    assert events[0]["forecast"] == "0.2%"
    assert events[0]["source"] == "ShowMyTrades"
    assert events[0]["category"] == "CPI"
    assert events[0]["minutes_remaining"] in range(89, 91)
    assert provider.get_calendar_status()["available"] is True
    assert provider.get_calendar_status()["source"] == "ShowMyTrades"

    # A regular poll serves cached events but recalculates their live countdown.
    provider.get_upcoming_high_impact_events()
    assert len(requests_seen) == 1
    assert requests_seen[0][0] == "https://showmytrades.com/api/public/calendar/v1"
    assert requests_seen[0][1]["params"]["days"] == 14


def test_faireconomy_is_used_when_primary_calendar_is_unreachable(monkeypatch):
    provider = EconomicCalendarProvider()
    requests_seen = []

    def fake_get(url, **kwargs):
        requests_seen.append(url)
        if "showmytrades.com" in url:
            raise requests.ConnectionError("offline")
        return FakeResponse([{
            "id": "weekly-event-1",
            "title": "Federal Funds Rate",
            "country": "USD",
            "impact": "High",
            "date": _future_utc(120),
            "forecast": "4.0%",
            "previous": "4.0%",
        }])

    monkeypatch.setattr("taikry.data.economic_calendar.requests.get", fake_get)

    events = provider.get_upcoming_high_impact_events(force_refresh=True)
    assert len(events) == 1
    assert events[0]["source"] == "FairEconomy"
    assert events[0]["category"] == "FOMC"
    assert requests_seen == [
        "https://showmytrades.com/api/public/calendar/v1",
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    ]
    assert provider.get_calendar_status()["available"] is True
    assert provider.get_calendar_status()["source"] == "FairEconomy"


def test_all_calendar_feeds_unavailable_is_reported_without_fabricating_events(monkeypatch):
    provider = EconomicCalendarProvider()

    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("taikry.data.economic_calendar.requests.get", fail)

    events = provider.get_upcoming_high_impact_events(force_refresh=True)
    assert events == []
    status = provider.get_calendar_status()
    assert status["available"] is False
    assert status["error"] == "FairEconomy: ConnectionError"
    assert provider.check_news_blackout()["status"] == "UNAVAILABLE"


def test_successful_empty_calendar_is_clear_not_a_feed_failure(monkeypatch):
    provider = EconomicCalendarProvider()

    monkeypatch.setattr(
        "taikry.data.economic_calendar.requests.get",
        lambda *_args, **_kwargs: FakeResponse({"events": []}),
    )

    assert provider.get_upcoming_high_impact_events(force_refresh=True) == []
    assert provider.get_calendar_status()["available"] is True
    assert provider.check_news_blackout()["status"] == "CLEAR"


def test_naive_event_time_is_treated_as_utc(monkeypatch):
    provider = EconomicCalendarProvider()
    event_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60))
    event_time_text = event_time.replace(tzinfo=None, microsecond=0).isoformat()
    monkeypatch.setattr(
        "taikry.data.economic_calendar.requests.get",
        lambda *_args, **_kwargs: FakeResponse({"events": [{
            "title": "FOMC Statement",
            "currency": "USD",
            "impact": "high",
            "time": event_time_text,
        }]}),
    )

    event = provider.get_upcoming_high_impact_events(force_refresh=True)[0]
    assert event["minutes_remaining"] in range(59, 61)
