"""Server-resolved identity: who is calling and for which organization.

Nothing here reads the request body or query string. Demo tokens are HMAC-signed by the server;
Clerk tokens are RS256 JWTs verified against the instance's JWKS.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, Request

from app.heirloom.config import HeirloomSettings
from app.heirloom.envelope import ApiError

DEMO_PREFIX = "demo"


@dataclass(frozen=True)
class RequestContext:
    external_user_id: str
    organization_id: str


def _unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated", "Sign in to continue.")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str, settings: HeirloomSettings) -> str:
    digest = hmac.new(settings.demo_secret.encode(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64(digest)


def issue_demo_token(
    external_user_id: str, organization_id: str, settings: HeirloomSettings, ttl_s: int | None = None
) -> str:
    ttl = settings.demo_token_ttl_s if ttl_s is None else ttl_s
    claims = {"sub": external_user_id, "org": organization_id, "exp": int(time.time()) + ttl}
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{DEMO_PREFIX}.{payload}.{_sign(payload, settings)}"


def _resolve_demo(token: str, settings: HeirloomSettings) -> RequestContext:
    try:
        prefix, payload, signature = token.split(".")
        # Compare the encoded strings: a decoded comparison would accept a flipped padding bit.
        if prefix != DEMO_PREFIX or not hmac.compare_digest(
            signature.encode("ascii"), _sign(payload, settings).encode("ascii")
        ):
            raise _unauthenticated()
        claims = json.loads(_unb64(payload))
        if not isinstance(claims["exp"], int | float) or claims["exp"] <= time.time():
            raise _unauthenticated()
        return RequestContext(str(claims["sub"]), str(claims["org"]))
    except ApiError:
        raise
    except (ValueError, KeyError, TypeError):
        raise _unauthenticated() from None


@lru_cache
def _jwks_client(clerk_domain: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://{clerk_domain}/.well-known/jwks.json")


def _resolve_clerk(token: str, settings: HeirloomSettings) -> RequestContext:
    if not settings.clerk_domain:
        raise _unauthenticated()
    try:
        signing_key = _jwks_client(settings.clerk_domain).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=f"https://{settings.clerk_domain}",
            options={"require": ["exp", "iss", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError:
        raise _unauthenticated() from None
    org = claims.get("org_id") or (claims.get("o") or {}).get("id")
    if not org:
        raise _unauthenticated()
    return RequestContext(str(claims["sub"]), str(org))


def resolve_request_context(authorization: str | None, settings: HeirloomSettings) -> RequestContext:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthenticated()
    if settings.mode == "demo":
        return _resolve_demo(token, settings)
    return _resolve_clerk(token, settings)


def current_context(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> RequestContext:
    return resolve_request_context(authorization, request.app.state.settings)


ContextDep = Annotated[RequestContext, Depends(current_context)]
