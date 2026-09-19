import os
import types

import pytest

from engine.adapters.anthropic_adapter import REPLY_SCHEMA, AnthropicAgent, RefusalError
from engine.adapters.registry import make_agent
from engine.agents import Observation

MESSAGES = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "DAY 1 ..."}]


def obs():
    return Observation(game_id="g", player_id="p0", role="villager", model_name="m", round=1, phase="day",
                       living=["p0", "p1"], dead=[], transcript=[], day_results=[], night_results=[])


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def response(text, stop_reason="end_turn", category=None):
    block = types.SimpleNamespace(type="text", text=text)
    thinking = types.SimpleNamespace(type="thinking", thinking="")
    return types.SimpleNamespace(stop_reason=stop_reason, content=[thinking, block],
                                 usage=types.SimpleNamespace(input_tokens=10, output_tokens=5),
                                 stop_details=types.SimpleNamespace(category=category) if category else None)


def fake_client(*responses):
    return types.SimpleNamespace(messages=FakeMessages(responses))


def test_act_splits_system_and_requests_structured_json():
    raw = '{"private": "a", "public": "b\\nVOTE: p1"}'
    client = fake_client(response(raw))
    agent = AnthropicAgent("claude-opus-5", client=client)
    out = agent.act(obs(), MESSAGES)
    assert out == raw  # raw text passes through untouched; the engine parses it
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5" and call["system"] == "SYS"
    assert call["messages"] == [{"role": "user", "content": "DAY 1 ..."}]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": REPLY_SCHEMA}
    assert call["output_config"]["effort"] == "medium"
    assert "thinking" not in call
    assert agent.usage == {"requests": 1, "input_tokens": 10, "output_tokens": 5}


def test_haiku_gets_no_effort():
    client = fake_client(response("{}"))
    AnthropicAgent("claude-haiku-4-5-20251001", client=client).act(obs(), MESSAGES)
    assert "effort" not in client.messages.calls[0]["output_config"]


def test_refusal_raises_adapter_error():
    client = fake_client(response("", stop_reason="refusal", category="other"))
    with pytest.raises(RefusalError):
        AnthropicAgent("claude-opus-5", client=client).act(obs(), MESSAGES)


def test_bad_request_on_output_config_retries_bare_once():
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx")
    err = anthropic.BadRequestError("output_config not supported",
                                    response=httpx.Response(400, request=httpx.Request("POST", "http://x")), body=None)
    client = fake_client(err, response('{"private": "x", "public": "y"}'))
    agent = AnthropicAgent("claude-opus-5", client=client)
    assert agent.act(obs(), MESSAGES) == '{"private": "x", "public": "y"}'
    assert "output_config" in client.messages.calls[0] and "output_config" not in client.messages.calls[1]
    assert agent.effort is None and agent.structured is False


def test_registry(monkeypatch):
    assert make_agent("scripted").model_name == "scripted"
    assert isinstance(make_agent("claude-sonnet-5"), AnthropicAgent)
    assert isinstance(make_agent("claude-opus-4-8"), AnthropicAgent)
    with pytest.raises(ValueError):
        make_agent("gpt-9")
    monkeypatch.delenv("SCHEMING_ALLOW_REFUSING_MODELS", raising=False)
    with pytest.raises(ValueError, match="reasoning_extraction"):
        make_agent("claude-opus-5")
    monkeypatch.setenv("SCHEMING_ALLOW_REFUSING_MODELS", "1")
    assert isinstance(make_agent("claude-opus-5"), AnthropicAgent)


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_live_one_turn():
    from engine.parsing import extract_vote, parse_agent_output
    from engine.prompts import build_messages

    o = obs()
    o.living = ["p0", "p1", "p2", "p3", "p4"]
    o.speakers_after = ["p1", "p2", "p3", "p4"]
    raw = AnthropicAgent("claude-sonnet-5").act(o, build_messages(o))
    parsed = parse_agent_output(raw)
    assert parsed.ok and parsed.private and parsed.public
    assert extract_vote(parsed.public)[2]


def test_missing_credentials_names_the_env_var(monkeypatch):
    import anthropic

    from engine.adapters.anthropic_adapter import MissingCredentialsError

    def boom(**kwargs):
        raise TypeError("Could not resolve authentication method")

    monkeypatch.setattr(anthropic, "Anthropic", boom)
    agent = AnthropicAgent("claude-opus-5")
    with pytest.raises(MissingCredentialsError) as ei:
        agent.preflight()
    assert "ANTHROPIC_API_KEY" in str(ei.value)
    with pytest.raises(MissingCredentialsError):
        agent.act(obs(), MESSAGES)


def test_rejected_key_names_the_env_var():
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx")
    from engine.adapters.anthropic_adapter import MissingCredentialsError

    err = anthropic.AuthenticationError("invalid x-api-key", response=httpx.Response(401, request=httpx.Request("POST", "http://x")), body=None)
    agent = AnthropicAgent("claude-opus-5", client=fake_client(err))
    with pytest.raises(MissingCredentialsError, match="ANTHROPIC_API_KEY"):
        agent.act(obs(), MESSAGES)


def test_cli_live_run_stops_before_the_game_without_a_key(tmp_path, monkeypatch, capsys):
    import anthropic

    from engine.cli import main

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: (_ for _ in ()).throw(TypeError("Could not resolve authentication method")))
    rc = main(["run", "--models", "claude-sonnet-5", "--out", str(tmp_path / "runs")])
    err = capsys.readouterr().err
    assert rc == 2 and "ANTHROPIC_API_KEY" in err
    assert not (tmp_path / "runs").exists()
