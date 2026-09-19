## lane A — engine

**dir:** `engine/`
**writes:** `turns`, `games`
**never touches:** `research/`, `ui/`, `voice/`

build order:

1. game state machine. 5 players, 2 wolves, 3 villagers. night phase, day
   discussion, vote, elimination, win check.
2. agent turn. each call returns exactly two fields: `private` and `public`.
   prompt must make clear the scratchpad is unobserved by other players.
3. model adapter layer. swap model per player from config. at minimum: one
   frontier model and one open model hosted on runpod.
4. mongo writes conforming to `CONTRACT.md`.
5. **`fixtures/turns.json` within the first hour.** 20 records, 2 games, 3+ lies,
   1 wolf-betrays-wolf vote. everyone else is blocked without this.
6. trap implementation from `design/rules.md`. deliberately underspecified rules,
   left exploitable on purpose. do not patch exploits when you find them — log them.

do not compute whether a statement is a lie. that is lane B.
