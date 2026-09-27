# Notes for the required content deliverables

Every team member must publish their own article + LinkedIn post, and the team
publishes one video. These notes save you the "what do I even say" step — feed
this whole file (plus the repo) to Claude Code/Codex and run the guide's three
prompts, or just use it directly.

**Rule that disqualifies you if broken: never write the word "hackathon"
anywhere — title, body, or hashtags, in any of the three deliverables.**

## Working title options (pick one, or riff)

- Why our incident bot forgets nothing after the first postmortem
- I gave our on-call bot a memory of every past incident
- Six minutes to five seconds: what memory did to incident triage
- Our checkout service breaks the same way every few weeks — now the bot notices
- What changes when an agent remembers your last outage
- Building an on-call assistant that cites its own precedent

## One-sentence pitch

An on-call assistant that remembers every resolved incident — symptoms, root
cause, the fix that worked — and recalls the closest match the second a new
incident comes in, instead of making an engineer re-read old postmortems.

## Before/after to lead with

Without memory: "check recent deploys, check error rates, check dependency
health" — the same generic checklist every time.

With memory: "this is the same connection-pool exhaustion pattern as INC-014
and INC-021, both on checkout-service — try the fix that worked there first,"
with the incident IDs cited.

## Code snippets worth pulling into the article

- `app/agent.py::triage()` — the retain-before-respond loop
- `app/hindsight_client.py::HindsightMemory.retain_incident` — how a resolved
  incident gets written to Hindsight
- `app/data/synthetic_incidents.py::as_retain_text` — how a raw incident dict
  becomes the text Hindsight indexes

## Honest lessons to include (per the organizers' rubric)

1. Recall quality lives and dies on how the incident is worded at retain time —
   no summarization pass yet.
2. A naive keyword-overlap fallback (used offline) makes obvious how much work
   Hindsight's real semantic + graph retrieval is doing under the hood.
3. Groq function-calling needs an explicit retry/fallback path — it does fail
   sometimes, and failing silently in an on-call tool is worse than useless.
4. Seeding realistic data (recurring incident patterns, like the connection-pool
   issue hitting the same service three times) mattered more for a believable
   demo than any UI polish.

## Links to include (per submission rules)

- Hindsight GitHub: https://github.com/vectorize-io/hindsight
- Hindsight docs: https://hindsight.vectorize.io/
- Vectorize — what is agent memory: https://vectorize.io/what-is-agent-memory
