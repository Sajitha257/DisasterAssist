"""Gemini access for the agent steps (Stage 5).

GeminiAgentProvider adds the two decision requests (`plan`, `evaluate`) to the
GeminiProvider and keeps its `select` request (the final choice of IDs) exactly
as it was. Client creation, key checks, timeouts, error mapping and the privacy
rules are all inherited. The `google.genai` package is still imported only inside
the provider's own functions.

Error text from Gemini is never used or logged; every failure becomes one fixed code.
"""

from typing import Protocol, Sequence

from src.chatbot.agent import prompts
from src.chatbot.models import RetrievedItem
from src.chatbot.providers import base
from src.chatbot.providers.gemini_provider import GeminiProvider
from src.chatbot.providers.navigate_provider import NavigateProvider


class AgentProvider(Protocol):
    def plan(self, question: str) -> base.ProviderReply:
        ...

    def evaluate(self, question: str, items: Sequence[RetrievedItem]) -> base.ProviderReply:
        ...

    def select(self, question: str, items: Sequence[RetrievedItem]) -> base.ProviderReply:
        ...


class GeminiAgentProvider(GeminiProvider):
    def plan(self, question: str) -> base.ProviderReply:
        return self._structured(prompts.build_plan_messages(question), prompts.PLAN_SCHEMA)

    def evaluate(self, question: str, items: Sequence[RetrievedItem]) -> base.ProviderReply:
        return self._structured(prompts.build_evaluate_messages(question, items), prompts.EVALUATE_SCHEMA)


class NavigateAgentProvider(NavigateProvider):
    """Same two decision requests as GeminiAgentProvider, sent through Navigate Labs."""

    def plan(self, question: str) -> base.ProviderReply:
        return self._structured(prompts.build_plan_messages(question), prompts.PLAN_SCHEMA)

    def evaluate(self, question: str, items: Sequence[RetrievedItem]) -> base.ProviderReply:
        return self._structured(prompts.build_evaluate_messages(question, items), prompts.EVALUATE_SCHEMA)


class UnsupportedAgentProvider:
    """Used when LLM_PROVIDER names a provider that does not exist."""

    def plan(self, question, *args):
        raise base.ProviderError(base.NOT_CONFIGURED)

    def evaluate(self, question, items):
        raise base.ProviderError(base.NOT_CONFIGURED)

    def select(self, question, items):
        raise base.ProviderError(base.NOT_CONFIGURED)
