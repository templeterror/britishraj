from typing import Literal

from app.heirloom.dto.common import AssetDTO, DecisionDTO, FamilyDTO, IntentDTO, PersonRef, StrictModel
from app.heirloom.dto.heir import HeirDecisionView


class ParentDecisionDTO(DecisionDTO):
    shared_with_heir: bool


class HeirRef(StrictModel):
    person_id: str
    display_name: str


class ParentSharing(StrictModel):
    decision_excerpts: int
    estate_intent: Literal["off"] = "off"
    balances: Literal["not_available_in_pilot"] = "not_available_in_pilot"


class ParentSnapshot(StrictModel):
    family: FamilyDTO
    me: PersonRef
    assets: list[AssetDTO]
    decisions: list[ParentDecisionDTO]
    intents: list[IntentDTO]
    preserve_values: list[str]
    heirs: list[HeirRef]
    sharing: ParentSharing


class HeirPreview(StrictModel):
    """Exactly what the heir sees of the parent's decisions (same function as the heir snapshot)."""

    approved_decisions: list[HeirDecisionView]
