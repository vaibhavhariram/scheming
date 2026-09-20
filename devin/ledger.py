"""repairs.jsonl — one row per dispatched repair attempt.

Distinct from watcher.Ledger (which dedupes exploits). This is the audit trail a human
reads: which exploit, which session, which PR, what the PR claimed, whether the gate
passed, and which exploit tags a resim still produces.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROW_KEYS = ("exploit_tag", "game_id", "round", "player_id", "devin_session_url",
            "pr_url", "rule_before", "rule_after", "test_name", "gate_passed",
            "wall_clock_seconds", "new_exploit_tags_after_resim", "ts")

_SECTION_RE = re.compile(r"^## (Rule before|Rule after|Test)\s*$", re.M)
_TEST_RE = re.compile(r"test_[a-z0-9_]+")


def append_repair(path: Path | str, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {k: row.get(k) for k in ROW_KEYS}
    rec["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def extract_pr_fields(pr_body: str) -> dict:
    """Pull rule_before / rule_after / test_name out of the mandated PR body sections."""
    out = {"rule_before": None, "rule_after": None, "test_name": None}
    marks = [(m.group(1), m.end()) for m in _SECTION_RE.finditer(pr_body)]
    for i, (name, start) in enumerate(marks):
        end = pr_body.find("\n## ", start)
        section = pr_body[start:end if end != -1 else len(pr_body)].strip()
        if name == "Rule before":
            out["rule_before"] = section or None
        elif name == "Rule after":
            out["rule_after"] = section or None
        elif name == "Test":
            m = _TEST_RE.search(section)
            out["test_name"] = m.group(0) if m else None
    return out


def pr_body(pr_url: str, runner=subprocess.run) -> str:
    try:
        r = runner(["gh", "pr", "view", pr_url, "--json", "body", "-q", ".body"],
                   capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""
