"""Build the 10-family Sandbox book used by mock_data.json.

Run once from the repo root. The file it writes is the dataset; this script
keeps the dollar amounts and transaction counts checkable.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

AS_OF = date(2026, 10, 9)
PRICE = {
    "VNQ": 89.40,
    "MUB": 107.25,
    "SPY": 572.00,
    "TLT": 92.15,
    "VMFXX": 1.00,
    "BRK.B": 458.00,
}
NAME = {
    "VNQ": "Vanguard Real Estate ETF",
    "MUB": "iShares National Muni Bond ETF",
    "SPY": "SPDR S&P 500 ETF Trust",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "VMFXX": "Vanguard Federal Money Market",
    "BRK.B": "Berkshire Hathaway Class B",
}

FAMILIES = [
    {
        "slug": "hale",
        "display_name": "Hale",
        "is_demo": True,
        "parent": ("Robert", "Hale"),
        "heir": ("James", "Hale"),
        "street": "18 Fernwood Lane",
        "city": "Greenwich",
        "region": "CT",
        "postal_code": "06831",
        "investable": 25_000_000,
        "reit_share": 0.68,
        "equity_share": 0.12,
        "muni_share": 0.11,
        "treasury_share": 0.06,
        "checking_available": 400_000,
        "checking_current": 450_000,
        "savings_available": 1_100_000,
        "mortgage": 6_400_000,
        "account_base": "110000001",
    },
    {
        "slug": "whitfield",
        "display_name": "Whitfield",
        "is_demo": False,
        "parent": ("Eleanor", "Whitfield"),
        "heir": ("Thomas", "Whitfield"),
        "street": "940 Park Avenue",
        "city": "New York",
        "region": "NY",
        "postal_code": "10028",
        "investable": 42_000_000,
        "reit_share": 0.22,
        "equity_share": 0.46,
        "muni_share": 0.18,
        "treasury_share": 0.10,
        "checking_available": 900_000,
        "checking_current": 900_000,
        "savings_available": 3_300_000,
        "mortgage": 8_750_000,
        "account_base": "110000011",
    },
    {
        "slug": "okonkwo",
        "display_name": "Okonkwo",
        "is_demo": False,
        "parent": ("Adaeze", "Okonkwo"),
        "heir": ("Chidi", "Okonkwo"),
        "street": "410 Lakeshore Drive",
        "city": "Chicago",
        "region": "IL",
        "postal_code": "60611",
        "investable": 18_000_000,
        "reit_share": 0.41,
        "equity_share": 0.28,
        "muni_share": 0.16,
        "treasury_share": 0.10,
        "checking_available": 350_000,
        "checking_current": 350_000,
        "savings_available": 850_000,
        "mortgage": 3_200_000,
        "account_base": "110000021",
    },
    {
        "slug": "bergstrom",
        "display_name": "Bergstrom",
        "is_demo": False,
        "parent": ("Ingrid", "Bergstrom"),
        "heir": ("Lars", "Bergstrom"),
        "street": "27 Summit Road",
        "city": "Aspen",
        "region": "CO",
        "postal_code": "81611",
        "investable": 61_000_000,
        "reit_share": 0.15,
        "equity_share": 0.52,
        "muni_share": 0.14,
        "treasury_share": 0.14,
        "checking_available": 1_100_000,
        "checking_current": 1_100_000,
        "savings_available": 3_000_000,
        "mortgage": 12_400_000,
        "account_base": "110000031",
    },
    {
        "slug": "moreau",
        "display_name": "Moreau",
        "is_demo": False,
        "parent": ("Camille", "Moreau"),
        "heir": ("Julien", "Moreau"),
        "street": "88 Royal Street",
        "city": "New Orleans",
        "region": "LA",
        "postal_code": "70130",
        "investable": 33_000_000,
        "reit_share": 0.34,
        "equity_share": 0.31,
        "muni_share": 0.20,
        "treasury_share": 0.10,
        "checking_available": 600_000,
        "checking_current": 600_000,
        "savings_available": 1_800_000,
        "mortgage": 5_600_000,
        "account_base": "110000041",
    },
    {
        "slug": "shah",
        "display_name": "Shah",
        "is_demo": False,
        "parent": ("Vikram", "Shah"),
        "heir": ("Anika", "Shah"),
        "street": "1500 Willow Road",
        "city": "Palo Alto",
        "region": "CA",
        "postal_code": "94301",
        "investable": 15_500_000,
        "reit_share": 0.18,
        "equity_share": 0.55,
        "muni_share": 0.12,
        "treasury_share": 0.08,
        "checking_available": 280_000,
        "checking_current": 280_000,
        "savings_available": 770_000,
        "mortgage": 2_400_000,
        "account_base": "110000051",
    },
    {
        "slug": "lindqvist",
        "display_name": "Lindqvist",
        "is_demo": False,
        "parent": ("Astrid", "Lindqvist"),
        "heir": ("Noah", "Lindqvist"),
        "street": "6 Harbor View",
        "city": "Newport",
        "region": "RI",
        "postal_code": "02840",
        "investable": 52_000_000,
        "reit_share": 0.12,
        "equity_share": 0.40,
        "muni_share": 0.22,
        "treasury_share": 0.18,
        "checking_available": 1_200_000,
        "checking_current": 1_200_000,
        "savings_available": 3_800_000,
        "mortgage": 9_100_000,
        "account_base": "110000061",
    },
    {
        "slug": "alvarez",
        "display_name": "Alvarez",
        "is_demo": False,
        "parent": ("Mateo", "Alvarez"),
        "heir": ("Sofia", "Alvarez"),
        "street": "330 Alhambra Circle",
        "city": "Coral Gables",
        "region": "FL",
        "postal_code": "33134",
        "investable": 27_000_000,
        "reit_share": 0.48,
        "equity_share": 0.24,
        "muni_share": 0.14,
        "treasury_share": 0.08,
        "checking_available": 500_000,
        "checking_current": 500_000,
        "savings_available": 1_300_000,
        "mortgage": 4_800_000,
        "account_base": "110000071",
    },
    {
        "slug": "chen",
        "display_name": "Chen",
        "is_demo": False,
        "parent": ("Mei", "Chen"),
        "heir": ("David", "Chen"),
        "street": "2100 Pacific Avenue",
        "city": "San Francisco",
        "region": "CA",
        "postal_code": "94115",
        "investable": 74_000_000,
        "reit_share": 0.20,
        "equity_share": 0.48,
        "muni_share": 0.16,
        "treasury_share": 0.12,
        "checking_available": 1_400_000,
        "checking_current": 1_400_000,
        "savings_available": 3_000_000,
        "mortgage": 14_200_000,
        "account_base": "110000081",
    },
    {
        "slug": "rossi",
        "display_name": "Rossi",
        "is_demo": False,
        "parent": ("Giovanni", "Rossi"),
        "heir": ("Lucia", "Rossi"),
        "street": "14 Beacon Hill",
        "city": "Boston",
        "region": "MA",
        "postal_code": "02108",
        "investable": 21_000_000,
        "reit_share": 0.30,
        "equity_share": 0.34,
        "muni_share": 0.20,
        "treasury_share": 0.10,
        "checking_available": 450_000,
        "checking_current": 450_000,
        "savings_available": 1_750_000,
        "mortgage": 3_900_000,
        "account_base": "110000091",
    },
]


def money(value: float) -> float:
    return round(value, 2)


def shares(dollars: float, price: float) -> float:
    return round(dollars / price, 4)


def security(ticker: str) -> dict:
    return {"ticker_symbol": ticker, "name": NAME[ticker], "currency": "USD"}


def holding(ticker: str, quantity: float, cost_basis: float) -> dict:
    return {
        "institution_price": PRICE[ticker],
        "institution_price_as_of": AS_OF.isoformat(),
        "cost_basis": money(cost_basis),
        "quantity": quantity,
        "currency": "USD",
        "security": security(ticker),
    }


def positions(target: float, weights: dict[str, float]) -> list[dict]:
    """Build holdings that sum to target. Money market absorbs the rounding gap."""
    priced = []
    spent = 0.0
    for ticker, weight in weights.items():
        if ticker == "VMFXX":
            continue
        quantity = shares(target * weight, PRICE[ticker])
        value = quantity * PRICE[ticker]
        spent += value
        basis_ratio = {"VNQ": 0.78, "SPY": 0.71, "BRK.B": 0.74, "MUB": 0.96, "TLT": 1.04}[ticker]
        priced.append(holding(ticker, quantity, value * basis_ratio))
    cash_qty = money(target - spent)
    if cash_qty <= 0:
        raise SystemExit(f"weights overshoot target {target}: spent {spent}")
    priced.append(holding("VMFXX", cash_qty, cash_qty))
    return priced


def split_book(all_holdings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Put most of each risk holding in the brokerage and the rest in the trust."""
    brokerage = []
    trust = []
    for item in all_holdings:
        ticker = item["security"]["ticker_symbol"]
        if ticker == "VMFXX":
            brokerage.append(item)
            continue
        broker_qty = round(item["quantity"] * 0.72, 4)
        trust_qty = round(item["quantity"] - broker_qty, 4)
        if trust_qty <= 0:
            brokerage.append(item)
            continue
        ratio_b = broker_qty / item["quantity"]
        ratio_t = trust_qty / item["quantity"]
        brokerage.append(
            holding(ticker, broker_qty, item["cost_basis"] * ratio_b)
        )
        trust.append(holding(ticker, trust_qty, item["cost_basis"] * ratio_t))
    return brokerage, trust


def book_value(items: list[dict]) -> float:
    return money(sum(item["quantity"] * item["institution_price"] for item in items))


BUY_DATES = [
    date(2024, 11, 14),
    date(2025, 3, 18),
    date(2025, 8, 7),
    date(2026, 2, 11),
]
TRUST_DATES = [date(2025, 1, 16), date(2025, 10, 9)]


def investment_activity(items: list[dict], dates: list[date], family: str) -> list[dict]:
    activity = []
    for item in items:
        ticker = item["security"]["ticker_symbol"]
        if ticker == "VMFXX":
            continue
        slices = len(dates)
        remaining = item["quantity"]
        for index, when in enumerate(dates):
            quantity = round(item["quantity"] / slices, 4)
            if index == slices - 1:
                quantity = round(remaining, 4)
            remaining = round(remaining - quantity, 4)
            price = round(item["cost_basis"] / item["quantity"], 4)
            activity.append(
                {
                    "date": when.isoformat(),
                    "name": f"Buy {ticker}",
                    "quantity": quantity,
                    "price": price,
                    "fees": 250 if quantity * price < 1_000_000 else 750,
                    "type": "buy",
                    "currency": "USD",
                    "security": security(ticker),
                }
            )
        activity.append(
            {
                "date": date(2026, 6, 15).isoformat(),
                "name": f"{ticker} distribution",
                "quantity": 1,
                "price": money(item["quantity"] * item["institution_price"] * 0.012),
                "fees": 0,
                "type": "cash",
                "currency": "USD",
                "security": security(ticker),
            }
        )
    activity.append(
        {
            "date": date(2026, 9, 30).isoformat(),
            "name": f"{family} advisory fee",
            "quantity": 1,
            "price": 0,
            "fees": 35000,
            "type": "fee",
            "currency": "USD",
            "security": security("VMFXX"),
        }
    )
    activity.sort(key=lambda row: row["date"], reverse=True)
    return activity


def cash_row(when: date, amount: float, description: str) -> dict:
    return {
        "date_transacted": when.isoformat(),
        "date_posted": (when + timedelta(days=1)).isoformat(),
        "amount": money(amount),
        "description": description,
        "currency": "USD",
    }


def checking_activity(spec: dict, holder: str) -> list[dict]:
    scale = spec["investable"] / 25_000_000
    rows = [
        cash_row(date(2026, 10, 6), -money(180_000 * scale), f"Dividend sweep to {holder}"),
        cash_row(date(2026, 9, 22), money(min(750_000, 75_000 * scale)), "Art advisory wire"),
        cash_row(date(2026, 8, 14), money(min(180_000, 28_000 * scale + 40_000)), "Household office wire"),
        cash_row(date(2026, 6, 18), money(min(750_000, 400_000 * scale)), "Private fund capital call"),
        cash_row(date(2026, 6, 2), -money(min(1_500_000, 250_000 * scale)), "Trust distribution received"),
        cash_row(date(2026, 5, 20), money(min(220_000, 62_000 * scale)), "Property and casualty insurance"),
        cash_row(date(2026, 5, 1), money(min(150_000, 45_000 * scale)), "Wealth advisory fee"),
        cash_row(date(2026, 4, 15), money(min(350_000, 85_000 * scale)), "Property tax wire"),
    ]
    rows.sort(key=lambda row: row["date_transacted"], reverse=True)
    return rows


def savings_activity(holder: str) -> list[dict]:
    rows = [
        cash_row(date(2026, 9, 28), -420_000, f"Transfer from {holder} checking"),
        cash_row(date(2026, 8, 3), 250_000, f"Transfer to {holder} checking"),
        cash_row(date(2026, 6, 30), -600_000, "Reserve funding from brokerage sweep"),
        cash_row(date(2026, 5, 12), 150_000, "Reserve draw for insurance"),
        cash_row(date(2026, 4, 20), -300_000, "Incoming wire from trust"),
    ]
    rows.sort(key=lambda row: row["date_transacted"], reverse=True)
    return rows


def mortgage_activity(principal: float) -> list[dict]:
    payment = money(max(25_000, principal * 0.004))
    rows = [
        cash_row(date(2026, 10, 1), payment, "Mortgage payment"),
        cash_row(date(2026, 9, 1), payment, "Mortgage payment"),
        cash_row(date(2026, 8, 1), payment, "Mortgage payment"),
        cash_row(date(2026, 7, 1), payment, "Mortgage payment"),
        cash_row(date(2026, 6, 1), payment, "Mortgage payment"),
        cash_row(date(2026, 5, 1), payment, "Mortgage payment"),
    ]
    return rows


def identity(holder: str, spec: dict) -> dict:
    return {
        "names": [holder],
        "addresses": [
            {
                "primary": True,
                "data": {
                    "country": "US",
                    "city": spec["city"],
                    "street": spec["street"],
                    "postal_code": spec["postal_code"],
                    "region": spec["region"],
                },
            }
        ],
    }


def account_number(spec: dict, slot: int) -> str:
    return str(int(spec["account_base"]) + slot)


def wrap_account(
    spec: dict,
    holder: str,
    slot: int,
    type_: str,
    subtype: str,
    label: str,
    current: float,
    available: float | None,
    extra: dict,
) -> dict:
    override = {
        "type": type_,
        "subtype": subtype,
        "starting_balance": money(current),
        "meta": {"name": label, "official_name": label},
        "identity": identity(holder, spec),
    }
    if type_ != "investment":
        override["numbers"] = {
            "account": account_number(spec, slot),
            "ach_routing": "021000021",
        }
    override.update(extra)
    record = {
        "name": label,
        "official_name": label,
        "type": type_,
        "subtype": subtype,
        "current_balance": money(current),
        "available_balance": None if available is None else money(available),
        "currency": "USD",
        "override": override,
    }
    return record


def build_family(spec: dict) -> dict:
    holder = f"{spec['parent'][0]} {spec['parent'][1]}"
    weights = {
        "VNQ": spec["reit_share"],
        "SPY": spec["equity_share"],
        "MUB": spec["muni_share"],
        "TLT": spec["treasury_share"],
    }
    brokerage, trust = split_book(positions(spec["investable"], weights))
    brokerage_value = book_value(brokerage)
    trust_value = book_value(trust)
    cash_sleeve = next(
        item["quantity"] for item in brokerage if item["security"]["ticker_symbol"] == "VMFXX"
    )
    family_name = spec["display_name"]
    accounts = [
        wrap_account(
            spec,
            holder,
            1,
            "investment",
            "brokerage",
            f"{family_name} Taxable Brokerage",
            brokerage_value,
            cash_sleeve,
            {
                "holdings": brokerage,
                "investment_transactions": investment_activity(brokerage, BUY_DATES, family_name),
            },
        ),
        wrap_account(
            spec,
            holder,
            2,
            "investment",
            "trust",
            f"{family_name} Family Trust",
            trust_value,
            0,
            {
                "holdings": trust,
                "investment_transactions": investment_activity(trust, TRUST_DATES, family_name),
            },
        ),
        wrap_account(
            spec,
            holder,
            3,
            "depository",
            "checking",
            f"{family_name} Private Checking",
            spec["checking_current"],
            spec["checking_available"],
            {"transactions": checking_activity(spec, holder)},
        ),
        wrap_account(
            spec,
            holder,
            4,
            "depository",
            "savings",
            f"{family_name} Reserve Savings",
            spec["savings_available"],
            spec["savings_available"],
            {"transactions": savings_activity(holder)},
        ),
        wrap_account(
            spec,
            holder,
            5,
            "loan",
            "mortgage",
            f"{family_name} Residence Mortgage",
            spec["mortgage"],
            None,
            {"transactions": mortgage_activity(spec["mortgage"])},
        ),
    ]
    goals = []
    if spec["is_demo"]:
        goals.append(
            {
                "person_role": "heir",
                "statement": (
                    "I want to start a technology company in the next three years. "
                    "I'll need about $5 million I can actually get to, not money "
                    "that's tied up in real estate."
                ),
            }
        )
    return {
        "slug": spec["slug"],
        "display_name": spec["display_name"],
        "is_demo": spec["is_demo"],
        "seed": f"wealthbridge-{spec['slug']}-2026",
        "people": [
            {
                "role": "parent",
                "given_name": spec["parent"][0],
                "family_name": spec["parent"][1],
            },
            {
                "role": "heir",
                "given_name": spec["heir"][0],
                "family_name": spec["heir"][1],
            },
        ],
        "goals": goals,
        "holder_name": holder,
        "address": {
            "street": spec["street"],
            "city": spec["city"],
            "region": spec["region"],
            "postal_code": spec["postal_code"],
            "country": "US",
        },
        "accounts": accounts,
    }


def plaid_payload(family: dict) -> dict:
    return {
        "seed": family["seed"],
        "override_accounts": [account["override"] for account in family["accounts"]],
    }


def validate(book: dict) -> None:
    families = book["families"]
    if len(families) != 10:
        raise SystemExit(f"expected 10 families, got {len(families)}")
    accounts = sum(len(family["accounts"]) for family in families)
    if accounts != 50:
        raise SystemExit(f"expected 50 accounts, got {accounts}")
    goals = [goal for family in families for goal in family["goals"]]
    if len(goals) != 1 or "statement" not in goals[0] or "target_amount" in goals[0]:
        raise SystemExit("expected one goal written as a statement")
    for family in families:
        payload = json.dumps(plaid_payload(family), separators=(",", ":"))
        if len(payload.encode()) > 55_000:
            raise SystemExit(f"{family['slug']} payload is {len(payload)} bytes")
        investable = sum(
            account["current_balance"]
            for account in family["accounts"]
            if account["type"] == "investment"
        )
        if not 15_000_000 <= investable <= 75_000_000:
            raise SystemExit(f"{family['slug']} investable {investable} outside band")
        cash = sum(
            account["available_balance"] or 0
            for account in family["accounts"]
            if account["subtype"] in {"checking", "savings"}
        )
        if not 1_000_000 <= cash <= 5_000_000:
            raise SystemExit(f"{family['slug']} cash {cash} outside band")
        txns = 0
        for account in family["accounts"]:
            txns += len(account["override"].get("transactions", []))
            txns += len(account["override"].get("investment_transactions", []))
        if txns > 250:
            raise SystemExit(f"{family['slug']} has {txns} transactions")
        subtypes = [account["subtype"] for account in family["accounts"]]
        if subtypes != ["brokerage", "trust", "checking", "savings", "mortgage"]:
            raise SystemExit(f"{family['slug']} account mix {subtypes}")
    hale = families[0]
    investable = sum(
        account["current_balance"]
        for account in hale["accounts"]
        if account["type"] == "investment"
    )
    cash = sum(
        account["available_balance"] or 0
        for account in hale["accounts"]
        if account["subtype"] in {"checking", "savings"}
    )
    reit = 0.0
    for account in hale["accounts"]:
        if account["type"] != "investment":
            continue
        for item in account["override"]["holdings"]:
            if item["security"]["ticker_symbol"] == "VNQ":
                reit += item["quantity"] * item["institution_price"]
    if abs(investable - 25_000_000) > 50_000:
        raise SystemExit(f"Hale investable {investable}")
    if abs(cash - 1_500_000) > 1:
        raise SystemExit(f"Hale cash {cash}")
    if reit / investable < 0.6:
        raise SystemExit(f"Hale REIT share {reit / investable:.2%}")
    print(f"families={len(families)} accounts={accounts} goals={len(goals)}")
    for family in families:
        investable = sum(
            account["current_balance"]
            for account in family["accounts"]
            if account["type"] == "investment"
        )
        cash = sum(
            account["available_balance"] or 0
            for account in family["accounts"]
            if account["subtype"] in {"checking", "savings"}
        )
        payload = json.dumps(plaid_payload(family), separators=(",", ":"))
        print(
            f"{family['slug']}: investable={investable:,.0f} cash={cash:,.0f} "
            f"payload_bytes={len(payload.encode())}"
        )


def main() -> None:
    book = {"families": [build_family(spec) for spec in FAMILIES]}
    validate(book)
    destination = Path(__file__).resolve().parents[1] / "mock_data.json"
    destination.write_text(json.dumps(book, indent=2) + "\n")
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
