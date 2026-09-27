"""IncidentResponseAgent: the retain/recall/respond loop.

This is the whole point of the project — everything else (CLI, data,
wrappers) exists to make this loop demonstrable.
"""
from app.hindsight_client import HindsightMemory
from app.llm_client import LLMClient
from app.data.synthetic_incidents import as_retain_text, summarize_pattern_memory

SYSTEM_PROMPT_BASE = (
    "You are an on-call incident response assistant. An engineer has just "
    "paged you about a new production incident. Be concise and actionable: "
    "say what you think is going on, what to check first, and what to try. "
    "If you have relevant past incidents to draw on, cite them by ID and say "
    "explicitly what makes this one similar. If you have nothing relevant, "
    "say so plainly and give generic triage steps instead of guessing."
)


class IncidentResponseAgent:
    def __init__(self, bank_id: str = None):
        self.memory = HindsightMemory(bank_id=bank_id)
        self.llm = LLMClient()

    # ---- retain -----------------------------------------------------
    def close_incident(self, incident: dict) -> str:
        """Call this once an incident is resolved to retain it for next time."""
        content = as_retain_text(incident)
        return self.memory.retain_incident(content)

    def seed(self, incidents: list) -> int:
        count = 0
        for inc in incidents:
            self.close_incident(inc)
            count += 1
        return count

    # ---- recall + respond --------------------------------------------
    def triage(self, new_incident_description: str, use_memory: bool = True) -> dict:
        """Handle a new incident. Returns the recalled memories (if any) and
        the agent's response, so the caller (CLI/demo) can show both."""
        recalled_texts = []
        if use_memory:
            recall = self.memory.recall(new_incident_description, limit=3)
            recalled_texts = [m.text for m in getattr(recall, "results", [])]

        if recalled_texts:
            memory_block = "\n\n".join(recalled_texts)
            system = (
                f"{SYSTEM_PROMPT_BASE}\n\nPAST INCIDENTS (retained in memory, "
                f"most relevant first):\n{memory_block}"
            )
        else:
            system = f"{SYSTEM_PROMPT_BASE}\n\nPAST INCIDENTS: No relevant memories found."

        response_text = self.llm.chat(system=system, user=new_incident_description)

        return {
            "used_memory": bool(recalled_texts),
            "recalled": recalled_texts,
            "response": response_text,
        }

    def reflect(self, query: str) -> str:
        """Ask Hindsight to synthesize across everything retained so far —
        e.g. 'what incident patterns have we seen this quarter?'"""
        try:
            return self.memory.reflect(query).text
        except Exception:
            return summarize_pattern_memory()

    def close(self):
        self.memory.close()
