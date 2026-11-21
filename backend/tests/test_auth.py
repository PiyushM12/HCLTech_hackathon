from contextlib import closing

from fastapi.testclient import TestClient

from app.auth import COOKIE


def test_login_ignores_identity_headers_and_revokes_session(client, account_client):
    account_client("C1001")  # provision the account without sharing its client cookie
    spoof = {"X-Citizen-Id": "C1001", "X-Role": "admin"}
    with closing(TestClient(client.app)) as browser:
        assert browser.get("/auth/me", headers=spoof).json() == {"account": None}
        guest = browser.post("/ask", headers=spoof, json={"message": "Can I get old age pension?"}).json()
        assert guest["answer_type"] == "clarification_needed"
        credentials = {"username": "C1001", "password": "temporary-test-password", "role": "user"}
        assert browser.post("/auth/login", json={**credentials, "password": "wrong"}).status_code == 401
        login = browser.post("/auth/login", json=credentials)
        assert login.status_code == 200
        assert "HttpOnly" in login.headers["set-cookie"] and "SameSite=strict" in login.headers["set-cookie"]
        account = browser.get("/auth/me", headers={"X-Citizen-Id": "C1002"}).json()["account"]
        assert account["citizen_id"] == "C1001" and account["role"] == "user"
        assert browser.get(f"/conversations/{guest['conversation_id']}").status_code == 404
        token = browser.cookies.get(COOKIE)
        assert browser.post("/auth/logout", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert browser.post("/auth/logout").status_code == 204
        replay = browser.get("/auth/me", headers={"Cookie": f"{COOKIE}={token}"})
        assert replay.json() == {"account": None}


def test_admin_endpoints_require_an_admin_session(client, account_client):
    user = account_client("C1001")
    admin = account_client()
    assert admin.get("/auth/me").json()["account"]["role"] == "admin"
    assert client.get("/citizens/demo").status_code == 401
    assert user.get("/citizens/demo").status_code == 403
    assert admin.get("/citizens/demo").status_code == 200
    assert admin.post("/ask", json={"message": "Can I get the old age pension?"}).status_code == 403
    for path in ("/ingest", "/admin/load"):
        assert client.post(path).status_code == 401
        assert user.post(path).status_code == 403


def test_login_requires_the_accounts_role(client, account_client):
    user = account_client("C1001").get("/auth/me").json()["account"]
    admin = account_client().get("/auth/me").json()["account"]
    with closing(TestClient(client.app)) as browser:
        for account, other_role in ((user, "admin"), (admin, "user")):
            credentials = {"username": account["username"], "password": "temporary-test-password"}
            assert browser.post("/auth/login", json=credentials).status_code == 422
            rejected = browser.post("/auth/login", json={**credentials, "role": other_role})
            assert rejected.status_code == 403 and "set-cookie" not in rejected.headers
            assert browser.get("/auth/me").json()["account"] is None
            allowed = browser.post("/auth/login", json={**credentials, "role": account["role"]})
            assert allowed.status_code == 200 and allowed.json()["account"]["role"] == account["role"]
            assert browser.post("/auth/logout").status_code == 204


def test_registration_creates_and_signs_in_a_new_citizen(client):
    credentials = {"username": "New-Citizen", "password": "test-registration-password"}
    with closing(TestClient(client.app)) as browser:
        response = browser.post("/auth/register", json={**credentials, "consent": True})
        assert response.status_code == 201, response.text
        account = response.json()["account"]
        assert account["username"] == "new-citizen" and account["role"] == "user"
        assert account["citizen_id"].startswith("USR-") and account["consent_given"] == "Y"
        assert "HttpOnly" in response.headers["set-cookie"]
        assert browser.get("/auth/me").json()["account"]["citizen_id"] == account["citizen_id"]
        assert browser.post("/admin/load").status_code == 403

        draft = browser.post("/ask", json={"message": "Fill in the pension form for me.",
                                          "as_of_date": "2026-11-21"}).json()
        assert draft["answer_type"] == "confirmation_needed"
        action = draft["pending_action"]["action_id"]
        confirmed = browser.post(f"/actions/{action}/confirm")
        assert confirmed.status_code == 200 and confirmed.json()["result"]["status"] == "draft"

        assert browser.post("/auth/logout").status_code == 204
        login = browser.post("/auth/login", json={**credentials, "role": "user"})
        assert login.status_code == 200 and login.json()["account"]["citizen_id"] == account["citizen_id"]


def test_registration_rejects_role_assignment_and_duplicate_accounts(client, conn):
    credentials = {"username": "another-user", "password": "test-registration-password"}
    with closing(TestClient(client.app)) as browser:
        for payload in ({"role": "admin"}, {"citizen_id": "C1001"}, {"password": "too-short"}):
            invalid = browser.post("/auth/register", json={**credentials, **payload})
            assert invalid.status_code == 422
            assert credentials["password"] not in invalid.text and "too-short" not in invalid.text

        response = browser.post("/auth/register", json=credentials)
        assert response.status_code == 201 and response.json()["account"]["consent_given"] == "N"
        assert browser.post("/auth/logout").status_code == 204
        before = conn.execute("SELECT COUNT(*) FROM citizens").fetchone()[0]
        duplicate = browser.post("/auth/register", json={**credentials, "username": "ANOTHER-USER"})
        assert duplicate.status_code == 409 and "set-cookie" not in duplicate.headers
        assert conn.execute("SELECT COUNT(*) FROM citizens").fetchone()[0] == before
        assert browser.get("/auth/me").json() == {"account": None}


def test_private_records_are_scoped_to_owner_or_admin(client, account_client):
    owner = account_client("C1009")
    other_user = account_client("C1002")
    admin = account_client()
    referral = owner.post("/ask", json={"message": "An officer asked for a bribe. I want to talk to an officer."}).json()
    assert referral["referral_id"]
    for path in (f"/conversations/{referral['conversation_id']}", f"/audit/{referral['trace_id']}",
                 f"/referrals/{referral['referral_id']}"):
        assert owner.get(path).status_code == 200
        assert other_user.get(path).status_code == 404
        assert client.get(path).status_code == 404
        assert admin.get(path).status_code == 200

    guest = client.post("/ask", json={"message": "What are the documents for the old age pension?"}).json()
    assert client.get(f"/conversations/{guest['conversation_id']}").status_code == 200
    with closing(TestClient(client.app)) as other_guest:
        other_guest.post("/ask", json={"message": "Can I get old age pension?"})
        assert other_guest.get(f"/conversations/{guest['conversation_id']}").status_code == 404
