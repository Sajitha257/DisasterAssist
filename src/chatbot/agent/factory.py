"""Builds the Stage 5 chatbot once, when the website starts (same rules as Stage 4 service.py)."""

import sys
from typing import Callable, Optional

from src.chatbot.agent.provider import GeminiAgentProvider, NavigateAgentProvider, UnsupportedAgentProvider
from src.chatbot.agent.workflow import AgentService
from src.chatbot.retriever import Retriever
from src.chatbot.settings import LLMSettings, load_settings
from src.guide.loader import ApprovedData, ApprovedDataError, load_approved_data


def build_agent_provider(settings: LLMSettings):
    if settings.provider == "gemini":
        return GeminiAgentProvider(settings)
    if settings.provider == "navigate":
        return NavigateAgentProvider(settings)
    return UnsupportedAgentProvider()


def build_agent_service(load: Callable[[], ApprovedData] = load_approved_data,
                        settings: Optional[LLMSettings] = None, provider=None) -> Optional[AgentService]:
    """Returns the agent chatbot, or None if the approved data fails verification (no chatbot is shown then)."""
    try:
        approved = load()
    except ApprovedDataError as error:
        print("Chatbot NOT started: approved data failed verification.", file=sys.stderr)
        for problem in error.problems:
            print("  - " + problem, file=sys.stderr)
        return None
    retriever = Retriever.from_approved_data(approved)
    if provider is None:
        settings = settings if settings is not None else load_settings()
        provider = build_agent_provider(settings)
    return AgentService(retriever, provider)
