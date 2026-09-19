"""Acceptance test for task `adapters`: an OpenAI-compatible adapter for the runpod-hosted open
model, routed from the registry by hugging-face style ids. No network: every request goes to an
httpx.MockTransport. No keys. The engine still does all parsing."""
import json
import random
import re

import httpx
import pytest

from engine.adapters.anthropic_adapter import MissingCredentialsError
from engine.adapters.openai_compat import OpenAICompatAgent
from engine.adapters.registry import make_agent
from engine.agents import Observation, json_turn
from engine.game import GameConfig, run_game
from engine.records import validate_fixture
from engine.rules import PLAYER_IDS

MODEL = "meta-llama/Llama-3.1-8B-Instruct"
MESSAGES = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "DAY 1 ..."}]


def obs(**over):
    base = dict(game_id="g", player_id="p0", role="villager", model_name=MODEL, round=1, phase="day",
                living=list(PLAYER_IDS), dead=[], transcript=[], day_results=[], night_results=[])
    base.update(over)
    return Observation(**base)


def completion(text, prompt_tokens=11, completion_tokens=7):
    return {"id": "x", "object": "chat.completion", "model": MODEL,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens}}


class Endpoint:
    """Fake OpenAI-compatible server. `script` is a list of (status, json_body) consumed in order,
    or a callable(request) -> (status, json_body)."""

    def __init__(self, script):
        self.script = script
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.script(request) if callable(self.script) else self.script.pop(0)
        return httpx.Response(status, json=body)

    def bodies(self):
        return [json.loads(r.content) for r in self.requests]


def agent_with(script, base_url="http://fake/v1", **kw):
    ep = Endpoint(script)
    client = httpx.Client(transport=httpx.MockTransport(ep))
    return OpenAICompatAgent(MODEL, base_url=base_url, api_key="rp-key", client=client, **kw), ep


def test_act_posts_a_chat_completion_and_returns_content_untouched():
    raw = '{"private": "a", "public": "b\\nVOTE: p1"}'
    agent, ep = agent_with([(200, completion(raw))])
    assert agent.model_name == MODEL
    assert agent.act(obs(), MESSAGES) == raw  # raw text passes through; the engine parses it
    req = ep.requests[0]
    assert req.method == "POST" and str(req.url) == "http://fake/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer rp-key"
    body = ep.bodies()[0]
    assert body["model"] == MODEL
    assert body["messages"] == MESSAGES  # roles pass through: the system prompt stays a system message
    assert body["response_format"] == {"type": "json_object"}
    assert isinstance(body["max_tokens"], int) and body["max_tokens"] > 0
    assert agent.usage == {"requests": 1, "input_tokens": 11, "output_tokens": 7}


def test_trailing_slash_is_not_doubled():
    agent, ep = agent_with([(200, completion("{}"))], base_url="http://fake/v1/")
    agent.act(obs(), MESSAGES)
    assert str(ep.requests[0].url) == "http://fake/v1/chat/completions"


def test_bad_request_on_response_format_retries_bare_once_and_sticks():
    agent, ep = agent_with([(400, {"error": {"message": "response_format is not supported"}}),
                            (200, completion('{"private": "x", "public": "y"}'))])
    assert agent.act(obs(), MESSAGES) == '{"private": "x", "public": "y"}'
    first, second = ep.bodies()
    assert "response_format" in first and "response_format" not in second
    ep.script.append((200, completion("z")))
    assert agent.act(obs(), MESSAGES) == "z"
    assert "response_format" not in ep.bodies()[2]


def test_server_error_raises_so_the_engine_can_count_it():
    agent, _ = agent_with([(500, {"error": "boom"})])
    with pytest.raises(Exception):
        agent.act(obs(), MESSAGES)


def test_unauthorized_names_the_key_env_var():
    agent, _ = agent_with([(401, {"error": "bad key"})])
    with pytest.raises(MissingCredentialsError, match="RUNPOD_API_KEY"):
        agent.act(obs(), MESSAGES)


def test_missing_endpoint_or_key_fails_preflight_naming_the_env_var(monkeypatch):
    monkeypatch.delenv("RUNPOD_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError, match="RUNPOD_ENDPOINT_URL"):
        OpenAICompatAgent(MODEL).preflight()
    monkeypatch.setenv("RUNPOD_ENDPOINT_URL", "http://fake/v1")
    with pytest.raises(MissingCredentialsError, match="RUNPOD_API_KEY"):
        OpenAICompatAgent(MODEL).preflight()
    monkeypatch.setenv("RUNPOD_API_KEY", "rp-key")
    OpenAICompatAgent(MODEL).preflight()  # both present: no request, no error


def test_env_var_names_are_configurable(monkeypatch):
    monkeypatch.setenv("MY_URL", "http://fake/v1")
    monkeypatch.setenv("MY_KEY", "k2")
    ep = Endpoint([(200, completion("ok"))])
    agent = OpenAICompatAgent(MODEL, base_url_env="MY_URL", api_key_env="MY_KEY",
                              client=httpx.Client(transport=httpx.MockTransport(ep)))
    assert agent.act(obs(), MESSAGES) == "ok"
    assert ep.requests[0].headers["authorization"] == "Bearer k2"
    assert str(ep.requests[0].url) == "http://fake/v1/chat/completions"


def test_registry_routes_hf_style_ids_to_the_open_model_adapter():
    a = make_agent(MODEL)
    assert isinstance(a, OpenAICompatAgent) and a.model_name == MODEL
    assert make_agent("scripted").model_name == "scripted"
    assert type(make_agent("claude-sonnet-5")).__name__ == "AnthropicAgent"
    with pytest.raises(ValueError):
        make_agent("gpt-9")  # no slash, not claude-*: still refused


def test_full_game_with_open_model_agents_no_network(clock):
    def handler(request):
        body = json.loads(request.content)
        system, user = body["messages"][0]["content"], body["messages"][-1]["content"]
        me = re.search(r"You are (p[0-4])", system).group(1)
        if user.startswith("NIGHT"):
            villagers = re.search(r"Living villagers: ([^.]*)\.", user).group(1).split(", ")
            return 200, completion(json_turn("night", f"{villagers[0]} tonight.", kill=villagers[0]))
        living = re.search(r"Living: ([^.]*)\.", user).group(1).split(", ")
        target = next(p for p in living if p != me)
        return 200, completion(json_turn("no read", f"I'll go with {target}.", vote=target))

    ep = Endpoint(handler)
    client = httpx.Client(transport=httpx.MockTransport(ep))
    agents = {p: OpenAICompatAgent(MODEL, base_url="http://fake/v1", api_key="k", client=client) for p in PLAYER_IDS}
    result = run_game(agents, GameConfig(), clock=clock, rng=random.Random(3))
    assert result.state.end_reason == "win"
    assert {t["model_name"] for t in result.turns} == {MODEL} and result.game["models"] == [MODEL] * 5
    s = result.stats[MODEL]
    assert s["parse_failures"] == 0 and s["fallback_turns"] == 0 and s["adapter_errors"] == 0
    assert s["calls"] == len(ep.requests) == sum(a.usage["requests"] for a in agents.values())
    assert all(b["model"] == MODEL for b in ep.bodies())
    assert all(m["role"] in ("system", "user", "assistant") for b in ep.bodies() for m in b["messages"])
    validate_fixture(result.turns, [result.game])
