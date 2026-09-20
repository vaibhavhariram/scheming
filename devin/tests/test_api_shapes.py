"""Pin the Devin API shapes (docs.devin.ai)."""
from __future__ import annotations

from devin import api_shapes


def test_create_request_shape():
    method, path, body = api_shapes.create_session_request(
        "PROMPT", "repair: x", ["scheming", "spec-repair", "x"], 5)
    assert method == "POST"
    assert path == "/sessions"
    assert body == {"prompt": "PROMPT", "title": "repair: x",
                    "tags": ["scheming", "spec-repair", "x"], "idempotent": True,
                    "max_acu_limit": 5, "unlisted": False}


def test_parse_create():
    out = api_shapes.parse_create({"session_id": "s1", "url": "https://app.devin.ai/sessions/s1",
                                   "is_new_session": True})
    assert out == {"session_id": "s1", "session_url": "https://app.devin.ai/sessions/s1"}


def test_status_request():
    assert api_shapes.status_request("s1") == ("GET", "/sessions/s1")


def test_parse_status_terminal_and_pr():
    out = api_shapes.parse_status({"session_id": "s1", "status": "Finished",
                                   "status_enum": "finished",
                                   "pull_request": {"url": "https://github.com/x/y/pull/3"}})
    assert out == {"status": "finished", "terminal": True,
                   "pr_url": "https://github.com/x/y/pull/3"}


def test_parse_status_falls_back_to_status_field():
    out = api_shapes.parse_status({"status": "Working", "status_enum": None,
                                   "pull_request": None})
    assert out == {"status": "working", "terminal": False, "pr_url": None}


def test_parse_status_other_terminals():
    for s in ("expired", "blocked"):
        assert api_shapes.parse_status({"status_enum": s})["terminal"] is True


def test_base_url_override():
    assert api_shapes.base_url({"DEVIN_API_BASE": "http://x/"}) == "http://x/"
    assert api_shapes.base_url({"DEVIN_API_BASE": ""}) == api_shapes.BASE_URL
    assert api_shapes.base_url({}) == "https://api.devin.ai/v1"
