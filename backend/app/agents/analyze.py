"""Write an alignment report from the slices triage kept."""

from __future__ import annotations

import json

from app.agents.catalog import TaskModels
from app.agents.client import ChatClient, json_schema
from app.agents.schemas import CallRecord, IntakeBrief, SliceName
from app.agents.triage import record
from app.market.reduce import source_urls
from app.market.schemas import (
    AlignmentReport,
    CompSet,
    HomeEvidence,
    LiquidityFacts,
    MarketEvidence,
)
from app.market.validate import CitationError, validate_report

ANALYST_INSTRUCTIONS = (
    "Write an alignment report from the need, the facts, and the evidence. "
    "The heir's words were already read. Do not expect them again. "
    "Every discrepancy needs evidence ids from allowed_evidence_ids. "
    "source_urls and any url in the text must be copied from allowed_source_urls. "
    "Do not recommend a purchase or a sale. "
    "gap_usd is how far cash_reachable falls short of need.amount_usd."
)

OMITTED_HOME = "omitted:home"
OMITTED_COMPS = "omitted:comps"


def allowed_ids(evidence: MarketEvidence, slices: set[str]) -> set[str]:
    ids: set[str] = set()
    if "quotes" in slices:
        ids.update(quote.id for quote in evidence.quotes)
    if "home" in slices:
        ids.add(evidence.home.id)
    if "comps" in slices:
        ids.add(evidence.comps.id)
        ids.update(listing.id for listing in evidence.comps.listings)
    if "funding" in slices:
        ids.update(company.id for company in evidence.funding)
    return ids


def visible_evidence(evidence: MarketEvidence, slices: set[str]) -> MarketEvidence:
    quotes = evidence.quotes if "quotes" in slices else []
    funding = evidence.funding if "funding" in slices else []
    home = evidence.home if "home" in slices else HomeEvidence(id=OMITTED_HOME, home_status="not_found")
    comps = (
        evidence.comps
        if "comps" in slices
        else CompSet(id=OMITTED_COMPS, postal_code=evidence.comps.postal_code)
    )
    parts = {"quotes": quotes, "home": home, "comps": comps, "funding": funding}
    return MarketEvidence(
        family_slug=evidence.family_slug,
        quotes=quotes,
        home=home,
        comps=comps,
        funding=funding,
        source_urls=source_urls(parts),
    )


def prompt_packet(evidence: MarketEvidence, slices: set[str]) -> dict:
    packet: dict = {}
    if "quotes" in slices:
        packet["quotes"] = [quote.model_dump(mode="json") for quote in evidence.quotes]
    if "home" in slices:
        packet["home"] = evidence.home.model_dump(mode="json")
    if "comps" in slices:
        packet["comps"] = evidence.comps.model_dump(mode="json")
    if "funding" in slices:
        packet["funding"] = [company.model_dump(mode="json") for company in evidence.funding]
    visible = visible_evidence(evidence, slices)
    packet["allowed_evidence_ids"] = sorted(allowed_ids(evidence, slices))
    packet["allowed_source_urls"] = list(visible.source_urls)
    return packet


def check_report(report: AlignmentReport, evidence: MarketEvidence, slices: set[str]) -> None:
    validate_report(report, visible_evidence(evidence, slices))
    allowed = allowed_ids(evidence, slices)
    for item in report.discrepancies:
        unknown = [evidence_id for evidence_id in item.evidence_ids if evidence_id not in allowed]
        if unknown:
            raise CitationError(f"unknown evidence ids: {', '.join(unknown)}")


def facts_for_analyst(facts: LiquidityFacts, slices: set[str]) -> dict:
    payload = facts.model_dump(mode="json")
    if "quotes" not in slices:
        return payload
    trimmed = []
    for position in payload["positions"]:
        trimmed.append(
            {
                "ticker": position["ticker"],
                "quantity": position["quantity"],
                "book_price": position["book_price"],
                "book_price_as_of": position["book_price_as_of"],
            }
        )
    payload["positions"] = trimmed
    return payload


def analyze(
    client: ChatClient,
    tasks: TaskModels,
    brief: IntakeBrief,
    facts: LiquidityFacts,
    evidence: MarketEvidence,
    slices: list[SliceName],
    calls: list[CallRecord],
) -> AlignmentReport:
    kept = set(slices)
    user = {
        "need": {
            "amount_usd": brief.amount_usd,
            "horizon": brief.horizon,
            "intent": brief.intent,
            "decisions": brief.decisions,
        },
        "facts": facts_for_analyst(facts, kept),
        "evidence": prompt_packet(evidence, kept),
    }
    messages: list[dict[str, str]] = [
        {"role": "system", "content": ANALYST_INSTRUCTIONS},
        {"role": "user", "content": json.dumps(user)},
    ]
    schema = json_schema(AlignmentReport)
    report = _once(client, tasks, tasks.analyst_effort, messages, schema, calls)
    try:
        check_report(report, evidence, kept)
    except CitationError as error:
        messages = [
            *messages,
            {"role": "assistant", "content": report.model_dump_json()},
            {
                "role": "user",
                "content": (
                    f"The report was rejected: {error}. "
                    "Cite only allowed_evidence_ids and allowed_source_urls. Return the report again."
                ),
            },
        ]
        report = _once(client, tasks, tasks.analyst_effort, messages, schema, calls)
        check_report(report, evidence, kept)
    return report


def _once(
    client: ChatClient,
    tasks: TaskModels,
    effort: str,
    messages: list[dict[str, str]],
    schema: dict,
    calls: list[CallRecord],
) -> AlignmentReport:
    completion = client.complete(
        task="analyst",
        model=tasks.analyst_model,
        effort=effort,
        messages=messages,
        schema_name="alignment_report",
        schema=schema,
    )
    calls.append(record("analyst", completion))
    return AlignmentReport.model_validate_json(completion.text)
