"""Reject an alignment report that cites anything outside the evidence packet."""

from __future__ import annotations

import re
from pathlib import Path

from app.market.schemas import AlignmentReport, MarketEvidence

URL_RE = re.compile(r"https?://[^\s)>\"]+")


class CitationError(ValueError):
    pass


def evidence_ids(evidence: MarketEvidence) -> set[str]:
    ids = {quote.id for quote in evidence.quotes}
    ids.add(evidence.home.id)
    ids.add(evidence.comps.id)
    ids.update(listing.id for listing in evidence.comps.listings)
    ids.update(company.id for company in evidence.funding)
    return ids


def text_urls(report: AlignmentReport) -> set[str]:
    chunks = [report.verdict, *report.meeting_agenda]
    chunks.extend(item.claim for item in report.discrepancies)
    return set(URL_RE.findall(" ".join(chunks)))


def validate_report(report: AlignmentReport, evidence: MarketEvidence) -> None:
    allowed_ids = evidence_ids(evidence)
    allowed_urls = set(evidence.source_urls)
    for item in report.discrepancies:
        if not item.evidence_ids:
            raise CitationError("a discrepancy has no evidence id")
        unknown = [evidence_id for evidence_id in item.evidence_ids if evidence_id not in allowed_ids]
        if unknown:
            raise CitationError(f"unknown evidence ids: {', '.join(unknown)}")
    unknown_urls = [url for url in report.source_urls if url not in allowed_urls]
    if unknown_urls:
        raise CitationError(f"unknown source urls: {', '.join(unknown_urls)}")
    invented = text_urls(report) - allowed_urls
    if invented:
        raise CitationError(f"report text cites urls outside the packet: {', '.join(sorted(invented))}")


def validate_run(run_directory: Path) -> AlignmentReport:
    evidence = MarketEvidence.model_validate_json((run_directory / "evidence.json").read_text())
    report = AlignmentReport.model_validate_json((run_directory / "alignment.json").read_text())
    validate_report(report, evidence)
    return report
