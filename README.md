# Aegis — Memory-Powered Account Takeover Triage Agent

Aegis is a security-alert triage agent built on Hindsight. It investigates account-takeover and credential-stuffing alerts, recalls how similar past cases were actually resolved, and gets more accurate every time an analyst confirms a verdict.

The core idea: **a memory isn't trustworthy until a human confirms it.** Aegis doesn't just store what happened — it stores what an analyst *decided* happened, and uses that confirmed judgment to ground its next recommendation.

## Problem

Security teams triage authentication alerts constantly, but most triage tools are stateless. Every alert — even one that matches a pattern already investigated and confirmed — gets analyzed from scratch. Analyst judgment calls (malicious, benign, needs review) are made and then lost the moment the case closes. That costs response time, creates inconsistent verdicts across analysts, and buries institutional knowledge in individual people's memory instead of anywhere retrievable.

## What Aegis does

- **Investigates** a new alert (failed-login pattern, network context, account history) and produces a risk verdict with a confidence score.
- **Recalls** similar past cases from Hindsight — including the exact case ID, the previous action taken, and the outcome recorded.
- **Explains why a recalled case matters** — e.g. "the same account appears in the recalled case" or "the recalled case describes a similar behavior pattern" — rather than just returning a similarity score.
- **Closes the loop**: when an analyst clicks **Confirm: Malicious** or **Confirm: False Positive** (with an optional note, e.g. "user confirmed traveling"), that decision is retained back into Hindsight as the case's real outcome.
- **Compounds over time**: the next similar alert doesn't just recall "an incident happened here" — it recalls the specific, human-confirmed verdict from that incident.
- **Fails safely**: if the reasoning model can't be reached or returns something unparseable, Aegis conservatively routes the alert to `needs_review` instead of guessing.

## Dashboard overview

The main screen surfaces three running totals plus three controls:

| Alerts triaged | Resolved | Latest confidence |
|---|---|---|
| 8 | 2 | 40% |

**Controls:**
- **Start before/after demo** — runs the scripted 5-step memory comparison (see below)
- **Generate one-off alert** — creates a fresh, non-scripted alert to triage manually
- **Refresh history** — reloads the alert history panel from Hindsight

## Before / after demo

The dashboard runs a scripted five-step comparison:

1. **Before feedback** — an alert is assessed with no analyst memory available.
2. **Analyst decision** — the analyst confirms a verdict on that alert.
3. **Hindsight memory** — the confirmed decision is retained.
4. **Similar alert** — a new, related alert is generated.
5. **Compare** — Aegis's verdict on the new alert is shown side-by-side with the original, unassisted assessment.

The run is resumable: analyst feedback saved to Hindsight persists across a backend restart, and the demo can be re-run (**Run demo again**) or resumed by generating the similar follow-up to check what Recall retrieves.

Example from an actual run:

| | Before — no analyst memory | After — 3 recalled cases |
|---|---|---|
| **Verdict** | malicious | needs_review |
| **Confidence** | 85% | 40% |
| **Reasoning** | Pattern-matched only | "Analyst confirmed INC-904E61D7 as benign. Previous action: No action taken; alert marked as false positive. Outcome: Analyst confirmed benign; no containment action was recorded. Hindsight returned prior case memory for this assessment." |

This is the moment the demo should linger on: memory didn't just add data, it **changed the verdict** — because a human had already looked at this exact pattern before and called it benign.

## Anatomy of a single alert

Worked example — **Alert #ff1288d6**, 9/28/2026, 11:06:47 AM:

> 22 failed login attempts against `rahul.reddy@northbridge-finco.com` in under 90 seconds, followed by one success, from IP `185.220.101.82`.

- **Verdict:** needs review · **Confidence:** 40% · **Used memory:** yes
- **Reasoning shown to the analyst:** "The reasoning model could not be reached or returned an unparseable response, so this alert is being conservatively routed for manual review."
- **Recommended action:** Escalate to on-call analyst for manual triage.

**Investigation evidence panel:**
- Failed-login pattern — 22 failures in under 90 seconds
- Successful authentication — one login succeeded immediately after the failure burst
- Network context — `185.220.101.82` via `AS200011`; flagged explicitly as *supporting evidence, not a standalone verdict*
- Account history — same account previously investigated in Alert #904e61d7, confirmed benign by the analyst
- Hindsight memory — 3 related case(s) retrieved

**Incident timeline (per-second granularity):**

| Time (UTC) | Event |
|---|---|
| 05:35:29Z | First cluster of authentication failures |
| 05:36:16Z | Failure burst continues — 22 failures accumulated |
| 05:36:39Z | Login succeeds immediately after the failure burst |
| 05:36:56Z | Aegis investigation — behavior, account, network, and historical evidence correlated |
| 05:36:57Z | Hindsight recall — 3 related case(s) returned |
| 05:36:58Z | Risk assessment — needs review · 40% confidence |

**Memory Impact line** (shown directly under the timeline): *1 retained case(s), 1 unlinked record(s) · current verdict: needs_review*

## Recall detail: what gets shown per recalled case

`RECALL · COMPLETED — Hindsight Recall retrieved 3 record(s), grouped into 1 case(s).`

**Why these cases matter:**
- The same account or employee appears in the recalled case
- The recalled case describes a similar incident behavior pattern

**Case document — `INC-904E61D7` (benign):**
- Previous action: No action taken; alert marked as false positive
- Outcome: Analyst confirmed benign; no containment action was recorded
- Relevant signals: same account/employee; similar behavior pattern
- Hindsight records: `d4a9b51e-5245-43b1-9cde-2b63b8c9e8d5`, `fd122a42-d310-4ed6-a4d7-f038e0351b6c`

**Partial record — `HIN-c343a21b`:**
- Case ID not preserved in this Hindsight record
- Previous action / outcome: not preserved
- Relevant signals: same account/employee; similar behavior pattern
- Hindsight record: `c343a21b-d3cf-4b62-aca0-c12fabb43340`

Showing partial records honestly — rather than backfilling missing fields — is intentional. It reflects real memory-quality behavior instead of hiding it, which matters for demonstrating that Aegis's confidence is grounded in what memory actually returned.

## Analyst feedback

*Analyst decision → Hindsight memory → future triage*

- Optional free-text notes field (e.g. "user confirmed traveling")
- **Confirm: Malicious**
- **Confirm: False positive**
- A live **confidence trend** chart tracks how confidence shifts across the session as more feedback is retained

## Learning journey

The dashboard tracks memory accumulation explicitly, not just per-alert:

- **Alert 1** — analyst decision retained (`INC-904E61D7 · benign · Hindsight Retain confirmed`)
- **Alert 2** — that decision recalled for a follow-up assessment
- **Alert 3** — accumulated security history: **14 distinct case IDs found across 5 matching pattern categories**
- **Current alert** — verdict (`needs_review · 40%`) informed by 1 recalled case

## Security patterns in Hindsight

`RECALL · COMPLETED — 14 distinct case ID(s) across 6 queried patterns.`

| Pattern | Cases | Unlinked records |
|---|---|---|
| Credential stuffing | 4 | 8 |
| Repeated failures followed by success | 4 | 4 |
| Impossible travel | 3 | 3 |
| New device activity | 5 | 2 |
| MFA method or setting changes | 0 | 0 |
| MFA fatigue or bypass | 2 | 3 |

Grouping recalled records into named attack categories lets Aegis reason about recurring threat types, not just isolated incidents — and the "unlinked record" count is a deliberately visible signal of memory that hasn't yet been consolidated into a confirmed case.

## Alert history

A running log of triaged alerts, most recent first:

| Account | Verdict | Confidence |
|---|---|---|
| rahul.reddy | needs review | 40% |
| rahul.reddy | malicious | 85% |
| fatima.reddy | malicious | 85% |
| fatima.sharma | benign | 88% |
| fatima.sharma | malicious | 80% |
| vikram.nair | needs review | 60% |
| sameer.iyer | needs review | 60% |
| priya.menon | malicious | 95% |

## Architecture

```
Analyst
   ↓
Alert Dashboard (triage UI, before/after demo, analyst feedback controls)
   ↓
Aegis Agent
   ├── Recall from Hindsight (account, IP, ASN, behavior pattern)
   ├── Reflect — group recalled records into pattern categories
   ├── Call Groq for risk assessment / recommendation
   └── Retain analyst-confirmed verdict back into Hindsight
   ↓
Hindsight Memory Bank
```

**Stack:**
- **Memory:** Hindsight Cloud
- **Reasoning:** Groq
- **Frontend:** Alert triage dashboard (investigation evidence, timeline, recalled-case panel, analyst feedback controls, confidence trend, learning journey, pattern breakdown)

## Running the project

1. **Install dependencies**
```bash
   pip install -r requirements.txt
```
2. **Configure environment** — create a `.env` file:
```env
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   HINDSIGHT_API_KEY=your_hindsight_key
   HINDSIGHT_BANK_ID=account-takeover-triage
   GROQ_API_KEY=your_groq_key
   GROQ_MODEL=openai/gpt-oss-120b
```
3. **Seed the memory bank** with sample alerts and confirmed cases.
4. **Run the app** and open the dashboard.
5. Click **Start before/after demo** to run the scripted comparison, or **Generate one-off alert** to triage a fresh case manually. Use **Refresh history** to reload the alert log from Hindsight.

> If the reasoning model can't be reached, Aegis falls back to routing the alert for manual review rather than guessing — this fallback is intentional and visible in the UI (see the `needs_review · 40%` case above), not a bug.

## Honest limitations

- Some recalled Hindsight records don't preserve full case metadata (case ID, previous action) — shown transparently rather than backfilled.
- The reasoning model has an explicit conservative fallback (route to manual review) when it can't be reached — a safety choice, but it does mean confidence scores can appear low even when the underlying evidence is strong.
- This is a triage *assistant*, not an automated containment system — all containment actions (password reset, session revocation) are analyst-confirmed, not agent-executed.
- The synthetic alert data is realistic but demo-oriented.

## Why this matters

Aegis isn't just retrieving similar-looking text. It's tracking which past judgment calls were actually confirmed by a human, weighting new recommendations by that precedent, and getting measurably more accurate the more an analyst uses it. That's the operational difference between a stateless classifier and a triage system that accumulates real institutional judgment.
