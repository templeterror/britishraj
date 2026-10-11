"""Shrink raw Bright Data records into the packet the model is allowed to see."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.market.planner import crunchbase_org_url, yahoo_url, zillow_url
from app.market.schemas import (
    CASH_FUND_TICKERS,
    LIQUID_TICKERS,
    REIT_TICKERS,
    CompEvidence,
    CompSet,
    FamilySlice,
    FundingComp,
    FundingRound,
    HomeEvidence,
    LiquidityFacts,
    MarketEvidence,
    NewsItem,
    PositionValue,
    QueryPlan,
    QuoteEvidence,
)

RAW_NAMES = (
    "yahoo",
    "zillow_residence_search",
    "zillow_residence",
    "zillow_residence_history",
    "zillow_comps_search",
    "zillow_comps",
    "crunchbase_search",
    "crunchbase",
)


def money(value: float) -> float:
    return round(value + 1e-9, 2)


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("records", "data", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return [payload]
    return []


def parse_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("raw", "value", "amount", "rate", "price"):
            if key in value:
                parsed = parse_number(value[key])
                if parsed is not None:
                    return parsed
        return None
    if not isinstance(value, str):
        return None
    text = value.strip().replace(",", "").replace("%", "")
    if not text or text in {"-", "—", "N/A", "n/a"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    suffix = text[match.end() :].strip().lower()
    if suffix.startswith("b"):
        number *= 1_000_000_000
    elif suffix.startswith("m"):
        number *= 1_000_000
    elif suffix.startswith("k"):
        number *= 1_000
    return number


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > 10_000_000_000:
            stamp = datetime.fromtimestamp(value / 1000, timezone.utc)
            return stamp.date().isoformat()
        if value > 1_000_000_000:
            stamp = datetime.fromtimestamp(value, timezone.utc)
            return stamp.date().isoformat()
        return str(value)
    return None


def news_items(value: Any, limit: int = 3) -> list[NewsItem]:
    rows: list[Any]
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        nested = value.get("items") or value.get("news") or value.get("recent_news") or []
        rows = nested if isinstance(nested, list) else []
    else:
        rows = []
    items: list[NewsItem] = []
    for row in rows:
        if len(items) >= limit or not isinstance(row, dict):
            continue
        title = as_text(row.get("title") or row.get("headline") or row.get("name"))
        url = as_text(row.get("url") or row.get("link") or row.get("href"))
        if title and url and url.startswith("http"):
            items.append(NewsItem(title=title, url=url))
    return items


def record_url(record: dict) -> str | None:
    for key in ("url", "input_url"):
        value = record.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value.split("?")[0]
    input_row = record.get("input")
    if isinstance(input_row, dict):
        value = input_row.get("url")
        if isinstance(value, str) and value.startswith("http"):
            return value.split("?")[0]
    return None


def ticker_of(record: dict) -> str | None:
    for key in ("stock_ticker", "ticker", "symbol"):
        value = as_text(record.get(key))
        if value:
            return value.upper().replace("-", ".")
    url = record_url(record) or ""
    match = re.search(r"/quote/([^/?]+)", url)
    if match:
        return match.group(1).upper().replace("-", ".")
    return None


def dividend_yield(value: Any) -> float | None:
    if isinstance(value, str):
        match = re.search(r"\(([-0-9.]+)\s*%\)", value)
        if match:
            return float(match.group(1))
    return parse_number(value)


def quote_from_record(ticker: str, record: dict | None) -> QuoteEvidence:
    url = yahoo_url(ticker)
    if record is None or record.get("error"):
        return QuoteEvidence(id=f"yahoo:{ticker}", ticker=ticker, url=url, status="missing")
    page_url = record_url(record) or url
    week = record.get("week_range")
    return QuoteEvidence(
        id=f"yahoo:{ticker}",
        ticker=ticker,
        url=page_url if page_url.startswith("http") else url,
        status="ok",
        closing_price=parse_number(record.get("closing_price")),
        previous_close=parse_number(record.get("previous_close")),
        week_range=as_text(week) if not isinstance(week, (int, float)) else str(week),
        volume=parse_number(record.get("volume")),
        avg_volume=parse_number(record.get("avg_volume")),
        beta=parse_number(record.get("beta")),
        dividend_yield=dividend_yield(record.get("dividend_yield")),
        currency=as_text(record.get("currency")),
        recent_news=news_items(record.get("recent_news")),
    )


def quotes_for(plan: QueryPlan, records: list[dict]) -> list[QuoteEvidence]:
    by_symbol: dict[str, dict] = {}
    for record in records:
        symbol = ticker_of(record)
        if not symbol:
            continue
        current = by_symbol.get(symbol)
        if current is None or (current.get("error") and not record.get("error")):
            by_symbol[symbol] = record
    quotes: list[QuoteEvidence] = []
    for position in plan.family.positions:
        quotes.append(quote_from_record(position.ticker, by_symbol.get(position.ticker)))
    return quotes


def mortgage_rate(value: Any) -> float | None:
    parsed = parse_number(value)
    if parsed is not None and not isinstance(value, (dict, list)):
        return parsed
    if isinstance(value, dict):
        for key in (
            "rate",
            "apr",
            "thirtyYearFixed",
            "thirty_year_fixed",
            "15_year_fixed",
            "arm5",
        ):
            if key in value:
                found = mortgage_rate(value[key])
                if found is not None:
                    return found
        for nested in value.values():
            found = mortgage_rate(nested)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = mortgage_rate(item)
            if found is not None:
                return found
    return None


def last_sale_from_history(records: list[dict]) -> tuple[float | None, str | None]:
    sold: list[tuple[str, float]] = []
    for record in records:
        event = (as_text(record.get("event")) or "").lower()
        if "sold" not in event:
            continue
        price = parse_number(record.get("price"))
        when = as_text(record.get("date"))
        if price is not None and when:
            sold.append((when, price))
    if not sold:
        return None, None
    sold.sort()
    when, price = sold[-1]
    return price, when


def home_from_record(record: dict | None, history: list[dict]) -> HomeEvidence:
    empty = HomeEvidence(id="zillow:residence", home_status="not_found")
    if record is None or record.get("error"):
        return empty
    url = zillow_url(record_url(record) or "") or zillow_url(as_text(record.get("url")) or "")
    price = parse_number(record.get("price"))
    zestimate = parse_number(record.get("zestimate"))
    if url is None or (price is None and zestimate is None):
        return empty
    last_sold = parse_number(record.get("last_sold_price"))
    sold_on = as_text(record.get("date_sold"))
    if last_sold is None:
        last_sold, sold_on = last_sale_from_history(history)
    return HomeEvidence(
        id="zillow:residence",
        home_status="found",
        url=url,
        price=price,
        zestimate=zestimate,
        zestimate_low_percent=parse_number(record.get("zestimate_low_percent")),
        zestimate_high_percent=parse_number(record.get("zestimate_high_percent")),
        days_on_zillow=parse_number(record.get("days_on_zillow") or record.get("time_on_zillow")),
        rent_zestimate=parse_number(record.get("rent_zestimate")),
        mortgage_rate=mortgage_rate(record.get("mortgage_zhl_rates")),
        property_tax_rate=parse_number(record.get("property_tax_rate")),
        last_sold_price=last_sold,
        date_sold=sold_on,
    )


def comp_from_record(index: int, postal_code: str, record: dict) -> CompEvidence | None:
    if record.get("error"):
        return None
    url = zillow_url(record_url(record) or "") or zillow_url(as_text(record.get("url")) or "")
    if url is None:
        return None
    return CompEvidence(
        id=f"zillow:{postal_code}:{index}",
        url=url,
        price=parse_number(record.get("price")),
        zestimate=parse_number(record.get("zestimate")),
        days_on_zillow=parse_number(record.get("days_on_zillow") or record.get("time_on_zillow")),
    )


def comps_for(postal_code: str, records: list[dict], residence_url: str | None) -> CompSet:
    listings: list[CompEvidence] = []
    for record in records:
        comp = comp_from_record(len(listings) + 1, postal_code, record)
        if comp is None or comp.url == residence_url:
            continue
        listings.append(comp)
        if len(listings) == 5:
            break
    return CompSet(id=f"zillow:{postal_code}", postal_code=postal_code, listings=listings)


def industry_text(record: dict) -> str | None:
    for key in ("company_industry", "industries", "industry"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            names = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                elif isinstance(item, dict):
                    label = as_text(item.get("name") or item.get("value"))
                    if label:
                        names.append(label)
            if names:
                return ", ".join(names[:3])
    return None


def round_rows(record: dict) -> list[Any]:
    for key in ("funding_rounds_list", "funding_rounds_detailed", "funding_rounds"):
        value = record.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for inner in ("rounds", "items", "list"):
                nested = value.get(inner)
                if isinstance(nested, list):
                    return nested
    return []


def funding_round(row: Any) -> FundingRound | None:
    if not isinstance(row, dict):
        return None
    stage = as_text(
        row.get("investment_type")
        or row.get("funding_type")
        or row.get("round_type")
        or row.get("title")
        or row.get("stage")
        or row.get("name")
    )
    amount = parse_number(
        row.get("money_raised")
        or row.get("raised_amount")
        or row.get("amount")
        or row.get("money_raised_usd")
        or row.get("raised_amount_usd")
    )
    when = as_text(row.get("announced_on") or row.get("announced_date") or row.get("date"))
    if stage is None and amount is None and when is None:
        return None
    return FundingRound(stage=stage, amount=amount, date=when)


def funding_id(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1].lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-")
    return f"crunchbase:{slug}"


def funding_from_record(record: dict) -> FundingComp | None:
    if record.get("error"):
        return None
    url = crunchbase_org_url(record_url(record) or "") or crunchbase_org_url(as_text(record.get("url")) or "")
    if url is None:
        return None
    name = as_text(record.get("name") or record.get("legal_name")) or url.rstrip("/").split("/")[-1]
    rounds = []
    for row in round_rows(record):
        parsed = funding_round(row)
        if parsed is not None:
            rounds.append(parsed)
        if len(rounds) == 5:
            break
    return FundingComp(
        id=funding_id(url),
        name=name,
        url=url,
        industry=industry_text(record),
        investment_stage=as_text(record.get("investment_stage")),
        rounds=rounds,
    )


def funding_for(records: list[dict]) -> list[FundingComp]:
    comps: list[FundingComp] = []
    seen: set[str] = set()
    for record in records:
        comp = funding_from_record(record)
        if comp is None or comp.id in seen:
            continue
        seen.add(comp.id)
        comps.append(comp)
        if len(comps) == 5:
            break
    return comps


def source_urls(evidence_parts: dict) -> list[str]:
    urls: list[str] = []

    def add(value: str | None) -> None:
        if value and value.startswith("http") and value not in urls:
            urls.append(value)

    for quote in evidence_parts["quotes"]:
        add(quote.url)
        for item in quote.recent_news:
            add(item.url)
    add(evidence_parts["home"].url)
    for listing in evidence_parts["comps"].listings:
        add(listing.url)
    for company in evidence_parts["funding"]:
        add(company.url)
    return urls


def first_useful_home(records: list[dict]) -> dict | None:
    for record in records:
        if record.get("error"):
            continue
        if parse_number(record.get("price")) is None and parse_number(record.get("zestimate")) is None:
            continue
        return record
    return None


def build_evidence(plan: QueryPlan, raw_dir: Path) -> MarketEvidence:
    yahoo = load_records(raw_dir / "yahoo.json")
    residence_full = load_records(raw_dir / "zillow_residence.json")
    history = load_records(raw_dir / "zillow_residence_history.json")
    comp_full = load_records(raw_dir / "zillow_comps.json")
    comp_search = load_records(raw_dir / "zillow_comps_search.json")
    crunchbase_full = load_records(raw_dir / "crunchbase.json")
    home = home_from_record(first_useful_home(residence_full), history)
    comps = comps_for(
        plan.family.address.postal_code,
        comp_full or comp_search,
        home.url,
    )
    quotes = quotes_for(plan, yahoo)
    funding = funding_for(crunchbase_full)
    parts = {"quotes": quotes, "home": home, "comps": comps, "funding": funding}
    return MarketEvidence(
        family_slug=plan.family_slug,
        quotes=quotes,
        home=home,
        comps=comps,
        funding=funding,
        source_urls=source_urls(parts),
    )


def position_value(position, quote: QuoteEvidence | None) -> PositionValue:
    live = quote.closing_price if quote and quote.status == "ok" else None
    if live is None and quote and quote.previous_close is not None:
        live = quote.previous_close
    source = "live" if live is not None else "book"
    used = live if live is not None else position.institution_price
    change = None
    if live is not None and position.institution_price:
        change = (live - position.institution_price) / position.institution_price
    return PositionValue(
        ticker=position.ticker,
        quantity=position.quantity,
        book_price=position.institution_price,
        book_price_as_of=position.institution_price_as_of,
        live_price=live,
        price_used=used,
        price_source=source,
        market_value=money(position.quantity * used),
        change_vs_book=change,
    )


def build_facts(family: FamilySlice, evidence: MarketEvidence) -> LiquidityFacts:
    by_ticker = {quote.ticker: quote for quote in evidence.quotes}
    positions = [position_value(position, by_ticker.get(position.ticker)) for position in family.positions]
    money_market = sum(item.market_value for item in positions if item.ticker in CASH_FUND_TICKERS)
    liquid = sum(item.market_value for item in positions if item.ticker in LIQUID_TICKERS)
    reit = sum(item.market_value for item in positions if item.ticker in REIT_TICKERS)
    cash = money(family.checking_available + family.savings_available + money_market)
    home_equity = None
    if evidence.home.home_status == "found" and evidence.home.zestimate is not None:
        home_equity = money(evidence.home.zestimate - family.mortgage_balance)
    return LiquidityFacts(
        cash_reachable=cash,
        checking=money(family.checking_available),
        savings=money(family.savings_available),
        money_market=money(money_market),
        positions=positions,
        goal_amount=money(family.goal.target_amount),
        goal_gap=money(family.goal.target_amount - cash),
        liquid_securities=money(liquid),
        reit_sleeve=money(reit),
        home_equity=home_equity,
    )


def reduce_run(run_directory: Path) -> tuple[MarketEvidence, LiquidityFacts]:
    plan = QueryPlan.model_validate_json((run_directory / "query_plan.json").read_text())
    evidence = build_evidence(plan, run_directory / "raw")
    facts = build_facts(plan.family, evidence)
    (run_directory / "evidence.json").write_text(evidence.model_dump_json(indent=2) + "\n")
    (run_directory / "facts.json").write_text(facts.model_dump_json(indent=2) + "\n")
    return evidence, facts
