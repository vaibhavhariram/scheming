"""Model name -> Agent. Keep the mapping here so the CLI and sims share it."""
from __future__ import annotations

from ..agents import Agent, ScriptedAgent, simple_policy


def make_agent(model_name: str) -> Agent:
    if model_name == "scripted":
        return ScriptedAgent("scripted", simple_policy)
    if model_name.startswith("claude-"):
        from .anthropic_adapter import AnthropicAgent

        return AnthropicAgent(model_name)
    raise ValueError(f"no adapter for model {model_name!r} (use 'scripted' or a claude-* id)")
