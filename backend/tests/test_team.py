from datetime import datetime, timezone

from app.core.refs import members_ref

OWNER_UID = "owner-1"
OWNER_EMAIL = "owner@example.com"


def _seed_member(fake_db, org_id, uid, email, role, status="active"):
    """Directly writes a membership doc, bypassing the invite/accept flow -
    for tests that only care about role *enforcement*, not the invitation
    flow itself (that's covered separately in test_accept_invitation_flow)."""
    members_ref(fake_db, org_id).document(uid).set(
        {
            "user_id": uid,
            "email": email,
            "display_name": email,
            "role": role,
            "status": status,
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "invited_by": OWNER_UID,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def test_owner_membership_is_backfilled_on_first_request(make_client):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    response = owner.get("/team")
    assert response.status_code == 200
    members = response.json()["members"]
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == OWNER_EMAIL


def test_invite_creation(make_client):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    response = owner.post("/team/invitations", json={"email": "manager@example.com", "role": "manager"})
    assert response.status_code == 201
    assert response.json()["status"] == "pending"

    team = owner.get("/team").json()
    assert len(team["pending_invitations"]) == 1
    assert team["pending_invitations"][0]["email"] == "manager@example.com"


def test_duplicate_invitation_rejected(make_client):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.post("/team/invitations", json={"email": "manager@example.com", "role": "manager"})
    second = owner.post("/team/invitations", json={"email": "manager@example.com", "role": "worker"})
    assert second.status_code == 409


def test_cannot_invite_someone_as_owner(make_client):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    response = owner.post("/team/invitations", json={"email": "manager@example.com", "role": "owner"})
    assert response.status_code == 422


def test_worker_cannot_invite_or_manage_team(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")  # backfill owner membership
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    worker = make_client("worker-1", "worker@example.com", org_id=OWNER_UID)
    assert worker.post("/team/invitations", json={"email": "x@example.com", "role": "worker"}).status_code == 403
    assert worker.patch(f"/team/members/{OWNER_UID}", json={"role": "worker"}).status_code == 403
    assert worker.delete(f"/team/members/{OWNER_UID}").status_code == 403

    # But a worker CAN see the team list (viewing isn't a sensitive action).
    assert worker.get("/team").status_code == 200


def test_manager_cannot_access_billing(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    _seed_member(fake_db, OWNER_UID, "manager-1", "manager@example.com", "manager")

    manager = make_client("manager-1", "manager@example.com", org_id=OWNER_UID)
    assert manager.get("/billing").status_code == 403
    assert manager.get("/billing/usage").status_code == 403


def test_role_update_by_owner(make_client, fake_db):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    response = owner.patch("/team/members/worker-1", json={"role": "manager"})
    assert response.status_code == 200
    assert response.json()["role"] == "manager"


def test_cannot_remove_or_demote_the_only_owner(make_client):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")  # backfill

    assert owner.delete(f"/team/members/{OWNER_UID}").status_code == 400
    assert owner.patch(f"/team/members/{OWNER_UID}", json={"role": "manager"}).status_code == 400


def test_removing_member_clears_their_org_access(make_client, fake_db, mock_firebase_claims):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    owner.get("/team")
    _seed_member(fake_db, OWNER_UID, "worker-1", "worker@example.com", "worker")

    response = owner.delete("/team/members/worker-1")
    assert response.status_code == 200
    assert "worker-1" in mock_firebase_claims["revoked"]
    assert any(uid == "worker-1" for uid, _claims in mock_firebase_claims["set_claims"])

    team = owner.get("/team").json()
    assert all(m["id"] != "worker-1" for m in team["members"])


def test_accept_invitation_end_to_end(make_client, mock_firebase_claims):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    invite = owner.post("/team/invitations", json={"email": "manager@example.com", "role": "manager"}).json()

    manager = make_client("manager-uid", "manager@example.com")  # no org_id yet - brand new user
    discovered = manager.get("/team/my-invitations").json()
    assert len(discovered) == 1
    assert discovered[0]["id"] == invite["id"]
    assert discovered[0]["org_id"] == OWNER_UID
    assert discovered[0]["role"] == "manager"

    accept = manager.post("/team/invitations/accept", json={"org_id": OWNER_UID, "invitation_id": invite["id"]})
    assert accept.status_code == 200
    assert accept.json()["role"] == "manager"
    assert ("manager-uid", {"org_id": OWNER_UID}) in mock_firebase_claims["set_claims"]

    # Once accepted, it's simulated by re-authenticating with the org_id
    # claim now set (mirrors a real token refresh after acceptance).
    manager_in_org = make_client("manager-uid", "manager@example.com", org_id=OWNER_UID)
    team = manager_in_org.get("/team").json()
    assert any(m["id"] == "manager-uid" and m["role"] == "manager" for m in team["members"])

    # And the invitation itself is no longer pending / not re-discoverable.
    assert manager_in_org.get("/team/my-invitations").json() == []


def test_accept_invitation_wrong_email_rejected(make_client):
    owner = make_client(OWNER_UID, OWNER_EMAIL)
    invite = owner.post("/team/invitations", json={"email": "manager@example.com", "role": "manager"}).json()

    stranger = make_client("stranger-uid", "someone-else@example.com")
    response = stranger.post("/team/invitations/accept", json={"org_id": OWNER_UID, "invitation_id": invite["id"]})
    assert response.status_code == 403


def test_cannot_join_org_by_supplying_arbitrary_org_id(make_client):
    """Even with a syntactically valid request, accepting requires a real
    pending invitation whose email matches the caller - never just an org_id."""
    stranger = make_client("stranger-uid", "stranger@example.com")
    response = stranger.post(
        "/team/invitations/accept", json={"org_id": OWNER_UID, "invitation_id": "does-not-exist"}
    )
    assert response.status_code == 404


def test_cross_org_team_isolation(make_client, fake_db):
    org_a_owner = make_client("org-a-owner", "a@example.com")
    org_a_owner.get("/team")
    org_a_owner.post("/team/invitations", json={"email": "invitee@example.com", "role": "manager"})

    org_b_owner = make_client("org-b-owner", "b@example.com")
    team_b = org_b_owner.get("/team").json()
    assert len(team_b["members"]) == 1  # only org B's own owner
    assert team_b["pending_invitations"] == []  # never sees org A's invitation
