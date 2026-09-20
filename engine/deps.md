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
