# deps — task adapters

no new dependencies beyond httpx (already cited).

| dependency | license | url | where used |
|---|---|---|---|
| `httpx` (already declared in `pyproject.toml`) | BSD-3-Clause | https://github.com/encode/httpx | `engine/adapters/openai_compat.py` — the only HTTP client; imported lazily, so scripted games never load it. tests use `httpx.MockTransport`, no network. |

nothing was added with `uv add`; `pyproject.toml` and `uv.lock` are unchanged by this task.
