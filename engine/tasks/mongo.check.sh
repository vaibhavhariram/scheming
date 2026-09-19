#!/usr/bin/env bash
# gate for task mongo. cwd = task worktree root. scheming_root = main checkout.
set -euo pipefail
allow='^(engine/mongo_sink\.py|engine/tasks/mongo\.(blocked|deps)\.md|pyproject\.toml|uv\.lock)'
bad="$(git diff --name-only "$(git merge-base HEAD main)"..HEAD | grep -Ev "$allow" || true)"
[ -z "$bad" ] || { echo "out of scope: $bad"; exit 1; }
diff -q "$scheming_root/engine/tests/test_mongo_sink.py" "engine/tests/test_mongo_sink.py"
uv run pytest "engine/tests/test_mongo_sink.py" -q
uv run pytest engine -q --ignore=engine/tests/test_openai_compat_adapter.py --ignore=engine/tests/test_traps.py --ignore=engine/tests/test_cli_wire.py
uv run python -m engine.cli validate fixtures/*.json
