"""
Thin wrapper around the Hindsight client.

This is the ONLY file that talks to Hindsight directly. Everything else in the
app (detection rules, the LLM agent, the API routes) goes through these three
functions: remember(), recall_similar(), and synthesize().

Hindsight concepts used:
- bank_id: a namespace for related memories. We use one bank per deployment
  (e.g. "soc-account-takeover") so the agent's case history is shared across
  all analysts/alerts for this org.
- retain(): writes a new memory (a resolved incident) into the bank.
- recall(): semantic search over the bank for memories relevant to a query.
- reflect(): asks Hindsight to produce a synthesized, disposition-aware answer
  grounded in the bank's memories (used as a second opinion alongside recall).
"""

from hindsight_client import Hindsight
from threading import local
import config

_client_context = local()


def get_client() -> Hindsight:
    client = getattr(_client_context, "client", None)
    if client is None:
        kwargs = {"base_url": config.HINDSIGHT_BASE_URL}
        if config.HINDSIGHT_API_KEY:
            kwargs["api_key"] = config.HINDSIGHT_API_KEY
        client = Hindsight(**kwargs)
        _client_context.client = client
    return client


def remember(content: str, bank_id: str = None, document_id: str = None,
             metadata: dict = None, tags: list = None) -> dict:
    """Store a resolved incident (or analyst correction) as a new memory."""
    client = get_client()
    bank = bank_id or config.HINDSIGHT_BANK_ID
    try:
        response = client.retain(
            bank_id=bank,
            content=content,
            document_id=document_id,
            metadata=metadata,
            tags=tags,
        )
        return {
            "success": bool(response.success and response.items_count > 0),
            "items_count": response.items_count,
            "bank_id": response.bank_id,
            "document_id": document_id,
        }
    except Exception as e:
        # Never let a memory-write failure break the triage flow for the analyst.
        print(f"[hindsight] retain() failed: {e}")
        return {"success": False, "items_count": 0, "bank_id": bank, "document_id": document_id}


def recall_with_status(query: str, bank_id: str = None, limit: int = 10) -> dict:
    """Return Hindsight Recall status and actual records without conflating errors with emptiness."""
    client = get_client()
    bank = bank_id or config.HINDSIGHT_BANK_ID
    try:
        result = client.recall(bank_id=bank, query=query)
        items = getattr(result, "results", None) or []
        records = [
            {
                "id": str(getattr(item, "id", "")),
                "document_id": getattr(item, "document_id", None),
                "metadata": dict(getattr(item, "metadata", None) or {}),
                "type": getattr(item, "type", None),
                "text": getattr(item, "text", None) or getattr(item, "content", None) or str(item),
                "tags": list(getattr(item, "tags", None) or []),
            }
            for item in items[:limit]
        ]
        return {"status": "completed" if records else "empty", "records": records, "bank_id": bank}
    except Exception as e:
        status = "empty" if getattr(e, "status", None) == 404 else "failed"
        print(f"[hindsight] recall() failed: {e}")
        return {"status": status, "records": [], "bank_id": bank, "error": str(e)}


def recall_records(query: str, bank_id: str = None, limit: int = 10) -> list[dict]:
    """Return actual Hindsight Recall records with their stable IDs and metadata."""
    return recall_with_status(query, bank_id, limit)["records"]


def recall_similar(query: str, bank_id: str = None, limit: int = 5) -> list[str]:
    """Semantic search for past incidents relevant to the current alert."""
    return [record["text"] for record in recall_records(query, bank_id, limit)]


def synthesize(query: str, bank_id: str = None) -> str:
    """Ask Hindsight for a synthesized, memory-grounded second opinion."""
    client = get_client()
    bank = bank_id or config.HINDSIGHT_BANK_ID
    try:
        response = client.reflect(bank_id=bank, query=query)
        return getattr(response, "text", "") or ""
    except Exception as e:
        print(f"[hindsight] reflect() failed: {e}")
        return ""
