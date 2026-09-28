"""
The reasoning layer. Combines:
  - the current alert (from detection_rules.py)
  - recalled past incidents (from Hindsight recall())
  - a synthesized second opinion (from Hindsight reflect())
into one LLM call that produces a structured triage verdict.

Uses Groq. Falls back to a safe default verdict if the LLM call fails or
returns malformed JSON — this matters because the hackathon brief specifically
calls out handling function-calling / parsing errors gracefully.
"""

import json
import re
from groq import Groq
import config
import hindsight_wrapper

_groq_client = None


def _client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


SYSTEM_PROMPT = """You are Aegis, a SOC triage assistant. You are given a new login-anomaly \
alert plus memories of past, already-resolved incidents that may be related. \
Decide whether this alert is likely `malicious`, `benign`, or `needs_review`, \
and recommend one concrete containment action.

Ground your verdict in the recalled memories when they are genuinely similar \
(same IP/ASN, same campaign, same attacker technique). If nothing relevant was \
recalled, say so plainly and give a more cautious, generic assessment with \
lower confidence. Weigh the behavior pattern, authentication outcome, account \
history, infrastructure, and prior analyst decisions together. Never classify an \
alert as malicious solely because its IP address or ASN appeared in a past case. \
For each recalled memory, state only relevance reasons supported by that memory.

Respond with ONLY a JSON object, no markdown fences, no commentary, matching \
exactly this shape:
{
  "verdict": "malicious" | "benign" | "needs_review",
  "confidence": <integer 0-100>,
  "reasoning": "<2-3 sentences, plain language, mention specific recalled cases if used>",
  "recommended_action": "<one concrete next step>",
    "used_memory": true | false,
    "relevance_reasons": ["<specific matching signal>"]
}"""


def _build_query(alert: dict) -> str:
    evidence = "\n".join(
        f"- {item['label']}: {item['detail']}"
        for item in alert.get("evidence", [])
    )
    return (
        f"Login anomaly for {alert['user']['email']} ({alert['user']['department']}): "
        f"{alert['description']} Signature: {alert['signature']}. "
        f"IP: {alert['ip']} ({alert['asn']}, {alert['geo']}).\n"
        f"Observed evidence:\n{evidence or '(no structured evidence supplied)'}"
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def _fallback_verdict(recalled: list) -> dict:
    return {
        "verdict": "needs_review",
        "confidence": 40,
        "reasoning": "The reasoning model could not be reached or returned an unparseable "
                     "response, so this alert is being conservatively routed for manual review.",
        "recommended_action": "Escalate to on-call analyst for manual triage.",
        "used_memory": bool(recalled),
        "relevance_reasons": [],
    }


def _memory_relevance_reasons(alert: dict, recalled: list) -> list:
    if not recalled:
        return []

    memory_text = "\n".join(recalled).casefold()
    reasons = []
    user = alert.get("user", {})
    email = user.get("email", "").casefold()
    name = user.get("name", "").casefold()
    if (email and email in memory_text) or (name and name in memory_text):
        reasons.append("The same account or employee appears in the recalled case.")

    signature_terms = {
        "credential_stuffing": ("credential stuffing", "credential-stuffing", "failed login"),
        "mfa_bypass_attempt": ("mfa fatigue", "mfa bypass", "push notification"),
        "impossible_travel": ("impossible travel", "impossible-travel"),
        "new_device_odd_hour": ("new device", "unusual hour", "odd hour"),
    }
    if any(term in memory_text for term in signature_terms.get(alert.get("signature"), ())):
        reasons.append("The recalled case describes a similar incident behavior pattern.")

    asn_id = alert.get("asn", "").split(" ", 1)[0].casefold()
    if asn_id.startswith("as") and any(char.isdigit() for char in asn_id) and asn_id in memory_text:
        reasons.append(f"The same ASN ({asn_id.upper()}) appears in the recalled case.")

    disposition_terms = (
        "final verdict:",
        "analyst corrected",
        "analyst confirmed",
        "confirmed malicious",
        "confirmed credential-stuffing",
        "confirmed credential stuffing",
        "determined to be benign",
        "malicious activity",
    )
    if any(term in memory_text for term in disposition_terms):
        reasons.append("The recalled case includes a previous analyst disposition.")

    return reasons or ["Hindsight ranked this case as semantically related; inspect the incident detail below."]


def _memory_cases(alert: dict, records: list[dict]) -> list[dict]:
    cases = {}
    for record in records:
        metadata = record.get("metadata") or {}
        document_id = record.get("document_id") or metadata.get("case_id")
        record_id = record.get("id") or "unknown-record"
        case_key = document_id or record_id
        case = cases.setdefault(case_key, {
            "case_id": document_id or f"HIN-{record_id[:8]}",
            "identity_type": "case document" if document_id else "Hindsight record; case ID not preserved",
            "document_id": document_id,
            "record_ids": [],
            "verdict": "Not preserved in this Hindsight record",
            "previous_action": "Not preserved in this Hindsight record",
            "outcome": "Not preserved in this Hindsight record",
            "relevant_signals": [],
            "memory_text": [],
        })
        if record_id not in case["record_ids"]:
            case["record_ids"].append(record_id)

        text = record.get("text", "")
        if text and text not in case["memory_text"]:
            case["memory_text"].append(text)

        verdict = metadata.get("analyst_verdict") or metadata.get("verdict")
        if not verdict:
            match = re.search(
                r"(?:final analyst verdict|final verdict|analyst verdict)\s*[:=-]\s*(malicious|benign|needs_review)",
                text,
                re.IGNORECASE,
            )
            verdict = match.group(1) if match else None
        if verdict:
            case["verdict"] = verdict

        action = metadata.get("analyst_action") or metadata.get("action_taken")
        if not action:
            match = re.search(r"(?:analyst action|action taken)\s*[:=-]\s*(.+?)(?=\.\s*(?:outcome|analyst notes)\s*[:=-]|$)", text, re.IGNORECASE)
            action = match.group(1).strip() if match else None
        if action:
            case["previous_action"] = action

        outcome = metadata.get("outcome") or metadata.get("analyst_notes")
        if not outcome:
            match = re.search(r"(?:outcome|analyst notes)\s*[:=-]\s*(.+?)(?:\.\s|$)", text, re.IGNORECASE)
            outcome = match.group(1).strip() if match else None
        if outcome:
            case["outcome"] = outcome

        for signal in _memory_relevance_reasons(alert, [text]):
            if signal not in case["relevant_signals"]:
                case["relevant_signals"].append(signal)

    return list(cases.values())


def triage(alert: dict, bank_id: str = None) -> dict:
    query = _build_query(alert)

    recall_operation = hindsight_wrapper.recall_with_status(query, bank_id=bank_id, limit=20)
    recalled_records = recall_operation["records"]
    recalled = [record["text"] for record in recalled_records]
    reflection = hindsight_wrapper.synthesize(query, bank_id=bank_id)

    memory_block = "\n".join(f"- {m}" for m in recalled) if recalled else "(none found)"

    user_prompt = f"""NEW ALERT:
{query}

RECALLED PAST INCIDENTS (via Hindsight recall):
{memory_block}

CURRENT ALERT EVIDENCE (consider all applicable signals, not just network identity):
{chr(10).join(f"- {item['label']}: {item['detail']}" for item in alert.get('evidence', [])) or '(none supplied)'}

HINDSIGHT SYNTHESIZED OPINION (via reflect):
{reflection or "(no synthesized opinion available)"}

Produce your JSON verdict now."""

    try:
        completion = _client().chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        raw = completion.choices[0].message.content
        result = _extract_json(raw)
    except Exception as e:
        print(f"[llm_agent] triage failed, using fallback: {e}")
        result = _fallback_verdict(recalled)

    memory_cases = _memory_cases(alert, recalled_records)
    retained_case_count = sum(1 for memory_case in memory_cases if memory_case["document_id"])
    unlinked_record_count = sum(1 for memory_case in memory_cases if not memory_case["document_id"])
    result["relevance_reasons"] = _memory_relevance_reasons(alert, recalled)
    result["recalled_incidents"] = recalled
    result["recalled_records"] = recalled_records
    result["memory_impact"] = {
        "recall_status": recall_operation["status"],
        "bank_id": recall_operation["bank_id"],
        "recalled_record_count": len(recalled_records),
        "case_count": retained_case_count,
        "unlinked_record_count": unlinked_record_count,
        "cases": memory_cases,
        "current_verdict": result.get("verdict", "needs_review"),
    }
    result["reflection"] = reflection
    return result


def build_resolution_memory(alert: dict, verdict_result: dict, analyst_verdict: str,
                             analyst_action: str, analyst_notes: str) -> str:
    """
    Turn a resolved incident into a natural-language memory to retain().
    This is the write side of the learning loop.
    """
    query = _build_query(alert)
    corrected = analyst_verdict != verdict_result.get("verdict")
    correction_note = (
        f" NOTE: the agent's initial verdict was '{verdict_result.get('verdict')}' but the "
        f"analyst corrected it to '{analyst_verdict}' — weigh this correction heavily for "
        f"similar future alerts."
        if corrected else ""
    )
    case_id = f"INC-{alert['id'].upper()}"
    evidence = "; ".join(
        f"{item['label']}: {item['detail']}"
        for item in alert.get("evidence", [])
        if item.get("label") != "Hindsight memory"
    )
    outcome = analyst_notes or (
        "Analyst confirmed the alert as malicious; operational action completion was not verified."
        if analyst_verdict == "malicious"
        else "Analyst confirmed the alert as benign; no containment action was recorded."
    )
    return (
        f"AEGIS RESOLVED INCIDENT. Case ID: {case_id}. Alert ID: {alert['id']}. "
        f"Account: {alert['user']['email']} ({alert['user']['name']}, {alert['user']['department']}). "
        f"Pattern: {alert['signature']}. Observed signals: {evidence or query}. "
        f"Network context: {alert['ip']} via {alert['asn']} ({alert['geo']}). "
        f"Final analyst verdict: {analyst_verdict}. Analyst action: {analyst_action}. "
        f"Outcome: {outcome}.{correction_note}"
    )
