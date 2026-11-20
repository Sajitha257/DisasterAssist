"""Navigate Labs provider: Google Gemini reached through the Navigate Labs API.

IMPORTANT - what is and is not verified
    The request shape used here is an OpenAI-style chat-completions call with a Bearer key
    (`POST {NAVIGATE_BASE_URL}{NAVIGATE_CHAT_PATH}`, `choices[0].message.content` in the reply).
    That shape was NOT confirmed against Navigate Labs documentation or a live call when this file was
    written. Run `python scripts/check_navigate.py` on your own computer: it probes the real API with
    your key from .env and reports what works. Every assumption is overridable in .env
    (NAVIGATE_CHAT_PATH, NAVIGATE_JSON_MODE) so no code edit is needed if the API differs.

The provider keeps the same contract as GeminiProvider: it sends the question plus the retrieved approved
instructions, asks for JSON that follows the strict schema, and returns the raw JSON text. It never decides
what is shown: answer.py and agent/decisions.py validate everything.

Error text and response bodies are never used or logged (they can echo parts of the request or key). Every
failure becomes one fixed error code (see providers/base.py).
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Sequence

import httpx

from src.chatbot import prompt
from src.chatbot.models import RetrievedItem
from src.chatbot.providers import base
from src.chatbot.settings import KEY_MALFORMED, KEY_MISSING, PROVIDER_NAVIGATE, LLMSettings

log = logging.getLogger("disasterassist.navigate")

RETRY_ATTEMPTS = 2                                   # one automatic retry, same as the Gemini provider
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
RETRY_DELAY_SECONDS = 1.0
SCHEMA_NAME = "disasterassist_reply"


def _fail(code: str) -> base.ProviderError:
    return base.ProviderError(code, provider=PROVIDER_NAVIGATE)


def classify_status(status: int) -> str:
    """Map an HTTP status from Navigate to one fixed error code."""
    if status in (401, 403):
        return base.INVALID_KEY
    if status == 429:
        return base.RATE_LIMIT
    if status in (408, 504):
        return base.TIMEOUT
    if status >= 500:
        return base.SERVER
    return base.BAD_REQUEST                          # other 4xx, including "model not found"


def classify_error(error: BaseException) -> str:
    """Turn any exception raised while calling Navigate into one fixed error code."""
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return base.TIMEOUT
    if isinstance(error, (httpx.TransportError, ConnectionError, OSError)):
        return base.NETWORK
    return base.UNKNOWN


class NavigateProvider:
    def __init__(self, settings: LLMSettings, http_client: Optional[httpx.Client] = None):
        """`http_client` lets the tests replace the network (httpx.MockTransport). Real use passes none."""
        self._settings = settings
        self._http_client = http_client

    # ------------------------------------------------------------------ request building
    def _check_ready(self) -> None:
        state = self._settings.key_state
        if state == KEY_MISSING:
            raise _fail(base.MISSING_KEY)
        if state == KEY_MALFORMED:
            raise _fail(base.INVALID_KEY)
        if not self._settings.model or not self._settings.base_url.lower().startswith(("https://", "http://")):
            raise _fail(base.NOT_CONFIGURED)

    def _url(self) -> str:
        return self._settings.base_url + self._settings.chat_path

    def _body(self, messages: Sequence[Dict[str, str]], schema: Dict[str, object]) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self._settings.model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "max_tokens": self._settings.max_output_tokens,
            "stream": False,
        }
        mode = self._settings.json_mode
        if mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": schema},
            }
        elif mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        # mode "none": no response_format is sent. The prompts already demand JSON only and Python
        # validates every reply, so an unsupported parameter can be switched off without losing safety.
        return body

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": "Bearer " + self._settings.api_key, "Content-Type": "application/json",
                "Accept": "application/json"}

    # ------------------------------------------------------------------ requests
    def _post(self, body: Dict[str, Any]) -> httpx.Response:
        client = self._http_client
        owns_client = client is None
        if owns_client:
            client = httpx.Client(timeout=httpx.Timeout(self._settings.timeout_seconds))
        try:
            response: Optional[httpx.Response] = None
            for attempt in range(1, RETRY_ATTEMPTS + 1):
                try:
                    response = client.post(self._url(), headers=self._headers(), content=json.dumps(body),
                                           timeout=self._settings.timeout_seconds)
                except Exception as error:                  # mapped to a fixed code; the text is never used
                    code = classify_error(error)
                    log.warning("Navigate request failed: %s (%s)", code, type(error).__name__)
                    raise _fail(code) from None            # timeouts / network errors are not retried (as with Gemini)
                if response.status_code in RETRY_STATUS_CODES and attempt < RETRY_ATTEMPTS:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                break
        finally:
            if owns_client:
                client.close()
        if not 200 <= response.status_code < 300:
            code = classify_status(response.status_code)
            log.warning("Navigate request failed: %s (HTTP %d)", code, response.status_code)
            raise _fail(code)
        return response

    def _structured(self, messages: Sequence[Dict[str, str]], schema: Dict[str, object]) -> base.ProviderReply:
        self._check_ready()
        response = self._post(self._body(messages, schema))
        return self._read(response)

    def select(self, question: str, items: Sequence[RetrievedItem]) -> base.ProviderReply:
        return self._structured(prompt.build_messages(question, items), prompt.RESPONSE_SCHEMA)

    @staticmethod
    def _read(response: httpx.Response) -> base.ProviderReply:
        """Accept only a complete, text reply. Cut-off, empty, blocked or oddly shaped replies are rejected."""
        try:
            data = response.json()
            choices = data["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise _fail(base.INVALID_RESPONSE)
            choice = choices[0]
            finish = choice.get("finish_reason")
            content = choice["message"]["content"]
            model = data.get("model")
        except base.ProviderError:
            raise
        except Exception:
            raise _fail(base.INVALID_RESPONSE) from None
        # "stop" is a complete reply. "length" (hit max_tokens), "content_filter" etc. are not used.
        if finish not in ("stop", "STOP") or not isinstance(content, str) or not content.strip():
            raise _fail(base.INVALID_RESPONSE)
        return base.ProviderReply(content=content, model=model if isinstance(model, str) else None)
