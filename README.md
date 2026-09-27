# Incident Response Agent — built on Hindsight

This project is an incident-response agent that learns from the incidents the team has already solved. It stores what happened, why it happened, what fixed it, and which runbook was used in Hindsight; then it recalls the closest prior examples when a new outage appears.

The value of the system is not just “an LLM answering a question.” The system gets more useful as more incidents are retained and recalled over time.

## Problem

A stateless incident bot gives the same generic advice every time: check recent deploys, look at error rates, inspect the database. That is not enough when the team has already solved the same class of problem multiple times.

Operators need an assistant that can say:

- this looks like the same pattern we saw on checkout-service last month
- the last fix was to roll back the pool config
- the relevant precedent is INC-014 and INC-021
- the runbook to follow is RB-DB-CONN-POOL

## Why Hindsight is central

Hindsight is the core of the product, not a side feature. The application becomes more valuable as incident history accumulates because the same operational patterns are remembered and retrieved automatically.

The memory flow is explicit:

1. Retain: save a resolved incident and its fix to the bank
2. Recall: search the bank for the closest historical precedents
3. Reflect: look for recurring patterns across retained incidents
4. Respond: use the recalled evidence to produce a better incident recommendation

Without Hindsight, the agent would give a generic checklist. With Hindsight, it can reason from previous failure modes and successful remediations.

## What the agent remembers

For every resolved incident, the agent stores:

- service
- date
- symptoms
- root cause
- fix that worked
- runbook used
- operational context and recurring pattern hints

This is stored in the same Hindsight bank used for future recall and pattern analysis.

## How the demo tells the story

The project is built around a before/after incident-triage story:

- Scene 1: without memory, the assistant provides generic guidance
- Scene 2: past incidents are retained
- Scene 3: a new incident arrives with similar symptoms
- Scene 4: relevant historical incidents are recalled
- Scene 5: recurring patterns are surfaced
- Scene 6: the improved recommendation uses precedent and evidence
- Scene 7: the new incident is resolved and retained, increasing future knowledge

## Learning over time

The demo intentionally shows a learning journey:

- Incident #1 establishes an initial pattern
- Incident #5 shows the same service recurs
- Pattern analysis identifies the recurring failure mode
- A later incident uses the accumulated evidence to guide a stronger recommendation

This is visible in the project’s learning timeline and in the increased specificity of recall results over time.

## Architecture

```text
User / Operator
    ↓
Incident Input (service, symptoms, severity, logs)
    ↓
IncidentResponseAgent
    ├── Recall from Hindsight
    ├── Compare to historical incidents
    ├── Reflect / identify recurring patterns
    ├── Call Groq for recommendation synthesis
    └── Retain resolved incident back into Hindsight
```

Key files:

- app/agent.py — retain / recall / reflect / respond workflow
- app/hindsight_client.py — Hindsight API wrapper with offline fallback
- app/llm_client.py — Groq chat client with fallback logic
- app/data/synthetic_incidents.py — realistic recurring incident data and learning timeline helpers
- demo.py — live demo and before/after incident story
- scripts/seed_memory.py — stores example incidents in Hindsight

## How retain and recall work

### Retain

When an incident is marked resolved, the agent calls close_incident() and stores a structured incident summary in Hindsight. The summary includes the service, symptoms, root cause, fix, and runbook.

### Recall

Before generating a response, the agent queries Hindsight for similar past incidents. The returned memory items are inserted into the Groq prompt as precedent and evidence.

### Reflect

The agent can also ask the memory bank to summarize recurring patterns, such as a repeated checkout-service database pool exhaustion pattern.

## Before / after example

Without memory:

> Check recent deploys, inspect error rates, look at dependency health, and start generic triage.

With memory:

> This matches the checkout-service pool-exhaustion pattern from INC-014 and INC-021. The same symptoms were solved by increasing max_connections and isolating shared connection pools. Use that runbook first.

## Running the project

### 1) Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure your environment

Create a .env file based on the sample and fill in your keys:

```env
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_KEY=your_hindsight_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=qwen/qwen3-32b
HINDSIGHT_BANK_ID=incident-response
```

### 4) Seed the memory bank

```bash
python scripts/seed_memory.py
```

### 5) Run the demo

```bash
python demo.py
```

If no keys are present, the app falls back to a local offline demo path so the flow still executes. The live mode remains the primary experience when API credentials are set.

## Tech stack

- Memory: Hindsight
- LLM: Groq
- Language: Python
- Data: realistic synthetic incidents for recurring service patterns

## Why the system is better with memory

The bot is not just retrieving text. It is learning from previous resolutions, identifying recurring problems, and weighting the recommendation according to historical precedent.

That is the operational difference between a generic assistant and an incident-response system that accumulates institutional knowledge.

## Honest limitations

- The synthetic dataset is intentionally realistic but still demo-oriented
- Memory quality depends on how incidents are retained
- The project is a focused CLI demo rather than a full PagerDuty/Opsgenie workflow integration
- Real production usage would add richer telemetry, automation, and workflow integration

## Safety and correctness

- The Hindsight integration remains central
- Live mode remains supported
- The fallback offline mode remains intact
- API keys stay in .env and are not exposed in the project code or logs

## Need for live demo screenshots

For a judge demo, the most compelling screenshots are:

1. Hindsight memory bank
2. LIVE (Hindsight + Groq) mode
3. Recalled historical incidents
4. Agent WITHOUT memory
5. Agent WITH memory
6. The memory journey / learning timeline

These visuals make the memory-driven value obvious in under one minute.
