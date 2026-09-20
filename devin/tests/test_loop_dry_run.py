"""Dry-run end-to-end test for devin/loop.py."""
from __future__ import annotations

import json
from pathlib import Path

from devin.loop import main
from devin.watcher import FixtureSource, exploit_id

ROOT = Path(__file__).resolve().parents[2]


def test_dry_run_writes_briefs_and_prompts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MONGODB_URI", "")  # keep .env's real URI out of the test
    rc = main(["--dry-run", "--state-dir", str(tmp_path)])
    assert rc == 0
    exploits = FixtureSource(ROOT / "fixtures" / "exploits.json").fetch_undesigned()
    out = capsys.readouterr().out
    for rec in exploits:
        eid = exploit_id(rec)
        brief = tmp_path / "briefs" / f"{eid}.md"
        prompt = tmp_path / "prompts" / f"{eid}.md"
        assert brief.is_file() and prompt.is_file()
        text = prompt.read_text()
        assert "# Repair task: close one undesigned rule hole" in text
        assert brief.read_text() in text
        assert f"dry-run  {eid}  {rec['tag']}" in out
    assert json.loads((tmp_path / "processed.json").read_text())

    # DEVIN_API_BASE flows into the written request
    monkeypatch.setenv("DEVIN_API_BASE", "https://example.test/v1")
    (tmp_path / "processed.json").unlink()
    rc = main(["--dry-run", "--state-dir", str(tmp_path)])
    assert rc == 0
    req = json.loads((tmp_path / "requests" / f"{exploit_id(exploits[0])}.json").read_text())
    assert req["url"].startswith("https://example.test/v1")

    # second run: ledger dedupe -> nothing new
    rc = main(["--dry-run", "--state-dir", str(tmp_path)])
    assert rc == 0
    assert "done: 0 processed" in capsys.readouterr().out
