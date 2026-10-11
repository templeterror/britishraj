"""Build a Bright Data query plan from one family in the book."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.market.schemas import (
    CRUNCHBASE_DATASET_ID,
    YAHOO_DATASET_ID,
    ZILLOW_HISTORY_DATASET_ID,
    ZILLOW_PROPERTY_DATASET_ID,
    ZILLOW_SEARCH_DATASET_ID,
    Address,
    BookPosition,
    FamilySlice,
    Goal,
    QueryPlan,
    ScraperCall,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOK_PATH = REPO_ROOT / "mock_data.json"


def yahoo_symbol(ticker: str) -> str:
    return ticker.replace(".", "-")


def yahoo_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{yahoo_symbol(ticker)}"


_YEAR_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def goal_amount(statement: str) -> float:
    million = re.search(r"\$\s*(\d+(?:\.\d+)?)\s*million", statement, re.I)
    if million:
        return float(million.group(1)) * 1_000_000
    plain = re.search(r"\$\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", statement)
    if plain:
        return float(plain.group(1).replace(",", ""))
    raise ValueError("goal statement has no dollar amount")


def goal_horizon_years(statement: str) -> int:
    match = re.search(r"(\d+|one|two|three|four|five)\s+years", statement, re.I)
    if not match:
        raise ValueError("goal statement has no year horizon")
    token = match.group(1).lower()
    if token in _YEAR_WORDS:
        return _YEAR_WORDS[token]
    return int(token)


def goal_keyword(statement: str) -> str:
    """Search hint for market context. The stored goal stays the heir's words."""
    text = statement.lower()
    if "technology" in text or re.search(r"\btech\b", text):
        return "technology"
    words = re.findall(r"[a-z]{4,}", text)
    skipped = {
        "about",
        "actually",
        "capital",
        "company",
        "money",
        "need",
        "next",
        "start",
        "three",
        "want",
        "years",
    }
    for word in words:
        if word not in skipped:
            return word
    raise ValueError("goal text has no keyword to search")


def load_family(slug: str, book_path: Path = BOOK_PATH) -> dict:
    book = json.loads(book_path.read_text())
    for family in book["families"]:
        if family["slug"] == slug:
            return family
    raise KeyError(f"no family named {slug}")


def family_slice(family: dict) -> FamilySlice:
    goals = family.get("goals") or []
    if len(goals) != 1:
        raise ValueError(f"{family['slug']} needs exactly one goal, found {len(goals)}")
    goal = goals[0]
    grouped: dict[str, dict] = {}
    order: list[str] = []
    checking = 0.0
    savings = 0.0
    mortgage = 0.0
    for account in family["accounts"]:
        subtype = account["subtype"]
        if subtype == "checking":
            checking += float(account["available_balance"] or 0)
        elif subtype == "savings":
            savings += float(account["available_balance"] or 0)
        elif subtype == "mortgage":
            mortgage += float(account["current_balance"] or 0)
        if account["type"] != "investment":
            continue
        for item in account["override"]["holdings"]:
            security = item["security"]
            ticker = security["ticker_symbol"]
            quantity = float(item["quantity"])
            price = float(item["institution_price"])
            if ticker not in grouped:
                order.append(ticker)
                grouped[ticker] = {
                    "ticker": ticker,
                    "name": security["name"],
                    "quantity": 0.0,
                    "cost": 0.0,
                    "as_of": item["institution_price_as_of"],
                }
            grouped[ticker]["quantity"] += quantity
            grouped[ticker]["cost"] += quantity * price
            grouped[ticker]["as_of"] = max(grouped[ticker]["as_of"], item["institution_price_as_of"])
    positions = []
    for ticker in order:
        row = grouped[ticker]
        positions.append(
            BookPosition(
                ticker=ticker,
                name=row["name"],
                quantity=row["quantity"],
                institution_price=row["cost"] / row["quantity"],
                institution_price_as_of=row["as_of"],
            )
        )
    return FamilySlice(
        slug=family["slug"],
        holder_name=family["holder_name"],
        address=Address.model_validate(family["address"]),
        goal=Goal(
            person_role=goal["person_role"],
            statement=goal["statement"],
            target_amount=goal_amount(goal["statement"]),
            horizon_years=goal_horizon_years(goal["statement"]),
        ),
        positions=positions,
        checking_available=checking,
        savings_available=savings,
        mortgage_balance=mortgage,
    )


def scraper_calls(family: FamilySlice) -> list[ScraperCall]:
    quotes = [{"url": yahoo_url(position.ticker)} for position in family.positions]
    residence = family.address.one_line()
    return [
        ScraperCall(
            name="yahoo",
            dataset_id=YAHOO_DATASET_ID,
            method="collect_by_url",
            input=quotes,
        ),
        ScraperCall(
            name="zillow_residence_search",
            dataset_id=ZILLOW_SEARCH_DATASET_ID,
            method="discover_by_input_filters",
            input=[{"location": residence, "exact_address": True}],
            limit_per_input=1,
        ),
        ScraperCall(
            name="zillow_comps_search",
            dataset_id=ZILLOW_SEARCH_DATASET_ID,
            method="discover_by_input_filters",
            input=[
                {
                    "location": family.address.postal_code,
                    "listingCategory": "House for sale",
                    "exact_address": False,
                }
            ],
            limit_per_input=5,
        ),
        ScraperCall(
            name="crunchbase_search",
            dataset_id=CRUNCHBASE_DATASET_ID,
            method="discover_by_keyword",
            input=[{"keyword": goal_keyword(family.goal.statement)}],
            limit_per_input=5,
        ),
    ]


def build_plan(slug: str, run_id: str | None = None, book_path: Path = BOOK_PATH) -> QueryPlan:
    family = family_slice(load_family(slug, book_path))
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return QueryPlan(
        family_slug=family.slug,
        run_id=run_id,
        family=family,
        calls=scraper_calls(family),
    )


def run_dir(plan: QueryPlan, root: Path = REPO_ROOT) -> Path:
    return root / "data" / "market" / plan.family_slug / plan.run_id


def write_plan(plan: QueryPlan, root: Path = REPO_ROOT) -> Path:
    destination = run_dir(plan, root)
    (destination / "raw").mkdir(parents=True, exist_ok=True)
    (destination / "query_plan.json").write_text(plan.model_dump_json(indent=2) + "\n")
    return destination


def zillow_url(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        text = "https:" + text
    if text.startswith("/"):
        text = "https://www.zillow.com" + text
    if "zillow.com" not in text:
        return None
    if "homedetails" not in text and "/homedetails/" not in text:
        return None
    return text.split("?")[0]


def collect_urls(records: list[dict], predicate) -> list[str]:
    found: list[str] = []
    for record in records:
        if not isinstance(record, dict) or record.get("error"):
            continue
        candidates = [
            record.get("url"),
            record.get("hdpUrl"),
            record.get("hdp_url"),
        ]
        input_row = record.get("input")
        if isinstance(input_row, dict):
            candidates.append(input_row.get("url"))
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            cleaned = predicate(candidate)
            if cleaned and cleaned not in found:
                found.append(cleaned)
    return found


def crunchbase_org_url(value: str) -> str | None:
    text = value.strip().split("?")[0].rstrip("/")
    if "crunchbase.com/organization/" not in text:
        return None
    return text


def follow_up_calls(
    residence_records: list[dict],
    comp_records: list[dict],
    crunchbase_records: list[dict],
) -> list[ScraperCall]:
    """Second-wave fetches. Search rows usually contain only a URL."""
    calls: list[ScraperCall] = []
    residence_urls = collect_urls(residence_records, zillow_url)[:1]
    if residence_urls:
        calls.append(
            ScraperCall(
                name="zillow_residence",
                dataset_id=ZILLOW_PROPERTY_DATASET_ID,
                method="collect_by_url",
                input=[{"url": url} for url in residence_urls],
            )
        )
        calls.append(
            ScraperCall(
                name="zillow_residence_history",
                dataset_id=ZILLOW_HISTORY_DATASET_ID,
                method="collect_by_url",
                input=[{"url": url} for url in residence_urls],
            )
        )
    comp_urls = [url for url in collect_urls(comp_records, zillow_url) if url not in residence_urls][:5]
    if comp_urls:
        calls.append(
            ScraperCall(
                name="zillow_comps",
                dataset_id=ZILLOW_PROPERTY_DATASET_ID,
                method="collect_by_url",
                input=[{"url": url} for url in comp_urls],
            )
        )
    org_urls = collect_urls(crunchbase_records, crunchbase_org_url)[:5]
    if org_urls:
        calls.append(
            ScraperCall(
                name="crunchbase",
                dataset_id=CRUNCHBASE_DATASET_ID,
                method="collect_by_url",
                input=[{"url": url} for url in org_urls],
            )
        )
    return calls
