def _setup_alert(client, farm_id, house_id):
    return client.post(
        f"/farms/{farm_id}/houses/{house_id}/flock-checks",
        json={
            "period": "morning",
            "bird_count": 1000,
            "mortality": 0,
            "activity": "lethargic",
            "feeding_behaviour": "none",
            "water_level": "lower",
        },
    ).json()


def test_inspection_uses_authenticated_identity_not_user_input(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    house = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()

    inspection = authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/inspections",
        json={"findings": "Checked feeders, all normal.", "finding_category": "everything_normal"},
    ).json()

    assert inspection["performed_by"] == "farmer@example.com"  # from the authed_client fixture's fake token


def test_inspection_auto_links_and_resolves_open_alert(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    house = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()
    _setup_alert(authed_client, farm["id"], house["id"])

    open_alerts = authed_client.get("/alerts", params={"resolved": False}).json()
    assert len(open_alerts) == 1

    inspection = authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/inspections",
        json={
            "findings": "Water line was blocked, cleared it.",
            "finding_category": "water_issue",
            "action_taken": "Cleared blocked water line",
        },
    ).json()

    assert inspection["alert_id"] == open_alerts[0]["id"]

    still_open = authed_client.get("/alerts", params={"resolved": False}).json()
    assert [a for a in still_open if a["house_id"] == house["id"]] == []

    resolved = authed_client.get("/alerts", params={"resolved": True}).json()
    resolved_for_house = [a for a in resolved if a["house_id"] == house["id"]]
    assert len(resolved_for_house) == 1
    assert resolved_for_house[0]["resolution_reason"] == "inspection_completed"
    assert resolved_for_house[0]["resolving_inspection_id"] == inspection["id"]


def test_inspection_history_answers_what_did_we_find_last_time(authed_client):
    farm = authed_client.post("/farms", json={"name": "Farm"}).json()
    house = authed_client.post(f"/farms/{farm['id']}/houses", json={"name": "House A"}).json()
    _setup_alert(authed_client, farm["id"], house["id"])
    authed_client.post(
        f"/farms/{farm['id']}/houses/{house['id']}/inspections",
        json={"findings": "Found sick birds, isolated them.", "finding_category": "sick_birds_observed"},
    )

    history = authed_client.get(f"/farms/{farm['id']}/houses/{house['id']}/inspections").json()
    assert len(history) == 1
    assert history[0]["finding_category"] == "sick_birds_observed"
