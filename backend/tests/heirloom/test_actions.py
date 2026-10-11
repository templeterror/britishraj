from datetime import datetime
from uuid import UUID

import pytest
from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.ids import ref_id
from app.heirloom.models import Asset, AuditLog, DomainEvent, Family, Insight, LegalInstrument
from app.heirloom.services import heir_text_guard

MORGAN = ref_id("demo-morgan")
BASE = f"/api/v1/families/{MORGAN}"
GOAL = ref_id("goal-james-business")
SARAH = ref_id("person-sarah")
ROBERT = ref_id("person-robert")
JAMES = ref_id("person-james")
RESERVE = ref_id("decision-liquidity-reserve")
LLC = "asset-family-llc"

PARENT_REVIEW = (
    "Agenda — review with Robert (and estate counsel if he wishes)\n"
    "1. Confirm the 2026 estate planning letter still reflects Robert's intent for the LLC interest.\n"
    "2. Review the operating agreement's partner-consent and sale provisions and how they would apply "
    "after a transfer.\n"
    "3. Discuss whether Robert wants the plan to address liquidity for whoever receives the interest.\n"
    "Robert's portfolio continues to be managed for Robert's own objectives; nothing here is a "
    "recommendation to change it."
)
HEIR_INTRO = (
    "Hi James, thanks for sharing your plans to build a company. If it would help, I'd be glad to offer a "
    "no-pressure planning conversation about funding options and timing for your own goals. Best, Sarah"
)
UNKNOWN_TERMS = "attorney review"


def _share_goal(client: TestClient, active: bool = True, scope: str = "goal_summary") -> None:
    response = client.put(
        f"{BASE}/consents/{GOAL}",
        headers=auth(client, "james"),
        json={"scope": scope, "recipient_person_id": str(SARAH), "active": active},
    )
    assert response.status_code == 200, response.text


def _robert_shares_decision_with_james(client: TestClient, active: bool = True) -> None:
    """A consent change that has nothing to do with James's goal."""
    response = client.put(
        f"{BASE}/consents/{RESERVE}",
        headers=auth(client, "robert"),
        json={"scope": "decision_excerpt", "recipient_person_id": str(JAMES), "active": active},
    )
    assert response.status_code == 200, response.text


def _insights(client: TestClient) -> list[dict]:
    response = client.get(f"{BASE}/insights", headers=auth(client, "sarah"))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _gap(client: TestClient) -> dict:
    (gap,) = [i for i in _insights(client) if i["type"] == "liquidity_gap"]
    return gap


def _create(client: TestClient, insight_id: str, action_type: str, persona: str = "sarah", **body):
    return client.post(
        f"{BASE}/insights/{insight_id}/actions",
        headers=auth(client, persona),
        json={"action_type": action_type, **body},
    )


def _created(client: TestClient, insight_id: str, action_type: str, **body) -> dict:
    response = _create(client, insight_id, action_type, **body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def _patch(client: TestClient, action_id: str, persona: str = "sarah", **body):
    return client.patch(f"{BASE}/actions/{action_id}", headers=auth(client, persona), json=body)


def _actions(client: TestClient) -> list[dict]:
    response = client.get(f"{BASE}/actions", headers=auth(client, "sarah"))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _revision(client: TestClient) -> int:
    return client.get(f"{BASE}/revision", headers=auth(client, "sarah")).json()["data"]["revision"]


def _patch_terms(client: TestClient, asset: str = LLC, persona: str = "sarah", **terms):
    return client.patch(f"{BASE}/assets/{asset}/terms", headers=auth(client, persona), json=terms)


def _james_invitations(client: TestClient) -> list[dict]:
    response = client.get(f"{BASE}/snapshot", headers=auth(client, "james"))
    assert response.status_code == 200, response.text
    return response.json()["data"]["invitations"]


def _code(response) -> str:
    return response.json()["errors"][0]["code"]


def _family_terms(db_session: Session) -> list[str]:
    return [
        *db_session.scalars(select(Asset.label).where(Asset.family_id == MORGAN)),
        *db_session.scalars(select(LegalInstrument.title).where(LegalInstrument.family_id == MORGAN)),
    ]


# --- Heir-safe text guard ----------------------------------------------------------------------


def test_default_heir_intro_passes_guard(client: TestClient, db_session: Session):
    assert heir_text_guard.find_violations(HEIR_INTRO, _family_terms(db_session)) == []

    _share_goal(client)
    action = _created(client, _gap(client)["id"], "heir_intro")
    assert action["draft_text"] == HEIR_INTRO
    assert action["status"] == "draft"


def test_guard_flags_base_terms_amounts_and_family_terms(db_session: Session):
    family_terms = _family_terms(db_session)
    assert "40% interest, Morgan Family Holdings LLC" in family_terms
    find = heir_text_guard.find_violations

    assert find("Your father's will names you.", family_terms) == ["will"]
    assert find("A bequest, an INHERITance and a Trust.", family_terms) == ["inherit", "bequest", "trust"]
    assert find("Funding about $ 5 million, or 750,000 cash.", family_terms) == ["$ 5", "750,000"]
    assert find("Hi James, 2026 is a good year.", family_terms) == [
        "2026"
    ]  # any 4+ digit run reads as an amount
    assert find("Your Estate Planning Letter, 2026 is on file.", family_terms) == [
        "estate",
        "2026",
        "Estate planning letter, 2026",
    ]
    assert find("About the concentrated position,\nNorthwind Robotics (nwrb).", family_terms) == [
        "Concentrated position, Northwind Robotics (NWRB)"
    ]
    assert find("Funding options and timing.", ["", "  "]) == []  # blank family terms never match


@pytest.mark.parametrize(
    ("text", "hit"),
    [
        ("Hi James, I saw your plans for the LLC. Happy to talk funding.", "llc"),
        ("Hi James, happy to help with the Morgan Family Holdings LLC interest.", "llc"),
        (  # an asset label is caught even where no base term appears in it
            "Hi James, about the Concentrated position, Northwind Robotics (NWRB), happy to talk.",
            "Concentrated position, Northwind Robotics (NWRB)",
        ),
    ],
)
def test_heir_intro_mentioning_llc_rejected_422(client: TestClient, text: str, hit: str):
    _share_goal(client)
    response = _create(client, _gap(client)["id"], "heir_intro", draft_text=text)
    assert response.status_code == 422, response.text
    assert _code(response) == "heir_unsafe_text"
    assert hit in response.json()["errors"][0]["message"]
    assert _actions(client) == []


@pytest.mark.parametrize(
    "text", ["Hi James, I can fund $500K.", "Hi James, about $ 5 million.", "Hi James, 500,000 helps."]
)
def test_heir_intro_with_amount_rejected_422(client: TestClient, text: str):
    _share_goal(client)
    response = _create(client, _gap(client)["id"], "heir_intro", draft_text=text)
    assert response.status_code == 422, response.text
    assert _code(response) == "heir_unsafe_text"
    assert _actions(client) == []


def test_guard_applies_to_heir_intro_only_and_to_edits(client: TestClient):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    # The advisor's own agenda may name the LLC and the letter: it never reaches the heir.
    review = _created(
        client, insight_id, "parent_review", draft_text="Review the LLC interest and the estate letter."
    )
    assert review["draft_text"] == "Review the LLC interest and the estate letter."

    intro = _created(client, insight_id, "heir_intro")
    unsafe = _patch(client, intro["id"], status="approved", draft_text="Hi James, about your estate plans.")
    assert unsafe.status_code == 422, unsafe.text
    assert _code(unsafe) == "heir_unsafe_text"
    assert [(a["id"], a["status"], a["draft_text"]) for a in _actions(client) if a["id"] == intro["id"]] == [
        (intro["id"], "draft", HEIR_INTRO)
    ]

    safe = _patch(client, intro["id"], status="approved", draft_text="Hi James, happy to talk funding. Sarah")
    assert safe.status_code == 200, safe.text
    assert safe.json()["data"]["draft_text"] == "Hi James, happy to talk funding. Sarah"
    assert _james_invitations(client)[0]["text"] == "Hi James, happy to talk funding. Sarah"


# --- Lifecycle ---------------------------------------------------------------------------------


def test_action_lifecycle(client: TestClient):
    _share_goal(client)
    gap = _gap(client)
    assert gap["review_status"] == "new"
    before = _revision(client)

    action = _created(client, gap["id"], "parent_review")
    assert set(action) == {
        "id",
        "insight_id",
        "insight_key",
        "action_type",
        "status",
        "draft_text",
        "outcome_note",
        "created_at",
        "updated_at",
    }
    assert action["insight_id"] == gap["id"]
    assert action["insight_key"] == gap["insight_key"]
    assert (action["action_type"], action["status"], action["outcome_note"]) == (
        "parent_review",
        "draft",
        None,
    )
    assert action["draft_text"] == PARENT_REVIEW
    assert _gap(client)["review_status"] == "actioned"
    assert _revision(client) > before

    approved = _patch(client, action["id"], status="approved")
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    for note in ({}, {"outcome_note": "   "}):
        missing = _patch(client, action["id"], status="completed", **note)
        assert missing.status_code == 422, missing.text
        assert _code(missing) == "outcome_required"
    assert [a["status"] for a in _actions(client)] == ["approved"]

    note = "Met Robert; he will review the operating agreement with counsel."
    done = _patch(client, action["id"], status="completed", outcome_note=note)
    assert done.status_code == 200, done.text
    completed = done.json()["data"]
    assert (completed["status"], completed["outcome_note"]) == ("completed", note)
    assert datetime.fromisoformat(completed["updated_at"]) > datetime.fromisoformat(completed["created_at"])
    assert completed["draft_text"] == PARENT_REVIEW  # kept: only revocation purges text

    back = _patch(client, action["id"], status="draft")
    assert back.status_code == 409, back.text
    assert _code(back) == "invalid_transition"
    assert _actions(client)[0]["status"] == "completed"


@pytest.mark.parametrize(
    ("path", "final"),
    [
        (("cancelled",), "approved"),
        (("approved", "cancelled"), "approved"),
        (("approved", "cancelled"), "completed"),
        (("approved",), "draft"),
        ((), "completed"),
    ],
)
def test_invalid_transitions_409(client: TestClient, path: tuple[str, ...], final: str):
    _share_goal(client)
    action = _created(client, _gap(client)["id"], "parent_review")
    for status in path:
        assert _patch(client, action["id"], status=status).status_code == 200
    response = _patch(client, action["id"], status=final, outcome_note="Done.")
    assert response.status_code == 409, response.text
    assert _code(response) == "invalid_transition"


def test_draft_text_edits_only_while_draft(client: TestClient):
    _share_goal(client)
    action = _created(client, _gap(client)["id"], "parent_review")
    assert _patch(client, action["id"], status="approved", draft_text="  ").status_code == 422

    edited = _patch(client, action["id"], status="approved", draft_text="Agenda: confirm the 2026 letter.")
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["draft_text"] == "Agenda: confirm the 2026 letter."

    late = _patch(
        client, action["id"], status="completed", outcome_note="Done.", draft_text="Rewritten afterwards"
    )
    assert late.status_code == 409, late.text
    assert _actions(client)[0]["draft_text"] == "Agenda: confirm the 2026 letter."


def test_unknown_action_and_insight_404(client: TestClient):
    _share_goal(client)
    for ident in ("not-a-uuid", str(ref_id("no-such-action"))):
        assert _patch(client, ident, status="approved").status_code == 404, ident
        assert _create(client, ident, "parent_review").status_code == 404, ident


def test_actions_and_terms_are_advisor_only(client: TestClient):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    action = _created(client, insight_id, "parent_review")
    for persona in ("james", "robert"):
        assert _create(client, insight_id, "parent_review", persona=persona).status_code == 403, persona
        assert _patch(client, action["id"], persona=persona, status="approved").status_code == 403, persona
        headers = auth(client, persona)
        assert client.get(f"{BASE}/actions", headers=headers).status_code == 403, persona
        assert client.get(f"{BASE}/activity", headers=headers).status_code == 403, persona
        assert _patch_terms(client, persona=persona, sale_delay_years=0).status_code == 403, persona
    assert _actions(client)[0]["status"] == "draft"


def test_cannot_act_on_unshared_or_withdrawn_insight(client: TestClient):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    _share_goal(client, active=False)  # the insight is withdrawn with the goal
    response = _create(client, insight_id, "parent_review")
    assert response.status_code == 404, response.text
    assert _actions(client) == []


# --- Invitations and revocation ----------------------------------------------------------------


def test_heir_sees_invitation_only_after_approval(client: TestClient):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    review = _created(client, insight_id, "parent_review")
    assert (
        _patch(client, review["id"], status="approved").status_code == 200
    )  # an agenda is never an invitation

    intro = _created(client, insight_id, "heir_intro")
    assert _james_invitations(client) == []  # a draft is invisible

    approved = _patch(client, intro["id"], status="approved")
    assert approved.status_code == 200, approved.text
    assert _james_invitations(client) == [
        {"from_display": "Sarah Lin", "text": HEIR_INTRO, "status": "approved"}
    ]

    done = _patch(client, intro["id"], status="completed", outcome_note="James took the meeting.")
    assert done.status_code == 200, done.text
    assert _james_invitations(client) == [
        {"from_display": "Sarah Lin", "text": HEIR_INTRO, "status": "completed"}
    ]
    assert "James took the meeting" not in str(
        _james_invitations(client)
    )  # the outcome note stays with the advisor

    other = _created(client, insight_id, "heir_intro")
    assert _patch(client, other["id"], status="cancelled").status_code == 200
    assert len(_james_invitations(client)) == 1  # cancelled drafts never show


@pytest.mark.parametrize("approve", [False, True])
def test_revocation_cancels_and_purges_unsent_drafts(client: TestClient, approve: bool):
    _share_goal(client)
    intro = _created(client, _gap(client)["id"], "heir_intro")
    assert intro["draft_text"] == HEIR_INTRO
    if approve:
        assert _patch(client, intro["id"], status="approved").status_code == 200
        assert len(_james_invitations(client)) == 1

    _share_goal(client, active=False)

    (action,) = _actions(client)
    assert action["id"] == intro["id"]
    assert (action["status"], action["draft_text"]) == ("cancelled", "")
    assert _james_invitations(client) == []


def test_completed_invitation_disappears_when_sharing_is_revoked(client: TestClient):
    _share_goal(client)
    intro = _created(client, _gap(client)["id"], "heir_intro")
    assert _patch(client, intro["id"], status="approved").status_code == 200
    assert _patch(client, intro["id"], status="completed", outcome_note="Sent by hand.").status_code == 200
    assert len(_james_invitations(client)) == 1

    _share_goal(client, active=False)
    assert _james_invitations(client) == []
    assert [a["status"] for a in _actions(client)] == ["completed"]  # the advisor's own record stays


def test_unrelated_consent_change_keeps_invitation_and_drafts(client: TestClient):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    intro = _created(client, insight_id, "heir_intro")
    assert _patch(client, intro["id"], status="approved").status_code == 200
    review = _created(client, insight_id, "parent_review")
    assert _james_invitations(client) == [
        {"from_display": "Sarah Lin", "text": HEIR_INTRO, "status": "approved"}
    ]

    _robert_shares_decision_with_james(client)  # James's goal sharing is unchanged

    assert _james_invitations(client) == [
        {"from_display": "Sarah Lin", "text": HEIR_INTRO, "status": "approved"}
    ]
    kept = {a["id"]: (a["status"], a["draft_text"]) for a in _actions(client)}
    assert kept == {intro["id"]: ("approved", HEIR_INTRO), review["id"]: ("draft", PARENT_REVIEW)}


def test_revocation_still_purges_after_an_unrelated_consent_change(client: TestClient, db_session: Session):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    intro = _created(client, insight_id, "heir_intro")
    assert _patch(client, intro["id"], status="approved").status_code == 200
    review = _created(client, insight_id, "parent_review")

    _robert_shares_decision_with_james(client)  # the recompute replaces the insight the actions sit on
    db_session.expire_all()
    replaced = db_session.get(Insight, UUID(insight_id))
    assert replaced.review_status == "invalidated"
    assert replaced.payload["goal_ref"] == "goal-james-business"  # still holds the shared goal's details

    _share_goal(client, active=False)

    assert _james_invitations(client) == []
    assert {a["id"]: (a["status"], a["draft_text"]) for a in _actions(client)} == {
        intro["id"]: ("cancelled", ""),
        review["id"]: ("cancelled", ""),
    }
    db_session.expire_all()
    assert db_session.get(Insight, UUID(insight_id)).payload == {"withdrawn": "consent_revoked"}


def test_narrowing_detail_to_summary_withdraws_what_was_drafted_from_detail(client: TestClient):
    _share_goal(client, scope="goal_detail")
    detail_gap = _gap(client)
    assert any(e["kind"] == "goal" and e["status"] == "shared_detail" for e in detail_gap["evidence"])
    review = _created(client, detail_gap["id"], "parent_review")

    _share_goal(client, active=False, scope="goal_detail")  # the summary stays shared

    assert [(a["id"], a["status"], a["draft_text"]) for a in _actions(client)] == [
        (review["id"], "cancelled", "")
    ]
    assert any(e["status"] == "shared_summary" for e in _gap(client)["evidence"] if e["kind"] == "goal")


# --- Recompute ---------------------------------------------------------------------------------


def test_actions_list_carries_insight_key(client: TestClient, db_session: Session):
    _share_goal(client)
    first = _gap(client)
    action = _created(client, first["id"], "parent_review")

    changed = _patch_terms(client, liquidatable_fraction=None)  # the pipeline replaces the insight row
    assert changed.status_code == 200, changed.text
    current = _gap(client)
    assert current["id"] != first["id"]
    assert current["review_status"] == "new"

    (listed,) = _actions(client)
    assert listed["id"] == action["id"]
    assert listed["insight_id"] == first["id"]  # never re-pointed on recompute
    assert listed["insight_key"] == current["insight_key"]
    db_session.expire_all()
    assert db_session.get(Insight, UUID(listed["insight_id"])).review_status == "invalidated"


def test_approving_after_recompute_does_not_revive_the_old_insight(client: TestClient, db_session: Session):
    _share_goal(client)
    first = _gap(client)
    action = _created(client, first["id"], "parent_review")
    assert _patch_terms(client, liquidatable_fraction=None).status_code == 200

    assert _patch(client, action["id"], status="approved").status_code == 200
    db_session.expire_all()
    assert db_session.get(Insight, UUID(first["id"])).review_status == "invalidated"
    assert [i["id"] for i in _insights(client) if i["type"] == "liquidity_gap"] != [first["id"]]


def test_actions_listed_newest_first(client: TestClient):
    _share_goal(client)
    insight_id = _gap(client)["id"]
    ids = [
        _created(client, insight_id, kind)["id"]
        for kind in ("parent_review", "heir_intro", "planning_meeting")
    ]
    assert [a["id"] for a in _actions(client)] == ids[::-1]
    planning = _actions(client)[0]
    assert (planning["action_type"], planning["draft_text"]) == ("planning_meeting", "")  # no template


def test_parent_review_template_has_no_portfolio_change_recommendation(client: TestClient):
    _share_goal(client)
    action = _created(client, _gap(client)["id"], "parent_review")
    text = action["draft_text"]
    assert text == PARENT_REVIEW
    assert "managed for Robert's own objectives" in text
    for phrase in ("should sell", "recommend selling", "reduce your", "rebalance", "diversify"):
        assert phrase not in text.lower()


# --- Asset terms -------------------------------------------------------------------------------


def test_terms_patch_changes_flag(client: TestClient, db_session: Session):
    _share_goal(client)
    before = _gap(client)
    assert before["headline_probability"] is not None

    faster = _patch_terms(client, sale_delay_years=0)
    assert faster.status_code == 200, faster.text
    assert faster.json()["data"]["terms"]["sale_delay_years"] == 0
    assert faster.json()["data"]["terms"]["liquidatable_fraction"] == 0.25  # fields not sent are kept
    gaps = [i for i in _insights(client) if i["type"] == "liquidity_gap"]
    # Ruling R6: a faster sale either clears the flag or leaves a higher headline probability.
    assert not gaps or gaps[0]["headline_probability"] > before["headline_probability"]

    unknown = _patch_terms(client, liquidatable_fraction=None)
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["data"]["terms"]["liquidatable_fraction"] is None
    flag = _gap(client)  # the asset-specific insight
    assert flag["headline_probability"] is None
    assert UNKNOWN_TERMS in flag["headline_condition"]
    assert all(row["p"] is None for row in flag["scenario_rows"])

    db_session.expire_all()
    assert (
        db_session.scalars(select(Asset).where(Asset.external_ref == LLC)).one().terms["sale_delay_years"]
        == 0
    )


def test_terms_patch_emits_event_and_skips_no_ops(client: TestClient):
    start = _revision(client)
    assert (
        _patch_terms(client, sale_delay_years=2, liquidatable_fraction=0.25).status_code == 200
    )  # unchanged
    assert _revision(client) == start

    changed = _patch_terms(client, distribution_yield=0.02, partner_consent_process_documented=None)
    assert changed.status_code == 200, changed.text
    terms = changed.json()["data"]["terms"]
    assert (terms["distribution_yield"], terms["partner_consent_process_documented"]) == (0.02, None)
    assert _revision(client) == start + 1
    assert changed.json()["meta"]["revision"] == start + 1


@pytest.mark.parametrize(
    "terms",
    [
        {},
        {"sale_delay_years": -1},
        {"sale_delay_years": 11},
        {"sale_delay_years": 1.5},
        {"sale_delay_years": None},
        {"liquidatable_fraction": 1.01},
        {"liquidatable_fraction": -0.1},
        {"distribution_yield": 0.21},
        {"distribution_yield": -0.01},
        {"distribution_yield": None},
        {"expected_return": 0.5},  # only the four editable terms are accepted
        {"sale_delay_years": 1, "partner_consent_required": False},
    ],
)
def test_terms_patch_validation_422(client: TestClient, terms: dict):
    start = _revision(client)
    response = _patch_terms(client, **terms)
    assert response.status_code == 422, response.text
    assert _revision(client) == start
    snapshot = client.get(f"{BASE}/snapshot", headers=auth(client, "sarah")).json()["data"]
    (llc,) = [a for a in snapshot["assets"] if a["ref"] == LLC]
    assert llc["terms"]["sale_delay_years"] == 2
    assert llc["terms"]["partner_consent_required"] is True


@pytest.mark.parametrize(
    "asset", ["not-a-uuid", str(ref_id("no-such-asset")), "person-james", "goal-james-business"]
)
def test_terms_patch_unknown_asset_404(client: TestClient, asset: str):
    assert _patch_terms(client, asset=asset, sale_delay_years=0).status_code == 404


def test_terms_patch_accepts_the_asset_id(client: TestClient):
    response = _patch_terms(client, asset=str(ref_id(LLC)), sale_delay_years=3)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["ref"] == LLC


# --- Activity ----------------------------------------------------------------------------------


def _activity(client: TestClient) -> list[dict]:
    response = client.get(f"{BASE}/activity", headers=auth(client, "sarah"))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def test_activity_lists_actions_audit_and_events_without_payloads(client: TestClient):
    _share_goal(client)
    action = _created(client, _gap(client)["id"], "heir_intro")
    assert _patch(client, action["id"], status="approved").status_code == 200

    rows = _activity(client)
    assert {r["kind"] for r in rows} == {"action", "audit", "event"}
    for row in rows:
        assert set(row) == {"id", "kind", "at", "type", "resource", "actor", "outcome", "allowed"}
    times = [datetime.fromisoformat(r["at"]) for r in rows]
    assert times == sorted(times, reverse=True)

    (action_row,) = [r for r in rows if r["kind"] == "action"]
    assert (action_row["type"], action_row["actor"], action_row["outcome"]) == (
        "heir_intro",
        "Sarah Lin",
        "approved",
    )
    assert any(r["kind"] == "event" and r["type"] == "advisor_action.updated.v1" for r in rows)
    assert any(r["kind"] == "event" and r["type"] == "consent.changed.v1" for r in rows)
    audit = [r for r in rows if r["kind"] == "audit" and r["type"] == "action.update"]
    assert [(r["actor"], r["outcome"], r["allowed"]) for r in audit] == [("Sarah Lin", "approved", True)]

    text = str(rows)
    for private in (HEIR_INTRO, "Hi James", "insight_key", "liquidity_gap:"):
        assert private not in text, private


def test_activity_hides_the_heirs_private_activity(client: TestClient):
    james = auth(client, "james")
    assert (
        client.patch(
            f"{BASE}/heir-goals/{GOAL}", headers=james, json={"version": 1, "milestone": "Hire a cofounder"}
        ).status_code
        == 200
    )
    assert client.post(f"{BASE}/memory/ask", headers=james, json={"question": "Why?"}).status_code == 200
    _share_goal(client)

    rows = _activity(client)
    assert any(r["type"] == "consent.changed.v1" for r in rows)
    types = {r["type"] for r in rows}
    assert not {"heir_goal.update", "heir_goal.updated.v1", "memory.ask"} & types
    assert "cofounder" not in str(rows)


def test_activity_hides_the_heirs_evidence_reads(client: TestClient):
    james = auth(client, "james")  # James has shared nothing with Sarah
    assert client.get(f"{BASE}/evidence/goal-james-business", headers=james).status_code == 200
    secret = "secret-note-i-wrote-about-my-startup"
    assert client.get(f"{BASE}/evidence/{secret}", headers=james).status_code == 404

    assert _activity(client) == []


def test_activity_lists_only_known_advisor_side_audit_rows_and_events(client: TestClient, db_session: Session):
    family = db_session.get(Family, MORGAN)
    db_session.add(
        AuditLog(
            organization_id=family.organization_id,
            actor_external_id="james",
            family_id=MORGAN,
            action="heir_notes.read",  # a future heir-side action nobody has classified yet
            resource_type="heir_notes",
            resource_id="my-private-notes",
            allowed=True,
            reason_code="allowed",
        )
    )
    db_session.add(
        DomainEvent(
            organization_id=family.organization_id,
            family_id=MORGAN,
            type="heir_notes.read.v1",
            aggregate_id="my-private-notes",
            idempotency_key="test-unclassified-heir-event",
        )
    )
    db_session.commit()
    assert _activity(client) == []

    assert _patch_terms(client, sale_delay_years=1).status_code == 200
    assert {(r["kind"], r["type"]) for r in _activity(client)} == {
        ("audit", "asset.terms_update"),
        ("event", "asset.terms_updated.v1"),
    }


def test_activity_is_capped_at_50_newest_first(client: TestClient):
    for index in range(30):
        assert (
            _patch_terms(client, sale_delay_years=index % 2).status_code == 200
        )  # an audit row and an event each
    rows = _activity(client)
    assert len(rows) == 50
    times = [datetime.fromisoformat(r["at"]) for r in rows]
    assert times == sorted(times, reverse=True)
    assert len({r["id"] for r in rows}) == 50


def test_activity_records_denied_attempts(client: TestClient):
    assert _create(client, str(ref_id("x")), "parent_review", persona="james").status_code == 403
    denied = [r for r in _activity(client) if r["kind"] == "audit" and r["allowed"] is False]
    assert [(r["type"], r["actor"], r["outcome"]) for r in denied] == [
        ("family.role_check", "James Morgan", "role_not_permitted")
    ]
