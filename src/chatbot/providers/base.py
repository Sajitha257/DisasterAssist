"""What every AI provider must offer, and the one error type it may raise.

Error messages shown to the user are FIXED sentences chosen by `code`. The text
of the original exception is never shown or logged, because provider error
messages can contain parts of the API key.
"""

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from src.chatbot.models import RetrievedItem

# Error codes
MISSING_KEY = "missing_key"
INVALID_KEY = "invalid_key"          # key refused by the provider (or written wrongly in .env)
RATE_LIMIT = "rate_limit"
TIMEOUT = "timeout"
NETWORK = "network"
SERVER = "server"                    # provider-side problem (5xx)
BAD_REQUEST = "bad_request"          # includes "model not found"
INVALID_RESPONSE = "invalid_response"
NOT_CONFIGURED = "not_configured"    # unsupported LLM_PROVIDER, google-genai package missing, ...
UNKNOWN = "unknown"

USER_MESSAGES = {
    MISSING_KEY: "The AI service is not set up: no Gemini API key was found. See docs/gemini.md.",
    INVALID_KEY: "The AI service did not accept the API key. Check GEMINI_API_KEY in the .env file, then restart the website. See docs/gemini.md.",
    RATE_LIMIT: "The AI service is busy (rate limit reached). Please wait a minute and try again.",
    TIMEOUT: "The AI service took too long to answer. Please try again.",
    NETWORK: "The AI service could not be reached. Check the internet connection and try again.",
    SERVER: "The AI service had a problem on its side. Please try again later.",
    BAD_REQUEST: "The AI service refused the request (for example the model name may be wrong). See docs/gemini.md.",
    INVALID_RESPONSE: "The AI service returned an answer that could not be checked, so it was not used.",
    NOT_CONFIGURED: "The AI service is not configured correctly. See docs/gemini.md.",
    UNKNOWN: "Something went wrong with the AI service. Please try again.",
}


# Used instead of the Gemini sentences above when LLM_PROVIDER=navigate (otherwise they would name the wrong key).
NAVIGATE_MESSAGES = {
    MISSING_KEY: "The AI service is not set up: no Navigate API key was found. See docs/navigate.md.",
    INVALID_KEY: "The AI service did not accept the API key. Check NAVIGATE_API_KEY in the .env file, then restart the website. See docs/navigate.md.",
    BAD_REQUEST: "The AI service refused the request (for example NAVIGATE_MODEL or NAVIGATE_CHAT_PATH may be wrong). See docs/navigate.md.",
    NOT_CONFIGURED: "The AI service is not configured correctly (check NAVIGATE_MODEL and NAVIGATE_BASE_URL). See docs/navigate.md.",
}


class ProviderError(Exception):
    """Raised by a provider. `code` is one of the constants above. The message holds no secrets."""

    def __init__(self, code: str, provider: Optional[str] = None):
        super().__init__(code)
        self.code = code
        self.provider = provider

    @property
    def user_message(self) -> str:
        if self.provider == "navigate" and self.code in NAVIGATE_MESSAGES:
            return NAVIGATE_MESSAGES[self.code]
        return USER_MESSAGES.get(self.code, USER_MESSAGES[NOT_CONFIGURED])


@dataclass(frozen=True)
class ProviderReply:
    """The raw JSON text returned by the model. It is NOT trusted until answer.py validates it."""
    content: str
    model: Optional[str] = None


class Provider(Protocol):
    def select(self, question: str, items: Sequence[RetrievedItem]) -> ProviderReply:
        ...
