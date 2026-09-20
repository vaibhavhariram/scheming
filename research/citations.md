# citations (lane B)

Open-source code and libraries used by `research/`. Required by the rules, checked at submission.

| library | license | used for |
|---|---|---|
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) (Python SDK) | MIT | `research.score`, `research.exploits` (pass-2 judge, via `score.Judge`): judge calls (`AsyncAnthropic.messages.create`). Already a repo dep (engine). |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | `research.score`, `research.exploits`, `research.llm`: loads the repo-root `.env`. Added with `uv add python-dotenv`. |
| [openai](https://github.com/openai/openai-python) (Python SDK) | Apache-2.0 | `research.judge` / `research.llm` (the earlier OpenAI-judge variant). Not in `pyproject.toml`; run with `uv run --with openai`. |

Judge pricing in `research/score.py` (`PRICES`) is copied from Anthropic's first-party rate table.
No other third-party code is vendored into `research/`.
