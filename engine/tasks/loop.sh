#!/usr/bin/env bash
# usage, from repo root: engine/tasks/loop.sh <task>
set -uo pipefail
t="$1"; export scheming_root="$(pwd)"; log="$HOME/scheming-logs"; mkdir -p "$log"
unset ANTHROPIC_API_KEY   # else -p bills the api key, not the max plan
for pass in 1 2 3 4 5 6; do
  echo "pass $pass $(date +%H:%M)" >> "$log/$t.state"
  claude -w "$t" -p "/goal build engine/tasks/$t.md. first read $scheming_root/engine/tasks/$t.notes.md if it exists. done when: scheming_root=$scheming_root bash engine/tasks/$t.check.sh exits 0 with output shown; only paths in the task scope changed; acceptance tests and check script unmodified; everything committed on this branch. blocked by CONTRACT.md or another lane: append to engine/tasks/$t.blocked.md, skip, keep going. new dependency: uv add it, log name + license + url in engine/tasks/$t.deps.md. ask nothing. stop after 40 turns." \
    --permission-mode auto --output-format stream-json --verbose >> "$log/$t.jsonl" 2>&1
  if (cd "$scheming_root/.claude/worktrees/$t" && bash "$scheming_root/engine/tasks/$t.check.sh") >> "$log/$t.gate" 2>&1; then
    echo "gate-pass $(date +%H:%M)" >> "$log/$t.state"; exit 0
  fi
done
echo "exhausted $(date +%H:%M)" >> "$log/$t.state"; exit 1
