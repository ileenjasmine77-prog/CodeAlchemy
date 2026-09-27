"""Thin wrapper around the Hindsight SDK.

If no HINDSIGHT_API_KEY is configured, falls back to a tiny local JSON store
with the same retain/recall shape, so the demo works before you've signed up
for Hindsight Cloud. Swap to real Hindsight by just filling in .env — no code
changes needed anywhere else in the project.

Real Hindsight usage (what this class calls under the hood):

    from hindsight_client import Hindsight
    client = Hindsight(base_url=HINDSIGHT_BASE_URL, api_key=HINDSIGHT_API_KEY)
    client.create_bank(bank_id=..., name=..., background=...)
    client.retain(bank_id=..., content=...)
    client.recall(bank_id=..., query=...)
    client.reflect(bank_id=..., query=...)
"""
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from app import config


@dataclass
class MemoryResult:
    text: str
    memory_id: str = ""
    score: float = 0.0


@dataclass
class RecallResponse:
    results: List[MemoryResult] = field(default_factory=list)


@dataclass
class ReflectResponse:
    text: str = ""


class _LocalMemoryStore:
    """Fallback store used when no Hindsight API key is configured.

    Does naive keyword-overlap search instead of Hindsight's real semantic
    + graph retrieval, which is why real incidents should use the real
    service — this only exists so the demo is runnable with zero setup.
    """

    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            self._write({"banks": {}})

    def _read(self):
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def create_bank(self, bank_id, name="", background="", disposition=None):
        data = self._read()
        data["banks"].setdefault(bank_id, {"name": name, "background": background, "memories": []})
        self._write(data)

    def retain(self, bank_id, content):
        data = self._read()
        bank = data["banks"].setdefault(bank_id, {"name": bank_id, "background": "", "memories": []})
        mem_id = str(uuid.uuid4())[:8]
        bank["memories"].append({
            "id": mem_id,
            "text": content,
            "retained_at": datetime.now(timezone.utc).isoformat(),
        })
        self._write(data)
        return mem_id

    @staticmethod
    def _score(query: str, text: str) -> float:
        q = {w.lower() for w in query.split() if len(w) > 3}
        t = {w.lower() for w in text.split() if len(w) > 3}
        if not q or not t:
            return 0.0
        return len(q & t) / len(q)

    def recall(self, bank_id, query, limit=5):
        data = self._read()
        bank = data["banks"].get(bank_id, {"memories": []})
        scored = [
            MemoryResult(text=m["text"], memory_id=m["id"], score=self._score(query, m["text"]))
            for m in bank["memories"]
        ]
        scored = [m for m in scored if m.score > 0]
        scored.sort(key=lambda m: m.score, reverse=True)
        return RecallResponse(results=scored[:limit])

    def reflect(self, bank_id, query):
        recalled = self.recall(bank_id, query, limit=5)
        if not recalled.results:
            return ReflectResponse(text="No relevant memories retained yet.")
        joined = "\n".join(f"- {m.text}" for m in recalled.results)
        return ReflectResponse(text=f"Based on {len(recalled.results)} related past incidents:\n{joined}")

    def close(self):
        pass


class HindsightMemory:
    """Unified interface used by the agent. Backed by real Hindsight or the
    local fallback store depending on config.OFFLINE_MEMORY."""

    def __init__(self, bank_id: str = None):
        self.bank_id = bank_id or config.HINDSIGHT_BANK_ID
        self.offline = config.OFFLINE_MEMORY

        if self.offline:
            self._client = _LocalMemoryStore(config.LOCAL_MEMORY_STORE_PATH)
        else:
            from hindsight_client import Hindsight  # imported lazily so the
            # package is only required when real credentials are present
            self._client = Hindsight(
                base_url=config.HINDSIGHT_BASE_URL,
                api_key=config.HINDSIGHT_API_KEY,
            )

        self._client.create_bank(
            bank_id=self.bank_id,
            name="Incident Response Agent",
            background=(
                "Stores resolved production incidents for an on-call engineering "
                "team: service affected, symptoms, root cause, the fix that "
                "worked, and which runbook applied. Used to brief responders on "
                "new incidents by surfacing the closest past precedent."
            ),
        )

    def retain_incident(self, content: str) -> str:
        return self._client.retain(bank_id=self.bank_id, content=content)

    def recall(self, query: str, limit: int = 5):
        """Call the backing Hindsight client using the SDK's real API.

        The installed SDK does not accept a `limit` keyword on `recall()`. It
        returns a `RecallResponse` whose `results` list is already ranked; we keep
        the app-facing contract by truncating the list here.
        """
        response = self._client.recall(bank_id=self.bank_id, query=query)
        if hasattr(response, "results") and response.results is not None:
            response.results = response.results[:limit]
        return response

    def reflect(self, query: str):
        return self._client.reflect(bank_id=self.bank_id, query=query)

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass
