"""Deterministic checks. Every outcome here is computed from the numbers.

The tree is the explanation a wealth manager reads. Each node is one
question, its outcome, the figures behind it, and the evidence ids a
reader can follow. The analyst later adds a plain-word finding to each
node and resolves the one node code cannot judge: the parent's notes.
"""

from __future__ import annotations

from app.agents.schemas import DecisionTree, GoalBrief, Node, Severity, Status
from app.market.schemas import LIQUID_TICKERS, LiquidityFacts, MarketEvidence, REIT_TICKERS

PENALTY: dict[Severity, int] = {"high": 35, "medium": 15, "low": 5}
RUBRIC = (
    "Start at 100. Subtract 35 for each high, 15 for each medium, and 5 for each low "
    "misaligned check. Evidence gaps subtract nothing. Floor at 0."
)
REAL_ESTATE_WORDS = ("real estate", "property", "house", "home", "reit", "land")


def usd(value: float) -> str:
    return f"${value:,.2f}"


def months(value: int) -> str:
    if value % 12 == 0:
        years = value // 12
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{value} months"


def build_tree(brief: GoalBrief, status: Status, facts: LiquidityFacts, evidence: MarketEvidence) -> DecisionTree:
    root = goal_node(brief, status)
    cash = cash_node(brief, facts)
    cash.children.append(liquid_node(brief, facts, cash))
    cash.children[0].children.append(horizon_node(brief, facts, cash.children[0]))
    root.children.append(cash)
    root.children.append(concentration_node(brief, facts))
    if "home" in brief.slices:
        root.children.append(home_node(facts, evidence))
    if "funding" in brief.slices:
        root.children.append(purpose_node(evidence))
    if brief.decisions:
        root.children.append(notes_node(brief))
    return DecisionTree(root=root, score=score(root), rubric=RUBRIC)


def score(root: Node) -> int:
    total = 100
    for node in root.walk():
        if node.outcome == "misaligned" and node.severity:
            total -= PENALTY[node.severity]
    return max(total, 0)


def goal_node(brief: GoalBrief, status: Status) -> Node:
    title = "Is the goal specific enough to check?"
    if status == "ready":
        parts = [brief.intent]
        if brief.amount_usd:
            parts.append(f"Amount: {usd(brief.amount_usd)}{' (estimate)' if brief.amount_is_estimate else ''}.")
        if brief.horizon_months:
            parts.append(f"Horizon: {months(brief.horizon_months)}.")
        return Node(id="goal", title=title, outcome="aligned", detail=" ".join(parts))
    missing = ", ".join(brief.missing) or "nothing"
    return Node(
        id="goal",
        title=title,
        outcome="gap",
        detail=f"{brief.intent} After three questions the heir still has not given: {missing}.",
    )


def cash_node(brief: GoalBrief, facts: LiquidityFacts) -> Node:
    title = "Does cash the family can reach cover the amount?"
    ids = [f"yahoo:{item.ticker}" for item in facts.positions if item.ticker not in LIQUID_TICKERS | REIT_TICKERS]
    if not brief.amount_usd:
        return Node(id="cash", title=title, outcome="skipped", detail="No amount to compare against.", evidence_ids=ids)
    gap = round(brief.amount_usd - facts.cash_reachable, 2)
    if gap <= 0:
        return Node(
            id="cash",
            title=title,
            outcome="aligned",
            detail=(
                f"Cash reachable now is {usd(facts.cash_reachable)} (checking {usd(facts.checking)}, "
                f"savings {usd(facts.savings)}, money market {usd(facts.money_market)}), "
                f"which covers {usd(brief.amount_usd)}."
            ),
            evidence_ids=ids,
        )
    return Node(
        id="cash",
        title=title,
        outcome="misaligned",
        severity="high",
        detail=(
            f"Cash reachable now is {usd(facts.cash_reachable)} (checking {usd(facts.checking)}, "
            f"savings {usd(facts.savings)}, money market {usd(facts.money_market)}). "
            f"That is {usd(gap)} short of {usd(brief.amount_usd)}."
        ),
        evidence_ids=ids,
    )


def cover(brief: GoalBrief, facts: LiquidityFacts) -> tuple[float, float]:
    """The cash gap and how many times the liquid securities cover it."""
    if not brief.amount_usd:
        return 0.0, 0.0
    gap = round(brief.amount_usd - facts.cash_reachable, 2)
    if gap <= 0:
        return 0.0, 0.0
    return gap, facts.liquid_securities / gap


def liquid_node(brief: GoalBrief, facts: LiquidityFacts, cash: Node) -> Node:
    title = "Do liquid securities cover the remaining gap?"
    ids = [f"yahoo:{item.ticker}" for item in facts.positions if item.ticker in LIQUID_TICKERS]
    if cash.outcome == "skipped":
        return Node(id="liquid", title=title, outcome="skipped", detail="No amount to compare against.", evidence_ids=ids)
    if cash.outcome == "aligned":
        return Node(id="liquid", title=title, outcome="skipped", detail="Cash already covers the amount.", evidence_ids=ids)
    gap, ratio = cover(brief, facts)
    tickers = ", ".join(sorted(item.ticker for item in facts.positions if item.ticker in LIQUID_TICKERS))
    detail = (
        f"{tickers} are worth {usd(facts.liquid_securities)} at the live quotes, "
        f"{ratio:.2f} times the {usd(gap)} gap."
    )
    if ratio >= 2:
        return Node(id="liquid", title=title, outcome="aligned", detail=detail, evidence_ids=ids)
    severity: Severity = "high" if ratio < 1 else "medium" if ratio < 1.25 else "low"
    return Node(id="liquid", title=title, outcome="misaligned", severity=severity, detail=detail, evidence_ids=ids)


def horizon_node(brief: GoalBrief, facts: LiquidityFacts, liquid: Node) -> Node:
    title = "Does the horizon leave room for prices to move?"
    ids = list(liquid.evidence_ids)
    if liquid.outcome == "skipped":
        return Node(id="horizon", title=title, outcome="skipped", detail=liquid.detail, evidence_ids=ids)
    if not brief.horizon_months:
        return Node(id="horizon", title=title, outcome="skipped", detail="No horizon was given.", evidence_ids=ids)
    _, ratio = cover(brief, facts)
    moved = [item for item in facts.positions if item.ticker in LIQUID_TICKERS and item.change_vs_book is not None]
    worst = min(moved, key=lambda item: item.change_vs_book) if moved else None
    move = (
        f"{worst.ticker} has moved {worst.change_vs_book * 100:+.1f}% against its book price."
        if worst is not None
        else "No live price move is on record."
    )
    detail = f"The horizon is {months(brief.horizon_months)} and liquid cover is {ratio:.2f} times the gap. {move}"
    if brief.horizon_months < 36 and ratio < 2:
        return Node(id="horizon", title=title, outcome="misaligned", severity="low", detail=detail, evidence_ids=ids)
    return Node(id="horizon", title=title, outcome="aligned", detail=detail, evidence_ids=ids)


def excludes_real_estate(brief: GoalBrief) -> bool:
    if brief.must_be_reachable:
        return True
    text = " ".join(brief.exclusions).lower()
    return any(word in text for word in REAL_ESTATE_WORDS)


def concentration_node(brief: GoalBrief, facts: LiquidityFacts) -> Node:
    title = "How much of the book sits in what the heir said they cannot use?"
    ids = [f"yahoo:{item.ticker}" for item in facts.positions if item.ticker in REIT_TICKERS]
    book = facts.cash_reachable + facts.liquid_securities + facts.reit_sleeve
    share = facts.reit_sleeve / book if book else 0.0
    detail = (
        f"The real-estate sleeve is {usd(facts.reit_sleeve)}, {share * 100:.1f}% of the "
        f"{usd(book)} in cash and securities."
    )
    if excludes_real_estate(brief) and share >= 0.5:
        detail += " The heir said that kind of money does not count toward this goal."
        return Node(id="concentration", title=title, outcome="misaligned", severity="medium", detail=detail, evidence_ids=ids)
    if not excludes_real_estate(brief):
        detail += " The heir did not exclude it."
    return Node(id="concentration", title=title, outcome="aligned", detail=detail, evidence_ids=ids)


def home_node(facts: LiquidityFacts, evidence: MarketEvidence) -> Node:
    title = "Can the residence add equity?"
    ids = [evidence.home.id]
    if evidence.home.home_status != "found" or facts.home_equity is None:
        return Node(id="home", title=title, outcome="gap", detail="The residence was not found, so there is no equity figure.", evidence_ids=ids)
    return Node(
        id="home",
        title=title,
        outcome="aligned",
        detail=f"Zestimate {usd(evidence.home.zestimate or 0)} less the mortgage leaves {usd(facts.home_equity)} of equity.",
        evidence_ids=ids,
    )


def purpose_node(evidence: MarketEvidence) -> Node:
    title = "Does the market show what this kind of goal usually costs?"
    ids = [company.id for company in evidence.funding]
    amounts = [
        (company.name, round_.amount)
        for company in evidence.funding
        for round_ in company.rounds
        if round_.amount
    ]
    if not amounts:
        return Node(
            id="purpose",
            title=title,
            outcome="gap",
            detail=f"The company search returned {len(evidence.funding)} companies and no funding round amounts.",
            evidence_ids=ids,
        )
    sample = "; ".join(f"{name} {usd(amount)}" for name, amount in amounts[:5])
    return Node(id="purpose", title=title, outcome="aligned", detail=f"Funding rounds on record: {sample}.", evidence_ids=ids)


def notes_node(brief: GoalBrief) -> Node:
    ids = [f"note:{index}" for index in range(1, len(brief.decisions) + 1)]
    return Node(
        id="notes",
        title="Do the parent's recorded decisions conflict with the goal?",
        outcome="pending",
        detail=f"{len(brief.decisions)} decision(s) from the meeting notes are on record for the analyst to weigh.",
        evidence_ids=ids,
    )
