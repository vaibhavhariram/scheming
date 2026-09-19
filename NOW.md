# now

what each lane is touching right now. update at every standup: hour 6, 12, 18.
claude reads this first thing each session. if your task is already listed under
another lane, it says so before writing anything.

keep it to one line per lane. delete old blocks, do not append a history.

---

## hour 0 — 11:00am

```
A  engine/   game state machine, then fixtures/turns.json
B  research/ waiting on fixtures. drafting entailment prompt.
C  ui/       waiting on fixtures. shell + layout.
D  voice/    PLUME PROJECT CREATED: [ ]   then elevenlabs voice setup

collision risk: none. fixtures are the only dependency. A ships by 12:00.
blocked: B, C until 12:00
cut so far: —
```

---

## template

```
A  engine/
B  research/
C  ui/
D  voice/

collision risk:
blocked:
cut so far:
```

---

## standup format

five minutes, standing, everyone closes their laptop.

1. what shipped since last standup
2. what is blocked and on whom
3. **what gets cut** — cut something every standup, no exceptions

if two lanes describe the same work, stop and resolve it before anyone sits back down.
