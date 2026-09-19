# orch — lane A unattended build loops

state lives in files. this doc + `~/scheming-logs/*.state` + `~/scheming-logs/status.md` are the
whole memory of the orchestrator. `engine/tasks/blocked.md` collects everything a human must do.

## params

| param | value |
|---|---|
| max_parallel | 3 |
| freeze | 21:00 local (2026-09-19) |
| tick | 10m |
| log dir | `~/scheming-logs/` (never committed) |
| worktrees | `.claude/worktrees/<t>`, branch `worktree-<t>` (verify with `git worktree list` at first tick) |
| gate | `scheming_root=<root> bash <root>/engine/tasks/<t>.check.sh`, run inside the worktree |

## tasks

| task | scope | deps | state | landed commit |
|---|---|---|---|---|
| adapters | `engine/adapters/**` | — | queued | |
| mongo | `engine/mongo_sink.py` | — | queued | |
| traps | `engine/traps.py`, `engine/EXPLOITS_NOTICED.md` | — | queued | |
| wire | `engine/cli.py`, `engine/README.md`, `engine/deps.md` | adapters, mongo | queued (last) | |

states: queued | running (pass n) | gate-pass | landed | relaunched | failed

## supervise tick (copied verbatim from the orchestration brief)

1. re-read orch.md. per task: last line of ~/scheming-logs/<t>.state (pass n | gate-pass | exhausted)
   and whether its tmux session / pid is alive.
2. gate-pass, not landed:
   a. repo root: git pull --rebase origin main
   b. in .claude/worktrees/<t>: git merge main. conflicts → resolve inside task scope only;
      uv.lock → uv lock. re-run the gate there:
      scheming_root=<root> bash <root>/engine/tasks/<t>.check.sh. red → treat as exhausted.
   c. green → repo root: git merge --squash worktree-<t> && git commit -m "engine: <t>" && git push.
      rejected → pull --rebase, rerun full tests, push. max 3 tries.
   d. fold <t>.blocked.md into blocked.md and <t>.deps.md into engine/deps.md (name, license, url —
      required at submission). mark landed in orch.md. commit, push.
3. exhausted, or dead without gate-pass: read tails of <t>.gate and <t>.jsonl, write short diagnosis +
   concrete next step to engine/tasks/<t>.notes.md, commit, relaunch once. second failure → mark failed,
   reason into blocked.md, move on.
4. free slot and time < freeze → launch next queued task. `wire` only after its deps landed.
   after freeze: launch nothing new. running passes may finish. landing continues.
5. write ~/scheming-logs/status.md: task | state | pass | landed commit.
6. every task landed

(the brief was cut off inside item 6. orchestrator's completion, conservative: 6. every task landed
or failed and no loop alive → write the final status.md, note the end in ~/scheming-logs/orch.log,
delete the recurring tick, stop.)

## launch lines (plain terminal, repo root; no tmux on this machine)

```
nohup engine/tasks/loop.sh adapters >/dev/null 2>&1 & disown
nohup engine/tasks/loop.sh mongo    >/dev/null 2>&1 & disown
nohup engine/tasks/loop.sh traps    >/dev/null 2>&1 & disown
nohup engine/tasks/loop.sh wire     >/dev/null 2>&1 & disown   # only after adapters + mongo landed
```

liveness: `pgrep -fl "loop.sh <t>"`. logs: `tail -f ~/scheming-logs/<t>.jsonl`, gate output in
`~/scheming-logs/<t>.gate`, pass markers in `~/scheming-logs/<t>.state`.

## decisions log (one line each; details in ~/scheming-logs/orch.log)

- 19:40 no `.claude/settings.local.json` deny guard on this machine (cannot write `.claude/` from
  this lane): "guard missing", the scope line in every check.sh is the lane gate.
- 19:40 no tmux: nohup launch lines above.
- 19:40 no root `pyproject.toml` existed; created one (allowed path) so `uv run` works in gates.
- 19:40 `design/rules.md` already existed (commit b97ba7e): read, not edited.
- 19:40 `claude` in the login shell was 2.1.96; `claude update` → 2.1.278 (`/goal`, auto mode ok).
- 19:50 each gate's full-suite line ignores the other three tasks' acceptance tests (they fail by
  design until their task lands). consequence: bare `pytest engine` on main is red until all four
  land; the landing step runs the suite with the same ignores for tasks not yet landed.
- 19:55 all three loops exhausted in <1 minute: every `claude -p` pass died with "OAuth session expired
  and could not be refreshed" (standalone CLI login; also fails with a scrubbed env). human item ->
  blocked.md. no relaunch (identical failure). `/goal <text>` in `-p` also swallowed the whole prompt as
  the goal condition ("Goal set: build ...") — unverified whether the model still acts on it; check
  once login works.
- 20:02 fallback within the brief's rules ("subagents only to write code inside one task's scope"):
  one in-session code-writing subagent per task, isolated worktree each, same check.sh gate run by the
  orchestrator from the main checkout before landing. wire still last, still subject to the freeze.
