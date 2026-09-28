"""
Pre-populates Hindsight with a realistic set of already-resolved historical
incidents, so the demo doesn't start from a completely empty memory bank.

Run:
    python synthetic_data.py --seed
"""

import argparse
import random
from datetime import datetime, timedelta

import hindsight_wrapper
from detection_rules import generate_synthetic_alert, KNOWN_ATTACKER_CAMPAIGNS

random.seed(7)  # reproducible demo history

RESOLUTIONS_FOR_ATTACK = [
    ("malicious", "Forced password reset + revoked all active sessions + required MFA re-enrollment.",
     "Confirmed via IP reputation and repeated targeting of finance accounts."),
    ("malicious", "Blocked source IP/ASN at the edge, forced password reset.",
     "Confirmed account takeover; user did not recognize the login location."),
    ("malicious", "Locked account, opened a security ticket, notified the user directly by phone.",
     "User confirmed they never attempted this login."),
]

RESOLUTIONS_FOR_BENIGN = [
    ("benign", "No action; added travel note to user profile.",
     "User confirmed they were traveling for a client visit."),
    ("benign", "No action.", "New personal laptop, verified with user via Slack."),
]


def seed_history(n: int = 15):
    print(f"Seeding {n} historical resolved incidents into bank '{__import__('config').HINDSIGHT_BANK_ID}'...")
    base_time = datetime.utcnow() - timedelta(days=60)

    for i in range(n):
        is_attack = random.random() < 0.6
        alert = generate_synthetic_alert(force_known_campaign=is_attack)
        alert["timestamp"] = (base_time + timedelta(days=random.randint(0, 55))).isoformat() + "Z"

        if is_attack:
            verdict, action, notes = random.choice(RESOLUTIONS_FOR_ATTACK)
        else:
            verdict, action, notes = random.choice(RESOLUTIONS_FOR_BENIGN)

        case_id = f"INC-{alert['id'].upper()}"
        outcome = notes or "Analyst disposition recorded; no additional outcome note supplied."
        signals = "; ".join(item["detail"] for item in alert.get("evidence", []))
        memory_text = (
            f"AEGIS RESOLVED INCIDENT. Case ID: {case_id}. Alert ID: {alert['id']}. "
            f"Account: {alert['user']['email']} ({alert['user']['name']}, {alert['user']['department']}). "
            f"Pattern: {alert['signature']}. Observed signals: {signals or alert['description']}. "
            f"Network context: {alert['ip']} via {alert['asn']} ({alert['geo']}). "
            f"Final analyst verdict: {verdict}. Analyst action: {action}. Outcome: {outcome}."
        )
        hindsight_wrapper.remember(
            memory_text,
            document_id=case_id,
            metadata={
                "case_id": case_id,
                "alert_id": alert["id"],
                "analyst_verdict": verdict,
                "analyst_action": action,
                "outcome": outcome,
                "account": alert["user"]["email"],
                "user_name": alert["user"]["name"],
                "pattern": alert["signature"],
                "network_context": f"{alert['ip']} via {alert['asn']} ({alert['geo']})",
                "signals": signals or alert["description"],
            },
            tags=["aegis", "synthetic-history", alert["signature"], verdict],
        )
        print(f"  [{i+1}/{n}] {alert['signature']:22s} -> {verdict:10s} ({alert.get('campaign') or 'one-off'})")

    print("Done. Historical memory seeded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Seed historical incidents into Hindsight")
    parser.add_argument("--count", type=int, default=15)
    args = parser.parse_args()

    if args.seed:
        seed_history(args.count)
    else:
        print("Nothing to do. Pass --seed to populate historical incidents.")
