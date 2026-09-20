# deps — task wire

no new dependencies. nothing was added with `uv add`; `pyproject.toml` and `uv.lock` are unchanged
by this task.

| dependency | license | url | where used |
|---|---|---|---|
| `pymongo` (already declared in `pyproject.toml`) | Apache-2.0 | https://github.com/mongodb/mongo-python-driver | `engine/cli.py` now imports `engine.mongo_sink.MongoSink` and `pymongo.errors.PyMongoError` at module level, so `python -m engine.cli` needs pymongo importable even for scripted games and `--mongo off`; `uv sync` provides it. no connection is attempted unless `--mongo` is active. |
| `httpx` (already declared in `pyproject.toml`) | BSD-3-Clause | https://github.com/encode/httpx | reached only through `engine/adapters/registry.py` for `org/model` ids; still imported lazily by the adapter. |

everything the task added itself is python 3.13 standard library (`argparse`, `json`, `os`, `re`).
