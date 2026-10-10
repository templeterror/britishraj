"""Consent grants. Task 6 implements grants; this module already owns advisor goal visibility.

`goal_view_for_advisor` is the single gate every advisor-facing read (snapshot, graph projection,
evidence, readiness) goes through to see an heir goal. Callers use it as
`consent.goal_view_for_advisor(...)` so its body can change without touching them.
"""

from sqlalchemy.orm import Session

from app.heirloom.dto.advisor import AdvisorGoalDetail, AdvisorGoalSummary
from app.heirloom.models import Family, HeirGoal


def goal_view_for_advisor(
    session: Session, family: Family, goal: HeirGoal
) -> AdvisorGoalSummary | AdvisorGoalDetail | None:
    """What the family advisor may see of `goal`, or None when the heir has not shared it.

    No grants can exist before Task 6, so every goal is private.
    """
    return None
