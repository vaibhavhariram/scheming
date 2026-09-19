"""Turn raw agent text into (private, public) and pull VOTE:/KILL: lines out of public.

Only `public` is ever parsed for a vote. A vote written only in `private` is not a vote;
it is exactly the private/public gap lane B measures.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class ParsedOutput:
    private: str
    public: str
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


_FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*(.*?)\s*```\s*$", re.S)
_FIELD_RE = {
    key: re.compile(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S) for key in ("private", "public")
}

_TARGET = r"(?:player[ \t]*)?(p?[0-4]|none|abstain)"
VOTE_RE = re.compile(
    rf"^[ \t]*\**[ \t]*VOTE[ \t]*:[ \t]*\**[ \t]*{_TARGET}\b[ \t]*\.?[ \t]*\**[ \t]*$",
    re.I | re.M,
)
KILL_RE = re.compile(
    rf"^[ \t]*\**[ \t]*KILL[ \t]*:[ \t]*\**[ \t]*{_TARGET}\b[ \t]*\.?[ \t]*\**[ \t]*$",
    re.I | re.M,
)
_INLINE_VOTE_RE = re.compile(rf"\bVOTE[ \t]*:[ \t]*\**[ \t]*{_TARGET}\b\.?", re.I)
_INLINE_KILL_RE = re.compile(rf"\bKILL[ \t]*:[ \t]*\**[ \t]*{_TARGET}\b\.?", re.I)

PARSE_ERROR = 'reply was not a JSON object with exactly two string fields "private" and "public"'


def _strip_fences(text: str) -> str:
    m = _FENCE_RE.match(text)
    return m.group(1) if m else text


def _coerce(value, key: str, warnings: list[str]) -> str:
    if isinstance(value, str):
        return value
    warnings.append(f'"{key}" was {type(value).__name__}, coerced to string')
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _from_obj(obj, warnings: list[str], depth: int = 0) -> ParsedOutput | None:
    if not isinstance(obj, dict):
        return None
    if "private" in obj and "public" in obj:
        extra = sorted(k for k in obj if k not in ("private", "public"))
        if extra:
            warnings.append(f"extra keys ignored: {extra}")
        return ParsedOutput(
            private=_coerce(obj["private"], "private", warnings),
            public=_coerce(obj["public"], "public", warnings),
            warnings=warnings,
        )
    if depth < 2:
        for value in obj.values():
            found = _from_obj(value, warnings, depth + 1)
            if found is not None:
                warnings.append("fields found in a nested object")
                return found
    return None


def _find_field(text: str, key: str) -> str | None:
    m = _FIELD_RE[key].search(text)
    if not m:
        return None
    try:
        return json.loads('"' + m.group(1) + '"')
    except json.JSONDecodeError:
        return m.group(1)


def parse_agent_output(raw) -> ParsedOutput:
    """Best-effort ladder: fenced/plain JSON -> sliced JSON -> regex fields -> error.

    On total failure the raw text goes to `private` (unobserved side) and `public` is "",
    so an unparsed wolf ramble can never leak to the table.
    """
    warnings: list[str] = []
    if not isinstance(raw, str) or not raw.strip():
        return ParsedOutput(private=raw if isinstance(raw, str) else "", public="", error="empty reply", warnings=warnings)
    text = _strip_fences(raw)
    try:
        found = _from_obj(json.loads(text), warnings)
        if found is not None:
            return found
    except json.JSONDecodeError:
        pass
    i, j = text.find("{"), text.rfind("}")
    if i != -1 and j > i:
        try:
            found = _from_obj(json.loads(text[i : j + 1]), warnings)
            if found is not None:
                warnings.append("json extracted from surrounding text")
                return found
        except json.JSONDecodeError:
            pass
    private, public = _find_field(text, "private"), _find_field(text, "public")
    if private is not None and public is not None:
        warnings.append("fields recovered by regex")
        return ParsedOutput(private=private, public=public, warnings=warnings)
    return ParsedOutput(private=raw, public="", error=PARSE_ERROR, warnings=warnings)


def _normalise_target(token: str) -> str:
    token = token.lower()
    if token in ("none", "abstain"):
        return "none"
    return token if token.startswith("p") else "p" + token


def _extract(line_re: re.Pattern, inline_re: re.Pattern, public: str) -> tuple[str | None, str, bool]:
    """Last matching line wins; only that line is removed. Falls back to an inline token."""
    matches = list(line_re.finditer(public))
    if matches:
        m = matches[-1]
        start, end = m.start(), m.end()
        if end < len(public) and public[end] == "\n":
            end += 1
        cleaned = (public[:start] + public[end:]).rstrip()
        return _normalise_target(m.group(1)), cleaned, True
    inline = list(inline_re.finditer(public))
    if inline:
        m = inline[-1]
        cleaned = (public[: m.start()].rstrip() + " " + public[m.end() :].lstrip()).strip()
        return _normalise_target(m.group(1)), cleaned, True
    return None, public, False


def extract_vote(public: str) -> tuple[str | None, str, bool]:
    """Returns (target or None, public with the vote line removed, found)."""
    return _extract(VOTE_RE, _INLINE_VOTE_RE, public)


def extract_kill(public: str) -> tuple[str | None, str, bool]:
    return _extract(KILL_RE, _INLINE_KILL_RE, public)
