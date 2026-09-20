"""Devin API request/response shapes, verified against docs.devin.ai.

This is the only module in the package that knows paths and field names.
Base URL: https://api.devin.ai/v1, override with env DEVIN_API_BASE.
Auth: `Authorization: Bearer $DEVIN_API_KEY` (set by the caller on the client).
"""
from __future__ import annotations

import os
from collections.abc import Mapping

BASE_URL = "https://api.devin.ai/v1"

TERMINAL = frozenset({"finished", "expired", "blocked"})


def base_url(env: Mapping[str, str] | None = None) -> str:
    source: Mapping[str, str] = os.environ if env is None else env
    return (source.get("DEVIN_API_BASE") or "").strip() or BASE_URL


def create_session_request(prompt: str, title: str, tags: list[str],
                           max_acu_limit: int | None) -> tuple[str, str, dict]:
    body = {
        "prompt": prompt,
        "title": title,
        "tags": list(tags),
        "idempotent": True,
        "max_acu_limit": max_acu_limit,
        "unlisted": False,
    }
    return "POST", "/sessions", body


def parse_create(resp_json: dict) -> dict:
    return {"session_id": resp_json["session_id"], "session_url": resp_json["url"]}


def status_request(session_id: str) -> tuple[str, str]:
    return "GET", f"/sessions/{session_id}"


def parse_status(resp_json: dict) -> dict:
    raw = resp_json.get("status_enum") or (resp_json.get("status") or "").lower()
    status = str(raw).lower()
    pr = resp_json.get("pull_request") or {}
    return {"status": status, "terminal": status in TERMINAL, "pr_url": pr.get("url")}
