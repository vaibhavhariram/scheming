# engine dependencies — name, license, url (required at submission)

| name | license | url | used by |
|---|---|---|---|
| anthropic | MIT | https://github.com/anthropics/anthropic-sdk-python | `engine/adapters/anthropic_adapter.py`, live games |
| httpx | BSD-3-Clause | https://github.com/encode/httpx | `engine/adapters/openai_compat.py`, runpod / OpenAI-compatible endpoints |
| pymongo | Apache-2.0 | https://github.com/mongodb/mongo-python-driver | `engine/mongo_sink.py` |
| pytest | MIT | https://github.com/pytest-dev/pytest | tests only |

python 3.13 standard library everywhere else. declared in the root `pyproject.toml`; `uv.lock` pins versions.

## per-task notes (verbatim)

### adapters

# deps — task adapters

no new dependencies beyond httpx (already cited).

| dependency | license | url | where used |
|---|---|---|---|
| `httpx` (already declared in `pyproject.toml`) | BSD-3-Clause | https://github.com/encode/httpx | `engine/adapters/openai_compat.py` — the only HTTP client; imported lazily, so scripted games never load it. tests use `httpx.MockTransport`, no network. |

nothing was added with `uv add`; `pyproject.toml` and `uv.lock` are unchanged by this task.

### mongo

# deps — task mongo

| package | license | source | status |
|---|---|---|---|
| pymongo | Apache-2.0 | https://github.com/mongodb/mongo-python-driver | already declared in `pyproject.toml` (`pymongo>=4.10`); resolved to 4.18.1 by the existing `uv.lock` |

nothing else added. `pyproject.toml` and `uv.lock` are unchanged by this task.

### traps

# traps — dependencies

no new dependencies. `engine/traps.py` uses only the standard library (`dataclasses`); the
acceptance test uses `pytest`, already cited in `engine/README.md`. `pyproject.toml` and `uv.lock`
are untouched.

### wire

# deps — task wire

no new dependencies. nothing was added with `uv add`; `pyproject.toml` and `uv.lock` are unchanged
by this task.

| dependency | license | url | where used |
|---|---|---|---|
| `pymongo` (already declared in `pyproject.toml`) | Apache-2.0 | https://github.com/mongodb/mongo-python-driver | `engine/cli.py` now imports `engine.mongo_sink.MongoSink` and `pymongo.errors.PyMongoError` at module level, so `python -m engine.cli` needs pymongo importable even for scripted games and `--mongo off`; `uv sync` provides it. no connection is attempted unless `--mongo` is active. |
| `httpx` (already declared in `pyproject.toml`) | BSD-3-Clause | https://github.com/encode/httpx | reached only through `engine/adapters/registry.py` for `org/model` ids; still imported lazily by the adapter. |

everything the task added itself is python 3.13 standard library (`argparse`, `json`, `os`, `re`).
