"""Judge-facing incident response demo with explicit memory flow.

The story is deliberately structured to show the before/after difference that
memory makes: no context, then relevant history, then a learned pattern and a
new retention event.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent import IncidentResponseAgent
from app import config
from app.data.synthetic_incidents import build_learning_timeline

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
except ImportError:  # rich is optional; fall back to plain print
    console = None


NEW_INCIDENT = (
    "Checkout API is returning 502s under normal load, p99 latency at 5.8s. "
    "Grafana shows DB connection pool near 100% utilization. Started 6 minutes ago, "
    "no recent deploy that we can see."
)


def show(title: str, body: str, style: str = "cyan"):
    if console:
        console.print(Panel(body, title=title, border_style=style, expand=False))
    else:
        print(f"\n=== {title} ===\n{body}\n")


def show_memory_status(agent: IncidentResponseAgent):
    mode = "OFFLINE demo mode (no Hindsight/Groq keys set)" if (config.OFFLINE_MEMORY or config.OFFLINE_LLM) else "LIVE (Hindsight + Groq)"
    bank_name = getattr(agent.memory, "bank_id", "incident-response")
    store_name = "offline JSON fallback" if getattr(agent.memory, "offline", False) else "Hindsight Cloud"
    status = (
        f"Mode: {mode}\n"
        f"Memory bank: {bank_name}\n"
        f"Storage: {store_name}\n"
        f"Hindsight memory: active"
    )
    show("Memory status", status, style="yellow")


def show_learning_timeline():
    if not console:
        return
    table = Table(title="Memory journey")
    table.add_column("Stage", style="cyan")
    table.add_column("What the system learns", style="magenta")
    for idx, item in enumerate(build_learning_timeline(), start=1):
        table.add_row(f"{idx}", item["detail"])
    console.print(table)


def main():
    agent = IncidentResponseAgent()
    show(
        "Incident response workflow",
        "New Incident\n→ Incident Analysis\n→ Hindsight Recall\n→ Similar Historical Incidents\n→ Recommended Action\n→ Resolve Incident\n→ Retain in Hindsight",
        style="blue",
    )

    show(
        "New incident just paged",
        NEW_INCIDENT,
        style="red",
    )
    show_memory_status(agent)

    # Scene 1: without memory
    without = agent.triage(NEW_INCIDENT, use_memory=False)
    show(
        "1) Agent WITHOUT memory",
        without["response"],
        style="grey58",
    )

    # Scene 2: recall from Hindsight
    with_mem = agent.triage(NEW_INCIDENT, use_memory=True)
    if with_mem["recalled"]:
        recalled_block = "\n\n".join(with_mem["recalled"][:3])
        show("2) Memories recalled from Hindsight", recalled_block, style="magenta")
    else:
        show(
            "2) Memories recalled from Hindsight",
            "None found — did you run `python scripts/seed_memory.py` first?",
            style="magenta",
        )

    # Scene 3: pattern analysis
    pattern_summary = agent.reflect("What recurring incident patterns are we seeing in checkout-service?")
    show("3) Pattern analysis / Reflect", pattern_summary, style="cyan")
    show_learning_timeline()

    # Scene 4: with memory + recommendation
    show(
        "4) Agent WITH memory",
        with_mem["response"],
        style="green",
    )

    # Scene 5: resolve and retain new experience
    resolved_incident = {
        "id": "INC-104",
        "service": "checkout-service",
        "date": "2026-09-27",
        "symptoms": "Checkout API p99 latency spiked and 502s returned during a short burst of traffic; pool near 100% again.",
        "root_cause": "DB pool pressure was caused by a sudden traffic increase combined with a lingering connection leak in the checkout workers.",
        "fix": "Increased max_connections, rolled out a pool-usage alert, and fixed the leak by ensuring the proxy closed stale connections after retries.",
        "runbook": "RB-DB-CONN-POOL",
    }
    retained_id = agent.close_incident(resolved_incident)
    show(
        "5) Hindsight Retain",
        f"Stored resolved incident {resolved_incident['id']} into Hindsight. Retention ID: {retained_id}",
        style="bright_magenta",
    )

    agent.close()

    show(
        "Why this matters",
        "Without memory, the agent gives generic triage steps that any on-call engineer can read in runbooks. "
        "With Hindsight, the system compares the live incident to past failures, identifies the recurring pattern, "
        "and uses historical fixes as evidence before recommending the next action.",
        style="blue",
    )


if __name__ == "__main__":
    main()
