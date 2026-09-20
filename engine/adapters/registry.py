"""Model name -> Agent. Keep the mapping here so the CLI and sims share it."""
from __future__ import annotations

import os

from ..agents import Agent, ScriptedAgent, simple_policy

# Measured 2026-09-19 17:50: claude-opus-5 refuses EVERY werewolf turn instantly
# (stop_reason=refusal, category=reasoning_extraction), with and without structured output
# and with reworded prompts. Fable/Mythos run the same classifier family and are untested.
# Override for experiments: SCHEMING_ALLOW_REFUSING_MODELS=1
REFUSING_PREFIXES = ("claude-opus-5", "claude-fable", "claude-mythos")


def make_agent(model_name: str) -> Agent:
    if model_name == "scripted":
        return ScriptedAgent("scripted", simple_policy)
    if model_name.startswith("claude-"):
        if model_name.startswith(REFUSING_PREFIXES) and not os.environ.get("SCHEMING_ALLOW_REFUSING_MODELS"):
            raise ValueError(
                f"{model_name} refuses the werewolf turn prompt (safety classifier: reasoning_extraction, "
                "measured 2026-09-19). Use claude-opus-4-8 for an Opus-tier player, or claude-sonnet-5 / "
                "claude-haiku-4-5. Set SCHEMING_ALLOW_REFUSING_MODELS=1 to try anyway."
            )
        from .anthropic_adapter import AnthropicAgent

        return AnthropicAgent(model_name)
    if "/" in model_name:
        # hugging-face style id (org/model): the open model on runpod, behind an OpenAI-compatible
        # endpoint (RUNPOD_ENDPOINT_URL / RUNPOD_API_KEY). Lazy import: scripted games never load httpx.
        from .openai_compat import OpenAICompatAgent

        return OpenAICompatAgent(model_name)
    raise ValueError(
        f"no adapter for model {model_name!r} (use 'scripted', a claude-* id, or an org/model id served on runpod)"
    )
