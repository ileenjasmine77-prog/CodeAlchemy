"""
Heuristic login-anomaly detection + synthetic alert generation.

Nothing in this file touches Hindsight. This is intentional: the RULES that
decide "this login event is worth investigating" are plain app logic. Only the
INVESTIGATION of a flagged alert (recall past cases, learn from outcomes) goes
through memory. Keeping this split explicit is part of the point of the project.
"""

import random
import uuid
from datetime import datetime, timedelta

FIRST_NAMES = ["Priya", "Arjun", "Fatima", "Rahul", "Meera", "Karthik", "Ananya", "Sameer",
               "Divya", "Vikram", "Nisha", "Rohan"]
LAST_NAMES = ["Rao", "Sharma", "Khan", "Iyer", "Reddy", "Nair", "Gupta", "Menon"]

DEPARTMENTS = ["Finance", "Engineering", "HR", "Sales", "Executive"]

# A small pool of *recurring* attacker infrastructure so the demo can show the
# agent recognizing "we've seen this exact campaign before" as more alerts resolve.
KNOWN_ATTACKER_CAMPAIGNS = [
    {
        "campaign": "Credential-stuffing cluster CS-114",
        "ip_range": "185.220.101.",
        "asn": "AS200011 (bulletproof hosting, Netherlands)",
        "signature": "credential_stuffing",
        "geo": "Amsterdam, NL",
    },
    {
        "campaign": "MFA-fatigue actor MF-07",
        "ip_range": "45.153.160.",
        "asn": "AS49505 (VPN exit, Russia)",
        "signature": "mfa_bypass_attempt",
        "geo": "Moscow, RU",
    },
    {
        "campaign": "Impossible-travel botnet IT-22",
        "ip_range": "103.75.190.",
        "asn": "AS132203 (cloud host, Singapore)",
        "signature": "impossible_travel",
        "geo": "Singapore, SG",
    },
]

BENIGN_PATTERNS = [
    {"signature": "new_device_odd_hour", "geo": "Bengaluru, IN"},
    {"signature": "new_device_odd_hour", "geo": "Hyderabad, IN"},
    {"signature": "impossible_travel", "geo": "Dubai, AE"},  # e.g. employee actually traveling
]


def _random_user():
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    dept = random.choice(DEPARTMENTS)
    email = name.lower().replace(" ", ".") + "@northbridge-finco.com"
    return {"name": name, "email": email, "department": dept}


def generate_synthetic_alert(force_known_campaign: bool = None) -> dict:
    """
    Generate one synthetic login-anomaly alert.

    ~55% chance of reusing a known attacker campaign (so recall has something
    real to find as the demo progresses), otherwise a one-off benign anomaly.
    """
    user = _random_user()
    is_attack = force_known_campaign if force_known_campaign is not None else (random.random() < 0.55)

    if is_attack:
        campaign = random.choice(KNOWN_ATTACKER_CAMPAIGNS)
        ip = campaign["ip_range"] + str(random.randint(2, 254))
        signature = campaign["signature"]
        geo = campaign["geo"]
        asn = campaign["asn"]
        campaign_name = campaign["campaign"]
    else:
        pattern = random.choice(BENIGN_PATTERNS)
        ip = f"{random.randint(20,220)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        signature = pattern["signature"]
        geo = pattern["geo"]
        asn = "AS(unremarkable ISP)"
        campaign_name = None

    now = datetime.utcnow() - timedelta(minutes=random.randint(0, 120))
    evidence = []
    timeline = []

    descriptions = {
        "credential_stuffing": f"{random.randint(6,40)} failed login attempts against {user['email']} in under 90 seconds, followed by one success, from IP {ip}.",
        "mfa_bypass_attempt": f"{random.randint(3,12)} rapid MFA push notifications sent to {user['email']} within 2 minutes ('MFA fatigue' pattern), originating from {ip}.",
        "impossible_travel": f"Login for {user['email']} from {geo} ({ip}) occurred {random.randint(1,4)}h after a login from their usual location, a distance impossible to travel in that time.",
        "new_device_odd_hour": f"Login for {user['email']} from a previously unseen device, at {random.choice(['2:14 AM','3:47 AM','1:02 AM'])} local time, from {ip}.",
    }

    if signature == "credential_stuffing":
        failed_count = int(descriptions[signature].split(" failed login", 1)[0])
        evidence = [
            {"label": "Failed-login pattern", "detail": f"{failed_count} failures in under 90 seconds."},
            {"label": "Successful authentication", "detail": "A login succeeded after the failure burst."},
            {"label": "Network context", "detail": f"{ip} via {asn}; use as supporting context, not a verdict by itself."},
            {"label": "Account history", "detail": "Check Hindsight for prior incidents and analyst decisions involving this account."},
        ]
        timeline = [
            {"time": (now - timedelta(seconds=78)).strftime("%H:%M:%S"), "event": "Failed logins", "detail": "First cluster of authentication failures."},
            {"time": (now - timedelta(seconds=31)).strftime("%H:%M:%S"), "event": "Failure burst continues", "detail": f"{failed_count} failures accumulated in under 90 seconds."},
            {"time": (now - timedelta(seconds=8)).strftime("%H:%M:%S"), "event": "Login succeeds", "detail": "Successful authentication follows the failed-login burst."},
        ]
    elif signature == "mfa_bypass_attempt":
        push_count = int(descriptions[signature].split(" rapid MFA", 1)[0])
        evidence = [
            {"label": "MFA fatigue pattern", "detail": f"{push_count} push requests in two minutes."},
            {"label": "Network context", "detail": f"{ip} via {asn}; compare with other signals and prior cases."},
            {"label": "Account history", "detail": "Check Hindsight for previous MFA incidents and analyst decisions."},
        ]
        timeline = [
            {"time": (now - timedelta(seconds=93)).strftime("%H:%M:%S"), "event": "MFA prompts begin", "detail": "Repeated approval requests sent to the account."},
            {"time": (now - timedelta(seconds=17)).strftime("%H:%M:%S"), "event": "Prompt burst detected", "detail": f"{push_count} prompts observed within two minutes."},
        ]
    elif signature == "impossible_travel":
        evidence = [
            {"label": "Travel velocity", "detail": "The two login locations cannot be reached within the observed interval."},
            {"label": "Network context", "detail": f"Current login from {geo} via {asn}."},
            {"label": "Account history", "detail": "Check Hindsight for travel exceptions or prior account incidents."},
        ]
        timeline = [
            {"time": (now - timedelta(hours=2)).strftime("%H:%M:%S"), "event": "Earlier login", "detail": "Login observed from the user's usual location."},
            {"time": (now - timedelta(minutes=6)).strftime("%H:%M:%S"), "event": "New location login", "detail": f"Authentication observed from {geo}."},
        ]
    else:
        evidence = [
            {"label": "Device context", "detail": "The device has not previously been seen for this account."},
            {"label": "Login timing", "detail": "The login occurred at an unusual local hour."},
            {"label": "Network context", "detail": f"{ip} via {asn}; compare with account history before acting."},
            {"label": "Account history", "detail": "Check Hindsight for prior device approvals or analyst decisions."},
        ]
        timeline = [
            {"time": (now - timedelta(minutes=4)).strftime("%H:%M:%S"), "event": "New device observed", "detail": "Device not previously associated with this account."},
            {"time": (now - timedelta(minutes=1)).strftime("%H:%M:%S"), "event": "Odd-hour login", "detail": "Authentication succeeded at an unusual local hour."},
        ]

    alert = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": now.isoformat() + "Z",
        "user": user,
        "ip": ip,
        "asn": asn,
        "geo": geo,
        "signature": signature,
        "campaign": campaign_name,
        "description": descriptions[signature],
        "evidence": evidence,
        "timeline": timeline,
        "resolved": False,
    }
    return alert


def generate_demo_alert(stage: int, user: dict = None, prior_alert_id: str = None,
                        prior_verdict: str = None) -> dict:
    """Build the two matching incidents used to demonstrate analyst learning."""
    user = user or _random_user()
    now = datetime.utcnow()
    ip = "185.220.101.74" if stage == 1 else "185.220.101.82"
    failed_count = 18 if stage == 1 else 22
    timestamp = now.isoformat() + "Z"
    alert_id = str(uuid.uuid4())[:8]
    description = (
        f"{failed_count} failed login attempts against {user['email']} in under 90 seconds, "
        f"followed by one success, from IP {ip}."
    )

    account_history = "No analyst disposition exists in this isolated demo memory bank yet."
    if prior_alert_id and prior_verdict:
        account_history = (
            f"The same account was investigated in Alert #{prior_alert_id}; the analyst "
            f"confirmed that incident as {prior_verdict}."
        )

    return {
        "id": alert_id,
        "timestamp": timestamp,
        "user": user,
        "ip": ip,
        "asn": "AS200011 (bulletproof hosting, Netherlands)",
        "geo": "Amsterdam, NL",
        "signature": "credential_stuffing",
        "campaign": "Aegis learning demo",
        "description": description,
        "evidence": [
            {"label": "Failed-login pattern", "detail": f"{failed_count} failures in under 90 seconds."},
            {"label": "Successful authentication", "detail": "One login succeeded immediately after the failure burst."},
            {"label": "Network context", "detail": f"{ip} via AS200011; supporting evidence, not a standalone verdict."},
            {"label": "Account history", "detail": account_history},
        ],
        "timeline": [
            {"time": (now - timedelta(seconds=78)).strftime("%H:%M:%S"), "event": "Failed logins", "detail": "First cluster of authentication failures."},
            {"time": (now - timedelta(seconds=31)).strftime("%H:%M:%S"), "event": "Failure burst continues", "detail": f"{failed_count} failures accumulated in under 90 seconds."},
            {"time": (now - timedelta(seconds=8)).strftime("%H:%M:%S"), "event": "Login succeeds", "detail": "Successful authentication follows the failed-login burst."},
        ],
        "resolved": False,
    }
