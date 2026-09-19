"""OpenAI calls for lane B.

Every call's token usage is appended to research/results/raw/llm_usage.jsonl. The contract
has no cost collection for lane B, so this local log is where judge cost comes from.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

USAGE_LOG = Path(__file__).parent / "results" / "raw" / "llm_usage.jsonl"
_log_lock = threading.Lock()
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY
    return _client


def structured(*, model: str, system: str, user: str, schema_name: str, schema: dict,
               purpose: str, effort: str = "low", retries: int = 2, meta: dict | None = None) -> dict:
    """One Responses API call constrained to a strict JSON schema. Returns the parsed object.

    GPT-5.x are reasoning models: temperature is not supported, `effort` controls latency.
    """
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.monotonic()
        try:
            resp = _get_client().responses.create(
                model=model,
                instructions=system,
                input=user,
                reasoning={"effort": effort},
                text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
            )
            out = json.loads(resp.output_text)
        except Exception as e:  # network, rate limit, refusal, bad JSON: retry with backoff
            last_err = e
            time.sleep(2 ** attempt)
            continue
        _log_usage(resp, model, purpose, int((time.monotonic() - t0) * 1000), meta or {})
        return out
    raise RuntimeError(f"{purpose} call failed after {retries + 1} attempts") from last_err


def _log_usage(resp, model: str, purpose: str, latency_ms: int, meta: dict) -> None:
    u = resp.usage
    rec = {
        "purpose": purpose,
        "model": model,
        "tokens_in": u.input_tokens,
        "tokens_out": u.output_tokens,
        "tokens_cached": getattr(u.input_tokens_details, "cached_tokens", 0) or 0,
        "tokens_reasoning": getattr(u.output_tokens_details, "reasoning_tokens", 0) or 0,
        "latency_ms": latency_ms,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **meta,
    }
    with _log_lock:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
