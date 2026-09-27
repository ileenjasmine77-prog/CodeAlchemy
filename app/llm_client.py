"""Thin wrapper around Groq chat completions, with explicit handling for
function-calling / malformed-response errors (the org's own guidance flags
this as a common failure point) and an offline fallback so the demo runs
without a Groq key.
"""
from app import config


class LLMClient:
    def __init__(self):
        self.offline = config.OFFLINE_LLM
        if not self.offline:
            from groq import Groq
            self._client = Groq(api_key=config.GROQ_API_KEY)

    def chat(self, system: str, user: str) -> str:
        if self.offline:
            return self._offline_reply(system, user)

        for model in (config.GROQ_MODEL, config.GROQ_FALLBACK_MODEL):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=600,
                )
                content = resp.choices[0].message.content
                if content and content.strip():
                    return content.strip()
            except Exception as exc:  # noqa: BLE001 - deliberately broad: any
                # Groq/model/function-calling error should fall through to the
                # next model rather than crash the on-call flow.
                last_error = exc
                continue
        return (
            "[LLM unavailable] Could not get a response from Groq after "
            f"retrying with a fallback model. Last error: {last_error}"
        )

    @staticmethod
    def _offline_reply(system: str, user: str) -> str:
        """Canned but genuinely different responses depending on whether the
        prompt included recalled memory context, so `demo.py` still shows a
        believable before/after with zero API keys configured."""
        if "PAST INCIDENTS" in system and "No relevant" not in system:
            return (
                "This matches a pattern I've seen before. Based on the retained "
                "incident(s) above, start with the fix that worked last time — "
                "it targets the same root cause these symptoms point to. "
                "(offline demo response — connect GROQ_API_KEY for real reasoning)"
            )
        return (
            "I don't have any prior context on this. Suggest starting with "
            "standard triage: check recent deploys, error rate by endpoint, "
            "and dependency health. "
            "(offline demo response — connect GROQ_API_KEY for real reasoning)"
        )
