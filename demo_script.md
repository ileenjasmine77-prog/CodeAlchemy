# Aegis Incident Response Demo

## Setup

Start the backend and dashboard, then choose **Start before/after demo**. The demo creates an isolated Hindsight bank so Alert 1 begins without a prior analyst decision. The regular seeded incident bank remains unchanged.

## 60-second walkthrough

**[0:00-0:10] Incident response scope**

> "Aegis helps SOC analysts investigate account-takeover alerts by combining authentication behavior, account context, network signals, and prior analyst decisions. It supports the analyst; it does not make the final response decision."

**[0:10-0:25] Alert 1: before analyst feedback**

Start the guided demo. Point out the failed-login burst, successful login afterward, account, IP/ASN context, and incident timeline. The first assessment is made against a fresh demo memory bank with no prior analyst disposition.

> "Aegis assesses the available evidence, but it has no resolved case from this demo to learn from yet. The network address is one signal, not the verdict by itself."

Choose **Confirm: Malicious** (or the appropriate analyst decision), optionally add a note, and point to **What Aegis Learned**. The demo continues only when Hindsight confirms that the analyst decision was written.

**[0:25-0:45] Alert 2: after analyst feedback**

Choose **Generate similar alert after learning**. The follow-up has the same account and credential-stuffing behavior with a nearby address on the same ASN. Point to the recalled case, the model's relevance reasons, and the before/after comparison.

> "The new alert is assessed with the analyst's resolved case available through Hindsight. We show the model's actual verdict and confidence; we don't hard-code a confidence increase."

If Hindsight returns no prior case, the dashboard says so rather than claiming a memory effect.

**[0:45-1:00] Human-in-the-loop learning**

> "The workflow is alert, evidence, Hindsight memory, assessment, analyst decision, then a new memory for future triage. Aegis gives the analyst useful precedent while leaving the decision and response in human hands."
