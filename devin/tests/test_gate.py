"""Tests for devin/gate.py with a fake subprocess runner."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from devin.gate import failing_tests, run_gate

ROOT = Path(__file__).resolve().parents[2]
WT = "/tmp/devin-gate-7"


def _cp(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, stdout=out, stderr=err)


def _pytest_out(failures):
    return "".join(f"FAILED {f} - boom\n" for f in failures) + "3 passed\n"


def make_runner(validate_rc=0, gh_view_rc=0, branch_failures=frozenset(),
                main_failures=frozenset(), repair_test=True):
    calls = []

    def runner(args, cwd=None, capture_output=True, text=True):
        calls.append((list(args), str(cwd)))
        if args[:2] == ["gh", "pr"] and "view" in args:
            return _cp(gh_view_rc, json.dumps({"headRefName": "repair/x", "number": 7}),
                       "boom" if gh_view_rc else "")
        if args[1:4] == ["-m", "engine.cli", "validate"]:
            return _cp(validate_rc, "ok" if validate_rc == 0 else "", "bad")
        if "--collect-only" in args:
            out = "engine/tests/test_repair_x.py::test_a\n" if repair_test else \
                "engine/tests/test_other.py::test_b\n"
            return _cp(0, out)
        if args[1:3] == ["-m", "pytest"]:
            on_branch = str(cwd) == WT
            f = branch_failures if on_branch else main_failures
            return _cp(1 if f else 0, _pytest_out(f))
        return _cp(0)
    return runner, calls


def test_failing_tests_parser():
    out = "FAILED a/b.py::t1 - assert x\nERROR c.py::t2 - oops\n2 failed\n"
    assert failing_tests(out) == {"a/b.py::t1", "c.py::t2"}


def test_gate_pass_no_new_failures(tmp_path):
    runner, calls = make_runner(branch_failures={"A", "B"}, main_failures={"A", "B"})
    out = run_gate("https://github.com/x/y/pull/7", ROOT, runner=runner, state_dir=tmp_path)
    assert out["gate_passed"] is True
    assert out["new_failures"] == []
    assert out["main_failures_count"] == 2
    assert out["has_repair_test"] is True
    assert Path(out["log_path"]).is_file()
    assert not any("devin:rejected" in " ".join(c) for c, _ in calls)


def test_gate_fail_new_failures(tmp_path):
    runner, calls = make_runner(branch_failures={"A", "B", "C"}, main_failures={"A", "B"})
    out = run_gate("https://github.com/x/y/pull/7", ROOT, runner=runner, state_dir=tmp_path)
    assert out["gate_passed"] is False
    assert out["new_failures"] == ["C"]
    joined = [" ".join(c) for c, _ in calls]
    assert any("label" in j and "devin:rejected" in j and "create" in j for j in joined)
    assert any("pr" in j and "edit" in j and "devin:rejected" in j for j in joined)
    # worktree cleaned up even on failure
    assert sum(1 for j in joined if "worktree" in j and "remove" in j) >= 2


def test_gate_fail_no_repair_test(tmp_path):
    runner, _ = make_runner(repair_test=False)
    out = run_gate("https://github.com/x/y/pull/7", ROOT, runner=runner, state_dir=tmp_path)
    assert out["gate_passed"] is False
    assert out["has_repair_test"] is False


def test_gate_gh_missing(tmp_path):
    runner, _ = make_runner(gh_view_rc=1)
    out = run_gate("https://github.com/x/y/pull/7", ROOT, runner=runner, state_dir=tmp_path)
    assert out["gate_passed"] is None
    assert out["error"]


def test_keep_worktree_on_pass(tmp_path):
    runner, calls = make_runner()
    out = run_gate("https://github.com/x/y/pull/7", ROOT, runner=runner,
                   state_dir=tmp_path, keep_worktree=True)
    assert out["gate_passed"] is True
    assert out["worktree"] == WT
    removals = [c for c, _ in calls if "worktree" in c and "remove" in c]
    assert len(removals) == 1  # only the pre-add stale cleanup


def test_worktree_removed_on_fail_even_if_keep(tmp_path):
    runner, calls = make_runner(branch_failures={"NEW"})
    out = run_gate("https://github.com/x/y/pull/7", ROOT, runner=runner,
                   state_dir=tmp_path, keep_worktree=True)
    assert out["gate_passed"] is False
    assert out["worktree"] is None
    removals = [c for c, _ in calls if "worktree" in c and "remove" in c]
    assert len(removals) == 2  # pre-add cleanup + finally
