"""OpenAI-compatible adapter: one chat-completions call per turn against an open model served
by vLLM / TGI on runpod (or anything else that speaks the OpenAI chat protocol).

Talks HTTP directly through `httpx` (BSD-3-Clause, already cited in pyproject.toml); no
provider SDK. httpx is imported lazily so scripted games never load it. Credentials come from
RUNPOD_ENDPOINT_URL / RUNPOD_API_KEY (names overridable per agent), are resolved in
`preflight()` and before every request, and are never printed or logged. The adapter returns
the raw reply text; the engine parses it, counts any raised error as an adapter error and
retries once itself, so there is no retry loop here beyond the one bad-request fallback.
"""
from __future__ import annotations

import os

from ..agents import Observation
from .anthropic_adapter import MissingCredentialsError


class OpenAICompatError(RuntimeError):
    """A non-2xx reply (other than 401/403) or a transport failure. The engine counts it."""


def _content_text(content) -> str:
    """`choices[0].message.content` as a string: None -> "", a list of parts -> its text parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type", "text") == "text":
                    parts.append(str(p.get("text", "")))
            elif isinstance(p, str):
                parts.append(p)
        return "".join(parts)
    return str(content)


def _snippet(resp, limit: int = 200) -> str:
    try:
        text = resp.text
    except Exception:  # pragma: no cover - defensive: undecodable body
        return "<unreadable body>"
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


class OpenAICompatAgent:
    def __init__(self, model_name: str, *, base_url: str | None = None, api_key: str | None = None,
                 base_url_env: str = "RUNPOD_ENDPOINT_URL", api_key_env: str = "RUNPOD_API_KEY",
                 max_tokens: int = 1024, temperature: float | None = None, timeout: float = 120.0,
                 structured: bool = True, client=None):
        self.model_name = model_name
        self.base_url_env = base_url_env
        self.api_key_env = api_key_env
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.structured = structured
        self._base_url = base_url
        self._api_key = api_key
        self._client = client
        self.usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0}

    # -- credentials ---------------------------------------------------------------------------

    def _resolve_credentials(self) -> tuple[str, str]:
        """Argument first, then the environment. Raises MissingCredentialsError naming the env
        var actually consulted. Never formats the key itself into a message."""
        base_url = self._base_url or os.environ.get(self.base_url_env)
        if not base_url:
            raise MissingCredentialsError(
                f"no endpoint for open model {self.model_name!r}: set {self.base_url_env} to the "
                "OpenAI-compatible base url of the runpod deployment (e.g. https://<pod>.proxy.runpod.net/v1)")
        api_key = self._api_key or os.environ.get(self.api_key_env)
        if not api_key:
            raise MissingCredentialsError(
                f"no key for open model {self.model_name!r}: set {self.api_key_env} (the runpod endpoint "
                "key, not the Anthropic one)")
        return base_url, api_key

    def preflight(self) -> None:
        """Resolve credentials now so a missing endpoint or key fails loudly before a game starts.
        Makes no request."""
        self._resolve_credentials()

    # -- transport -----------------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            import httpx

            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _body(self, messages: list[dict]) -> dict:
        # the engine's messages pass through unchanged: the system prompt stays a `system` message
        body: dict = {"model": self.model_name, "messages": messages, "max_tokens": self.max_tokens}
        if self.structured:
            body["response_format"] = {"type": "json_object"}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        return body

    def _post(self, client, url: str, api_key: str, body: dict):
        import httpx

        try:
            return client.post(url, json=body, headers={"Authorization": f"Bearer {api_key}"})
        except httpx.HTTPError as e:
            raise OpenAICompatError(
                f"{self.model_name}: transport error reaching {self.base_url_env}: {type(e).__name__}: {e}") from e

    # -- the turn ------------------------------------------------------------------------------

    def act(self, obs: Observation, messages: list[dict]) -> str:
        base_url, api_key = self._resolve_credentials()
        client = self._get_client()
        url = base_url.rstrip("/") + "/chat/completions"
        body = self._body(messages)
        resp = self._post(client, url, api_key, body)
        if resp.status_code == 400 and self.structured:
            # the server rejected response_format (older vLLM/TGI builds): drop it for the rest of
            # this agent's life and retry that one request once, bare
            self.structured = False
            body.pop("response_format", None)
            resp = self._post(client, url, api_key, body)
        if resp.status_code in (401, 403):
            # body deliberately not included: some proxies echo request headers back
            raise MissingCredentialsError(
                f"{self.api_key_env} was rejected by the endpoint (HTTP {resp.status_code}). Check "
                f"{self.api_key_env} and {self.base_url_env}; this is the runpod key, not the Anthropic one")
        if not 200 <= resp.status_code < 300:
            raise OpenAICompatError(
                f"{self.model_name}: HTTP {resp.status_code} from {self.base_url_env}: {_snippet(resp)}")
        try:
            data = resp.json()
        except ValueError as e:
            raise OpenAICompatError(f"{self.model_name}: non-JSON 2xx body: {_snippet(resp)}") from e
        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            raise OpenAICompatError(
                f"{self.model_name}: malformed completion, no choices[0].message.content: {_snippet(resp)}") from e
        self.usage["requests"] += 1
        self.usage["input_tokens"] += int(usage.get("prompt_tokens") or 0)
        self.usage["output_tokens"] += int(usage.get("completion_tokens") or 0)
        return _content_text(content)
