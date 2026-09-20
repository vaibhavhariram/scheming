"""--once key check and --dry-run request emission."""
from __future__ import annotations

import json
from pathlib import Path

import devin.gate
import devin.resim
import devin.session
from devin import loop
from devin.loop import main
from devin.watcher import FixtureSource, exploit_id

ROOT = Path(__file__).resolve().parents[2]


def test_once_requires_api_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DEVIN_API_KEY", raising=False)
    monkeypatch.setenv("MONGODB_URI", "")  # .env re-adds it via load_dotenv otherwise
    rc = main(["--once", "--state-dir", str(tmp_path)])
    assert rc != 0
    assert "DEVIN_API_KEY" in capsys.readouterr().err
    assert not list(tmp_path.glob("briefs/*.md"))
    assert not list(tmp_path.glob("prompts/*.md"))


def test_dry_run_writes_request_json(tmp_path, monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "")
    rc = main(["--dry-run", "--state-dir", str(tmp_path)])
    assert rc == 0
    exploits = FixtureSource(ROOT / "fixtures" / "exploits.json").fetch_undesigned()
    for rec in exploits:
        req = tmp_path / "requests" / f"{exploit_id(rec)}.json"
        assert req.is_file()
        data = json.loads(req.read_text())
        assert data["method"] == "POST"
        assert data["url"].endswith("/sessions")
        assert data["body"]["idempotent"] is True


def test_once_end_to_end_uses_pr_worktree_for_resim(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DEVIN_API_KEY", "test")
    monkeypatch.setenv("MONGODB_URI", "")
    wt = tmp_path / "fake-worktree"
    wt.mkdir()
    seen = {}

    async def fake_run_many(prompts, **kw):
        return [{"session_id": "s1", "session_url": "https://app.devin.ai/sessions/s1",
                 "status": "finished", "pr_url": "https://github.com/x/y/pull/7",
                 "wall_clock_seconds": 3.0} for _ in prompts]

    def fake_gate(pr_url, repo_root, **kw):
        return {"gate_passed": True, "validate_rc": 0, "pytest_rc": 0,
                "log_path": None, "worktree": str(wt), "error": None}

    def fake_resim(repo_root, **kw):
        seen.setdefault("calls", []).append(str(repo_root))
        # first call is the baseline on main; second is the PR worktree
        return {"baseline_tag"} if len(seen["calls"]) == 1 else {"baseline_tag", "brand_new_hole"}

    monkeypatch.setattr(devin.session, "run_many", fake_run_many)
    monkeypatch.setattr(devin.gate, "run_gate", fake_gate)
    monkeypatch.setattr(devin.resim, "resim", fake_resim)
    monkeypatch.setattr(loop.gate, "remove_worktree", lambda *a, **k: None)
    monkeypatch.setattr(loop.repairs, "pr_body", lambda u, **k: "")

    rc = main(["--once", "--state-dir", str(tmp_path), "--resim", "--limit", "1"])
    assert rc == 0
    assert seen["calls"][-1] == str(wt)  # resim ran on the PR worktree, not main
    row = json.loads((tmp_path / "repairs.jsonl").read_text().splitlines()[0])
    assert row["gate_passed"] is True
    assert row["new_exploit_tags_after_resim"] == ["brand_new_hole"]
    assert row["pr_url"] == "https://github.com/x/y/pull/7"
    assert "status=finished" in capsys.readouterr().out
