from datetime import datetime, timedelta
import re
from typing import Optional
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import detection_rules
import llm_agent
import hindsight_wrapper

app = FastAPI(title="Aegis — Memory-Powered Incident Response Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session state (just for the demo; not the "memory" the project is about —
# that's Hindsight. This is only holding the alerts generated during this run so the
# dashboard can reference them by id.)
ALERTS: dict = {}
STATS = {"total": 0, "resolved": 0}
DEMO_RUNS: dict = {}

PATTERN_QUERIES = [
    ("credential_stuffing", "Credential stuffing", "credential stuffing repeated failed logins followed by success", ("credential stuffing",)),
    ("failed_then_success", "Repeated failures followed by success", "many failed logins then successful authentication", ("failed login", "failed attempts")),
    ("impossible_travel", "Impossible travel", "impossible travel login locations too far apart", ("impossible travel", "impossible-travel")),
    ("new_device", "New device activity", "new unrecognized device login account", ("new device", "unrecognized device", "unrecognized laptop")),
    ("mfa_change", "MFA method or setting changes", "MFA method enrollment removal or account factor change", ("mfa change", "mfa method", "factor change", "mfa enrollment")),
    ("mfa_bypass", "MFA fatigue or bypass", "MFA fatigue repeated push approval bypass attempts", ("mfa fatigue", "mfa bypass", "push notification")),
]


class DemoContinueRequest(BaseModel):
    user: dict
    first_alert_id: str
    analyst_verdict: str
    before_verdict: str
    before_confidence: int


def _analyze_and_store(alert: dict, bank_id: str = None, demo: dict = None) -> dict:
    alert["triage"] = llm_agent.triage(alert, bank_id=bank_id)
    alert["evidence"].append({
        "label": "Hindsight memory",
        "detail": (
            f"Retrieved {len(alert['triage']['recalled_incidents'])} related case(s)."
            if alert["triage"]["recalled_incidents"]
            else "No relevant prior analyst decision was retrieved."
        ),
    })
    assessed_at = datetime.utcnow()
    recalled_at = assessed_at + timedelta(seconds=1)
    alert["timeline"].extend([
        {"time": assessed_at.strftime("%H:%M:%S"), "event": "Aegis investigation", "detail": "Correlated behavior, account, network, and historical evidence."},
        {"time": recalled_at.strftime("%H:%M:%S"), "event": "Hindsight recall", "detail": f"{len(alert['triage']['recalled_incidents'])} related case(s) returned."},
        {"time": (recalled_at + timedelta(seconds=1)).strftime("%H:%M:%S"), "event": "Risk assessment", "detail": f"{alert['triage']['verdict'].replace('_', ' ')} · {alert['triage']['confidence']}% confidence."},
    ])
    if demo:
        alert["demo"] = demo
    ALERTS[alert["id"]] = alert
    STATS["total"] += 1
    return alert


def _learning_summary(alert: dict, verdict: str) -> str:
    pattern = {
        "credential_stuffing": "credential-stuffing behavior and its failed-login-then-success sequence",
        "mfa_bypass_attempt": "repeated MFA-prompt behavior",
        "impossible_travel": "the impossible-travel pattern",
        "new_device_odd_hour": "the new-device, unusual-hour pattern",
    }.get(alert["signature"], "this incident pattern")
    return (
        f"The analyst confirmed this {pattern} as {verdict}. Future triage can compare "
        "the behavior, authentication outcome, account, network context, and this analyst decision."
    )


def _pattern_case_groups(records: list[dict], terms: tuple[str, ...]) -> list[dict]:
    groups = {}
    for record in records:
        text = record.get("text", "")
        lowered = text.casefold()
        if not any(term in lowered for term in terms):
            continue
        metadata = record.get("metadata") or {}
        document_id = record.get("document_id") or metadata.get("case_id")
        record_id = record.get("id") or "unknown-record"
        key = document_id or record_id
        case = groups.setdefault(key, {
            "case_id": document_id or f"HIN-{record_id[:8]}",
            "document_id": document_id,
            "identity_type": "case document" if document_id else "Hindsight record; case ID not preserved",
            "record_ids": [],
            "verdict": metadata.get("analyst_verdict") or metadata.get("verdict") or "Not preserved in this Hindsight record",
            "previous_action": metadata.get("analyst_action") or metadata.get("action_taken") or "Not preserved in this Hindsight record",
            "outcome": metadata.get("outcome") or "Not preserved in this Hindsight record",
            "signals": [],
            "memory_text": [],
        })
        if record_id not in case["record_ids"]:
            case["record_ids"].append(record_id)
        if text and text not in case["memory_text"]:
            case["memory_text"].append(text)
        if case["verdict"] == "Not preserved in this Hindsight record":
            verdict_match = re.search(r"(?:final analyst verdict|final verdict|analyst verdict)\s*[:=-]\s*(malicious|benign|needs_review)", text, re.IGNORECASE)
            if verdict_match:
                case["verdict"] = verdict_match.group(1).lower()
        if case["previous_action"] == "Not preserved in this Hindsight record":
            action_match = re.search(r"(?:analyst action|action taken)\s*[:=-]\s*(.+?)(?=\.\s*(?:outcome|analyst notes)\s*[:=-]|$)", text, re.IGNORECASE)
            if action_match:
                case["previous_action"] = action_match.group(1).strip()
        if case["outcome"] == "Not preserved in this Hindsight record":
            outcome_match = re.search(r"(?:outcome|analyst notes)\s*[:=-]\s*(.+?)(?:\.\s|$)", text, re.IGNORECASE)
            if outcome_match:
                case["outcome"] = outcome_match.group(1).strip()
        for term in terms:
            if term in lowered and term not in case["signals"]:
                case["signals"].append(term)
    return list(groups.values())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/alerts/generate")
def generate_alert():
    alert = detection_rules.generate_synthetic_alert()
    return _analyze_and_store(alert)


@app.post("/demo/start")
def start_learning_demo():
    run_id = uuid.uuid4().hex[:8]
    bank_id = f"aegis-demo-{run_id}"
    alert = detection_rules.generate_demo_alert(stage=1)
    DEMO_RUNS[run_id] = {
        "bank_id": bank_id,
        "user": alert["user"],
        "first_alert_id": alert["id"],
        "first_resolved": False,
        "memory_stored": False,
    }
    return _analyze_and_store(
        alert,
        bank_id=bank_id,
        demo={"run_id": run_id, "stage": "before", "label": "Before analyst feedback"},
    )


@app.post("/demo/{run_id}/next")
def generate_after_learning_demo(run_id: str, body: DemoContinueRequest):
    if not re.fullmatch(r"[0-9a-f]{8}", run_id):
        raise HTTPException(status_code=400, detail="Invalid learning-demo ID.")
    run = DEMO_RUNS.get(run_id)
    if run and not run["first_resolved"]:
        raise HTTPException(status_code=409, detail="Resolve the first alert with analyst feedback before continuing.")
    user = run["user"] if run else body.user
    first_alert_id = run["first_alert_id"] if run else body.first_alert_id
    analyst_verdict = run["analyst_verdict"] if run else body.analyst_verdict
    before_verdict = run["first_triage"]["verdict"] if run else body.before_verdict
    before_confidence = run["first_triage"]["confidence"] if run else body.before_confidence
    bank_id = f"aegis-demo-{run_id}"
    case_id = f"INC-{first_alert_id.upper()}"
    verification_query = (
        f"AEGIS RESOLVED INCIDENT Case ID: {case_id}. Account: {user['email']}. "
        f"Final analyst verdict: {analyst_verdict}. Pattern: credential_stuffing."
    )
    verified_records = hindsight_wrapper.recall_records(
        verification_query,
        bank_id=bank_id,
        limit=50,
    )
    retained_case_records = [
        record for record in verified_records
        if record.get("document_id") == case_id
        or (record.get("metadata") or {}).get("case_id") == case_id
    ]
    if not retained_case_records:
        raise HTTPException(
            status_code=409,
            detail="Hindsight could not verify Alert 1's retained case after restart; the follow-up was not generated.",
        )
    retained_metadata = next(
        (record.get("metadata") or {} for record in retained_case_records if record.get("metadata")),
        {},
    )
    retained_verdict = retained_metadata.get("analyst_verdict")
    if retained_verdict and retained_verdict != analyst_verdict:
        raise HTTPException(status_code=409, detail="The retained Hindsight verdict does not match this demo run.")

    alert = detection_rules.generate_demo_alert(
        stage=2,
        user=user,
        prior_alert_id=first_alert_id,
        prior_verdict=retained_verdict or analyst_verdict,
    )
    demo = {
        "run_id": run_id,
        "stage": "after",
        "label": "After analyst feedback",
        "previous_alert_id": first_alert_id,
        "previous_case_id": case_id,
        "previous_analyst_verdict": retained_verdict or analyst_verdict,
        "previous_action": retained_metadata.get("analyst_action", "Action recorded in Hindsight; details unavailable."),
        "previous_outcome": retained_metadata.get("outcome", "Outcome not preserved in Hindsight metadata."),
        "before_verdict": before_verdict,
        "before_confidence": before_confidence,
        "restart_recovery": run is None,
    }
    return _analyze_and_store(alert, bank_id=bank_id, demo=demo)


class ResolveRequest(BaseModel):
    verdict: str  # "malicious" | "benign"
    action: str
    notes: Optional[str] = ""


@app.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, body: ResolveRequest):
    alert = ALERTS.get(alert_id)
    if not alert:
        return {"error": "alert not found"}

    memory_text = llm_agent.build_resolution_memory(
        alert, alert["triage"], body.verdict, body.action, body.notes
    )
    demo = alert.get("demo")
    run = DEMO_RUNS.get(demo["run_id"]) if demo else None
    case_id = f"INC-{alert['id'].upper()}"
    outcome = body.notes or (
        "Analyst confirmed malicious; operational action completion was not verified."
        if body.verdict == "malicious"
        else "Analyst confirmed benign; no containment action was recorded."
    )
    retain_result = hindsight_wrapper.remember(
        memory_text,
        bank_id=run["bank_id"] if run else None,
        document_id=case_id,
        metadata={
            "case_id": case_id,
            "alert_id": alert["id"],
            "analyst_verdict": body.verdict,
            "analyst_action": body.action,
            "outcome": outcome,
            "account": alert["user"]["email"],
            "user_name": alert["user"]["name"],
            "pattern": alert["signature"],
            "network_context": f"{alert['ip']} via {alert['asn']} ({alert['geo']})",
            "signals": "; ".join(item["detail"] for item in alert.get("evidence", [])),
        },
        tags=["aegis", "analyst-feedback", alert["signature"], body.verdict],
    )
    memory_stored = retain_result["success"]

    alert["resolved"] = True
    alert["resolution"] = {
        "verdict": body.verdict,
        "action": body.action,
        "notes": body.notes,
    }
    STATS["resolved"] += 1
    learning_summary = _learning_summary(alert, body.verdict)
    if run and demo["stage"] == "before":
        run["first_resolved"] = True
        run["memory_stored"] = memory_stored
        run["analyst_verdict"] = body.verdict
        run["first_triage"] = alert["triage"]
        run["learning_summary"] = learning_summary
        run["case_id"] = case_id
    return {
        "status": "resolved",
        "memory_stored": memory_stored,
        "retain_operation": {
            "operation": "Hindsight Retain",
            "status": "confirmed" if memory_stored else "failed",
            "bank_id": retain_result["bank_id"],
            "case_id": case_id,
            "items_count": retain_result["items_count"],
        },
        "learning_summary": learning_summary,
        "demo_ready": bool(run and demo["stage"] == "before" and memory_stored),
    }


@app.get("/alerts")
def list_alerts():
    return list(ALERTS.values())[::-1]


@app.get("/stats")
def stats():
    return STATS


@app.get("/memory/patterns")
def memory_patterns():
    patterns = []
    all_case_ids = set()
    overall_status = "empty"
    for pattern_id, label, query, terms in PATTERN_QUERIES:
        recall = hindsight_wrapper.recall_with_status(
            query,
            bank_id=config.HINDSIGHT_BANK_ID,
            limit=100,
        )
        matched = [
            record for record in recall["records"]
            if any(term in record.get("text", "").casefold() for term in terms)
        ]
        cases = _pattern_case_groups(matched, terms)
        all_case_ids.update(case["document_id"] for case in cases if case["document_id"])
        if recall["status"] == "completed":
            overall_status = "completed"
        elif recall["status"] == "failed" and overall_status != "completed":
            overall_status = "partial" if patterns else "failed"
        patterns.append({
            "id": pattern_id,
            "label": label,
            "recall_status": recall["status"],
            "retrieved_record_count": len(matched),
            "case_count": len({case["document_id"] for case in cases if case["document_id"]}),
            "unlinked_record_count": sum(1 for record in matched if not record.get("document_id") and not (record.get("metadata") or {}).get("case_id")),
            "cases": cases,
        })
    return {
        "operation": "Hindsight Recall",
        "status": overall_status,
        "bank_id": config.HINDSIGHT_BANK_ID,
        "unique_case_count": len(all_case_ids),
        "patterns": patterns,
        "observed_at": datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
