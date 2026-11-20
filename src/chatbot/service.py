"""Builds the chatbot once, when the website starts."""

import sys
from typing import Callable, Optional

from src.chatbot.answer import AnswerService
from src.chatbot.providers import base
from src.chatbot.providers.gemini_provider import GeminiProvider
from src.chatbot.providers.navigate_provider import NavigateProvider
from src.chatbot.retriever import Retriever
from src.chatbot.settings import LLMSettings, load_settings
from src.guide.loader import ApprovedData, ApprovedDataError, load_approved_data


class UnsupportedProvider:
    """Used when LLM_PROVIDER names a provider that does not exist. Every question gets a clear message."""

    def select(self, question, items):
        raise base.ProviderError(base.NOT_CONFIGURED)


def build_provider(settings: LLMSettings):
    if settings.provider == "gemini":
        return GeminiProvider(settings)
    if settings.provider == "navigate":
        return NavigateProvider(settings)
    return UnsupportedProvider()


def build_service(load: Callable[[], ApprovedData] = load_approved_data,
                  settings: Optional[LLMSettings] = None, provider=None) -> Optional[AnswerService]:
    """Returns the chatbot, or None if the approved data fails verification (no chatbot is shown then).

    The settings (and the API key) are read here, once. Restart the website after changing `.env`.
    """
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
        provider = build_provider(settings)
    return AnswerService(retriever, provider)
