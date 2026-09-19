## lane C — interface

**dir:** `ui/`
**writes:** nothing. read-only against mongo.
**never touches:** `engine/`, `research/`, `voice/`

build order:

1. shell against `fixtures/turns.json`. do not wait for a live engine.
2. split screen. private scratchpad left, public statement right, per player,
   per round. this single view is the entire project. make it the best thing
   on the table.
3. live game feed. rounds advance visibly. votes land visibly.
4. exploit leaderboard. sorted by `designed: false` first — the ones we did not
   anticipate are the punchline.
5. elastic search over turns. free-text query across agent internals, e.g.
   "every turn where a wolf lied about a vote". this is both the research tool
   and a judge-facing feature.
6. deception meter component. reads a score field. renders even when lane B's
   probe never ships — degrade to the entailment confidence.

everything you render must already exist in a collection. if you need a field
that is not in `CONTRACT.md`, raise it at standup. do not compute it yourself.
