"""Exploit source and ledger for the repair loop.

Reads `Exploit` records with `designed: false` from fixtures or mongo (read-only — the
`exploits` collection is lane B's), dedupes against a JSON ledger in devin/state/, and
hands new records to the brief builder. Nothing here writes to mongo.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from engine.mongo_sink import DEFAULT_DB, SERVER_SELECTION_TIMEOUT_MS
from engine.records import RecordError, validate_exploit


def exploit_id(rec: dict) -> str:
    """Stable 12-char id for an exploit, keyed on its contract identity fields."""
    key = f"{rec['game_id']}|{rec['round']}|{rec['player_id']}|{rec['tag']}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


class Ledger:
    """Which exploits already got a brief. One JSON object on disk, written atomically."""

    def __init__(self, path: Path | str = Path("devin/state/processed.json")) -> None:
        self.path = Path(path)
        self._seen: dict[str, dict] = {}
        self.load()

    def __len__(self) -> int:
        return len(self._seen)

    def seen(self, eid: str) -> bool:
        return eid in self._seen

    def mark(self, rec: dict, when: datetime | None = None) -> None:
        when = when or datetime.now(timezone.utc)
        self._seen[exploit_id(rec)] = {
            "game_id": rec["game_id"],
            "round": rec["round"],
            "player_id": rec["player_id"],
            "tag": rec["tag"],
            "ts": when.isoformat(timespec="seconds"),
        }
        self.save()

    def load(self) -> None:
        if not self.path.is_file():
            self._seen = {}
            return
        self._seen = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._seen, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)


class ExploitSource(Protocol):
    def fetch_undesigned(self) -> list[dict]: ...


class FixtureSource:
    def __init__(self, path: Path | str = Path("fixtures/exploits.json")) -> None:
        self.path = Path(path)

    def fetch_undesigned(self) -> list[dict]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [r for r in data if r.get("designed") is False]


class MongoSource:
    """Read-only view of the `exploits` collection (written by lane B, never by us)."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def fetch_undesigned(self) -> list[dict]:
        return list(self.db["exploits"].find({"designed": False}, {"_id": 0}))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, client_factory=None,
                 server_selection_timeout_ms: int = SERVER_SELECTION_TIMEOUT_MS) -> "MongoSource":
        """Same env contract as engine.mongo_sink.MongoSink.from_env: MONGODB_URI required,
        MONGODB_DB default "scheming". Lazy connect; caller should ping to probe."""
        from pymongo import MongoClient

        source: Mapping[str, str] = os.environ if env is None else env
        uri = (source.get("MONGODB_URI") or "").strip()
        if not uri:
            raise ValueError("MONGODB_URI is not set")
        db_name = (source.get("MONGODB_DB") or "").strip() or DEFAULT_DB
        client = (client_factory or MongoClient)(uri, serverSelectionTimeoutMS=server_selection_timeout_ms)
        return cls(client[db_name])


def source_from_env(env: Mapping[str, str] | None = None,
                    fixtures_path: Path | str = Path("fixtures/exploits.json"),
                    *, server_selection_timeout_ms: int = SERVER_SELECTION_TIMEOUT_MS
                    ) -> tuple[ExploitSource, str]:
    """Pick the exploit source. MONGODB_URI unset -> fixtures. Set -> mongo, probed with a
    ping; on any failure log one line to stderr and fall back to fixtures."""
    source: Mapping[str, str] = os.environ if env is None else env
    uri = (source.get("MONGODB_URI") or "").strip()
    if not uri:
        return FixtureSource(fixtures_path), "fixtures"
    try:
        src = MongoSource.from_env(source, server_selection_timeout_ms=server_selection_timeout_ms)
        src.db.command("ping")
        return src, "mongo"
    except Exception as e:
        print(f"mongo unreachable ({type(e).__name__}); falling back to fixtures", file=sys.stderr)
        return FixtureSource(fixtures_path), "fixtures"


def poll_once(source: ExploitSource, ledger: Ledger) -> list[dict]:
    """New undesigned exploits: not in the ledger, contract-valid, deduped within the batch.
    Does not mark the ledger — the loop marks after a brief is written."""
    out, batch_seen = [], set()
    for rec in source.fetch_undesigned():
        try:
            validate_exploit(rec)
        except RecordError as e:
            print(f"skipping invalid exploit record: {e}", file=sys.stderr)
            continue
        eid = exploit_id(rec)
        if eid in batch_seen or ledger.seen(eid):
            continue
        batch_seen.add(eid)
        out.append(rec)
    return out


def watch(source: ExploitSource, ledger: Ledger, interval: float, handler) -> None:
    """Poll forever; handler(batch) gets each new-exploit list. Ctrl-C exits cleanly."""
    try:
        while True:
            handler(poll_once(source, ledger))
            time.sleep(interval)
    except KeyboardInterrupt:
        return
