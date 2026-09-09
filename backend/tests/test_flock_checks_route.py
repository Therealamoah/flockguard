from datetime import datetime, timezone

import app.api.routes.flock_checks as flock_checks_module


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
