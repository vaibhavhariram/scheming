"""Tests for devin/ledger.py."""
from __future__ import annotations

import json
import subprocess

from devin.ledger import ROW_KEYS, append_repair, extract_pr_fields, pr_body

BODY = """## Exploit tag
foo, g-1, r2, p1
## Rule before
a tie means nobody is eliminated.
## Rule after
ties now run off once.
## Evidence
"knew the gap"
## Test
test_repair_foo_blocks_it and output
## Files changed
- engine/rules.py
"""


def test_extract_pr_fields():
    out = extract_pr_fields(BODY)
    assert out["rule_before"] == "a tie means nobody is eliminated."
    assert out["rule_after"] == "ties now run off once."
    assert out["test_name"] == "test_repair_foo_blocks_it"


def test_extract_pr_fields_missing():
    assert extract_pr_fields("") == {"rule_before": None, "rule_after": None,
                                     "test_name": None}


def test_append_repair_row_keys(tmp_path):
    path = tmp_path / "repairs.jsonl"
    append_repair(path, {"exploit_tag": "t", "game_id": "g", "round": 2,
                         "player_id": "p1", "pr_url": None, "gate_passed": None,
                         "extra_ignored": "x"})
    row = json.loads(path.read_text().splitlines()[0])
    assert list(row.keys()) == list(ROW_KEYS)
    assert len(row) == 13
    assert row["exploit_tag"] == "t" and row["pr_url"] is None and row["ts"]


def test_pr_body_failure_returns_empty():
    def bad(*a, **k):
        return subprocess.CompletedProcess([], 1, "", "no gh")
    assert pr_body("u", runner=bad) == ""
