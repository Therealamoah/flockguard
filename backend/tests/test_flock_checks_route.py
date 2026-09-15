from datetime import datetime, timezone

import app.api.routes.flock_checks as flock_checks_module
from tests.conftest import FAKE_UID


class _FixedClock:
    def __init__(self, value: datetime):
        self.value = value

    def now(self, tz=None):
        return self.value


def _set_clock(monkeypatch, iso: str):
    monkeypatch.setattr(flock_checks_module, "datetime", _FixedClock(datetime.fromisoformat(iso)))


def _setup_farm_house(client):
    farm = client.post("/farms", json={"name": "Test Farm"}).json()
    house = client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()
    return farm["id"], house["id"]


def test_morning_then_evening_pairing_and_risk_delta(authed_client, monkeypatch):
    farm_id, house_id = _setup_farm_house(authed_client)

    _set_clock(monkeypatch, "2026-01-05T06:00:00+00:00")
    morning = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 1000, "mortality": 1, "feed_kg": 30},
    ).json()
    assert morning["risk_score"] == 0  # no baseline yet, low mortality

    _set_clock(monkeypatch, "2026-01-05T18:00:00+00:00")
    evening = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "evening",
            "bird_count": 1000,
            "mortality": 4,
            "feed_kg": 22,
            "water_level": "lower",
            "activity": "reduced",
        },
    ).json()

    assert evening["previous_risk_score"] == morning["risk_score"]
    assert evening["risk_change"] == evening["risk_score"] - morning["risk_score"]

    comparison = evening["morning_comparison"]
    assert comparison is not None
    assert comparison["morning_check_id"] == morning["id"]
    assert comparison["evening_check_id"] == evening["id"]
    assert comparison["mortality_change"] == 3
    assert comparison["feed_change"] == -8


def test_evening_check_with_no_morning_check_has_no_comparison(authed_client, monkeypatch):
    farm_id, house_id = _setup_farm_house(authed_client)
    _set_clock(monkeypatch, "2026-01-05T18:00:00+00:00")
    evening = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "evening", "bird_count": 1000, "mortality": 2},
    ).json()
    assert evening["morning_comparison"] is None
    assert evening["previous_risk_score"] is None


def test_emergency_check_between_morning_and_evening_still_pairs_with_morning(authed_client, monkeypatch):
    farm_id, house_id = _setup_farm_house(authed_client)

    _set_clock(monkeypatch, "2026-01-05T06:00:00+00:00")
    morning = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 1000, "mortality": 1},
    ).json()

    _set_clock(monkeypatch, "2026-01-05T12:00:00+00:00")
    emergency = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "emergency", "bird_count": 1000, "mortality": 5},
    ).json()
    assert emergency["morning_comparison"]["morning_check_id"] == morning["id"]

    _set_clock(monkeypatch, "2026-01-05T18:00:00+00:00")
    evening = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "evening", "bird_count": 1000, "mortality": 7},
    ).json()
    # Evening still pairs against the real Morning Check, not the emergency one.
    assert evening["morning_comparison"]["morning_check_id"] == morning["id"]


def test_comparison_is_scoped_to_the_same_house(authed_client, monkeypatch):
    farm_id, house_a = _setup_farm_house(authed_client)
    house_b = authed_client.post(f"/farms/{farm_id}/houses", json={"name": "House B"}).json()["id"]

    _set_clock(monkeypatch, "2026-01-05T06:00:00+00:00")
    authed_client.post(
        f"/farms/{farm_id}/houses/{house_b}/flock-checks",
        json={"period": "morning", "bird_count": 500, "mortality": 9},
    )

    _set_clock(monkeypatch, "2026-01-05T18:00:00+00:00")
    evening_house_a = authed_client.post(
        f"/farms/{farm_id}/houses/{house_a}/flock-checks",
        json={"period": "evening", "bird_count": 1000, "mortality": 2},
    ).json()

    # House A's evening check must never pair against House B's morning check.
    assert evening_house_a["morning_comparison"] is None


def test_comparison_is_scoped_to_the_same_flock(authed_client, monkeypatch):
    """A freshly placed flock's first Evening Check must not pair against a
    Morning Check left over from the house's previous flock, even same house,
    even same calendar date."""
    farm_id, house_id = _setup_farm_house(authed_client)

    flock_a = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flocks",
        json={"bird_type": "broiler", "breed": "Cobb 500", "start_date": "2026-01-01", "initial_bird_count": 1000},
    ).json()

    _set_clock(monkeypatch, "2026-01-05T06:00:00+00:00")
    authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 1000, "mortality": 1},
    )

    # Flock A's cycle ends and Flock B is placed the same day.
    authed_client.patch(f"/farms/{farm_id}/houses/{house_id}/flocks/{flock_a['id']}", json={"status": "closed"})
    authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flocks",
        json={"bird_type": "broiler", "breed": "Ross 308", "start_date": "2026-01-05", "initial_bird_count": 1200},
    )

    _set_clock(monkeypatch, "2026-01-05T18:00:00+00:00")
    evening = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "evening", "bird_count": 1200, "mortality": 0},
    ).json()

    assert evening["morning_comparison"] is None


def test_different_calendar_date_morning_check_not_used(authed_client, monkeypatch):
    farm_id, house_id = _setup_farm_house(authed_client)

    _set_clock(monkeypatch, "2026-01-04T06:00:00+00:00")
    authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 1000, "mortality": 1},
    )

    _set_clock(monkeypatch, "2026-01-05T18:00:00+00:00")
    evening = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "evening", "bird_count": 1000, "mortality": 2},
    ).json()
    assert evening["morning_comparison"] is None


def test_alert_created_once_and_updated_not_duplicated_across_checks(authed_client, monkeypatch):
    farm_id, house_id = _setup_farm_house(authed_client)

    for i, hour in enumerate(["06", "10", "14"]):
        _set_clock(monkeypatch, f"2026-01-0{i + 1}T{hour}:00:00+00:00")
        authed_client.post(
            f"/farms/{farm_id}/houses/{house_id}/flock-checks",
            json={
                "period": "morning",
                "bird_count": 1000,
                "mortality": 0,
                "activity": "lethargic",
                "feeding_behaviour": "none",
                "water_level": "lower",
            },
        )

    alerts = authed_client.get("/alerts", params={"resolved": False}).json()
    house_alerts = [a for a in alerts if a["house_id"] == house_id]
    assert len(house_alerts) == 1
    assert house_alerts[0]["occurrence_count"] == 3


def test_mortality_cannot_exceed_bird_count_returns_422(authed_client):
    farm_id, house_id = _setup_farm_house(authed_client)
    response = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 10, "mortality": 50},
    )
    assert response.status_code == 422


def test_flock_check_for_nonexistent_house_returns_404(authed_client):
    farm_id, _ = _setup_farm_house(authed_client)
    response = authed_client.post(
        f"/farms/{farm_id}/houses/does-not-exist/flock-checks",
        json={"period": "morning", "bird_count": 10, "mortality": 0},
    )
    assert response.status_code == 404


def test_critical_check_triggers_agent_investigation_end_to_end(authed_client, fake_db, monkeypatch):
    """Full chain through the real route: gating decides a Critical check is
    worth investigating, BackgroundTasks runs the agent (TestClient executes
    background tasks synchronously), and a real agent_run + recommendation
    land in Firestore - all without the AI call ever going anywhere real."""
    import json

    from app.core.refs import agent_recommendations_ref, agent_runs_ref
    from app.services.grok_service import grok_service

    farm_id, house_id = _setup_farm_house(authed_client)

    async def _fake_chat_completion(messages, tools=None, tool_choice=None, response_format=None, model=None):
        return {
            "content": json.dumps(
                {
                    "priority": "urgent",
                    "house_id": house_id,
                    "summary": "House A is critical with sharply rising mortality.",
                    "observed_data": ["Mortality 0 -> 30"],
                    "calculated_signals": ["Risk score 100, critical"],
                    "historical_context": [],
                    "reference_guidance": [],
                    "knowledge_sources": [],
                    "recommended_actions": ["Inspect water and feed access immediately"],
                    "confidence": "high",
                    "requires_inspection": True,
                    "requires_human_action": True,
                }
            ),
            "tool_calls": None,
        }

    monkeypatch.setattr(grok_service, "chat_completion", _fake_chat_completion)

    response = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "emergency",
            "bird_count": 1000,
            "mortality": 30,
            "sick_or_injured": 5,
            "feed_kg": 5,
            "water_level": "lower",
            "activity": "lethargic",
            "feeding_behaviour": "none",
        },
    )
    assert response.status_code == 201
    assert response.json()["risk_status"] == "critical"

    from tests.conftest import FAKE_UID  # authed_client's org_id defaults to its own uid

    runs = list(agent_runs_ref(fake_db, FAKE_UID).stream())
    assert len(runs) == 1
    assert runs[0].to_dict()["trigger"] == "emergency_check_submitted"
    assert runs[0].to_dict()["priority"] == "urgent"

    recommendations = list(agent_recommendations_ref(fake_db, FAKE_UID).stream())
    assert len(recommendations) == 1
    assert recommendations[0].to_dict()["house_id"] == house_id


def test_normal_check_does_not_trigger_agent_investigation(authed_client, fake_db):
    """A Normal check must not spend an AI call - proven here by leaving
    chat_completion unmocked (the autouse fail-fast fixture would surface
    as a failed background task, but no agent_run should even be attempted)."""
    from app.core.refs import agent_runs_ref
    from tests.conftest import FAKE_UID

    farm_id, house_id = _setup_farm_house(authed_client)
    response = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 1000, "mortality": 1},
    )
    assert response.status_code == 201
    assert response.json()["risk_status"] == "normal"

    assert list(agent_runs_ref(fake_db, FAKE_UID).stream()) == []


def test_new_alert_emails_the_orgs_owners_and_managers(authed_client, monkeypatch):
    """Only fires on the alert's CREATION (see alert_engine.sync_alert_for_check's
    "created" vs "updated" action) - proven by asserting exactly one call
    even though two alert-worthy checks are submitted for the same house."""
    calls = []

    async def _fake_send_alert_email(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(flock_checks_module, "send_alert_email", _fake_send_alert_email)

    authed_client.get("/team")  # backfills the owner's own membership doc (get_current_org_id alone never does)
    farm_id, house_id = _setup_farm_house(authed_client)
    # Email notifications default to off (opt-in) - turn them on for this
    # farm, same as a farmer would in Settings -> Notifications -> Channels.
    authed_client.patch(
        f"/settings?farm_id={farm_id}",
        json={"notification_preferences": {"channels": {"email": True}}},
    )

    first = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "emergency",
            "bird_count": 1000,
            "mortality": 30,
            "sick_or_injured": 5,
            "feed_kg": 5,
            "water_level": "lower",
            "activity": "lethargic",
            "feeding_behaviour": "none",
        },
    )
    assert first.status_code == 201
    assert first.json()["risk_status"] == "critical"
    assert len(calls) == 1
    assert calls[0]["house_name"] == "House A"
    assert calls[0]["farm_name"] == "Test Farm"
    assert calls[0]["status"] == "critical"
    assert calls[0]["to_emails"] == ["farmer@example.com"]  # authed_client's fake user, backfilled as owner

    # A second alert-worthy check for the SAME house updates the existing
    # open alert rather than opening a new one - must not email again.
    second = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "emergency",
            "bird_count": 970,
            "mortality": 20,
            "sick_or_injured": 5,
            "feed_kg": 5,
            "water_level": "lower",
            "activity": "lethargic",
            "feeding_behaviour": "none",
        },
    )
    assert second.status_code == 201
    assert len(calls) == 1


def test_new_alert_does_not_email_when_the_farm_has_email_notifications_off(authed_client, monkeypatch):
    """The opposite of test_new_alert_emails_the_orgs_owners_and_managers -
    without turning Settings -> Notifications -> Channels -> Email on
    first (it defaults off), a brand-new critical alert must NOT email
    anyone, proving the toggle actually gates delivery rather than being
    cosmetic."""
    calls = []

    async def _fake_send_alert_email(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(flock_checks_module, "send_alert_email", _fake_send_alert_email)

    authed_client.get("/team")
    farm_id, house_id = _setup_farm_house(authed_client)
    # Deliberately NOT enabling the email channel here.

    response = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "emergency",
            "bird_count": 1000,
            "mortality": 30,
            "sick_or_injured": 5,
            "feed_kg": 5,
            "water_level": "lower",
            "activity": "lethargic",
            "feeding_behaviour": "none",
        },
    )
    assert response.status_code == 201
    assert response.json()["risk_status"] == "critical"
    assert calls == []


def test_new_alert_pushes_to_the_orgs_owners_and_managers(authed_client, monkeypatch):
    """Mirrors test_new_alert_emails_the_orgs_owners_and_managers for the
    Push channel - independently gated, independently tested."""
    calls = []

    def _fake_send_push_to_uids(*args, **kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(flock_checks_module, "send_push_to_uids", _fake_send_push_to_uids)

    authed_client.get("/team")  # backfills the owner's own membership doc
    farm_id, house_id = _setup_farm_house(authed_client)
    authed_client.patch(
        f"/settings?farm_id={farm_id}",
        json={"notification_preferences": {"channels": {"push": True}}},
    )

    response = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "emergency",
            "bird_count": 1000,
            "mortality": 30,
            "sick_or_injured": 5,
            "feed_kg": 5,
            "water_level": "lower",
            "activity": "lethargic",
            "feeding_behaviour": "none",
        },
    )
    assert response.status_code == 201
    assert len(calls) == 1
    assert calls[0]["uids"] == [FAKE_UID]  # authed_client's fake user, backfilled as owner
    assert "House A" in calls[0]["title"]
    assert calls[0]["url"].endswith("/alerts")


def test_normal_check_never_emails_an_alert(authed_client, monkeypatch):
    calls = []

    async def _fake_send_alert_email(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(flock_checks_module, "send_alert_email", _fake_send_alert_email)

    farm_id, house_id = _setup_farm_house(authed_client)
    response = authed_client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={"period": "morning", "bird_count": 1000, "mortality": 1},
    )
    assert response.status_code == 201
    assert response.json()["risk_status"] == "normal"
    assert calls == []
