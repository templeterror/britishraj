"""Reducer and citation checks, including a home the scrapers never find."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.market.planner import build_plan, write_plan
from app.market.reduce import build_evidence, build_facts, reduce_run
from app.market.schemas import AlignmentReport
from app.market.validate import CitationError, validate_report


def hale_plan(root: Path):
    book = Path(__file__).resolve().parents[3] / "mock_data.json"
    return build_plan("hale", run_id="test", book_path=book)


class ReduceTests(unittest.TestCase):
    def test_missing_home_uses_book_prices_and_leaves_equity_empty(self) -> None:
        plan = hale_plan(Path("."))
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "yahoo.json").write_text(
                json.dumps(
                    [
                        {
                            "url": "https://finance.yahoo.com/quote/SPY",
                            "stock_ticker": "SPY",
                            "closing_price": "600.00",
                            "previous_close": 590,
                            "week_range": "580 - 605",
                            "volume": "80M",
                            "avg_volume": 70000000,
                            "beta": 1,
                            "dividend_yield": "1.20%",
                            "currency": "USD",
                            "recent_news": [
                                {
                                    "title": "Index funds rise",
                                    "url": "https://finance.yahoo.com/news/index-funds-rise",
                                }
                            ],
                        }
                    ]
                )
            )
            evidence = build_evidence(plan, raw)
            facts = build_facts(plan.family, evidence)

        self.assertEqual(evidence.home.home_status, "not_found")
        self.assertIsNone(evidence.home.url)
        self.assertIsNone(facts.home_equity)
        spy = next(item for item in facts.positions if item.ticker == "SPY")
        self.assertEqual(spy.price_source, "live")
        self.assertEqual(spy.live_price, 600)
        vnq = next(item for item in facts.positions if item.ticker == "VNQ")
        self.assertEqual(vnq.price_source, "book")
        self.assertIsNone(vnq.change_vs_book)
        self.assertGreater(facts.cash_reachable, facts.checking + facts.savings)
        self.assertIn("technology company", plan.family.goal.statement)
        self.assertIn("https://finance.yahoo.com/news/index-funds-rise", evidence.source_urls)
        spy_quote = next(item for item in evidence.quotes if item.ticker == "SPY")
        self.assertEqual(spy_quote.dividend_yield, 1.2)

    def test_parenthetical_dividend_yield_is_the_percent(self) -> None:
        from app.market.reduce import dividend_yield

        self.assertEqual(dividend_yield("5.66 (0.73%)"), 0.73)
        self.assertEqual(dividend_yield("0.00"), 0.0)

    def test_found_home_sets_equity_from_zestimate(self) -> None:
        plan = hale_plan(Path("."))
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / "zillow_residence.json").write_text(
                json.dumps(
                    [
                        {
                            "url": "https://www.zillow.com/homedetails/18-Fernwood-Lane/1_zpid/",
                            "price": 9000000,
                            "zestimate": 8000000,
                            "days_on_zillow": 12,
                            "rent_zestimate": 25000,
                            "property_tax_rate": 1.2,
                            "mortgage_zhl_rates": {"thirtyYearFixed": {"rate": 6.5}},
                            "last_sold_price": 5000000,
                            "date_sold": 1609459200000,
                        }
                    ]
                )
            )
            (raw / "zillow_comps.json").write_text(
                json.dumps(
                    [
                        {
                            "url": "https://www.zillow.com/homedetails/1-Main/2_zpid/",
                            "price": 4000000,
                            "days_on_zillow": "20 days",
                        }
                    ]
                )
            )
            (raw / "crunchbase.json").write_text(
                json.dumps(
                    [
                        {
                            "url": "https://www.crunchbase.com/organization/example-tech",
                            "name": "Example Tech",
                            "company_industry": "Software",
                            "investment_stage": "seed",
                            "funding_rounds_list": [
                                {
                                    "title": "Seed Round",
                                    "money_raised": {"value": 4000000, "currency": "USD"},
                                    "announced_on": "2025-04-01",
                                }
                            ],
                        }
                    ]
                )
            )
            evidence = build_evidence(plan, raw)
            facts = build_facts(plan.family, evidence)

        self.assertEqual(evidence.home.home_status, "found")
        self.assertEqual(facts.home_equity, 8000000 - plan.family.mortgage_balance)
        self.assertEqual(evidence.comps.listings[0].id, "zillow:06831:1")
        self.assertEqual(evidence.comps.listings[0].days_on_zillow, 20)
        self.assertEqual(evidence.funding[0].rounds[0].amount, 4000000)
        self.assertEqual(evidence.home.mortgage_rate, 6.5)

    def test_unknown_citation_is_rejected(self) -> None:
        plan = hale_plan(Path("."))
        evidence = build_evidence(plan, Path(tempfile.mkdtemp()))
        facts = build_facts(plan.family, evidence)
        report = AlignmentReport(
            score=40,
            gap_usd=3_500_000,
            verdict="See https://example.com/invented",
            discrepancies=[
                {
                    "claim": "Cash is short of the goal.",
                    "severity": "high",
                    "evidence_ids": ["yahoo:NOT-A-TICKER"],
                }
            ],
            meeting_agenda=["Discuss the gap."],
            source_urls=["https://example.com/invented"],
        )
        with self.assertRaises(CitationError):
            validate_report(report, evidence, facts)

    def test_reduce_run_writes_the_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = hale_plan(root)
            destination = write_plan(plan, root)
            raw = destination / "raw"
            (raw / "yahoo.json").write_text("[]")
            evidence, facts = reduce_run(destination)
            self.assertEqual(evidence.home.home_status, "not_found")
            self.assertTrue((destination / "evidence.json").exists())
            self.assertTrue((destination / "facts.json").exists())
            self.assertIn("three years", plan.family.goal.statement)
            self.assertEqual(facts.goal_amount, 5_000_000)
            self.assertAlmostEqual(facts.goal_gap, facts.goal_amount - facts.cash_reachable, places=2)


if __name__ == "__main__":
    unittest.main()
