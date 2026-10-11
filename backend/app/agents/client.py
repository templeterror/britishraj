"""One OpenAI-compatible client aimed at the Vercel AI Gateway."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from app.agents.catalog import ModelSpec, TaskModels, effort_allowed, resolve_tasks, specs_by_id

GATEWAY_BASE = "https://ai-gateway.vercel.sh/v1"
CATALOG_URL = f"{GATEWAY_BASE}/models"
BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    effort: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatClient(Protocol):
    def complete(
        self,
        *,
        task: str,
        model: str,
        effort: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict,
    ) -> Completion: ...


def completion_request(
    model: str,
    effort: str,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict,
) -> dict:
    return {
        "model": model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema},
        },
        "extra_body": {"reasoning": {"effort": effort, "exclude": True}},
    }


def json_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


class GatewayClient:
    def __init__(self, api_key: str, specs: dict[str, ModelSpec]) -> None:
        self._api_key = api_key
        self._specs = specs
        self._sdk = None

    def complete(
        self,
        *,
        task: str,
        model: str,
        effort: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict,
    ) -> Completion:
        del task
        spec = self._specs.get(model)
        if spec is None:
            raise ValueError(f"{model} is not in the model catalog")
        effort_allowed(spec, effort)
        request = completion_request(model, effort, messages, schema_name, schema)
        extra = request.pop("extra_body")
        completion = self._openai().chat.completions.create(**request, extra_body=extra)
        choice = completion.choices[0].message
        text = choice.content or ""
        if not text.strip():
            raise RuntimeError(f"{model} returned an empty response")
        usage = completion.usage
        return Completion(
            text=text,
            model=model,
            effort=effort,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )

    def _openai(self):
        if self._sdk is None:
            from openai import OpenAI

            self._sdk = OpenAI(api_key=self._api_key, base_url=GATEWAY_BASE)
        return self._sdk


def load_backend_env() -> None:
    if not BACKEND_ENV.exists():
        return
    for line in BACKEND_ENV.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch_catalog() -> list[dict]:
    request = urllib.request.Request(CATALOG_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.URLError as error:
        raise SystemExit(f"could not read the model catalog: {error.reason}") from error
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SystemExit("model catalog returned no data")
    return rows


def open_gateway() -> tuple[GatewayClient, TaskModels]:
    load_backend_env()
    key = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN") or ""
    if not key or "REPLACE_ME" in key:
        raise SystemExit("AI_GATEWAY_API_KEY is not set")
    rows = fetch_catalog()
    tasks = resolve_tasks(rows, os.environ)
    return GatewayClient(key, specs_by_id(rows)), tasks
