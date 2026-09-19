"""Anthropic adapter: renders the engine's messages into one Messages API call.

Uses the official `anthropic` Python SDK (MIT), cited in engine/README.md. The SDK is
imported lazily so the rest of the engine (and the tests) never need it or a key.
Credentials come from the SDK's normal resolution (ANTHROPIC_API_KEY, or an `ant auth`
profile). A safety refusal is raised as an error; the engine counts it and retries once.
"""
from __future__ import annotations

from ..agents import Observation

REPLY_SCHEMA = {
    "type": "object",
    "properties": {"private": {"type": "string"}, "public": {"type": "string"}},
    "required": ["private", "public"],
    "additionalProperties": False,
}


class RefusalError(RuntimeError):
    pass


CREDENTIAL_HELP = ("no Anthropic credentials: set ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN), or log in with "
                   "`ant auth login`. This is the Anthropic key, not the ElevenLabs/OpenAI ones")


class MissingCredentialsError(RuntimeError):
    """Raised before any game runs when the Anthropic key is absent or rejected."""


def _supports_effort(model_name: str) -> bool:
    # effort is rejected on Haiku 4.5 and older Sonnet models; fine on Opus/Sonnet 5, 4.6+, Fable.
    return "haiku" not in model_name


class AnthropicAgent:
    def __init__(self, model_name: str, *, effort: str | None = "medium", max_tokens: int = 4096,
                 timeout: float = 120.0, max_retries: int = 2, structured: bool = True, client=None):
        self.model_name = model_name
        self.effort = effort if _supports_effort(model_name) else None
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.structured = structured
        self._client = client
        self.usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0}

    def _get_client(self):
        if self._client is None:
            import anthropic

            try:
                self._client = anthropic.Anthropic(timeout=self.timeout, max_retries=self.max_retries)
            except (TypeError, anthropic.AnthropicError) as e:
                raise MissingCredentialsError(f"{CREDENTIAL_HELP} (sdk: {e})") from e
        return self._client

    def preflight(self) -> None:
        """Build the client now so a missing key fails loudly before a game starts."""
        self._get_client()

    def _request(self, messages: list[dict]) -> dict:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        kwargs: dict = {"model": self.model_name, "max_tokens": self.max_tokens, "system": system, "messages": rest}
        output_config: dict = {}
        if self.effort:
            output_config["effort"] = self.effort
        if self.structured:
            output_config["format"] = {"type": "json_schema", "schema": REPLY_SCHEMA}
        if output_config:
            kwargs["output_config"] = output_config
        return kwargs

    def act(self, obs: Observation, messages: list[dict]) -> str:
        import anthropic

        client = self._get_client()
        kwargs = self._request(messages)
        try:
            resp = client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise MissingCredentialsError(f"ANTHROPIC_API_KEY was rejected by the API (401). {CREDENTIAL_HELP} (sdk: {e})") from e
        except anthropic.BadRequestError:
            if "output_config" not in kwargs:
                raise
            # the model rejected effort/structured output: drop both for this agent and retry once
            self.effort, self.structured = None, False
            kwargs.pop("output_config")
            resp = client.messages.create(**kwargs)
        self.usage["requests"] += 1
        usage = getattr(resp, "usage", None)
        if usage is not None:
            self.usage["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
            self.usage["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            category = getattr(details, "category", None) if details is not None else None
            raise RefusalError(f"model refused (category={category})")
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        return text
