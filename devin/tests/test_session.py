"""Tests for devin/session.py — all traffic through httpx.MockTransport."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from devin import session


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler),
                             base_url="https://api.devin.ai/v1")


def _created(req):
    return httpx.Response(200, json={"session_id": "s1",
                                     "url": "https://app.devin.ai/sessions/s1",
                                     "is_new_session": True})


def test_missing_key():
    with pytest.raises(session.MissingApiKey, match="DEVIN_API_KEY"):
        session.api_key_from_env({})
    with pytest.raises(session.MissingApiKey):
        session.api_key_from_env({"DEVIN_API_KEY": "  "})
    assert session.api_key_from_env({"DEVIN_API_KEY": "k"}) == "k"


def test_run_session_polls_to_finished():
    polls = []
    sleeps = []

    def handler(req):
        if req.method == "POST":
            return _created(req)
        polls.append(1)
        status = "finished" if len(polls) > 2 else "working"
        pr = {"url": "https://github.com/x/y/pull/9"} if status == "finished" else None
        return httpx.Response(200, json={"session_id": "s1", "status": status,
                                         "status_enum": status, "pull_request": pr})

    async def fake_sleep(d):
        sleeps.append(d)

    clock = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    async def go():
        async with _client(handler) as c:
            return await session.run_session(
                c, "P", title="t", tags=[], poll_initial=5, poll_max=60,
                clock=lambda: next(clock), sleep=fake_sleep, rng=lambda: 0.5)
    res = asyncio.run(go())
    assert res["status"] == "finished"
    assert res["pr_url"] == "https://github.com/x/y/pull/9"
    assert res["session_id"] == "s1"
    # delays double (5,10,20) with rng=0.5 -> x(0.5+0.5)=identity, capped at 60
    assert sleeps[:3] == [5, 10, 20]


def test_run_session_timeout_returns_timed_out():
    def handler(req):
        if req.method == "POST":
            return _created(req)
        return httpx.Response(200, json={"status": "working", "status_enum": "working",
                                         "pull_request": None})

    times = iter(range(0, 10_000, 30))  # every clock() call jumps 30s -> over timeout_s=50 fast
    async def go():
        async with _client(handler) as c:
            return await session.run_session(
                c, "P", title="t", tags=[], timeout_s=50, poll_initial=1,
                clock=lambda: next(times), sleep=lambda d: asyncio.sleep(0),
                rng=lambda: 0.0)
    res = asyncio.run(go())
    assert res["status"] == "timed_out"
    assert res["session_id"] == "s1"


def test_run_many_concurrency_and_error_isolation():
    in_flight = {"n": 0, "max": 0}

    def handler(req):
        if req.method == "POST":
            sid = json.loads(req.content)["title"]  # encode which prompt
            return httpx.Response(200, json={"session_id": sid, "url": f"u/{sid}",
                                             "is_new_session": True})
        sid = req.url.path.rsplit("/", 1)[-1]
        if sid == "bad":
            return httpx.Response(500)
        in_flight["n"] += 1
        in_flight["max"] = max(in_flight["max"], in_flight["n"])
        try:
            return httpx.Response(200, json={"status_enum": "finished",
                                             "status": "finished",
                                             "pull_request": None})
        finally:
            in_flight["n"] -= 1

    prompts = [(f"e{i}", {"prompt": "p", "title": t, "tags": []})
               for i, t in enumerate(["ok1", "bad", "ok2"])]

    async def go():
        transport = httpx.MockTransport(handler)
        # patch AsyncClient to use the mock transport
        orig = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: orig(transport=transport, **kw)
            # 'bad' session: make run_session raise by failing create? instead its
            # polls 500 forever -> would loop; use timeout to end it
            return await session.run_many(
                prompts, concurrency=2, api_key="k",
                base_url="https://api.devin.ai/v1", timeout_s=10, poll_initial=0,
                sleep=lambda d: asyncio.sleep(0), rng=lambda: 0.0,
                clock=_FakeClock())
        finally:
            httpx.AsyncClient = orig

    res = asyncio.run(go())
    assert in_flight["max"] <= 2
    by_eid = {r["exploit_id"]: r for r in res}
    assert by_eid["e0"]["status"] == "finished"
    assert by_eid["e2"]["status"] == "finished"
    # 'bad' kept getting 500s -> timed_out, not crash
    assert by_eid["e1"]["status"] == "timed_out"


def _FakeClock():
    t = {"v": 0.0}
    def clock():
        t["v"] += 6.0
        return t["v"]
    return clock


def test_run_many_handler_exception_marks_error():
    def handler(req):
        if req.method == "POST" and b'"boom"' in req.content:
            return httpx.Response(500)
        if req.method == "POST":
            return httpx.Response(200, json={"session_id": "s9", "url": "u",
                                             "is_new_session": True})
        return httpx.Response(200, json={"status_enum": "finished", "status": "finished",
                                         "pull_request": None})

    prompts = [("ok", {"prompt": "p", "title": "t", "tags": []}),
               ("boom", {"prompt": "boom", "title": "boom", "tags": []})]

    async def go():
        orig = httpx.AsyncClient
        try:
            httpx.AsyncClient = lambda **kw: orig(transport=httpx.MockTransport(handler), **kw)
            return await session.run_many(prompts, concurrency=2, api_key="k",
                                          base_url="https://api.devin.ai/v1",
                                          poll_initial=0, sleep=lambda d: asyncio.sleep(0),
                                          rng=lambda: 0.0)
        finally:
            httpx.AsyncClient = orig

    res = {r["exploit_id"]: r for r in asyncio.run(go())}
    assert res["ok"]["status"] == "finished"
    assert res["boom"]["status"] == "error"
    assert res["boom"]["error"]


def test_dry_run_request_writes_json(tmp_path):
    p = session.dry_run_request("abc", "PROMPT", "t", ["x"], tmp_path)
    data = json.loads(p.read_text())
    assert data["method"] == "POST"
    assert data["url"].endswith("/sessions")
    assert data["body"]["prompt"] == "PROMPT"
