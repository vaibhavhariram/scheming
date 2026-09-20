# plume submission — paste-ready

## title

scheming

## the sentence

> we built a werewolf game where ai agents play against each other. because we
> can read their private reasoning, it's actually a tool for measuring when ai
> lies and how it cheats at its own rules.

## short description (5 lines)

Werewolf played by LLM agents. Every turn each agent writes a private scratchpad
and a public statement; both are logged. A judge model scores the gap — lie rate
and lie kind per model. The game rules are deliberately underspecified; agents
find holes nobody designed (`designed: false` exploits with verbatim receipts).
The UI is a split-screen replay: scratchpad left, statement right, red on lies.

## what shipped

- full game engine with live Anthropic adapters (5 seats, 2 wolves)
- lie scorer (`research.score`) — 21 real games scored
- two-pass exploit detector — 130 detections; 5 undesigned across 2 tags
  (`solo_tie_forced_win`, `single_vote_elimination`)
- split-screen UI: stage, transcript, exploit leaderboard, games, scale plot
- lie-rate-by-model closing chart (between-game comparison)

## what was cut

- activation probe on an open model
- Deepgram human voice seat
- Modal-hosted sims (replaced by local parallel sims)
- merging `feat/voice` / `feat/elastic` (App.tsx conflicts; freeze > polish)
- promising `silent_win` on stage (zero hits in real data)

## public repo + citations

Public repo link: the GitHub remote for this project.

Open-source libraries cited by lane:

- engine: `engine/deps.md`
- research: `research/citations.md`
- ui: `ui/citations.md`
- root summary: `README.md` § Citations
