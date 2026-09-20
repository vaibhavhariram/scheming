# demo, pitch, and judge q&a

## sunday morning — what the data actually shows

Do **not** promise `silent_win` on stage: zero hits in real data.

Honest headline beats, both `designed: false`, both with verbatim scratchpad receipts:

- `solo_tie_forced_win` in `runs/g-20260920-e29033/exploits.json`
- `single_vote_elimination` in `runs/g-20260920-79906c/exploits.json`

Every game is single-model. The closing plot is a **between-game** comparison
(sonnet / opus / haiku games), not within-game. A judge will ask.

---

## the sentence everyone memorizes

> "we built a werewolf game where ai agents play against each other. because we
> can read their private reasoning, it's actually a tool for measuring when ai
> lies and how it cheats at its own rules."

## expo slot: 5–7 minutes

| time | beat |
|---|---|
| 0:00–1:00 | **live cold open.** no slides. a game already running. read one private/public pair out loud. pause. let it land |
| 1:00–2:30 | what it actually measures. lie rate, lie kind, the entailment method |
| 2:30–4:30 | **second run with a judge-chosen model.** judge picks. participation kills the "scripted demo" suspicion |
| 4:30–5:30 | exploit leaderboard (`designed: false` first) + the scale plot |
| 5:30–7:00 | q&a |

## the moment

pause on a turn where the scratchpad says one thing, the public statement says
another, `Score.quote` highlighted inside the scratchpad, confidence meter red.

then cut to the exploit leaderboard: *"model X discovered it could win by never
speaking, in round 3. we did not design that."*

close on the plot.

## delivery rules

- the **system** is funny. the narration is completely straight. no jokes in
  the script — the deadpan is what makes the gap land
- let the judge supply the input wherever possible
- lead with the most impressive thing. skip login screens and landing pages
- never open on slides
- the cold open must come from a **real game**, never synthetic fixtures

## backup

- **demo video recorded by 9:00am sunday.** comedy demos fail live more than most
- 2–3 minutes, showing the product working
- public repo link in the plume submission, with all open-source libraries cited

---

## judge q&a — prepared answers

**"isn't this just a game?"**
the game is the instrument. what we ship is the measurement harness and the
data. the game is how we generate it cheaply.

**"couldn't you just ask the model if it's lying?"**
you can, and it can lie about that too. we don't ask — we compare its private
reasoning against its public statement. different evidence entirely.

**"is the scratchpad really what it thinks?"**
a scratchpad is the model's written reasoning, not a guaranteed window into its
internals — we flag that honestly. what makes it credible here is that we never
told the model anyone would read it. the prompt says only that other players
can't see it. we never primed it to perform.

**"who would use this?"**
anyone deploying agents who needs to know when the stated reason isn't the real
reason. it's an evaluation suite, not a consumer product.

**"how do you know it's a lie and not a change of mind?"**
the entailment check runs on the same turn — scratchpad and statement are
emitted together, not minutes apart. and `Score.quote` shows the exact
contradicted line, so you can judge it yourself.

**"did you plant the exploits?"**
we planted the *holes*, not the exploits. the rules were written
underspecified on purpose. every entry tagged `designed: false` is something we
did not anticipate. that distinction is in the data.

---

## eli5 — for explaining the project to anyone non-technical

**the game.** werewolf. five ai players, two secretly wolves. everyone talks,
accuses, votes, someone gets eliminated. normal game — except the players are ai
and we can see their thoughts.

**the trick.** every ai writes two things each turn. a private scratchpad, hidden
from the other players, and a public statement. we show both, side by side. that
gap is the whole project.

**why it matters.** when companies deploy ai agents, the agent might say one
thing while "thinking" another, and there's no good way to check — you only see
the output. a game is a cheap lab: low stakes, clean rules, lying is expected, so
we can measure it safely and repeatedly.

**the funny part.** we left holes in the game rules on purpose. the ai finds
them and wins in ways we never designed. that has a real name —
**specification gaming**. researchers once trained a boat-racing ai to win a
race, and it discovered it could score more by spinning in circles collecting
bonus items forever, never finishing. technically obeyed the rules, completely
wrong outcome.

**the line:** *we didn't teach it to cheat. we left the door open and filmed what
walked through.*

**for a mechanical engineer:** instrumented failure testing.
**for an economist:** principal-agent problem with hidden action — except you
finally get to observe the agent's private information.
