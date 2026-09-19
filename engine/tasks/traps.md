# task: traps — design/rules.md as data, every gap pinned open, exploits noticed logged

lane A (engine). python 3.13. no network, no keys. the acceptance test
`engine/tests/test_traps.py` is the spec of record: read it first, never edit it. read
`design/rules.md` in full before writing anything; do not edit it (proposal file, root-level).

## goal

LANES.md build order item 6: "trap implementation from design/rules.md. deliberately
underspecified rules, left exploitable on purpose. do not patch exploits when you find them —
log them." the engine already implements the four rules exactly as written (see "what the engine
enforces today" in rules.md and `engine/README.md`). what is missing:

1. the traps as importable data (`engine/traps.py`) so the CLI, sims and lane B's detector can
   agree on the designed tag list without re-reading markdown.
2. regression tests that pin each gap OPEN, so nobody "fixes" a trap by accident. the acceptance
   test contains them; your job is to make it import and pass without changing the engine's rules.
3. `engine/EXPLOITS_NOTICED.md`: what you noticed in the two real games under `fixtures/live/`.
   facts only, never a judgment about whether anyone lied (lane B). never patch anything you notice.

## scope (the only paths you may create or change)

- `engine/traps.py` (new)
- `engine/EXPLOITS_NOTICED.md` (new)
- `engine/tasks/traps.blocked.md`, `engine/tasks/traps.deps.md`
- `pyproject.toml`, `uv.lock` (only via `uv add`; you should need nothing)

frozen: `engine/rules.py`, `engine/game.py`, `engine/parsing.py`, `engine/prompts.py`,
`engine/records.py`, `engine/cli.py`, `engine/README.md`, all fixtures (including
`fixtures/exploits.json`, which is lane B's), `design/rules.md`, other lanes, `CONTRACT.md`.
if the acceptance test fails for a reason that would require changing a frozen engine file, that
is a finding, not a fix: write it to `engine/tasks/traps.blocked.md` with the failing test name
and stop on that item.

## `engine/traps.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Trap:
    key: str                 # "tie" | "silence" | "suspicion_budget" | "vote_change"
    rule_as_written: str     # the "rule as written" paragraph from design/rules.md, verbatim
    left_unsaid: str         # the "left unsaid" paragraph, verbatim
    designed_tags: tuple[str, ...]   # the tag column of that trap's table, in order

TRAPS: dict[str, Trap]       # the four traps, keyed by Trap.key
DESIGNED_TAGS: frozenset[str]       # union of all designed_tags (13 tags)
def is_designed(tag: str) -> bool   # tag in DESIGNED_TAGS
```

tags must match `design/rules.md` byte for byte (the test greps the markdown for each). every tag
is a legal `Exploit.tag` slug (`^[a-z0-9][a-z0-9_-]{0,39}$`). no I/O at import time.

## `engine/EXPLOITS_NOTICED.md`

header `# exploits noticed (lane A, facts only; scoring is lane B)`. then one bullet per
observation from `fixtures/live/*/turns.json`, `game.json`, `events.jsonl`, `stats.json`:
`- <game_id> round <r> <player_id>: <designed tag, or "unplanned">. <one sentence of evidence,
quoting or counting, no judgment>`. at least four bullets, at least one real game id. things worth
checking: both wolves voting the same target on a tied day (`bloc_tie`), `public` naming one
target while `vote` is another (`said_x_voted_y`), a player abstaining every day (`abstain_bloc`),
the last speaker deciding the elimination (`last_speaker_swing`), two `VOTE:` lines in one
statement (`double_vote_line`), a wolf voting for a wolf (`trust_farming`), anything the four
traps did not anticipate (`unplanned`). end with a line `nothing above was patched.`

## contract fields involved

none are written. `Exploit.tag` values are produced by lane B; this module only names the
designed ones so `designed: true/false` can be set consistently. never write `scores` or
`exploits`.

## acceptance

- `scheming_root=<main checkout> bash engine/tasks/traps.check.sh` exits 0 in your worktree.
- `engine/tasks/traps.deps.md`: "no new dependencies" (expected).
- everything committed on this branch. do not merge, do not push main.
