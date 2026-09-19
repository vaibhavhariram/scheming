# task: adapters — open model on runpod through an OpenAI-compatible adapter

lane A (engine). python 3.13. no network in tests, no keys, no live calls. the acceptance test
`engine/tests/test_openai_compat_adapter.py` is the spec of record: read it first, never edit it.

## goal

LANES.md build order item 3: "swap model per player from config. at minimum: one frontier model
and one open model hosted on runpod." the frontier side exists (`engine/adapters/anthropic_adapter.py`).
add the open-model side: one adapter that speaks the OpenAI chat-completions protocol (what a vLLM /
TGI endpoint on runpod serves), and route hugging-face style model ids to it in the registry.

## scope (the only paths you may create or change)

- `engine/adapters/openai_compat.py` (new)
- `engine/adapters/registry.py`
- `engine/adapters/__init__.py` (only if needed)
- `engine/tests/test_anthropic_adapter.py` (only if an existing registry assertion must move; prefer not)
- `engine/tasks/adapters.blocked.md`, `engine/tasks/adapters.deps.md`
- `pyproject.toml`, `uv.lock` (only via `uv add`)

everything else is frozen for this task: `engine/cli.py`, `engine/README.md`, `engine/game.py`,
prompts, parsing, sinks, fixtures, other lanes, `CONTRACT.md`.

## interfaces that must not change

- `engine.agents.Agent`: `model_name: str`, `act(obs, messages) -> str` returning the raw text; the
  engine parses it. the adapter never parses, never retries beyond what is listed below.
- `make_agent(model_name: str) -> Agent` in `engine/adapters/registry.py`: `"scripted"` and
  `claude-*` behave exactly as today (including `REFUSING_PREFIXES`). names with no `/` that are
  not `scripted`/`claude-*` still raise `ValueError`.
- `MissingCredentialsError` stays importable from `engine.adapters.anthropic_adapter` (the CLI
  catches it). the new adapter raises that same class for missing/rejected credentials.
- existing tests in `engine/tests/` keep passing unchanged.

## the adapter: `engine/adapters/openai_compat.py`

```python
class OpenAICompatAgent:
    def __init__(self, model_name: str, *, base_url: str | None = None, api_key: str | None = None,
                 base_url_env: str = "RUNPOD_ENDPOINT_URL", api_key_env: str = "RUNPOD_API_KEY",
                 max_tokens: int = 1024, temperature: float | None = None, timeout: float = 120.0,
                 structured: bool = True, client=None): ...
    model_name: str
    usage: dict            # {"requests": int, "input_tokens": int, "output_tokens": int}
    def preflight(self) -> None
    def act(self, obs, messages: list[dict]) -> str
```

- `client` is an `httpx.Client`; tests inject `httpx.Client(transport=httpx.MockTransport(handler))`.
  when `None`, build `httpx.Client(timeout=timeout)` lazily. `httpx` is already a dependency.
- credentials: `base_url` = argument, else `os.environ[base_url_env]`; `api_key` = argument, else
  `os.environ[api_key_env]`. resolve in `preflight()` and before the first request. missing base
  url -> `MissingCredentialsError` whose message contains the env var name actually consulted
  (`RUNPOD_ENDPOINT_URL` by default); missing key -> message contains `RUNPOD_API_KEY` (or the
  override). `preflight()` makes no request.
- request: `POST {base_url.rstrip('/')}/chat/completions`, headers `Authorization: Bearer <key>`,
  json body `{"model": model_name, "messages": messages, "max_tokens": max_tokens}` plus
  `"response_format": {"type": "json_object"}` while `structured` is true, plus `"temperature"`
  only when not `None`. the engine's messages (`role` system/user) pass through unchanged: the
  system prompt stays a `system` message.
- response 2xx: return `choices[0].message.content` as a string (`None` -> `""`; a list of parts
  -> join the text parts). add `usage.prompt_tokens` / `usage.completion_tokens` (0 when absent)
  to `self.usage`, `requests += 1`.
- 400 while `structured`: the server rejected `response_format`; set `self.structured = False`
  for the rest of this agent's life and retry that one request once without it (mirror of the
  anthropic adapter's bad-request fallback).
- 401 / 403: raise `MissingCredentialsError` naming the key env var.
- any other non-2xx or a transport error: raise (an `OpenAICompatError(RuntimeError)` is fine).
  the engine counts it as `adapter_errors` and retries once itself; do not add your own retry loop.
- never print or log the key. never read `.env` (the CLI does that).

## registry

`make_agent(name)`: a name containing `/` (hugging-face style, e.g.
`meta-llama/Llama-3.1-8B-Instruct`) -> `OpenAICompatAgent(name)` with the default env names. keep
the import lazy like the anthropic one so `scripted` games never import httpx.

## contract fields involved

`Turn.model_name` and `Game.models` carry the model id string exactly as given (the `/` stays).
nothing else in CONTRACT.md is touched. never write scores or exploits.

## acceptance

- `scheming_root=<main checkout> bash engine/tasks/adapters.check.sh` exits 0 in your worktree:
  scope clean, acceptance test byte-identical to main, `uv run pytest engine -q` green,
  `uv run python -m engine.cli validate fixtures/*.json` green.
- `engine/tasks/adapters.deps.md` lists any dependency you add (name, license, url). httpx is
  already cited in `pyproject.toml`; if you use nothing new, write "no new dependencies".
- everything committed on this branch. do not merge, do not push main.
