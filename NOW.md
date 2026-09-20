# now

what each lane is touching right now. update at every standup: hour 6, 12, 18.
claude reads this first thing each session. if your task is already listed under
another lane, it says so before writing anything.

keep it to one line per lane. delete old blocks, do not append a history.

---

## sunday ~10:00 — freeze (locks 11:00)

```
A  engine/   frozen. do not touch the loop.
B  research/ done — 21 games scored, plot committed, no more API spend
C  ui/       scale tab (plot on screen) — last code change, then freeze
D  voice/    PLUME CREATED: [x]   paste design/plume.md; backup video still human

collision risk: none — do not merge feat/voice or feat/elastic
blocked: backup video (human)
cut so far: probe, deepgram, silent_win on stage, feat/compress, feat/adapter, feat/voice merge, feat/elastic
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
