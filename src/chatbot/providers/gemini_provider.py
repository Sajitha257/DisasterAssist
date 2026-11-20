"""Google Gemini provider (official `google-genai` SDK).

It sends the question and the retrieved approved instructions, asks for JSON that
follows a strict schema, and returns the raw JSON text. It never decides what is
shown: answer.py and agent/decisions.py validate everything, and Python builds the
visible answer from the exact approved text.

The `google.genai` package is imported only when the first question is asked, so the
website and the Emergency Safety Guide start even if the package is missing.

Error text from the SDK is never used or logged. Every failure becomes one fixed
error code (see providers/base.py), because error messages can contain parts of
the request or key.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.chatbot import prompt
from src.chatbot.models import RetrievedItem
from src.chatbot.providers import base
from src.chatbot.settings import KEY_MALFORMED, KEY_MISSING, LLMSettings

log = logging.getLogger("disasterassist.gemini")

RETRY_ATTEMPTS = 2                                   # one automatic retry, as before
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
RETRY_DELAY_SECONDS = 1.0


def timeout_milliseconds(seconds: float) -> int:
    """`LLM_TIMEOUT_SECONDS` is in seconds, but `google.genai.types.HttpOptions.timeout` is in MILLISECONDS.
    The SDK divides by 1000 for the HTTP client and also sends the result, rounded up to whole seconds, in
    the `X-Server-Timeout` header, so the Gemini server gives up at the same time as the client."""
    return int(seconds * 1000)


def thinking_config(model: str, types: Any) -> Optional[Any]:
    """Low thinking for `gemini-3*` models (Gemini 3.x and 3.5 Flash-Lite accept `thinking_level` LOW).
    Other model names get no thinking setting. Shared with scripts/diagnose_gemini.py."""
    if model.lower().startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    return None


def _keep_sdk_logs_private() -> None:
    """The SDK's own loggers can describe requests when debug logging is on. docs/privacy.md promises
    that logs never hold question text, so the package's loggers are held at WARNING."""
    logging.getLogger("google_genai").setLevel(logging.WARNING)


def _split_messages(messages: Sequence[Dict[str, str]]) -> Tuple[str, str]:
    """The prompt builders return [system, user] messages. Gemini takes the system text as
    `system_instruction` and the user text as `contents`."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
    return system, user


class GeminiProvider:
    def __init__(self, settings: LLMSettings, client: Optional[Any] = None, http_client: Optional[Any] = None):
        """`client` / `http_client` let the tests replace the network. Real use passes neither."""
        self._settings = settings
        self._client = client
        self._http_client = http_client

    # ------------------------------------------------------------------ client
    def _get_client(self):
        if self._client is not None:
            return self._client
        state = self._settings.key_state
        if state == KEY_MISSING:
            raise base.ProviderError(base.MISSING_KEY)
        if state == KEY_MALFORMED:
            raise base.ProviderError(base.INVALID_KEY)
        try:
            from google.genai import Client, types
        except ImportError:
            raise base.ProviderError(base.NOT_CONFIGURED) from None
        _keep_sdk_logs_private()
        options = {
            "timeout": timeout_milliseconds(self._settings.timeout_seconds),   # the SDK counts milliseconds
            "retry_options": types.HttpRetryOptions(
                attempts=RETRY_ATTEMPTS, initial_delay=RETRY_DELAY_SECONDS,
                http_status_codes=list(RETRY_STATUS_CODES)),
        }
        if self._http_client is not None:
            options["httpx_client"] = self._http_client
        self._client = Client(api_key=self._settings.api_key, http_options=types.HttpOptions(**options))
        return self._client

    def _config(self, system: str, schema: Dict[str, object]):
        from google.genai import types
        settings: Dict[str, Any] = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "max_output_tokens": self._settings.max_output_tokens,
            "candidate_count": 1,
        }
        # Gemini 3 models think by default and count that thinking against the output limit.
        # Low thinking is enough for these small decisions. No temperature is sent: Google
        # lists it as deprecated for the Gemini 3 models. Python validates every reply anyway.
        thinking = thinking_config(self._settings.model, types)
        if thinking is not None:
            settings["thinking_config"] = thinking
        return types.GenerateContentConfig(**settings)

    # ------------------------------------------------------------------ requests
    def _structured(self, messages: Sequence[Dict[str, str]], schema: Dict[str, object]) -> base.ProviderReply:
        client = self._get_client()
        system, user = _split_messages(messages)
        try:
            response = client.models.generate_content(
                model=self._settings.model, contents=user, config=self._config(system, schema))
        except Exception as error:                      # mapped to a fixed code; the text is never used
            code = classify_error(error)
            log.warning("Gemini request failed: %s (%s)", code, type(error).__name__)
            raise base.ProviderError(code) from None
        return self._read(response)

    def select(self, question: str, items: Sequence[RetrievedItem]) -> base.ProviderReply:
        return self._structured(prompt.build_messages(question, items), prompt.RESPONSE_SCHEMA)

    @staticmethod
    def _read(response: Any) -> base.ProviderReply:
        """Accept only a complete, text reply. Blocked, cut-off, empty or oddly shaped replies are rejected."""
        try:
            candidates: List[Any] = list(response.candidates or [])
            if len(candidates) != 1:
                raise base.ProviderError(base.INVALID_RESPONSE)
            finish = getattr(candidates[0].finish_reason, "name", str(candidates[0].finish_reason))
            content = response.text
        except base.ProviderError:
            raise
        except Exception:
            raise base.ProviderError(base.INVALID_RESPONSE) from None
        if finish != "STOP" or not isinstance(content, str) or not content.strip():
            raise base.ProviderError(base.INVALID_RESPONSE)
        model = getattr(response, "model_version", None)
        return base.ProviderReply(content=content, model=model if isinstance(model, str) else None)


def _key_was_refused(error: Any) -> bool:
    """Gemini answers a wrong key with HTTP 400 (reason API_KEY_INVALID), not 401. The error text is only
    inspected here; it is never shown or logged."""
    text = (str(getattr(error, "details", "")) + " " + str(getattr(error, "message", ""))).lower()
    return "api_key_invalid" in text or "api key not valid" in text or "api key expired" in text


def _http_error_types() -> Tuple[tuple, tuple]:
    """(timeout classes, other network classes) of the HTTP libraries the SDK may use. Newer SDK
    versions can use `httpx2`, a fork of `httpx` with its own exception classes, so both are covered."""
    timeouts: list = []
    transports: list = []
    for name in ("httpx", "httpx2"):
        try:
            module = __import__(name)
        except ImportError:
            continue
        timeouts.append(module.TimeoutException)
        transports.append(module.TransportError)
    return tuple(timeouts), tuple(transports)


def classify_error(error: BaseException) -> str:
    """Turn any exception from the google-genai package (or the network layer) into one fixed error code."""
    try:
        from google.genai import errors as genai_errors
    except ImportError:
        return base.NOT_CONFIGURED
    if isinstance(error, TimeoutError):
        return base.TIMEOUT
    timeouts, transports = _http_error_types()
    if isinstance(error, timeouts):
        return base.TIMEOUT
    if isinstance(error, transports):
        return base.NETWORK
    if isinstance(error, genai_errors.APIError):
        status = getattr(error, "code", 0)
        status = status if isinstance(status, int) else 0
        if status in (401, 403) or (status == 400 and _key_was_refused(error)):
            return base.INVALID_KEY
        if status == 429:
            return base.RATE_LIMIT
        if status in (408, 504):
            return base.TIMEOUT
        if status >= 500:
            return base.SERVER
        return base.BAD_REQUEST
    if isinstance(error, (ConnectionError, OSError)):
        return base.NETWORK
    return base.UNKNOWN
