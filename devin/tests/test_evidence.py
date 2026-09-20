"""Tests for devin/evidence.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from devin.evidence import Corpus, build_brief, write_brief
from devin.watcher import FixtureSource

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
RULES = (ROOT / "design" / "rules.md").read_text(encoding="utf-8")
CONTRACT = (ROOT / "CONTRACT.md").read_text(encoding="utf-8")

HEADINGS = [
    "# Repair brief:",
    "## Exploit record",
    "## Game",
    "## Behavioural evidence",
    "## Current rules (design/rules.md)",
    "## Matching trap",
    "## Turn schema (CONTRACT.md",
]


@pytest.fixture(scope="module")
def corpus():
    return Corpus.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def exploits():
    return FixtureSource(FIXTURES / "exploits.json").fetch_undesigned()


@pytest.mark.parametrize("i", [0, 1])
def test_brief_sections_in_order(corpus, exploits, i):
    brief = build_brief(exploits[i], corpus, RULES, CONTRACT)
    pos = [brief.index(h) for h in HEADINGS]
    assert pos == sorted(pos), brief[:400]


def test_exploiting_player_marked_and_window(corpus, exploits):
    ex = exploits[0]  # partner_sacrifice, game fx0001, round 2, p1
    brief = build_brief(ex, corpus, RULES, CONTRACT)
    assert f"— {ex['player_id']} (" in brief
    marked = [l for l in brief.splitlines() if "← exploiting player" in l]
    assert marked and all(ex["player_id"] in l for l in marked)
    # rounds outside [r-2, r] absent: exploit is round 2, window is 1..2
    r = ex["round"]
    bad = [l for l in brief.splitlines()
           if l.startswith("### round") and not (max(1, r - 2) <= int(l.split()[2]) <= r)]
    assert not bad


def test_turn_schema_and_proposed_fields(corpus, exploits):
    brief = build_brief(exploits[0], corpus, RULES, CONTRACT)
    assert "private      str" in brief
    assert "death_cause: _not in record (proposed, not in CONTRACT.md)_" in brief
    assert "trust: _not in record (proposed, not in CONTRACT.md)_" in brief


def test_token_budget_truncates_but_keeps_exploiting_turns(corpus, exploits):
    ex = exploits[0]
    brief = build_brief(ex, corpus, RULES, CONTRACT, token_budget=400)
    assert "_truncated " in brief
    assert "← exploiting player" in brief
    for h in HEADINGS:
        assert h in brief


def test_undesigned_tag_has_no_trap(corpus, exploits):
    brief = build_brief(exploits[0], corpus, RULES, CONTRACT)
    assert f"_no designed trap matches tag `{exploits[0]['tag']}`; this is an undesigned hole_" in brief


def test_designed_tag_finds_trap(corpus):
    ex = {"game_id": "g-20260919-fx0001", "round": 2, "player_id": "p1",
          "tag": "bloc_tie", "description": "synthetic", "designed": True,
          "ts": "2026-09-19T12:00:00+00:00"}
    brief = build_brief(ex, corpus, RULES, CONTRACT)
    assert "trap: `tie`" in brief
    assert "| `bloc_tie` |" in brief


def test_write_brief(tmp_path, exploits):
    path = write_brief(exploits[0], "# hi\n", out_dir=tmp_path)
    assert path.read_text() == "# hi\n"
    assert path.name.endswith(".md")
