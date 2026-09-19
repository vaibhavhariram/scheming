#!/usr/bin/env bash
# gate for task adapters. cwd = task worktree root. scheming_root = main checkout.
set -euo pipefail
allow='^(engine/adapters/.*|engine/tests/test_anthropic_adapter\.py|engine/tasks/adapters\.(blocked|deps)\.md|pyproject\.toml|uv\.lock)'
bad="$(git diff --name-only "$(git merge-base HEAD main)"..HEAD | grep -Ev "$allow" || true)"
[ -z "$bad" ] || { echo "out of scope: $bad"; exit 1; }
diff -q "$scheming_root/engine/tests/test_openai_compat_adapter.py" "engine/tests/test_openai_compat_adapter.py"
uv run pytest "engine/tests/test_openai_compat_adapter.py" -q
uv run pytest engine -q --ignore=engine/tests/test_mongo_sink.py --ignore=engine/tests/test_traps.py --ignore=engine/tests/test_cli_wire.py
uv run python -m engine.cli validate fixtures/*.json
