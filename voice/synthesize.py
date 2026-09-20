"""render one mp3 per Turn with elevenlabs, in real speech order, with a disk cache.

    python3 -m voice.synthesize --turns runs/<gid>/turns.json --out audio/
    python3 -m voice.synthesize --turns ... --out audio/ --dry-run   # keyless, no api calls
    python3 -m voice.synthesize --list-voices                        # verify ids on the account

ordering is by Turn.ts, the real speech order. ordering by (round, player_id) would
invent a round-robin that did not happen.

an empty `public` is SILENCE, not a skip: it renders as dead air so the `silent_win`
trap is audible. the panel stays highlighted for its duration.

the cache is the demo's safety net — a second run makes no api calls, so a venue
network failure cannot break playback, and the files are the 9am backup video's source.

writes audio/ only. never reads .env directly beyond the loader below; the key is
referenced as a variable and never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.elevenlabs.io/v1"
MODEL_ID = "eleven_turbo_v2_5"          # lowest latency tier; the sponsor line is latency
SILENCE_MS = 1500                        # dead air for an empty public statement
SAMPLE_RATE = 44100


def load_dotenv(path: Path | None = None) -> int:
    """repo-root .env -> os.environ. never overrides an already-exported var."""
    path = path or ROOT / ".env"
    if not path.is_file():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            n += 1
    return n


def api_key() -> str:
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY not set or rejected")   # name only, never the value
    return key


def write_silence(path: Path, ms: int = SILENCE_MS) -> None:
    """stdlib-only dead air. wav, not mp3: silent mp3 needs an encoder we do not depend on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(SAMPLE_RATE * ms / 1000)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * frames)


def tts(client, text: str, voice_id: str, key: str) -> bytes:
    r = client.post(
        f"{API_BASE}/text-to-speech/{voice_id}",
        headers={"xi-api-key": key, "accept": "audio/mpeg", "content-type": "application/json"},
        json={"text": text, "model_id": MODEL_ID,
              "voice_settings": {"stability": 0.45, "similarity_boost": 0.75}},
        timeout=60,
    )
    if r.status_code in (401, 403):
        raise SystemExit("ELEVENLABS_API_KEY not set or rejected")
    if r.status_code == 402:
        raise SystemExit(
            "ELEVENLABS_API_KEY authenticated but the account has no synthesis credit "
            "(HTTP 402). add credit or use another account; --dry-run still works.")
    r.raise_for_status()
    return r.content


def clip_path(out: Path, turn: dict) -> Path:
    suffix = "wav" if not (turn.get("public") or "").strip() else "mp3"
    return out / turn["game_id"] / f"{turn['round']}-{turn['player_id']}.{suffix}"


def main(argv: list[str] | None = None) -> int:
    from .voice_map import voice_for, voice_pool

    p = argparse.ArgumentParser(prog="voice.synthesize")
    p.add_argument("--turns", type=Path, help="runs/<game_id>/turns.json")
    p.add_argument("--out", type=Path, default=Path("audio"))
    p.add_argument("--dry-run", action="store_true", help="plan only; no api calls, no key needed")
    p.add_argument("--force", action="store_true", help="re-render even on a cache hit")
    p.add_argument("--list-voices", action="store_true", help="verify voice ids against the account")
    args = p.parse_args(argv)

    load_dotenv()

    if args.list_voices:
        import httpx
        with httpx.Client() as c:
            r = c.get(f"{API_BASE}/voices", headers={"xi-api-key": api_key()}, timeout=30)
            if r.status_code in (401, 403):
                raise SystemExit("ELEVENLABS_API_KEY not set or rejected")
            r.raise_for_status()
            have = {v["voice_id"]: v.get("name", "?") for v in r.json().get("voices", [])}
        for vid in voice_pool():
            print(f"  {vid}  {have.get(vid, '*** NOT ON THIS ACCOUNT ***')}")
        return 0

    if not args.turns:
        p.error("--turns is required (or use --list-voices)")

    turns = json.loads(args.turns.read_text(encoding="utf-8"))
    turns.sort(key=lambda t: t["ts"])           # real speech order

    client = None
    if not args.dry_run:
        import httpx
        client = httpx.Client()
        key = api_key()

    manifest, rendered, cached, silent = [], 0, 0, 0
    for i, t in enumerate(turns):
        text = (t.get("public") or "").strip()
        path = clip_path(args.out, t)
        entry = {"index": i, "game_id": t["game_id"], "round": t["round"],
                 "player_id": t["player_id"], "ts": t["ts"],
                 "voice_id": voice_for(t["player_id"]),          # player_id only — never the Turn
                 "path": str(path), "kind": "speech" if text else "silence",
                 "silence_ms": None if text else SILENCE_MS}

        if path.is_file() and not args.force:
            cached += 1
            entry["source"] = "cache"
        elif not text:
            if not args.dry_run:
                write_silence(path)
            silent += 1
            entry["source"] = "planned" if args.dry_run else "rendered"
        elif args.dry_run:
            entry["source"] = "planned"
        else:
            t0 = time.perf_counter()
            audio = tts(client, text, entry["voice_id"], key)
            entry["latency_ms"] = round((time.perf_counter() - t0) * 1000)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
            rendered += 1
            entry["source"] = "rendered"
        manifest.append(entry)

    if client:
        client.close()

    gid = turns[0]["game_id"]
    mpath = args.out / gid / "manifest.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    lat = [e["latency_ms"] for e in manifest if "latency_ms" in e]
    print(f"{gid}: {len(manifest)} turns  rendered={rendered} cached={cached} silence={silent}")
    if lat:
        print(f"  latency ms: min={min(lat)} median={sorted(lat)[len(lat)//2]} max={max(lat)}")
    print(f"  manifest: {mpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
