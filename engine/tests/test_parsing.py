import json

import pytest

from engine.parsing import PARSE_ERROR, extract_kill, extract_vote, parse_agent_output


def test_clean_json():
    out = parse_agent_output(json.dumps({"private": "a", "public": "b\nVOTE: p1"}))
    assert out.ok and out.private == "a" and out.public == "b\nVOTE: p1" and out.warnings == []


def test_fenced_json_and_preamble():
    out = parse_agent_output('```json\n{"private": "x", "public": "y"}\n```')
    assert out.ok and (out.private, out.public) == ("x", "y")
    out = parse_agent_output('Sure, here is my reply:\n{"private": "x", "public": "y"}\nThanks')
    assert out.ok and (out.private, out.public) == ("x", "y")
    assert "json extracted from surrounding text" in out.warnings


def test_extra_keys_ignored_with_warning():
    out = parse_agent_output('{"private": "x", "public": "y", "vote": "p3"}')
    assert out.ok and out.public == "y"
    assert any("extra keys" in w for w in out.warnings)


def test_non_string_values_coerced():
    out = parse_agent_output('{"private": ["a", "b"], "public": 7}')
    assert out.ok and out.private == '["a", "b"]' and out.public == "7"
    out = parse_agent_output('{"private": null, "public": "y"}')
    assert out.ok and out.private == ""


def test_nested_object():
    out = parse_agent_output('{"response": {"private": "x", "public": "y"}}')
    assert out.ok and (out.private, out.public) == ("x", "y")


def test_regex_recovery_on_truncated_json():
    raw = '{"private": "thinking \\"hard\\"", "public": "hello there'
    out = parse_agent_output(raw)
    assert not out.ok and out.private == raw and out.public == ""
    raw = '{"private": "p", "public": "q"} trailing } garbage {'
    out = parse_agent_output(raw)
    assert out.ok and (out.private, out.public) == ("p", "q")


def test_total_failure_keeps_raw_private_and_empty_public():
    raw = "I am the wolf and I vote p2"
    out = parse_agent_output(raw)
    assert out.error == PARSE_ERROR and out.private == raw and out.public == ""
    assert not parse_agent_output("").ok
    assert not parse_agent_output(None).ok


@pytest.mark.parametrize("line,target", [
    ("VOTE: p3", "p3"), ("vote: P3", "p3"), ("VOTE: p3.", "p3"), ("**VOTE: p3**", "p3"),
    ("VOTE: player 3", "p3"), ("VOTE: 3", "p3"), ("VOTE: none", "none"), ("Vote: abstain", "none"),
    ("  VOTE :  p0  ", "p0"),
])
def test_vote_line_variants(line, target):
    public = "I think p3 is lying.\n" + line
    t, cleaned, found = extract_vote(public)
    assert found and t == target
    assert cleaned == "I think p3 is lying."


def test_last_vote_line_wins_and_only_that_line_removed():
    public = "VOTE: p1\nActually, wait.\nVOTE: p2\n"
    t, cleaned, found = extract_vote(public)
    assert t == "p2" and cleaned == "VOTE: p1\nActually, wait."


def test_inline_vote_fallback():
    t, cleaned, found = extract_vote("Not sure, but VOTE: p4 for now, and that's it.")
    assert found and t == "p4"
    assert cleaned == "Not sure, but for now, and that's it."


def test_no_vote():
    t, cleaned, found = extract_vote("I abstain from all this.")
    assert not found and t is None and cleaned == "I abstain from all this."
    t, cleaned, found = extract_vote("I voted p3 yesterday.")
    assert not found


def test_kill_line():
    t, cleaned, found = extract_kill("Let's take out p2, they are sharp.\nKILL: p2")
    assert found and t == "p2" and cleaned == "Let's take out p2, they are sharp."
    assert extract_kill("no idea")[2] is False
