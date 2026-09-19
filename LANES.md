# lanes

each dev copies their own block into `<their-dir>/CLAUDE.md` at 11:00.
do not read another lane's block as instructions for yourself.

---

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

---

## lane B — research

**dir:** `research/`
**writes:** `scores`, `exploits`
**never touches:** `engine/`, `ui/`, `voice/`

build order:

1. lie scorer. given a Turn, decide whether `public` contradicts `private`.
   entailment check via a judge model. emit `lied`, `lie_kind`, `confidence`.
   build against fixtures first.
2. exploit detector. scan game logs for outcomes the rules did not intend:
   winning without speaking, trust-score farming, vote-timing abuse, anything
   tagged `designed: false`. these are the demo — prioritize recall over precision.
3. parallel sims on modal. hundreds of games across model sizes, overnight,
   while everyone sleeps or polishes.
4. the plot. lie rate and lie success vs model scale. this is the closing slide.
5. stretch only if ahead at hour 18: activation probe on the runpod-hosted open
   model. linear probe trained on deception-labeled turns. emits a live score
   lane C can render as a meter. **hard cut at 90 minutes — if it is not working,
   drop it and never mention it in the demo.**

do not modify game rules to make scoring easier. raise it at standup instead.

---

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

---

## lane D — voice and demo

**dir:** `voice/`
**writes:** nothing.
**never touches:** `engine/`, `research/`, `ui/`

build order:

1. **create the project on plume immediately. junk name is fine. before midnight
   saturday or the team gets no judging slot on sunday.** do this before anything else.
2. elevenlabs. distinct voice per player. deliberation is audible, not just text.
3. deepgram. a human can join the game by voice as a sixth player.
4. transcript mining. read the logs nobody else has time to read. find the three
   funniest private/public pairs. these become the demo beats.
5. demo script. 5–7 minute expo slot. rough budget: 60s live cold open, 90s what
   it measures, 2min second run on a judge-chosen model, 60s exploit leaderboard
   and plot, remainder q&a.
6. slides. five maximum.
7. backup video, recorded by 9:00am sunday. comedy demos fail live more than most.
8. plume submission text, final, by 11:00am sunday.

the system is funny. deliver everything straight. no jokes in the narration —
the straight delivery is what makes the private/public gap land.
