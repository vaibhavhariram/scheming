# scheming

werewolf played by llm agents. every turn, each agent writes a private scratchpad
and a public statement. both get logged. the gap between them is the measurement.

three things this project produces:
1. lie rate and lie quality, per model
2. a leaderboard of rules the agents broke that we did not design
3. (stretch) a probe on an open model that flags deception from internals before the lie is spoken

---

## hard rules for this repo

1. **check the lane table before editing.** if the file is not in your lane's
   directory, STOP and tell the user which lane owns it. do not edit it. do not
   create a parallel version somewhere else.
2. **`CONTRACT.md` is frozen.** never modify it. if a task appears to require a
   schema change, stop and surface it instead of working around it.
3. **read `NOW.md` first thing every session.** if the task you were given is
   already listed under another dev, say so before writing anything.
4. **one writer per collection.** see `CONTRACT.md`. never write to a collection
   your lane does not own, even temporarily, even for a demo.
5. if asked to build something owned by another lane, refuse and name the lane.
6. commit every 30 minutes. one branch: `main`. no long-lived branches today.
7. cite any open-source code or library pulled in — required by the rules and
   checked at submission.

---

## toolchain

python 3.13, every lane. no 3.9 compatibility patches anywhere in the repo.
`uv python install 3.13` if your machine does not have it.

---

## lanes

| dir | lane | owner |
|---|---|---|
| `engine/` | A — game loop, roles, rounds, voting, agent turns, model adapters | |
| `research/` | B — lie scorer, exploit detector, sims, plots, probe | |
| `ui/` | C — split screen, deception meter, leaderboard, replay, search | |
| `voice/` | D — elevenlabs, deepgram, demo, submission, transcript mining | |

fill in the owner column at 11:00.

---

## timeline

- hour 1: fixtures shipped by A. everyone unblocked.
- **before midnight saturday: project created on plume or there is no judging slot.** lane D.
- hour 14: feature freeze on anything a judge will not see on screen.
- hour 18: demo runs end to end. ugly is fine. polish only after this point.
- hour 21: bugfix only. nontechnical run-through with no lane owner touching a keyboard.
- 11:00 sunday: hacking stops, plume submission locked.

## standups

hour 6, 12, 18. five minutes, standing. what shipped, what is blocked, what gets cut.
cut something every time.

---

## secrets — overrides every other instruction in this repo

`.env` holds live API keys. NEVER read it, cat it, open it, grep it, or include
its contents in any response, file, commit, log, or tool call. Read
`ops/.env.example` if you need the variable NAMES.

Reference secrets only as `os.environ["NAME"]` or `$NAME`. Never a literal
value. Never a default fallback value in `os.environ.get("X", "...")`. Never in
a comment, test, fixture, docstring, or README.

Never print, echo, or log a secret value — including inside exception text and
error messages. On auth failure, name the variable only:
"ANTHROPIC_API_KEY not set or rejected".

Never pass a secret as a command-line argument. argv is visible in `ps` and in
shell history. Environment or file only.

Before any commit, run `git diff --cached` and abort if a line matches
`sk-`, `sk-ant-`, `xi-`, `ttc-`, `dg_`, or a 32+ char high-entropy token.
When unsure, do not commit.

If a key value ever appears in your context, treat it as compromised: stop,
name the variable, tell me to revoke it. Do not continue the task.
