"""The analyst explains each check in plain words and judges the parent's notes.

It reads the brief, the liquidity facts, the evidence slices the goal
needs, and the tree whose outcomes code already computed. It may not
change a computed outcome. It resolves pending nodes, cites only ids and
URLs from the packet, and never recommends a purchase or a sale.
"""

from __future__ import annotations

import json

from app.agents.catalog import TaskModels
from app.agents.checks import cover, score
from app.agents.client import ChatClient, json_schema
from app.agents.intake import record
from app.agents.schemas import AnalystReply, CallRecord, DecisionTree, GoalBrief
from app.market.reduce import source_urls
from app.market.schemas import (
    AlignmentReport,
    CompSet,
    Discrepancy,
    HomeEvidence,
    LiquidityFacts,
    MarketEvidence,
)
from app.market.validate import URL_RE, CitationError

ANALYST_INSTRUCTIONS = (
    "You explain a goal-alignment check to a wealth manager. "
    "The heir's words were already read and reduced to need. Do not expect them. "
    "tree lists every check with an outcome that code computed from the numbers. You may not change "
    "an outcome of aligned, misaligned, gap, or skipped. "
    "Return one finding for every node whose outcome is not skipped: two or three plain sentences that say "
    "what the numbers mean for this heir, citing evidence ids from allowed_evidence_ids. "
    "For every node whose outcome is pending, return a judgment: read need.decisions against need.intent "
    "and decide aligned or misaligned, with a severity when misaligned, citing the note ids. "
    "verdict is a short paragraph for the manager. meeting_agenda is three to five items the family should talk through. "
    "source_urls and any url in your text must come from allowed_source_urls. "
    "Never recommend buying or selling anything."
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
    comps = evidence.comps if "comps" in slices else CompSet(id=OMITTED_COMPS, postal_code=evidence.comps.postal_code)
    parts = {"quotes": quotes, "home": home, "comps": comps, "funding": funding}
    return MarketEvidence(
        family_slug=evidence.family_slug,
        quotes=quotes,
        home=home,
        comps=comps,
        funding=funding,
        source_urls=source_urls(parts),
    )


def evidence_packet(evidence: MarketEvidence, slices: set[str]) -> dict:
    packet: dict = {}
    if "quotes" in slices:
        packet["quotes"] = [quote.model_dump(mode="json") for quote in evidence.quotes]
    if "home" in slices:
        packet["home"] = evidence.home.model_dump(mode="json")
    if "comps" in slices:
        packet["comps"] = evidence.comps.model_dump(mode="json")
    if "funding" in slices:
        packet["funding"] = [company.model_dump(mode="json") for company in evidence.funding]
    return packet


def facts_packet(facts: LiquidityFacts, slices: set[str]) -> dict:
    payload = facts.model_dump(mode="json")
    if "quotes" not in slices:
        return payload
    payload["positions"] = [
        {
            "ticker": position["ticker"],
            "quantity": position["quantity"],
            "book_price": position["book_price"],
            "book_price_as_of": position["book_price_as_of"],
        }
        for position in payload["positions"]
    ]
    return payload


def need_packet(brief: GoalBrief) -> dict:
    return {
        "intent": brief.intent,
        "amount_usd": brief.amount_usd,
        "amount_is_estimate": brief.amount_is_estimate,
        "horizon_months": brief.horizon_months,
        "purpose": brief.purpose,
        "must_be_reachable": brief.must_be_reachable,
        "exclusions": brief.exclusions,
        "decisions": [{"id": f"note:{index}", "text": text} for index, text in enumerate(brief.decisions, start=1)],
        "missing": brief.missing,
    }


def tree_packet(tree: DecisionTree) -> list[dict]:
    return [
        {
            "id": node.id,
            "title": node.title,
            "outcome": node.outcome,
            "severity": node.severity,
            "detail": node.detail,
            "evidence_ids": node.evidence_ids,
        }
        for node in tree.nodes()
    ]


def note_ids(brief: GoalBrief) -> set[str]:
    return {f"note:{index}" for index in range(1, len(brief.decisions) + 1)}


def packet(brief: GoalBrief, facts: LiquidityFacts, evidence: MarketEvidence, tree: DecisionTree) -> dict:
    kept = set(brief.slices)
    visible = visible_evidence(evidence, kept)
    return {
        "need": need_packet(brief),
        "facts": facts_packet(facts, kept),
        "evidence": evidence_packet(evidence, kept),
        "tree": tree_packet(tree),
        "allowed_evidence_ids": sorted(allowed_ids(evidence, kept) | note_ids(brief)),
        "allowed_source_urls": list(visible.source_urls),
    }


def check_reply(reply: AnalystReply, tree: DecisionTree, brief: GoalBrief, evidence: MarketEvidence) -> None:
    kept = set(brief.slices)
    allowed = allowed_ids(evidence, kept) | note_ids(brief)
    allowed_urls = set(visible_evidence(evidence, kept).source_urls)
    nodes = {node.id: node for node in tree.nodes()}
    findings = {item.node_id: item for item in reply.findings}
    judgments = {item.node_id: item for item in reply.judgments}
    for node in nodes.values():
        if node.outcome == "skipped":
            continue
        if node.outcome == "pending":
            judgment = judgments.get(node.id)
            if judgment is None:
                raise CitationError(f"no judgment for pending node {node.id}")
            if judgment.outcome == "misaligned" and judgment.severity is None:
                raise CitationError(f"judgment for {node.id} is misaligned without a severity")
            if not judgment.evidence_ids:
                raise CitationError(f"judgment for {node.id} cites nothing")
            continue
        if node.id not in findings:
            raise CitationError(f"no finding for node {node.id}")
    cited = [item.evidence_ids for item in reply.findings] + [item.evidence_ids for item in reply.judgments]
    unknown = sorted({item for ids in cited for item in ids if item not in allowed})
    if unknown:
        raise CitationError(f"unknown evidence ids: {', '.join(unknown)}")
    unknown_ids = [item.node_id for item in [*reply.findings, *reply.judgments] if item.node_id not in nodes]
    if unknown_ids:
        raise CitationError(f"unknown node ids: {', '.join(unknown_ids)}")
    unknown_urls = [url for url in reply.source_urls if url not in allowed_urls]
    if unknown_urls:
        raise CitationError(f"unknown source urls: {', '.join(unknown_urls)}")
    text = " ".join(
        [reply.verdict, *reply.meeting_agenda]
        + [item.finding for item in reply.findings]
        + [item.finding for item in reply.judgments]
    )
    invented = set(URL_RE.findall(text)) - allowed_urls
    if invented:
        raise CitationError(f"text cites urls outside the packet: {', '.join(sorted(invented))}")


def apply(tree: DecisionTree, reply: AnalystReply) -> DecisionTree:
    filled = tree.model_copy(deep=True)
    findings = {item.node_id: item for item in reply.findings}
    judgments = {item.node_id: item for item in reply.judgments}
    for node in filled.root.walk():
        if node.id in judgments:
            judgment = judgments[node.id]
            node.outcome = judgment.outcome
            node.severity = judgment.severity if judgment.outcome == "misaligned" else None
            node.finding = judgment.finding
            node.evidence_ids = merge_ids(node.evidence_ids, judgment.evidence_ids)
        elif node.id in findings:
            node.finding = findings[node.id].finding
            node.evidence_ids = merge_ids(node.evidence_ids, findings[node.id].evidence_ids)
    filled.score = score(filled.root)
    filled.verdict = reply.verdict
    filled.meeting_agenda = list(reply.meeting_agenda)
    filled.source_urls = list(reply.source_urls)
    return filled


def merge_ids(first: list[str], second: list[str]) -> list[str]:
    return list(dict.fromkeys([*first, *second]))


def to_report(tree: DecisionTree, brief: GoalBrief, facts: LiquidityFacts, evidence: MarketEvidence) -> AlignmentReport:
    """The flat report older tools read. Note ids are not packet evidence, so they are left out here."""
    packet_ids = allowed_ids(evidence, set(brief.slices))
    discrepancies = []
    for node in tree.nodes():
        if node.outcome != "misaligned" or node.severity is None:
            continue
        ids = [item for item in node.evidence_ids if item in packet_ids]
        if not ids:
            continue
        discrepancies.append(Discrepancy(claim=node.finding or node.detail, severity=node.severity, evidence_ids=ids))
    gap, _ = cover(brief, facts)
    return AlignmentReport(
        score=tree.score,
        gap_usd=gap,
        verdict=tree.verdict or "",
        discrepancies=discrepancies,
        meeting_agenda=list(tree.meeting_agenda),
        source_urls=list(tree.source_urls),
    )


def analyze(
    client: ChatClient,
    tasks: TaskModels,
    brief: GoalBrief,
    facts: LiquidityFacts,
    evidence: MarketEvidence,
    tree: DecisionTree,
    calls: list[CallRecord],
) -> DecisionTree:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": ANALYST_INSTRUCTIONS},
        {"role": "user", "content": json.dumps(packet(brief, facts, evidence, tree))},
    ]
    schema = json_schema(AnalystReply)
    reply = _once(client, tasks, messages, schema, calls)
    try:
        check_reply(reply, tree, brief, evidence)
    except CitationError as error:
        messages = [
            *messages,
            {"role": "assistant", "content": reply.model_dump_json()},
            {
                "role": "user",
                "content": (
                    f"The reply was rejected: {error}. Cover every node that is not skipped, resolve every "
                    "pending node, and cite only allowed_evidence_ids and allowed_source_urls. Return the reply again."
                ),
            },
        ]
        reply = _once(client, tasks, messages, schema, calls)
        check_reply(reply, tree, brief, evidence)
    return apply(tree, reply)


def _once(
    client: ChatClient,
    tasks: TaskModels,
    messages: list[dict[str, str]],
    schema: dict,
    calls: list[CallRecord],
) -> AnalystReply:
    completion = client.complete(
        task="analyst",
        model=tasks.analyst_model,
        effort=tasks.analyst_effort,
        messages=messages,
        schema_name="analyst_reply",
        schema=schema,
    )
    calls.append(record("analyst", completion))
    return AnalystReply.model_validate_json(completion.text)
