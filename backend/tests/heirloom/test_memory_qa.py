import pytest
from conftest import auth
from fastapi.testclient import TestClient

from app.heirloom.ids import ref_id

MORGAN = ref_id("demo-morgan")
BASE = f"/api/v1/families/{MORGAN}"
JAMES = ref_id("person-james")
RETAIN = ref_id("decision-retain-llc")
RESERVE = ref_id("decision-liquidity-reserve")
QUESTION = "Why was family control important?"
NO_RECORD = "No approved record answers that."
OFF_LIMITS = "Heirloom can't answer questions about estate plans, balances or inheritance."


def _verify_and_share(client: TestClient, decision_id) -> None:
    verified = client.post(
        f"{BASE}/decisions/{decision_id}/verify",
        headers=auth(client, "sarah"),
        json={"approved": True, "edited_rationale": None, "note": None},
    )
    assert verified.status_code == 200, verified.text
    _share(client, decision_id)


def _share(client: TestClient, decision_id) -> None:
    shared = client.put(
        f"{BASE}/consents/{decision_id}",
        headers=auth(client, "robert"),
        json={"scope": "decision_excerpt", "recipient_person_id": str(JAMES), "active": True},
    )
    assert shared.status_code == 200, shared.text


def _ask(client: TestClient, question: str, persona: str = "james"):
    return client.post(f"{BASE}/memory/ask", headers=auth(client, persona), json={"question": question})


def _answer(client: TestClient, question: str) -> dict:
    response = _ask(client, question)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_family_control_question_answered_after_sharing(client: TestClient):
    _verify_and_share(client, RETAIN)
    _share(client, RESERVE)  # shared but unrelated: must not outrank, or match at all

    answer = _answer(client, QUESTION)
    assert answer["status"] == "answered"
    assert answer["reason"] is None
    first = answer["matches"][0]
    assert first["decision_id"] == str(RETAIN)
    assert "keep control of the business" in first["excerpt"]
    assert first["score"] >= 2
    assert first["source_title"].startswith("Meeting transcript")
    assert first["verified_by_display"] == "Sarah Lin"
    assert first["date"] == "2026-04-15"
    assert [m["decision_id"] for m in answer["matches"]] == [str(RETAIN)]


def test_unshared_record_not_retrievable(client: TestClient):
    answer = _answer(client, QUESTION)
    assert answer == {"status": "refused", "reason": NO_RECORD, "matches": []}

    # Verified but not shared by Robert: still not retrievable.
    verified = client.post(
        f"{BASE}/decisions/{RETAIN}/verify",
        headers=auth(client, "sarah"),
        json={"approved": True, "edited_rationale": None, "note": None},
    )
    assert verified.status_code == 200
    assert _answer(client, QUESTION)["reason"] == NO_RECORD


@pytest.mark.parametrize(
    "question",
    [
        "What will I inherit?",
        "Who is the beneficiary of the family business?",
        "How much is the brokerage account worth?",
        "What is in the trust?",
        "Tell me about the estate plan and family control",
        "What balance does Dad keep?",
        "Is there an inheritance for me?",
    ],
)
def test_inheritance_question_refused(client: TestClient, question: str):
    _verify_and_share(client, RETAIN)
    answer = _answer(client, question)
    assert answer == {"status": "refused", "reason": OFF_LIMITS, "matches": []}


@pytest.mark.parametrize("persona", ["sarah", "robert"])
def test_advisor_cannot_use_heir_qa_403(client: TestClient, persona: str):
    response = _ask(client, QUESTION, persona)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "forbidden_for_role"


def test_blank_question_422(client: TestClient):
    assert _ask(client, "   ").status_code == 422
