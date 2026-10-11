"""The guard on text an heir will read: no estate, trust or family-record details, and no amounts.

Plain substring matching on purpose. It is cheap to explain to an advisor ("remove: llc") and errs
toward refusing a draft over letting a detail through.
"""

import re

from app.heirloom.envelope import ApiError

BASE_TERMS = ("inherit", "bequest", "estate", "beneficiar", "intended for", "trust", "llc", "will ")
AMOUNT = re.compile(r"\$\s?\d|\d[\d,]{3,}")  # "$5", "$ 5", or any run of four or more digits and commas


class HeirUnsafeText(ApiError):
    def __init__(self, hits: list[str]):
        super().__init__(
            422,
            "heir_unsafe_text",
            "This draft is not safe to show an heir. Remove: " + ", ".join(hits),
        )
        self.hits = hits


def find_violations(text: str, family_terms: list[str]) -> list[str]:
    """What in `text` an heir must not see: base terms, amounts, then any of `family_terms` (asset
    labels and instrument titles). Case-insensitive; the same hit is listed once."""
    flat = " ".join(text.lower().split())  # a line break inside a phrase must not hide it
    hits = [term.strip() for term in BASE_TERMS if term in flat]
    hits += [match.group() for match in AMOUNT.finditer(text)]
    hits += [term for term in family_terms if term.strip() and " ".join(term.lower().split()) in flat]
    return list(dict.fromkeys(hits))


def require_safe(text: str, family_terms: list[str]) -> None:
    """Raise `HeirUnsafeText` (422) when `find_violations` finds anything."""
    if hits := find_violations(text, family_terms):
        raise HeirUnsafeText(hits)
