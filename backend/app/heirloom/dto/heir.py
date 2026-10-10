from datetime import date

from app.heirloom.dto.common import PersonRef, StrictModel


class HeirFamily(StrictModel):
    id: str
    display_name: str


class AdvisorName(StrictModel):
    display_name: str


class HeirGoalView(StrictModel):
    goal_id: str
    ref: str | None
    goal_kind: str
    description_private: str
    amount_target: int | None
    target_year: int | None
    horizon_min_years: int | None
    horizon_max_years: int | None
    milestone: str | None
    goal_funding_source: str
    version: int


class HeirSharing(StrictModel):
    advisor_summary: bool
    advisor_detail: bool


class HeirDecisionView(StrictModel):
    """A decision the parent approved for this heir: no asset value or label, only a generic kind."""

    decision_id: str
    date: date
    title: str
    rationale: str | None
    source_title: str | None
    locator: dict | None
    verified_by_display: str | None
    asset_kind: str | None


class InvitationView(StrictModel):
    from_display: str
    text: str
    status: str


class HeirSnapshot(StrictModel):
    family: HeirFamily
    me: PersonRef
    advisor: AdvisorName
    my_goals: list[HeirGoalView]
    sharing: HeirSharing
    approved_decisions: list[HeirDecisionView]
    invitations: list[InvitationView]
    planning_prompts: list[str]
