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
