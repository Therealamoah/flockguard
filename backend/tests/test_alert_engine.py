from app.core.refs import alerts_ref
from app.risk_engine.models import RiskFactor, RiskResult
from app.services.alert_engine import sync_alert_for_check

ORG = "org-1"
FARM = "farm-1"
HOUSE = "house-1"


def _risk(score, status, factors=None):
    return RiskResult(score=score, status=status, factors=factors or [RiskFactor(key="mortality", label="x", points=score)])


def _open_alerts(db):
    return [d.to_dict() for d in alerts_ref(db, ORG).where("house_id", "==", HOUSE).stream() if not d.to_dict().get("resolved")]


def test_creates_first_alert_when_none_open(fake_db):
    result = sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-1", risk=_risk(58, "warning"), previous_risk_score=22,
    )
    assert result["action"] == "created"
    assert result["alert"]["status"] == "warning"
    assert result["alert"]["occurrence_count"] == 1
    assert result["alert"]["risk_change"] == 36
    assert len(_open_alerts(fake_db)) == 1


def test_does_not_duplicate_existing_open_alert(fake_db):
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-1", risk=_risk(30, "watch"), previous_risk_score=10,
    )
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-2", risk=_risk(35, "watch"), previous_risk_score=30,
    )
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-3", risk=_risk(40, "watch"), previous_risk_score=35,
    )

    open_alerts = _open_alerts(fake_db)
    assert len(open_alerts) == 1, "a house stuck in watch must not accumulate multiple open alerts"
    assert open_alerts[0]["occurrence_count"] == 3
    assert open_alerts[0]["latest_check_id"] == "check-3"
    assert open_alerts[0]["flock_check_id"] == "check-1"  # first-opened check is preserved


def test_updates_risk_and_status_on_existing_alert(fake_db):
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-1", risk=_risk(30, "watch"), previous_risk_score=10,
    )
    result = sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-2", risk=_risk(80, "critical"), previous_risk_score=30,
    )
    assert result["action"] == "updated"
    assert result["alert"]["status"] == "critical"
    assert result["alert"]["score"] == 80
    assert result["alert"]["risk_change"] == 50


def test_resolution_when_risk_returns_to_normal(fake_db):
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-1", risk=_risk(60, "warning"), previous_risk_score=20,
    )
    result = sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-2", risk=_risk(10, "normal"), previous_risk_score=60,
    )
    assert result["action"] == "resolved"
    assert result["alert"]["resolved"] is True
    assert result["alert"]["resolution_reason"] == "risk_returned_to_normal"
    assert _open_alerts(fake_db) == []

    # The alert document itself is still there (not deleted) - it's now history.
    all_alerts = list(alerts_ref(fake_db, ORG).where("house_id", "==", HOUSE).stream())
    assert len(all_alerts) == 1


def test_normal_with_no_open_alert_does_nothing(fake_db):
    result = sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-1", risk=_risk(5, "normal"), previous_risk_score=None,
    )
    assert result is None
    assert list(alerts_ref(fake_db, ORG).where("house_id", "==", HOUSE).stream()) == []


def test_new_alert_opens_again_after_previous_one_resolved(fake_db):
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-1", risk=_risk(60, "warning"), previous_risk_score=20,
    )
    sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-2", risk=_risk(5, "normal"), previous_risk_score=60,
    )
    result = sync_alert_for_check(
        fake_db, org_id=ORG, farm_id=FARM, house_id=HOUSE, flock_id="flock-1",
        flock_check_id="check-3", risk=_risk(55, "warning"), previous_risk_score=5,
    )
    assert result["action"] == "created"
    assert len(_open_alerts(fake_db)) == 1
    all_alerts = list(alerts_ref(fake_db, ORG).where("house_id", "==", HOUSE).stream())
    assert len(all_alerts) == 2, "resolved alert stays as history; a new episode opens a new alert"
