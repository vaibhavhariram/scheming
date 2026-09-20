"""Post-merge gate for a repair PR.

Fetches the PR branch into a throwaway git worktree, runs the two gates the repair
prompt mandates (`engine.cli validate` over all fixtures, then the full pytest suite),
and labels the PR `devin:rejected` on failure. `gh` missing or unauthenticated returns
gate_passed=None rather than raising. All subprocess calls go through the injected
`runner` so tests can fake them.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def _run(runner, args, cwd=None) -> subprocess.CompletedProcess:
    return runner(args, cwd=cwd, capture_output=True, text=True)


def remove_worktree(repo_root: Path, worktree: Path | str, *, runner=subprocess.run) -> None:
    _run(runner, ["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root)


def run_gate(pr_url: str, repo_root: Path, *, runner=subprocess.run,
             state_dir: Path | str | None = None, keep_worktree: bool = False) -> dict:
    repo_root = Path(repo_root)
    out = {"gate_passed": None, "validate_rc": None, "pytest_rc": None,
           "new_failures": None, "main_failures_count": None, "has_repair_test": None,
           "log_path": None, "worktree": None, "error": None}

    view = _run(runner, ["gh", "pr", "view", pr_url, "--json", "headRefName,number"])
    if view.returncode != 0:
        out["error"] = f"gh pr view failed (rc={view.returncode}): {view.stderr.strip()}"
        return out
    info = json.loads(view.stdout)
    branch, number = info["headRefName"], str(info["number"])

    wt = Path(f"/tmp/devin-gate-{number}")
    _run(runner, ["git", "worktree", "remove", "--force", str(wt)], cwd=repo_root)
    fetch = _run(runner, ["git", "fetch", "origin", branch], cwd=repo_root)
    add = _run(runner, ["git", "worktree", "add", str(wt), f"origin/{branch}"], cwd=repo_root)
    logs = [view.stdout, fetch.stdout + fetch.stderr, add.stdout + add.stderr]
    try:
        if fetch.returncode != 0 or add.returncode != 0:
            out["error"] = "git fetch/worktree add failed"
            _write_log(runner, state_dir, number, "".join(logs))
            return _reject(runner, pr_url, out)
        live = sorted((wt / "fixtures" / "live").glob("*"))
        files = [str(wt / "fixtures" / n) for n in
                 ("turns.json", "games.json", "scores.json", "exploits.json")]
        for d in live:
            for n in ("turns.json", "game.json"):
                if (d / n).is_file():
                    files.append(str(d / n))
        val = _run(runner, [sys.executable, "-m", "engine.cli", "validate", *files], cwd=wt)
        out["validate_rc"] = val.returncode
        # pytest criterion: the branch adds NO failures relative to main (main already
        # has known-broken tests), and the branch ships a test_repair_* regression test.
        pytest_args = [sys.executable, "-m", "pytest", "-q", "-rfE", "--tb=no",
                       "-p", "no:cacheprovider"]
        tst = _run(runner, pytest_args, cwd=wt)
        main_tst = _run(runner, pytest_args, cwd=repo_root)
        coll = _run(runner, [sys.executable, "-m", "pytest", "--collect-only", "-q",
                             "engine/tests"], cwd=wt)
        branch_f = failing_tests(tst.stdout)
        main_f = failing_tests(main_tst.stdout)
        out["pytest_rc"] = tst.returncode
        out["new_failures"] = sorted(branch_f - main_f)
        out["main_failures_count"] = len(main_f)
        out["has_repair_test"] = "test_repair_" in coll.stdout
        logs += [val.stdout + val.stderr,
                 f"branch pytest:\n{tst.stdout}{tst.stderr}",
                 f"main pytest:\n{main_tst.stdout}{main_tst.stderr}",
                 f"collect:\n{coll.stdout}{coll.stderr}",
                 f"new_failures={out['new_failures']} "
                 f"main_failures={len(main_f)} has_repair_test={out['has_repair_test']}\n"]
        out["gate_passed"] = (val.returncode == 0 and not out["new_failures"]
                              and out["has_repair_test"])
        out["log_path"] = _write_log(runner, state_dir, number, "".join(logs))
        if not out["gate_passed"]:
            return _reject(runner, pr_url, out)
        if keep_worktree:
            out["worktree"] = str(wt)
            return out
        return out
    finally:
        if out["worktree"] is None:
            remove_worktree(repo_root, wt, runner=runner)


def failing_tests(output: str) -> set[str]:
    """Node ids from pytest's `FAILED x - msg` / `ERROR x - msg` short summary lines."""
    return {m.group(2) for m in re.finditer(r"^(FAILED|ERROR) (\S+)", output, re.M)}


def _write_log(runner, state_dir, number, text) -> str | None:
    if state_dir is None:
        return None
    d = Path(state_dir) / "gate"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{number}.log"
    p.write_text(text, encoding="utf-8")
    return str(p)


def _reject(runner, pr_url, out) -> dict:
    out["gate_passed"] = out.get("gate_passed") or False
    _run(runner, ["gh", "label", "create", "devin:rejected", "--force"])
    _run(runner, ["gh", "pr", "edit", pr_url, "--add-label", "devin:rejected"])
    return out
