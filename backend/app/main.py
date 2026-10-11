"""HTTP entrypoint for Railway.

Railway sets PORT and injects variables. This process only reports whether
those variables are present. It does not print their values.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

REQUIRED = (
    "CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_DOMAIN",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "FRONTEND_ORIGIN",
)


def allowed_origins() -> list[str]:
    raw = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


app = FastAPI(title="Heirloom API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    xai = os.environ.get("XAI_API_KEY", "")
    return {
        "ok": True,
        "missing": missing,
        "xai": bool(xai) and "REPLACE_ME" not in xai,
    }
