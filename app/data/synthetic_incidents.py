"""Realistic synthetic past incidents used to seed the Hindsight bank.

Names, services and error signatures are fabricated but written the way a
real on-call postmortem would be, per the organizers' guidance that
realistic-looking data is what makes a demo feel production-real.
"""

from collections import Counter

SEED_INCIDENTS = [
    {
        "id": "INC-014",
        "service": "checkout-service",
        "date": "2026-08-03",
        "symptoms": "Checkout API p99 latency spiked from 180ms to 6.2s, 502s from the LB, error rate 14%",
        "root_cause": "Connection pool exhaustion after a config deploy dropped max_connections from 200 to 20",
        "fix": "Rolled back the connection-pool config change (deploy #4471); latency recovered within 3 minutes",
        "runbook": "RB-DB-CONN-POOL",
    },
    {
        "id": "INC-021",
        "service": "checkout-service",
        "date": "2026-09-11",
        "symptoms": "Checkout API 502s and rising latency during a traffic spike, DB connections maxed out in dashboard",
        "root_cause": "Same connection-pool exhaustion pattern as INC-014, this time triggered by a Black Friday-style traffic surge rather than a bad deploy",
        "fix": "Manually bumped max_connections to 300 and enabled connection pooling via PgBouncer",
        "runbook": "RB-DB-CONN-POOL",
    },
    {
        "id": "INC-032",
        "service": "auth-service",
        "date": "2026-07-19",
        "symptoms": "Login failures spiking, users seeing 'invalid token' errors even with valid sessions",
        "root_cause": "Clock drift on two auth nodes caused JWT 'iat' validation to reject otherwise-valid tokens",
        "fix": "Restarted NTP sync on affected nodes; added NTP drift alerting",
        "runbook": "RB-AUTH-CLOCK-DRIFT",
    },
    {
        "id": "INC-045",
        "service": "payments-worker",
        "date": "2026-08-22",
        "symptoms": "Payment webhook processing backlog growing, consumer lag on payments.events topic climbing past 50k",
        "root_cause": "A downstream ledger-service schema change silently broke deserialization for one event type, poison-pilling the consumer",
        "fix": "Deployed a dead-letter queue for unparseable events and patched the deserializer; backlog drained in 40 minutes",
        "runbook": "RB-KAFKA-CONSUMER-LAG",
    },
    {
        "id": "INC-051",
        "service": "search-service",
        "date": "2026-06-30",
        "symptoms": "Search results empty for ~8% of queries, no errors in logs",
        "root_cause": "Elasticsearch index alias pointed at a stale index after a reindex job finished out of order",
        "fix": "Manually repointed the alias to the correct index; added a post-reindex verification step to the job",
        "runbook": "RB-SEARCH-INDEX-ALIAS",
    },
    {
        "id": "INC-058",
        "service": "notifications-service",
        "date": "2026-09-02",
        "symptoms": "Push notifications delayed by 20-40 minutes for iOS users only",
        "root_cause": "APNs certificate was nearing expiry and Apple started rate-limiting the account as a warning signal",
        "fix": "Rotated the APNs certificate early; added a 30-day expiry alert for all push certs",
        "runbook": "RB-PUSH-CERT-EXPIRY",
    },
    {
        "id": "INC-063",
        "service": "checkout-service",
        "date": "2026-09-20",
        "symptoms": "Checkout API returning 502s under moderate load, DB connection dashboard showing pool near capacity again",
        "root_cause": "A new microservice (loyalty-points) was added upstream of checkout and wasn't given its own connection pool, competing for the same shared pool",
        "fix": "Gave loyalty-points its own dedicated connection pool instead of sharing checkout's",
        "runbook": "RB-DB-CONN-POOL",
    },
    {
        "id": "INC-070",
        "service": "billing-service",
        "date": "2026-07-05",
        "symptoms": "Duplicate charge complaints from 3 customers, all on retried payment attempts",
        "root_cause": "Missing idempotency key on the charge-retry code path let a network-timeout retry double-submit",
        "fix": "Added idempotency keys to all payment-retry calls; refunded affected customers",
        "runbook": "RB-PAYMENTS-IDEMPOTENCY",
    },
    {
        "id": "INC-081",
        "service": "auth-service",
        "date": "2026-08-14",
        "symptoms": "Spike in 'invalid token' login errors again, similar to INC-032 but on a different node pair",
        "root_cause": "NTP daemon had silently stopped on two newly-provisioned nodes; base AMI was missing the NTP health check added after INC-032",
        "fix": "Restarted NTP, and this time baked the health check into the base AMI so new nodes can't skip it",
        "runbook": "RB-AUTH-CLOCK-DRIFT",
    },
    {
        "id": "INC-090",
        "service": "recommendation-service",
        "date": "2026-06-11",
        "symptoms": "Recommendation API latency creeping up over 6 hours, no single spike, CPU normal",
        "root_cause": "A slow memory leak in the feature-embedding cache; GC pauses grew until p99 crossed the timeout threshold",
        "fix": "Rolled the service (temporary fix), then shipped a bounded LRU cache instead of an unbounded dict",
        "runbook": "RB-MEMORY-LEAK-CACHE",
    },
    {
        "id": "INC-097",
        "service": "search-service",
        "date": "2026-08-29",
        "symptoms": "Search latency doubled after a schema migration, some queries timing out",
        "root_cause": "New field added to the index wasn't marked as not-indexed, doubling index size and shard memory pressure",
        "fix": "Reindexed with the field correctly excluded from full-text indexing; added a schema-review step to the migration checklist",
        "runbook": "RB-SEARCH-SCHEMA-MIGRATION",
    },
    {
        "id": "INC-103",
        "service": "payments-worker",
        "date": "2026-09-15",
        "symptoms": "Payment webhook backlog again, consumer lag climbing on payments.events",
        "root_cause": "Same poison-pill pattern as INC-045 — a different downstream team shipped another breaking schema change without checking the consumer contract",
        "fix": "The DLQ from INC-045 caught it automatically this time; patched the deserializer and pinged the downstream team about the schema contract",
        "runbook": "RB-KAFKA-CONSUMER-LAG",
    },
]


def as_retain_text(incident: dict) -> str:
    """Format one incident as a single retain() payload."""
    return (
        f"[{incident['id']}] {incident['date']} — {incident['service']}\n"
        f"Symptoms: {incident['symptoms']}\n"
        f"Root cause: {incident['root_cause']}\n"
        f"Fix: {incident['fix']}\n"
        f"Runbook: {incident['runbook']}"
    )


def build_learning_timeline():
    """Build a lightweight learning story using the seeded incident data."""
    close_incidents = [
        inc for inc in SEED_INCIDENTS if inc["service"] == "checkout-service"
    ]
    timeline = [
        {
            "title": "Incident #1 — Database timeout precedent",
            "detail": "INC-014 established the first checkout-service connection-pool exhaustion pattern.",
        },
        {
            "title": "Incident #5 — Same service recurs",
            "detail": "INC-021 demonstrated that the same checkout-service issue could reappear under traffic pressure.",
        },
        {
            "title": "Pattern — Connection pool saturation becomes a known class",
            "detail": "The checkout-service incidents show a recurring failure mode tied to pool exhaustion and traffic spikes.",
        },
        {
            "title": "Incident #10 — Resolution history compounds",
            "detail": f"INC-063 adds a newer checkout-service case where a shared pool problem was solved by giving loyalty-points its own dedicated pool.",
        },
        {
            "title": "Learning state — knowledge accumulated",
            "detail": f"{len(close_incidents)} related checkout-service incidents now provide precedent for future requests.",
        },
    ]
    return timeline


def summarize_pattern_memory() -> str:
    """Return a compact narrative describing recurring operational patterns in the dataset."""
    service_counts = Counter(incident["service"] for incident in SEED_INCIDENTS)
    top_services = sorted(service_counts.items(), key=lambda item: (-item[1], item[0]))
    checkout_count = service_counts.get("checkout-service", 0)
    return (
        "Pattern memory: checkout-service is the clearest recurring incident pattern, "
        f"with {checkout_count} related incidents. Other repeated service families include "
        f"{', '.join(f'{name} ({count})' for name, count in top_services[:3])}. "
        "The historical evidence supports recurring connection-pool, auth-clock-drift, and schema-contract patterns."
    )
