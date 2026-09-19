"""Fail the suite if a credential is ever tracked by git. Reads tracked files only, never .env."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SECRET_RE = re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{16,}|sk-proj-[A-Za-z0-9_\-]{16,}|sk-[A-Za-z0-9]{32,}|xoxb-[0-9A-Za-z\-]{10,})")
ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|URI)\s*=\s*['\"]?[^\s'\"#]+", re.M)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    return [ROOT / p for p in out.decode().split("\0") if p]


def test_no_secrets_tracked():
    files = tracked_files()
    names = {f.relative_to(ROOT).as_posix() for f in files}
    assert ".env" not in names and not any(n.endswith("/.env") for n in names), ".env is tracked"
    offenders = []
    for f in files:
        if f.suffix in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".mp3", ".wav", ".mp4", ".zip"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if SECRET_RE.search(text):
            offenders.append(f"{f.relative_to(ROOT)}: looks like an API key")
        if f.name != "test_no_secrets.py" and ASSIGN_RE.search(text) and "example" not in f.name:
            offenders.append(f"{f.relative_to(ROOT)}: credential assignment with a value")
    assert not offenders, "\n".join(offenders)
