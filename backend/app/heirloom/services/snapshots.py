"""One snapshot per audience. Each returns its own DTO, so disallowed fields are absent, not masked.

Heir goals reach the advisor only through `consent.goal_view_for_advisor`; parent decisions reach an
heir only through `heir_approved_decisions`. Both are the single source for every such read.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor
from app.heirloom.dto.advisor import (
    AdvisorAssetDTO,
    AdvisorGoalDetail,
    AdvisorSnapshot,
    CoverageDTO,
    InstrumentDTO,
    MarketEventDTO,
)
from app.heirloom.dto.common import (
    AssetDTO,
    AssetTerms,
    DecisionDTO,
    FamilyDTO,
    IntentDTO,
    PersonDTO,
    PersonRef,
)
from app.heirloom.dto.heir import (
    AdvisorName,
    HeirDecisionView,
    HeirFamily,
    HeirGoalView,
    HeirSharing,
    HeirSnapshot,
)
from app.heirloom.dto.parent import HeirRef, ParentDecisionDTO, ParentSharing, ParentSnapshot
from app.heirloom.models import (
    Asset,
    DecisionRecord,
    Family,
    FamilyPerson,
    HeirGoal,
    Insight,
    LegalInstrument,
    MarketEvent,
    SourceDocument,
    TransferIntent,
)
from app.heirloom.services import consent
from app.heirloom.services.evidence import read_source_text
from app.heirloom.services.graph import is_current_verified_intent, record_ref
from app.heirloom.services.projection import Visibility

PLANNING_PROMPTS = [
    "What would you want to have in place before your next milestone?",
    "Which parts of your plan could you fund on your own, and where would advice help?",
    "What would you like to talk through with your family's advisor?",
]
OPEN_INSIGHT_STATUSES = ("new", "reviewed")


def heir_approved_decisions(
    session: Session, family: Family, heir_person: FamilyPerson
) -> list[HeirDecisionView]:
    """Verified decisions the parent shared with this heir, one `decision_excerpt` grant each.

    No grants can exist before Task 6, so nothing is shared yet.
    """
    return []


@dataclass
class _Family:
    """The family's rows, loaded once per snapshot."""

    family: Family
    people: dict[UUID, FamilyPerson]
    assets: dict[UUID, Asset]
    instruments: dict[UUID, LegalInstrument]
    sources: dict[UUID, SourceDocument]

    @classmethod
    def load(cls, session: Session, family: Family) -> "_Family":
        def rows(model, *order):
            query = select(model).where(model.family_id == family.id).order_by(*order, model.id)
            return {row.id: row for row in session.scalars(query)}

        return cls(
            family=family,
            people=rows(FamilyPerson, FamilyPerson.display_name),
            assets=rows(Asset, Asset.external_ref),
            instruments=rows(LegalInstrument, LegalInstrument.effective_date),
            sources=rows(SourceDocument),
        )

    def name(self, person_id: UUID | None) -> str | None:
        person = self.people.get(person_id)
        return person.display_name if person else None

    def ref(self, rows: dict, row_id: UUID | None) -> str | None:
        row = rows.get(row_id)
        return record_ref(row) if row else None


def _family_dto(family: Family) -> FamilyDTO:
    return FamilyDTO(id=str(family.id), display_name=family.display_name, as_of_year=family.as_of_year)


def _person_ref(person: FamilyPerson) -> PersonRef:
    return PersonRef(id=str(person.id), display_name=person.display_name, role=person.family_role)


def _asset(asset: Asset, cls=AssetDTO, **extra) -> AssetDTO:
    return cls(
        id=str(asset.id),
        ref=asset.external_ref,
        label=asset.label,
        asset_kind=asset.asset_type,
        liquidity_class=asset.liquidity_class,
        currency=asset.currency,
        as_of_date=asset.as_of_date,
        value=asset.estimated_value,
        liabilities=asset.liabilities,
        verified_status=asset.verified_status,
        terms=AssetTerms(**(asset.terms or {})),
        **extra,
    )


def _intent(intent: TransferIntent, f: _Family) -> IntentDTO:
    instrument = f.instruments.get(intent.instrument_id)
    return IntentDTO(
        id=str(intent.id),
        ref=intent.external_ref,
        instrument_ref=f.ref(f.instruments, intent.instrument_id),
        asset_ref=f.ref(f.assets, intent.asset_id),
        beneficiary_id=str(intent.beneficiary_person_id),
        beneficiary_display_name=f.name(intent.beneficiary_person_id) or "",
        allocation=intent.allocation_description,
        conditions=list(intent.conditions or []),
        status=intent.status,
        advisor_verified=intent.advisor_verified,
        verified_by_display=f.name(intent.verified_by),
        verification_notes=intent.verification_notes,
        confidence=intent.confidence,
        valid_from=intent.valid_from,
        valid_to=intent.valid_to,
        counsel_reviewed_at=instrument.counsel_reviewed_at if instrument else None,
    )


def _decision(decision: DecisionRecord, f: _Family, cls=DecisionDTO, **extra) -> DecisionDTO:
    source = f.sources.get(decision.source_document_id)
    return cls(
        id=str(decision.id),
        ref=decision.external_ref,
        decision_date=decision.decision_date,
        asset_ref=f.ref(f.assets, decision.asset_id),
        action=decision.action_text,
        rationale=decision.rationale_text,
        alternatives=list(decision.alternatives or []),
        verification_status=decision.verification_status,
        rationale_edited=decision.rationale_edited,
        advisor_note=decision.advisor_note,
        valid_to=decision.valid_to,
        confidence=decision.extraction_confidence,
        source_title=source.title if source else None,
        locator=dict(decision.source_locator or {}) or None,
        verified_by_display=f.name(decision.verified_by),
        **extra,
    )


def _instrument(instrument: LegalInstrument, f: _Family) -> InstrumentDTO:
    source = f.sources.get(instrument.source_document_id)
    return InstrumentDTO(
        id=str(instrument.id),
        ref=instrument.external_ref,
        title=instrument.title,
        kind=instrument.instrument_type,
        status=instrument.status,
        effective_date=instrument.effective_date,
        revocable=instrument.revocable,
        counsel_reviewed_at=instrument.counsel_reviewed_at,
        source_title=source.title if source else None,
        source_excerpt=read_source_text(source),
        source_version=source.revision if source else None,
    )


def intent_dto(session: Session, family: Family, intent: TransferIntent) -> IntentDTO:
    """One intent as the advisor and parent snapshots show it."""
    return _intent(intent, _Family.load(session, family))


def decision_dto(session: Session, family: Family, decision: DecisionRecord) -> DecisionDTO:
    return _decision(decision, _Family.load(session, family))


def instrument_dto(session: Session, family: Family, instrument: LegalInstrument) -> InstrumentDTO:
    return _instrument(instrument, _Family.load(session, family))


def _family_rows(session: Session, model, family: Family, *order) -> list:
    return list(session.scalars(select(model).where(model.family_id == family.id).order_by(*order, model.id)))


def _advisor(actor: FamilyActor, session: Session) -> AdvisorSnapshot:
    family = actor.family
    f = _Family.load(session, family)
    intents = _family_rows(session, TransferIntent, family, TransferIntent.valid_from)
    decisions = _family_rows(session, DecisionRecord, family, DecisionRecord.decision_date)
    goals = _family_rows(session, HeirGoal, family, HeirGoal.external_ref)

    shared = [(goal, view) for goal in goals if (view := consent.goal_view_for_advisor(session, family, goal))]
    if any(isinstance(view, AdvisorGoalDetail) for _, view in shared):
        goal_sharing = "detail"
    else:
        goal_sharing = "summary" if shared else "not_shared"

    events_by_asset: dict[UUID, list[MarketEventDTO]] = {}
    for event in _family_rows(session, MarketEvent, family, MarketEvent.published_at):
        events_by_asset.setdefault(event.asset_id, []).append(
            MarketEventDTO(
                title=event.title,
                url=event.url,
                published_at=event.published_at,
                proposed_stress=event.proposed_stress,
            )
        )

    vis = Visibility(actor, session)
    open_flags = sum(
        1
        for insight in _family_rows(session, Insight, family)
        if insight.review_status in OPEN_INSIGHT_STATUSES and vis.insight(insight)
    )
    coverage = CoverageDTO(
        decisions_verified=sum(d.verification_status == "verified" for d in decisions),
        decisions_total=sum(d.verification_status != "rejected" for d in decisions),
        assets_with_verified_intent=len(
            {t.asset_id for t in intents if is_current_verified_intent(t, f.instruments.get(t.instrument_id))}
        ),
        assets_total=len(f.assets),
        heirs_connected=len({goal.heir_person_id for goal, _ in shared}),
        heirs_total=sum(p.family_role == "adult_heir" for p in f.people.values()),
    )
    return AdvisorSnapshot(
        family=_family_dto(family),
        advisor=_person_ref(actor.person),
        people=[
            PersonDTO(
                id=str(p.id), ref=p.external_ref, display_name=p.display_name, role=p.family_role, age=p.age
            )
            for p in f.people.values()
        ],
        assets=[
            _asset(a, AdvisorAssetDTO, market_events=events_by_asset.get(a.id, [])) for a in f.assets.values()
        ],
        instruments=[_instrument(i, f) for i in f.instruments.values()],
        intents=[_intent(t, f) for t in intents],
        decisions=[_decision(d, f) for d in decisions],
        goal_sharing=goal_sharing,
        shared_goals=[view for _, view in shared],
        coverage=coverage,
        open_flags=open_flags,
    )


def _parent(actor: FamilyActor, session: Session) -> ParentSnapshot:
    family, me = actor.family, actor.person
    f = _Family.load(session, family)
    own_assets = [a for a in f.assets.values() if a.owner_person_id == me.id]
    own_asset_ids = {a.id for a in own_assets}
    intents = [
        t
        for t in _family_rows(session, TransferIntent, family, TransferIntent.valid_from)
        if t.asset_id in own_asset_ids
    ]
    decisions = [
        d
        for d in _family_rows(session, DecisionRecord, family, DecisionRecord.decision_date)
        if d.person_id == me.id
    ]
    heirs = [p for p in f.people.values() if p.family_role == "adult_heir"]
    shared_ids = {v.decision_id for heir in heirs for v in heir_approved_decisions(session, family, heir)}
    return ParentSnapshot(
        family=_family_dto(family),
        me=_person_ref(me),
        assets=[_asset(a) for a in own_assets],
        decisions=[
            _decision(d, f, ParentDecisionDTO, shared_with_heir=str(d.id) in shared_ids) for d in decisions
        ],
        intents=[_intent(t, f) for t in intents],
        preserve_values=list(family.preserve_values or []),
        heirs=[HeirRef(person_id=str(h.id), display_name=h.display_name) for h in heirs],
        sharing=ParentSharing(decision_excerpts=sum(str(d.id) in shared_ids for d in decisions)),
    )


def _heir(actor: FamilyActor, session: Session) -> HeirSnapshot:
    family, me = actor.family, actor.person
    goals = [
        g for g in _family_rows(session, HeirGoal, family, HeirGoal.external_ref) if g.heir_person_id == me.id
    ]
    views = [view for g in goals if (view := consent.goal_view_for_advisor(session, family, g))]
    advisor = session.scalars(
        select(FamilyPerson)
        .where(FamilyPerson.family_id == family.id, FamilyPerson.family_role == "advisor")
        .order_by(FamilyPerson.display_name)
    ).first()
    return HeirSnapshot(
        family=HeirFamily(id=str(family.id), display_name=family.display_name),
        me=_person_ref(me),
        advisor=AdvisorName(display_name=advisor.display_name if advisor else "Your family's advisor"),
        my_goals=[
            HeirGoalView(
                goal_id=str(g.id),
                ref=g.external_ref,
                goal_kind=g.goal_kind,
                description_private=g.description_private,
                amount_target=g.amount_target,
                target_year=g.target_year,
                horizon_min_years=g.horizon_min_years,
                horizon_max_years=g.horizon_max_years,
                milestone=g.milestone,
                goal_funding_source=g.goal_funding_source,
                version=g.version,
            )
            for g in goals
        ],
        sharing=HeirSharing(
            advisor_summary=bool(views),
            advisor_detail=any(isinstance(v, AdvisorGoalDetail) for v in views),
        ),
        approved_decisions=heir_approved_decisions(session, family, me),
        invitations=[],  # Task 9: approved heir_intro actions
        planning_prompts=list(PLANNING_PROMPTS),
    )


def build(actor: FamilyActor, session: Session) -> AdvisorSnapshot | ParentSnapshot | HeirSnapshot:
    match actor.role:
        case "advisor":
            return _advisor(actor, session)
        case "parent":
            return _parent(actor, session)
        case "adult_heir":
            return _heir(actor, session)
    raise ValueError(f"no snapshot for role {actor.role!r}")
