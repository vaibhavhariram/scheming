"""Async Devin sessions over httpx.

`run_session` creates one session and polls it to a terminal status with exponential
backoff and full jitter. `run_many` fans out under a semaphore on one shared client.
`dry_run_request` renders the would-be create call to disk — no network. The API key is
required up front; there is no mock fallback.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from collections.abc import Mapping
from pathlib import Path

import httpx

from . import api_shapes


class MissingApiKey(RuntimeError):
    pass


def api_key_from_env(env: Mapping[str, str] | None = None) -> str:
    source: Mapping[str, str] = os.environ if env is None else env
    key = (source.get("DEVIN_API_KEY") or "").strip()
    if not key:
        raise MissingApiKey("DEVIN_API_KEY is not set (put it in .env or the environment)")
    return key


async def run_session(client: httpx.AsyncClient, prompt: str, *, title: str,
                      tags: list[str], max_acu_limit: int | None = None,
                      timeout_s: float = 1200, poll_initial: float = 5.0,
                      poll_max: float = 60.0, clock=time.monotonic,
                      sleep=asyncio.sleep, rng=random.random) -> dict:
    """One session end to end. Returns {session_id, session_url, status, pr_url,
    wall_clock_seconds}. Timeout -> status "timed_out" (returned, not raised)."""
    start = clock()
    method, path, body = api_shapes.create_session_request(prompt, title, tags, max_acu_limit)
    resp = await client.request(method, path, json=body)
    resp.raise_for_status()
    created = api_shapes.parse_create(resp.json())
    session_id = created["session_id"]

    delay = poll_initial
    status, pr_url = "working", None
    while True:
        if clock() - start >= timeout_s:
            return {**created, "status": "timed_out", "pr_url": None,
                    "wall_clock_seconds": clock() - start}
        await sleep(delay * (0.5 + rng()))
        try:
            sm, sp = api_shapes.status_request(session_id)
            resp = await client.request(sm, sp)
            if resp.status_code >= 500:
                print(f"poll {session_id}: HTTP {resp.status_code}, retrying", file=sys.stderr)
            else:
                resp.raise_for_status()
                parsed = api_shapes.parse_status(resp.json())
                status, pr_url = parsed["status"], parsed["pr_url"]
                if parsed["terminal"]:
                    break
        except httpx.TransportError as e:
            print(f"poll {session_id}: {type(e).__name__}, retrying", file=sys.stderr)
        delay = min(delay * 2, poll_max)
    return {**created, "status": status, "pr_url": pr_url,
            "wall_clock_seconds": clock() - start}


async def run_many(prompts: list[tuple[str, dict]], *, concurrency: int = 3,
                   api_key: str, base_url: str, **kw) -> list[dict]:
    """`prompts` is [(exploit_id, {prompt, title, tags})]; results in input order.
    A failing session becomes {status: "error", error: str}; the rest continue."""
    sem = asyncio.Semaphore(concurrency)

    async def one(client, eid, spec):
        async with sem:
            try:
                res = await run_session(client, spec["prompt"], title=spec["title"],
                                        tags=spec["tags"],
                                        max_acu_limit=spec.get("max_acu_limit"), **kw)
                res["exploit_id"] = eid
                return res
            except Exception as e:
                return {"exploit_id": eid, "status": "error", "error": str(e),
                        "session_id": None, "session_url": None, "pr_url": None,
                        "wall_clock_seconds": None}

    async with httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(30)) as client:
        return await asyncio.gather(*(one(client, eid, s) for eid, s in prompts))


def dry_run_request(exploit_id: str, prompt: str, title: str, tags: list[str],
                    out_dir: Path | str, *, base: str = api_shapes.BASE_URL) -> Path:
    """Write the would-be create request to <out_dir>/requests/<exploit_id>.json."""
    method, path, body = api_shapes.create_session_request(prompt, title, tags, None)
    out = Path(out_dir) / "requests"
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{exploit_id}.json"
    p.write_text(json.dumps({"method": method, "url": base + path, "body": body}, indent=2),
                 encoding="utf-8")
    return p
