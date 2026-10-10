"""Build the family knowledge graph from SQL (the source of truth) and store it.

The stored graph is the full advisor-level picture; per-audience filtering happens in
`services.projection`. Rebuilds are deterministic: the same SQL rows always give the same graph.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.graph.factory import get_graph_repo
from app.heirloom.graph.repository import GEdge, GNode
from app.heirloom.models import (
    Asset,
    DecisionRecord,
    DomainEvent,
    Family,
    FamilyPerson,
    ForecastScenario,
    HeirGoal,
    Insight,
    LegalInstrument,
    TransferIntent,
)
from app.heirloom.services import events

REF_PREFIX = {
    FamilyPerson: "person",
    Asset: "asset",
    LegalInstrument: "instr",
    TransferIntent: "intent",
    DecisionRecord: "decision",
    HeirGoal: "goal",
    ForecastScenario: "forecast",
    Insight: "insight",
}

_INTENT_STATUS = {"proposed": "candidate", "verified": "verified", "superseded": "superseded", "contested": "contested"}
_INSTRUMENT_STATUS = {"draft": "candidate", "reported": "candidate", "verified": "verified", "superseded": "superseded"}
_ASSET_STATUS = {"verified": "verified", "reported": "candidate"}


def record_ref(row) -> str:
    """The graph/evidence id of a row: its business ref, or `<prefix>-<uuid>` when it has none."""
    return getattr(row, "external_ref", None) or f"{REF_PREFIX[type(row)]}-{row.id}"


def restriction_ref(asset: Asset) -> str:
    return f"restriction-{record_ref(asset)}"


def has_restriction(asset: Asset) -> bool:
    terms = asset.terms or {}
    fraction = terms.get("liquidatable_fraction")
    return terms.get("partner_consent_required") is True or (fraction is not None and fraction < 1)


def is_current_verified_intent(intent: TransferIntent, instrument: LegalInstrument | None) -> bool:
    """The only intents that earn an `INTENDED_FOR` edge (still a revocable intent, never ownership)."""
    return (
        intent.status == "verified"
        and instrument is not None
        and instrument.status == "verified"
        and intent.valid_to is None
    )


def _rows(session: Session, model, family: Family) -> list:
    return list(session.scalars(select(model).where(model.family_id == family.id).order_by(model.id)))


def restriction_label(asset: Asset) -> str:
    terms = asset.terms or {}
    parts = []
    if terms.get("partner_consent_required") is True:
        parts.append("Partner consent required")
    fraction = terms.get("liquidatable_fraction")
    if fraction is not None and fraction < 1:
        parts.append(f"{round(fraction * 100)}% liquidatable")
    return "; ".join(parts)


def _forecast_label(scenario: ForecastScenario) -> str:
    year = (scenario.settings or {}).get("transfer_year")
    if year is None:
        return "Illustrative forecast"
    return f"Illustrative: if transfer were to occur in year {year}"


def build_family_graph(session: Session, family: Family) -> tuple[list[GNode], list[GEdge]]:
    nodes: list[GNode] = []
    edges: list[GEdge] = []

    def node(row, kind, label, classification, evidence_status, valid_from=None, valid_to=None, **props):
        ref = record_ref(row)
        nodes.append(
            GNode(
                record_id=ref,
                label=label,
                kind=kind,
                classification=classification,
                valid_from=valid_from,
                valid_to=valid_to,
                evidence_status=evidence_status,
                props=props,
            )
        )
        return ref

    def edge(type_, source, target, classification, valid_from=None, valid_to=None) -> None:
        edges.append(
            GEdge(
                type=type_,
                source_id=source,
                target_id=target,
                valid_from=valid_from,
                valid_to=valid_to,
                classification=classification,
            )
        )

    people = {p.id: p for p in _rows(session, FamilyPerson, family)}
    for person in people.values():
        node(person, "person", person.display_name, "family_member", "verified", role=person.family_role)

    assets = {a.id: a for a in _rows(session, Asset, family)}
    for asset in assets.values():
        status = _ASSET_STATUS[asset.verified_status]
        ref = node(
            asset,
            "asset",
            asset.label,
            "internal_parent_advisor",
            status,
            asset_type=asset.asset_type,
            liquidity_class=asset.liquidity_class,
        )
        owner = people.get(asset.owner_person_id)
        # An heir never owns a parent's asset in this graph: intent is not ownership.
        if owner is not None and owner.family_role != "adult_heir":
            edge("OWNS", record_ref(owner), ref, "internal_parent_advisor")
        if has_restriction(asset):
            terms = asset.terms or {}
            nodes.append(
                GNode(
                    record_id=restriction_ref(asset),
                    label=restriction_label(asset),
                    kind="restriction",
                    classification="internal_parent_advisor",
                    evidence_status=status,
                    props={
                        "asset_ref": ref,
                        "partner_consent_required": terms.get("partner_consent_required"),
                        "liquidatable_fraction": terms.get("liquidatable_fraction"),
                        "sale_delay_years": terms.get("sale_delay_years"),
                    },
                )
            )
            edge("HAS_RESTRICTION", ref, restriction_ref(asset), "internal_parent_advisor")

    instruments = {i.id: i for i in _rows(session, LegalInstrument, family)}
    intents = _rows(session, TransferIntent, family)
    for instrument in instruments.values():
        ended = [t.valid_to for t in intents if t.instrument_id == instrument.id and t.valid_to]
        node(
            instrument,
            "instrument",
            instrument.title,
            "internal_parent_advisor",
            _INSTRUMENT_STATUS[instrument.status],
            valid_from=instrument.effective_date,
            valid_to=max(ended) if instrument.status == "superseded" and ended else None,
            instrument_type=instrument.instrument_type,
            status=instrument.status,
            revocable=instrument.revocable,
        )

    for intent in intents:
        instrument = instruments.get(intent.instrument_id)
        asset = assets[intent.asset_id]
        beneficiary = people[intent.beneficiary_person_id]
        dates = {"valid_from": intent.valid_from, "valid_to": intent.valid_to}
        ref = node(
            intent,
            "intent",
            intent.allocation_description,
            "internal_parent_advisor",
            _INTENT_STATUS[intent.status],
            **dates,
            status=intent.status,
            advisor_verified=intent.advisor_verified,
            confidence=intent.confidence,
            asset_ref=record_ref(asset),
            beneficiary_ref=record_ref(beneficiary),
        )
        if instrument is not None:
            edge("DOCUMENTS", record_ref(instrument), ref, "internal_parent_advisor")
        edge("REFERS_TO", ref, record_ref(asset), "internal_parent_advisor", **dates)
        if is_current_verified_intent(intent, instrument):
            edge("INTENDED_FOR", ref, record_ref(beneficiary), "internal_parent_advisor", **dates)

    for decision in _rows(session, DecisionRecord, family):
        if decision.verification_status == "rejected":
            continue
        dates = {"valid_from": decision.valid_from, "valid_to": decision.valid_to}
        ref = node(
            decision,
            "decision",
            decision.action_text,
            "internal_parent_advisor",
            decision.verification_status,
            **dates,
            decision_date=decision.decision_date.isoformat(),
            asset_ref=record_ref(assets[decision.asset_id]),
        )
        edge("CONCERNS", ref, record_ref(assets[decision.asset_id]), "internal_parent_advisor", **dates)
        reviewer = people.get(decision.verified_by)
        if decision.verification_status == "verified" and reviewer is not None:
            edge("REVIEWED_BY", ref, record_ref(reviewer), "internal_parent_advisor")

    goals = {g.id: g for g in _rows(session, HeirGoal, family)}
    for goal in goals.values():
        label = f"{goal.goal_kind.replace('_', ' ').capitalize()} goal"
        ref = node(goal, "goal", label, "private_heir", "verified", goal_kind=goal.goal_kind)
        edge("STATED", record_ref(people[goal.heir_person_id]), ref, "private_heir")

    for scenario in _rows(session, ForecastScenario, family):
        ref = node(
            scenario,
            "forecast",
            _forecast_label(scenario),
            "advisor_only",
            "unknown",
            model_version=scenario.model_version,
            seed=scenario.seed,
            settings=dict(scenario.settings or {}),
        )
        edge("MODELS", ref, record_ref(assets[scenario.asset_id]), "advisor_only")
        if scenario.goal_id in goals:
            edge("TESTS", ref, record_ref(goals[scenario.goal_id]), "advisor_only")

    supported: list[tuple[str, list[str]]] = []
    for insight in _rows(session, Insight, family):
        if insight.review_status == "invalidated":
            continue
        ref = node(
            insight,
            "insight",
            insight.title,
            "advisor_only",
            "unknown",
            type=insight.type,
            review_status=insight.review_status,
            filter_tags=list(insight.filter_tags or []),
        )
        evidence = (insight.payload or {}).get("evidence") or []
        supported.append((ref, [item["ref"] for item in evidence if isinstance(item, dict) and "ref" in item]))

    ids = {n.record_id for n in nodes}
    for ref, targets in supported:
        for target in targets:
            if target in ids:
                edge("SUPPORTED_BY", ref, target, "advisor_only")

    unique_edges = {e.key: e for e in edges if e.source_id in ids and e.target_id in ids}
    return sorted(nodes, key=lambda n: n.record_id), sorted(unique_edges.values(), key=lambda e: e.key)


def rebuild_family_graph(session: Session, family: Family) -> None:
    nodes, edges = build_family_graph(session, family)
    repo, _degraded = get_graph_repo()
    repo.replace_family(family.organization_id, family.id, nodes, edges)


def _on_event(session: Session, family: Family, _event: DomainEvent) -> None:
    rebuild_family_graph(session, family)


def register_handlers() -> None:
    """Rebuild on every domain event. Idempotent (`events.register` ignores duplicates)."""
    events.register("*", _on_event)


def family_records(session: Session, family: Family) -> dict[tuple[type, str], object]:
    """Every graph-backed SQL row of the family, by (model, record ref)."""
    return {(model, record_ref(row)): row for model in REF_PREFIX for row in _rows(session, model, family)}


def find_record(session: Session, family: Family, ref: str, models: tuple[type, ...]):
    """The family's row of one of `models` whose record ref is `ref`, or None."""
    for model in models:
        if hasattr(model, "external_ref"):
            row = session.scalars(
                select(model).where(model.family_id == family.id, model.external_ref == ref)
            ).first()
            if row is not None:
                return row
        prefix, _, raw_id = ref.partition("-")
        if prefix != REF_PREFIX[model]:
            continue
        try:
            row = session.get(model, UUID(raw_id))
        except ValueError:
            continue
        if row is not None and row.family_id == family.id and record_ref(row) == ref:
            return row
    return None
