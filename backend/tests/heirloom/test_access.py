import time
import uuid

import jwt
import pytest
from conftest import auth
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.config import HeirloomSettings
from app.heirloom.context import auth_context
from app.heirloom.ids import ref_id
from app.heirloom.models import AuditLog, Family
from app.heirloom.services import events
from app.main import create_app

MORGAN = ref_id("demo-morgan")
CHEN = ref_id("family-chen")


def _revision(client: TestClient, family_id: uuid.UUID, headers: dict[str, str] | None = None, **kwargs):
    return client.request("GET", f"/api/v1/families/{family_id}/revision", headers=headers, **kwargs)


def test_missing_token_401(client: TestClient):
    response = _revision(client, MORGAN)
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "unauthenticated"


def test_tampered_token_401(client: TestClient):
    token = auth(client, "sarah")["Authorization"].removeprefix("Bearer ")
    head, signature = token.rsplit(".", 1)
    flipped = "A" if signature[-1] != "A" else "B"
    response = _revision(client, MORGAN, {"Authorization": f"Bearer {head}.{signature[:-1]}{flipped}"})
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "unauthenticated"


def test_token_from_another_secret_401(client: TestClient):
    other = HeirloomSettings(mode="demo", demo_secret="some-other-secret")
    token = auth_context.issue_demo_token("demo_sarah", "org_relay_demo", other)
    assert _revision(client, MORGAN, {"Authorization": f"Bearer {token}"}).status_code == 401


def test_expired_token_401(client: TestClient, settings: HeirloomSettings):
    token = auth_context.issue_demo_token("demo_sarah", "org_relay_demo", settings, ttl_s=-1)
    response = _revision(client, MORGAN, {"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "unauthenticated"


def test_member_can_read_revision(client: TestClient):
    response = _revision(client, MORGAN, auth(client, "sarah"))
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["revision"] >= 0
    assert body["data"]["consent_revision"] == 0
    assert body["meta"]["mode"] == "demo"
    assert response.headers["cache-control"] == "no-store"


def test_demo_session_payload(client: TestClient):
    response = client.post("/api/v1/demo/sessions", json={"persona": "james"})
    data = response.json()["data"]
    assert data["family_id"] == str(MORGAN)
    assert data["person"] == {
        "id": str(ref_id("person-james")),
        "display_name": "James Morgan",
        "role": "adult_heir",
    }


def test_cross_org_family_is_404(client: TestClient, db_session: Session):
    response = _revision(client, MORGAN, auth(client, "other_advisor"))
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "family_not_found"
    row = db_session.scalars(select(AuditLog).where(AuditLog.actor_external_id == "demo_other_advisor")).one()
    assert row.allowed is False
    assert row.reason_code == "not_member"
    assert row.family_id == MORGAN
    assert row.organization_id == "org_other"  # the caller's org, not the target family's


def test_forged_family_id_is_404(client: TestClient, db_session: Session):
    response = _revision(client, CHEN, auth(client, "sarah"))
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "family_not_found"
    unknown = _revision(client, uuid.uuid4(), auth(client, "sarah"))
    assert unknown.status_code == 404
    denied = db_session.scalars(select(AuditLog).where(AuditLog.allowed.is_(False))).all()
    assert len(denied) == 2


def test_role_and_view_params_ignored(client: TestClient):
    headers = auth(client, "james")
    response = _revision(
        client, MORGAN, headers, params={"view": "advisor", "role": "advisor"}, json={"role": "advisor"}
    )
    assert response.status_code == 200
    families = client.get("/api/v1/me/families", headers=headers).json()["data"]
    assert [(f["family_id"], f["role"]) for f in families] == [(str(MORGAN), "adult_heir")]


def test_me_families_only_lists_own_memberships(client: TestClient):
    families = client.get("/api/v1/me/families", headers=auth(client, "other_advisor")).json()["data"]
    assert [f["family_id"] for f in families] == [str(CHEN)]
    assert client.get("/api/v1/me/families").status_code == 401


def test_require_role_denies_and_audits(client: TestClient, db_session: Session, settings: HeirloomSettings):
    from app.heirloom.context.access import require_family, require_role
    from app.heirloom.context.auth_context import RequestContext
    from app.heirloom.envelope import ApiError

    actor = require_family(MORGAN, RequestContext("demo_james", "org_relay_demo"), db_session)
    assert actor.role == "adult_heir"
    assert require_role(actor, "adult_heir", "parent") is actor
    with pytest.raises(ApiError) as caught:
        require_role(actor, "advisor")
    assert (caught.value.status, caught.value.code) == (403, "forbidden_for_role")
    row = db_session.scalars(select(AuditLog).where(AuditLog.allowed.is_(False))).one()
    assert (row.actor_external_id, row.family_id, row.reason_code) == (
        "demo_james",
        MORGAN,
        "role_not_permitted",
    )


def test_demo_sessions_disabled_in_clerk_mode():
    clerk = HeirloomSettings(mode="clerk", database_url="sqlite://", clerk_domain="clerk.example.test")
    with TestClient(create_app(clerk)) as client:
        response = client.post("/api/v1/demo/sessions", json={"persona": "sarah"})
        assert response.status_code == 404
        assert client.post("/api/v1/demo/reset").status_code == 404


def test_clerk_jwt_resolves_org_claims(monkeypatch: pytest.MonkeyPatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    clerk = HeirloomSettings(mode="clerk", database_url="sqlite://", clerk_domain="clerk.example.test")

    class FakeJwks:
        def get_signing_key_from_jwt(self, _token: str):
            return type("SigningKey", (), {"key": key.public_key()})()

    monkeypatch.setattr(auth_context, "_jwks_client", lambda _domain: FakeJwks())

    def token(claims: dict, signing_key=key) -> str:
        base = {"sub": "user_1", "iss": "https://clerk.example.test", "exp": int(time.time()) + 60}
        return jwt.encode({**base, **claims}, signing_key, algorithm="RS256")

    ctx = auth_context.resolve_request_context(f"Bearer {token({'org_id': 'org_a'})}", clerk)
    assert (ctx.external_user_id, ctx.organization_id) == ("user_1", "org_a")
    ctx = auth_context.resolve_request_context(f"Bearer {token({'o': {'id': 'org_b'}})}", clerk)
    assert ctx.organization_id == "org_b"
    for bad in (
        token({}),  # no organization
        token({"org_id": "org_a", "iss": "https://evil.example.test"}),
        token({"org_id": "org_a", "exp": int(time.time()) - 5}),
        token({"org_id": "org_a"}, rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    ):
        with pytest.raises(auth_context.ApiError) as caught:
            auth_context.resolve_request_context(f"Bearer {bad}", clerk)
        assert caught.value.status == 401
    demo_token = auth_context.issue_demo_token("demo_sarah", "org_relay_demo", HeirloomSettings(mode="demo"))
    with pytest.raises(auth_context.ApiError):
        auth_context.resolve_request_context(f"Bearer {demo_token}", clerk)


def test_demo_reset_reseeds(client: TestClient):
    headers = auth(client, "sarah")
    assert client.post("/api/v1/demo/reset").status_code == 401
    assert client.post("/api/v1/demo/reset", headers=headers).status_code == 200
    assert _revision(client, MORGAN, headers).status_code == 200


def test_event_idempotency(db_session: Session):
    family = db_session.get(Family, MORGAN)
    before = family.data_revision
    seen: list[str] = []
    events.register("*", lambda _session, _family, event: seen.append(event.type))
    try:
        assert (
            events.emit(db_session, family, "test.happened", "thing-1", {"a": 1}, idempotency_key="k-1")
            is True
        )
        assert (
            events.emit(db_session, family, "test.happened", "thing-1", {"a": 1}, idempotency_key="k-1")
            is False
        )
    finally:
        events.clear_handlers()
    assert family.data_revision == before + 1
    assert seen == ["test.happened"]
    assert events.emit(db_session, family, "test.happened", "thing-2", {}) is True  # no key: always new
    assert family.data_revision == before + 2
