"""Contracts for one live market run.

Python builds the query plan and the numeric facts. Bright Data fills the
raw snapshots. The reasoning model may read only MarketEvidence and
LiquidityFacts, and AlignmentReport may cite only ids and URLs from that packet.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


YAHOO_DATASET_ID = "gd_lmrpz3vxmz972ghd7"
ZILLOW_SEARCH_DATASET_ID = "gd_lfqkr8wm13ixtbd8f5"
ZILLOW_PROPERTY_DATASET_ID = "gd_m794g571225l6vm7gh"
ZILLOW_HISTORY_DATASET_ID = "gd_lxu1cz9r88uiqsosl"
CRUNCHBASE_DATASET_ID = "gd_l1vijqt9jfj7olije"

LIQUID_TICKERS = frozenset({"SPY", "MUB", "TLT"})
REIT_TICKERS = frozenset({"VNQ"})
CASH_FUND_TICKERS = frozenset({"VMFXX"})


class Address(BaseModel):
    street: str
    city: str
    region: str
    postal_code: str
    country: str

    def one_line(self) -> str:
        return f"{self.street}, {self.city}, {self.region} {self.postal_code}"


class BookPosition(BaseModel):
    ticker: str
    name: str
    quantity: float
    institution_price: float
    institution_price_as_of: str


class FamilySlice(BaseModel):
    slug: str
    holder_name: str
    address: Address
    positions: list[BookPosition]
    checking_available: float
    savings_available: float
    mortgage_balance: float


class ScraperCall(BaseModel):
    name: str
    dataset_id: str
    method: str
    input: list[dict[str, Any]]
    limit_per_input: int | None = None


class QueryPlan(BaseModel):
    family_slug: str
    run_id: str
    family: FamilySlice
    calls: list[ScraperCall]


class NewsItem(BaseModel):
    title: str
    url: str


class QuoteEvidence(BaseModel):
    id: str
    ticker: str
    url: str
    status: Literal["ok", "missing"]
    closing_price: float | None = None
    previous_close: float | None = None
    week_range: str | None = None
    volume: float | None = None
    avg_volume: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    currency: str | None = None
    recent_news: list[NewsItem] = Field(default_factory=list)


class HomeEvidence(BaseModel):
    id: str
    home_status: Literal["found", "not_found"]
    url: str | None = None
    price: float | None = None
    zestimate: float | None = None
    zestimate_low_percent: float | None = None
    zestimate_high_percent: float | None = None
    days_on_zillow: float | None = None
    rent_zestimate: float | None = None
    mortgage_rate: float | None = None
    property_tax_rate: float | None = None
    last_sold_price: float | None = None
    date_sold: str | None = None


class CompEvidence(BaseModel):
    id: str
    url: str
    price: float | None = None
    zestimate: float | None = None
    days_on_zillow: float | None = None


class CompSet(BaseModel):
    id: str
    postal_code: str
    listings: list[CompEvidence] = Field(default_factory=list)


class FundingRound(BaseModel):
    stage: str | None = None
    amount: float | None = None
    date: str | None = None


class FundingComp(BaseModel):
    id: str
    name: str
    url: str
    industry: str | None = None
    investment_stage: str | None = None
    rounds: list[FundingRound] = Field(default_factory=list)


class MarketEvidence(BaseModel):
    family_slug: str
    quotes: list[QuoteEvidence]
    home: HomeEvidence
    comps: CompSet
    funding: list[FundingComp]
    source_urls: list[str]


class PositionValue(BaseModel):
    ticker: str
    quantity: float
    book_price: float
    book_price_as_of: str
    live_price: float | None
    price_used: float
    price_source: Literal["live", "book"]
    market_value: float
    change_vs_book: float | None = None


class LiquidityFacts(BaseModel):
    cash_reachable: float
    checking: float
    savings: float
    money_market: float
    positions: list[PositionValue]
    liquid_securities: float
    reit_sleeve: float
    home_equity: float | None = None


class Discrepancy(BaseModel):
    claim: str
    severity: Literal["low", "medium", "high"]
    evidence_ids: list[str]


class AlignmentReport(BaseModel):
    score: int = Field(ge=0, le=100)
    gap_usd: float
    verdict: str
    discrepancies: list[Discrepancy]
    meeting_agenda: list[str]
    source_urls: list[str]
