# now

what each lane is touching right now. update at every standup: hour 6, 12, 18.
claude reads this first thing each session. if your task is already listed under
another lane, it says so before writing anything.

keep it to one line per lane. delete old blocks, do not append a history.

---

## hour 5 — 16:30

```
A  engine/   live run + traps from design/rules.md, then ui alongside C
B  research/ scorer on real turns → exploit detector → cost rollup
C  ui/       split screen on real data (reassign if not typing by 16:40)
D  voice/    PLUME CREATED: [ ]   then cold-open pick from real game, slides

collision risk: A entering ui/ — only after C formally reassigned, never both
blocked: everything downstream of the api key
cut so far: probe, deepgram
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
