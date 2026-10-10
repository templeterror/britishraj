import uuid

NAMESPACE = uuid.UUID("5b0e8a4e-1f0c-4c1a-9d8e-6f1e2a3b4c5d")


def ref_id(ref: str) -> uuid.UUID:
    """Deterministic UUID for a business ref such as `asset-family-llc`."""
    return uuid.uuid5(NAMESPACE, ref)
