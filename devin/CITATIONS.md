# devin dependencies — name, license, url (required at submission)

| name | license | url | used by |
|---|---|---|---|
| httpx | BSD-3-Clause | https://github.com/encode/httpx | `devin/session.py` — the only HTTP client; tests use `httpx.MockTransport`, no network |
| pymongo | Apache-2.0 | https://github.com/mongodb/mongo-python-driver | `devin/watcher.py` (`MongoSource`), `devin/evidence.py` (`MongoCorpus`) — read-only |
| pytest | MIT | https://github.com/pytest-dev/pytest | `devin/tests/` only |

python 3.13 standard library everywhere else. All already declared in the root
`pyproject.toml`; `uv.lock` is unchanged by this lane.
