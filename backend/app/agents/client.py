"""One OpenAI-compatible client aimed straight at the xAI API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from app.agents.catalog import TaskModels, effort_allowed, resolve_tasks

XAI_BASE = "https://api.x.ai/v1"
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
        "reasoning_effort": effort,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
    }


def json_schema(model: type[BaseModel]) -> dict:
    """A strict schema: every property required, no extra keys, no titles or defaults."""
    return strict(model.model_json_schema())


def strict(node):
    if isinstance(node, list):
        return [strict(item) for item in node]
    if not isinstance(node, dict):
        return node
    cleaned = {key: strict(value) for key, value in node.items() if key not in ("title", "default")}
    if cleaned.get("type") == "object" and "properties" in cleaned:
        cleaned["required"] = list(cleaned["properties"])
        cleaned["additionalProperties"] = False
    return cleaned


class XaiClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
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
        effort_allowed(model, effort)
        request = completion_request(model, effort, messages, schema_name, schema)
        completion = self._openai().chat.completions.create(**request)
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

            self._sdk = OpenAI(api_key=self._api_key, base_url=XAI_BASE)
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


def open_xai() -> tuple[XaiClient, TaskModels]:
    load_backend_env()
    key = os.environ.get("XAI_API_KEY") or ""
    if not key or "REPLACE_ME" in key:
        raise SystemExit("XAI_API_KEY is not set")
    return XaiClient(key), resolve_tasks(os.environ)
