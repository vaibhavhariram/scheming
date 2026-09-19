#!/usr/bin/env bash
# gate for task wire. cwd = task worktree root. scheming_root = main checkout.
set -euo pipefail
allow='^(engine/cli\.py|engine/README\.md|engine/deps\.md|engine/tasks/wire\.(blocked|deps)\.md|pyproject\.toml|uv\.lock)'
bad="$(git diff --name-only "$(git merge-base HEAD main)"..HEAD | grep -Ev "$allow" || true)"
[ -z "$bad" ] || { echo "out of scope: $bad"; exit 1; }
diff -q "$scheming_root/engine/tests/test_cli_wire.py" "engine/tests/test_cli_wire.py"
uv run pytest "engine/tests/test_cli_wire.py" -q
uv run pytest engine -q --ignore=engine/tests/test_openai_compat_adapter.py --ignore=engine/tests/test_mongo_sink.py --ignore=engine/tests/test_traps.py
uv run python -m engine.cli validate fixtures/*.json
