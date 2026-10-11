"""The four access terms an advisor can correct on an asset. Every other term is read-only.

`None` for `liquidatable_fraction` or `partner_consent_process_documented` means unknown (needs
attorney review); the forecast then shows no probability instead of a reassuring one. A change emits
`asset.terms_updated.v1`, which the readiness pipeline answers by recomputing the family's flags.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.envelope import ApiError
from app.heirloom.models import Asset
from app.heirloom.services import audit, events, lookup
from app.heirloom.services.graph import record_ref

NOT_NULL = ("sale_delay_years", "distribution_yield")


class TermsPatch(BaseModel):
    """Only the terms sent change. An unknown field is a 422, not a silent no-op."""

    model_config = ConfigDict(extra="forbid")

    sale_delay_years: Annotated[int, Field(ge=0, le=10)] | None = None
    liquidatable_fraction: Annotated[float, Field(ge=0, le=1)] | None = None
    partner_consent_process_documented: bool | None = None
    distribution_yield: Annotated[float, Field(ge=0, le=0.2)] | None = None


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation_error", f"Invalid request: {message}")


def update(actor: FamilyActor, session: Session, asset_id: str, patch: TermsPatch) -> Asset:
    require_role(actor, "advisor")
    asset = lookup.family_record(session, actor, Asset, asset_id)
    sent = {name: getattr(patch, name) for name in patch.model_fields_set}
    if not sent:
        raise _invalid("send at least one term")
    for name in NOT_NULL:
        if name in sent and sent[name] is None:
            raise _invalid(f"{name} cannot be null")

    terms = dict(asset.terms or {})
    changed = {name: value for name, value in sent.items() if name not in terms or terms[name] != value}
    if changed:  # saving what is already stored is not an event
        asset.terms = {**terms, **changed}
        ref = record_ref(asset)
        audit.record(
            session,
            actor.ctx.external_user_id,
            actor.family.id,
            "asset.terms_update",
            "asset",
            ref,
            True,
            "allowed",
        )
        events.emit(
            session,
            actor.family,
            "asset.terms_updated.v1",
            ref,
            {"asset_ref": ref, "terms": sorted(changed)},  # names only: the values stay in the asset
        )
    return asset
