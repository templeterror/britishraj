"""Advisor reads of insights and the forecasts behind them. Advisor only: heirs and parents get 403.

Every read re-checks consent: a goal-derived insight or forecast is visible only while the heir's goal
is still shared, and an insight only at the family's current consent revision.
"""

from typing import Literal, get_args

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.dto.advisor import FilterTag, InsightDTO, InsightType, ScenarioResultDTO
from app.heirloom.envelope import ApiError
from app.heirloom.models import INSIGHT_REVIEW_STATUSES, ForecastResult, ForecastScenario, Insight
from app.heirloom.services import audit, events, lookup
from app.heirloom.services.graph import record_ref
from app.heirloom.services.projection import Visibility
from app.heirloom.simulation import engine
from app.heirloom.simulation.engine import AssetTerms, ScenarioInput

ReviewStatus = Literal["reviewed", "dismissed"]
LISTED_STATUSES = tuple(s for s in INSIGHT_REVIEW_STATUSES if s != "invalidated")
FILTER_TAGS = get_args(FilterTag)
_TYPE_ORDER = get_args(InsightType)


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation_error", f"Invalid request: {message}")


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "Record not found.")


def _visible(vis: Visibility, insight: Insight) -> bool:
    """`Visibility.insight`, plus the defensive double check that a goal-derived insight is current."""
    if not vis.insight(insight):
        return False
    goal_derived = bool((insight.payload or {}).get("goal_ref"))
    return not goal_derived or insight.consent_revision == vis.family.consent_revision


def insight_dto(insight: Insight) -> InsightDTO:
    payload = insight.payload or {}
    return InsightDTO(
        id=str(insight.id),
        type=insight.type,
        insight_key=insight.insight_key,
        title=insight.title,
        summary=insight.advisor_safe_summary,
        why_now=payload.get("why_now", ""),
        known=list(payload.get("known", [])),
        conditional=list(payload.get("conditional", [])),
        contact=list(payload.get("contact", [])),
        headline_probability=payload.get("headline_probability"),
        headline_condition=payload.get("headline_condition", ""),
        scenario_rows=list(payload.get("scenario_rows", [])),
        evidence=list(payload.get("evidence", [])),
        filter_tags=list(insight.filter_tags or []),
        goal_ref=payload.get("goal_ref"),
        assumptions=dict(payload.get("assumptions", {})),
        review_status=insight.review_status,
        consent_revision=insight.consent_revision,
        created_at=insight.created_at,
    )


def list_for_advisor(
    actor: FamilyActor, session: Session, status: str | None, tag: str | None
) -> list[InsightDTO]:
    """The family's open insights (never `invalidated`), optionally by review status and filter tag."""
    require_role(actor, "advisor")
    if status is not None and status not in LISTED_STATUSES:
        raise _invalid(f"status must be one of {', '.join(LISTED_STATUSES)}")
    if tag is not None and tag not in FILTER_TAGS:
        raise _invalid(f"tag must be one of {', '.join(FILTER_TAGS)}")
    vis = Visibility(actor, session)
    rows = [
        row
        for row in session.scalars(
            select(Insight).where(
                Insight.family_id == actor.family.id, Insight.review_status != "invalidated"
            )
        )
        if _visible(vis, row)
        and status in (None, row.review_status)
        and (tag is None or tag in (row.filter_tags or []))
    ]
    rows.sort(key=lambda row: (_TYPE_ORDER.index(row.type), row.insight_key))
    return [insight_dto(row) for row in rows]


def get_visible(actor: FamilyActor, session: Session, insight_id: str) -> Insight:
    """The family's insight `insight_id` if this advisor may see it; 404 when unknown, withdrawn or unshared."""
    insight = lookup.family_record(session, actor, Insight, insight_id)
    if not _visible(Visibility(actor, session), insight):
        raise _not_found()
    return insight


def set_review(
    actor: FamilyActor, session: Session, insight_id: str, review_status: ReviewStatus
) -> InsightDTO:
    require_role(actor, "advisor")
    insight = get_visible(actor, session, insight_id)
    insight.review_status = review_status
    ref = record_ref(insight)
    audit.record(
        session,
        actor.ctx.external_user_id,
        actor.family.id,
        "insight.review",
        "insight",
        ref,
        True,
        review_status,
    )
    events.emit(
        session,
        actor.family,
        "insight.reviewed.v1",
        ref,
        {"insight_key": insight.insight_key, "review_status": review_status},
    )
    return insight_dto(insight)


def _forecast_dto(scenario: ForecastScenario, result: ForecastResult) -> ScenarioResultDTO:
    settings = dict(scenario.settings)
    run_input = ScenarioInput(**{**settings, "terms": AssetTerms(**settings["terms"])})
    proceeds, metrics = result.accessible_proceeds, result.goal_shortfall_metrics
    return ScenarioResultDTO(
        value_nominal=result.percentiles["value_nominal"],
        value_real=result.percentiles["value_real"],
        cash_by_year=proceeds["cash_by_year"],
        cash_at_goal=proceeds["cash_at_goal"],
        goal_nominal=metrics["goal_nominal"],
        p_cash_covers_goal=metrics["p_cash_covers_goal"],
        shortfall_share=metrics["shortfall_share"],
        sale_completion_year=proceeds["sale_completion_year"],
        transfer_after_goal=metrics["transfer_after_goal"],
        admin_cost_at_transfer_p50=proceeds["admin_cost_at_transfer_p50"],
        limitations=list(result.limitations),
        seed=scenario.seed,
        model_version=scenario.model_version,
        input_hash=engine.input_hash(run_input),
        settings=settings,
        computed_at=result.computed_at,
    )


def forecast_for_advisor(actor: FamilyActor, session: Session, scenario_id: str) -> ScenarioResultDTO:
    """One stored forecast. 404 when unknown, or when its heir goal is no longer shared."""
    require_role(actor, "advisor")
    try:
        scenario = lookup.family_record(session, actor, ForecastScenario, scenario_id)
    except ApiError:
        scenario = None
    allowed = scenario is not None and Visibility(actor, session).forecast(scenario)
    audit.record(
        session,
        actor.ctx.external_user_id,
        actor.family.id,
        "forecast.read",
        "forecast",
        scenario_id[:200],
        allowed,
        "allowed" if allowed else "not_visible",
    )
    result = None
    if allowed:
        result = session.scalars(
            select(ForecastResult).where(ForecastResult.scenario_id == scenario.id)
        ).first()
    if result is None:
        session.commit()  # keep the denial: the request-scoped session rolls back on error
        raise _not_found()
    return _forecast_dto(scenario, result)
