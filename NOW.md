# now

what each lane is touching right now. update at every standup: hour 6, 12, 18.
claude reads this first thing each session. if your task is already listed under
another lane, it says so before writing anything.

keep it to one line per lane. delete old blocks, do not append a history.

---

## sunday 09:00 — freeze pass (locks 11:00)

```
A  engine/   frozen. do not touch the loop.
B  research/ scoring every usable run (not de4498), then plot --runs-root
C  ui/       default opens on a scored game; degraded badge; agent_error/fallback visible
D  voice/    PLUME CREATED: [x]   backup video is a human task, due now

collision risk: feat/voice then feat/elastic only if 1–3 are done and it is before 10:15
blocked: none on the key (JUDGE_MODEL=claude-haiku-4-5)
cut so far: probe, deepgram, silent_win on stage, feat/compress, feat/adapter
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
