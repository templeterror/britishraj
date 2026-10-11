"""Heir memory Q&A: deterministic keyword retrieval over the decisions the parent approved for this heir.

No model is called and nothing is generated: an answer is a list of approved records, quoted as stored.
Questions about estate plans, balances or inheritance are refused before any retrieval.
"""

import re

from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.dto.heir import HeirDecisionView, MemoryAnswer, MemoryMatch
from app.heirloom.services import audit, snapshots

OFF_LIMITS_REASON = "Heirloom can't answer questions about estate plans, balances or inheritance."
NO_RECORD_REASON = "No approved record answers that."
MAX_MATCHES = 3

# Word-start matches, so "inherited", "estates", "beneficiaries" and "balances" are refused too.
_OFF_LIMITS = re.compile(r"\b(inherit|estate|beneficiar|trust|worth|balance|wills?\b|how\s+much\b)")
_WORD = re.compile(r"[a-z]+")
_STOPWORD_TEXT = """
    a about above after again all also am an and any are as at be because been before being below between
    both but by can could did do does doing down during each few for from further had has have having he her
    here hers him his how i if in into is it its just me more most my no nor not now of off on once only or
    other our ours out over own same she should so some such than that the their theirs them then there
    these they this those through to too under until up very was we were what when where which while who
    whom why with would you your yours
"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def _terms(text: str | None) -> set[str]:
    return {word for word in _WORD.findall((text or "").lower()) if word not in STOPWORDS}


def _excerpt(view: HeirDecisionView) -> str | None:
    return (view.locator or {}).get("quoted_span") or view.rationale


def _score(question_terms: set[str], view: HeirDecisionView) -> int:
    """Distinct question terms that appear in the record's title, rationale or quoted source span."""
    record_terms = _terms(view.title) | _terms(view.rationale) | _terms((view.locator or {}).get("quoted_span"))
    return len(question_terms & record_terms)


def _refused(reason: str) -> MemoryAnswer:
    return MemoryAnswer(status="refused", reason=reason, matches=[])


def _answer(actor: FamilyActor, session: Session, question: str) -> MemoryAnswer:
    if _OFF_LIMITS.search(question.lower()):
        return _refused(OFF_LIMITS_REASON)
    terms = _terms(question)
    approved = snapshots.heir_approved_decisions(session, actor.family, actor.person)
    scored = [(score, view) for view in approved if (score := _score(terms, view)) >= 1]
    if not scored:
        return _refused(NO_RECORD_REASON)
    # Highest score first; ties go to the more recent decision, then to the id (stable order).
    scored.sort(key=lambda item: (-item[0], -item[1].date.toordinal(), item[1].decision_id))
    return MemoryAnswer(
        status="answered",
        reason=None,
        matches=[
            MemoryMatch(
                decision_id=view.decision_id,
                title=view.title,
                date=view.date,
                excerpt=_excerpt(view),
                source_title=view.source_title,
                locator=view.locator,
                verified_by_display=view.verified_by_display,
                score=score,
            )
            for score, view in scored[:MAX_MATCHES]
        ],
    )


def ask(actor: FamilyActor, session: Session, question: str) -> MemoryAnswer:
    """Adult heirs only. The question itself is not stored; the audit row records only the outcome."""
    require_role(actor, "adult_heir")
    answer = _answer(actor, session, question)
    reason = "answered" if answer.status == "answered" else "refused"
    audit.record(session, actor.ctx.external_user_id, actor.family.id, "memory.ask", "memory", None, True, reason)
    return answer
