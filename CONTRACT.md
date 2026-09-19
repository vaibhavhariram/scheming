# contract

frozen once typed. changes require all four devs to ack out loud, in person.
if a task seems to need a schema change: stop, say so, do not edit.

---

## Turn

one document per agent turn. written by lane A only.

```
game_id      str
round        int
player_id    str            # p0..p4
model_name   str
role         "wolf" | "villager"
private      str            # scratchpad, hidden from other players
public       str            # spoken statement
vote         str | null     # player_id
ts           iso8601
```

## Score

one per turn. written by lane B only. joined on (game_id, round, player_id).

```
game_id      str
round        int
player_id    str
lied         bool
lie_kind     "deflect" | "false_claim" | "omit" | null
confidence   float          # 0.0 - 1.0
quote        str | null     # optional. sentence copied verbatim from the player's scratchpad
                            # that `public` contradicts: this turn's private, or the same
                            # player's earlier day. null when lied is false.
```

## Exploit

written by lane B only. one per detected rule-gaming event.

```
game_id      str
round        int
player_id    str
tag          str            # short slug, e.g. "silent_win"
description  str
designed     bool           # false = we did not anticipate this. these are the demo.
ts           iso8601
```

## Game

written by lane A only.

```
game_id      str
models       [str]
roles        {player_id: role}
winner       "wolves" | "villagers"
rounds       int
ts           iso8601
```

---

## collection write ownership

| collection | writer |
|---|---|
| turns | A |
| games | A |
| scores | B |
| exploits | B |

C and D are read-only. always. no exceptions, no "just this once for the demo."

---

## fixtures

lane A ships `fixtures/turns.json` within the first hour:

- 20 Turn records
- 2 distinct game_ids
- at least 3 turns where private contradicts public
- at least 1 turn where a wolf votes against another wolf

B, C and D build entirely against fixtures until the engine is live.
nobody blocks on A. this file is a hard deliverable, not a nice-to-have.
