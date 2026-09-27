"""Central config, loaded from environment variables (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()

HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "incident-response")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3-32b")

# If no Hindsight key is set, the agent runs against a local JSON file instead
# so the demo works before you've registered for either service.
OFFLINE_MEMORY = not bool(HINDSIGHT_API_KEY)
OFFLINE_LLM = not bool(GROQ_API_KEY)

LOCAL_MEMORY_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".local_memory_store.json",
)
