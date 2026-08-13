"""LLM call observability — one LlmCall row per raw model invocation.

Wired in as a LangChain callback so every call inside a node (including the
internal tool-call/response round-trips a create_react_agent makes) gets
logged, not just the top-level agent.invoke().
"""
import time
import logging
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

# Approximate list pricing, USD per 1K tokens (input, output). Update as
# Google's published rates change — this is for cost *estimation*, not billing.
PRICING_PER_1K = {
    "gemini-2.5-flash": (0.0003, 0.0025),
    "gemini-3.1-pro-preview": (0.00125, 0.005),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_rate, output_rate = PRICING_PER_1K.get(model, (0.0, 0.0))
    return round((prompt_tokens / 1000) * input_rate + (completion_tokens / 1000) * output_rate, 6)


class LlmUsageCallback(BaseCallbackHandler):
    """Logs one LlmCall row per chat-model invocation this handler observes."""

    def __init__(self, session_id: str, workspace_id: str, user_id: str, node: str, model: str):
        self.session_id = session_id
        self.workspace_id = workspace_id or None
        self.user_id = user_id or None
        self.node = node
        self.model = model
        self._starts = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self._starts[run_id] = time.time()

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self._starts[run_id] = time.time()

    def _usage(self, response):
        try:
            gen = response.generations[0][0]
            msg = getattr(gen, "message", None)
            usage = getattr(msg, "usage_metadata", None)
            if usage:
                return (
                    usage.get("input_tokens", 0) or 0,
                    usage.get("output_tokens", 0) or 0,
                    usage.get("total_tokens", 0) or 0,
                )
        except (AttributeError, IndexError, TypeError) as exc:
            logger.debug("LLM usage metadata unavailable", extra={"error": type(exc).__name__})
        return 0, 0, 0

    def on_llm_end(self, response, *, run_id, **kwargs):
        self._write(run_id, response, status="success", error_message=None)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._write(run_id, None, status="error", error_message=str(error))

    def _write(self, run_id, response, status, error_message):
        started = self._starts.pop(run_id, None)
        latency_ms = int((time.time() - started) * 1000) if started else None

        prompt_tokens = completion_tokens = total_tokens = 0
        if response is not None:
            prompt_tokens, completion_tokens, total_tokens = self._usage(response)

        try:
            # Deferred imports — avoids a circular import at module load time
            # (models.py -> core.extensions -> app factory -> agents package).
            from ..core.extensions import db
            from .models import LlmCall

            db.session.add(LlmCall(
                session_id=self.session_id,
                workspace_id=self.workspace_id,
                user_id=self.user_id,
                provider="google",
                model=self.model,
                node=self.node,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=_estimate_cost(self.model, prompt_tokens, completion_tokens),
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            ))
            db.session.commit()
        except Exception:
            logger.exception("Failed to persist LlmCall row")
