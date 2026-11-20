"""AI provider settings (Stage 4; Gemini since the provider migration).

Everything is read from the `.env` file (or the Windows environment) so that
nothing has to be edited in Python files. The API key is read ONCE, when the
website starts. To use a new key: change it in `.env`, then restart the website.

Rules:
* A value written in `.env` wins over a value in the Windows environment, so an
  old key left in the system settings can never silently override `.env`.
* The key is never printed, logged or shown. `repr()` of the settings hides it.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from dotenv import dotenv_values

from src.config import ENV_FILE

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
PROVIDER_GEMINI = "gemini"
PROVIDER_NAVIGATE = "navigate"
# Other accepted spellings of LLM_PROVIDER. They are mapped to the existing provider name, so the rest of the
# code (factories, messages, scripts) only ever sees "gemini" or "navigate".
PROVIDER_ALIASES = {"navigatelabs": PROVIDER_NAVIGATE}
DEFAULT_NAVIGATE_BASE_URL = "https://nexusapi.navigatelabs.ai"
DEFAULT_NAVIGATE_CHAT_PATH = "/v1/chat/completions"     # UNVERIFIED default; override with NAVIGATE_CHAT_PATH
NAVIGATE_JSON_MODES = ("json_schema", "json_object", "none")
DEFAULT_NAVIGATE_JSON_MODE = "json_schema"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_OUTPUT_TOKENS = 2000
MIN_TIMEOUT, MAX_TIMEOUT = 1.0, 120.0
MIN_TOKENS, MAX_TOKENS = 200, 8000

KEY_MISSING = "missing"
KEY_MALFORMED = "malformed"
KEY_PRESENT = "present"


@dataclass(frozen=True)
class LLMSettings:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    api_key: str = field(default="", repr=False)   # never shown by repr(); GEMINI_API_KEY or NAVIGATE_API_KEY
    # Used only when provider == "navigate". All have safe defaults so Gemini settings are unchanged.
    base_url: str = DEFAULT_NAVIGATE_BASE_URL
    chat_path: str = DEFAULT_NAVIGATE_CHAT_PATH
    json_mode: str = DEFAULT_NAVIGATE_JSON_MODE

    @property
    def key_state(self) -> str:
        key = self.api_key
        if not key:
            return KEY_MISSING
        # A real key is one run of plain ASCII characters. Spaces, quotes or other
        # characters mean the line in .env was pasted wrongly.
        if not key.isascii() or any(c.isspace() or c in "\"'" for c in key) or not key.isprintable():
            return KEY_MALFORMED
        return KEY_PRESENT


def _clean(value: Optional[str]) -> str:
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def _number(name: str, raw: str, default, low, high, cast, warnings: list):
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        warnings.append("%s is not a valid number; using %s." % (name, default))
        return default
    if not low <= value <= high:
        warnings.append("%s must be between %s and %s; using %s." % (name, low, high, default))
        return default
    return value


def load_settings(env_file: Optional[Path] = None, environ: Optional[Mapping[str, str]] = None,
                  warn=None, force_provider: Optional[str] = None) -> LLMSettings:
    """Read the settings. `env_file` and `environ` exist so tests never touch the real files.
    `force_provider` lets a check script read the Navigate (or Gemini) values whatever LLM_PROVIDER says."""
    env_file = ENV_FILE if env_file is None else env_file
    environ = os.environ if environ is None else environ
    from_file = dotenv_values(env_file) if Path(env_file).is_file() else {}

    def get(name: str) -> str:
        return _clean(from_file.get(name)) or _clean(environ.get(name))

    problems: list = []
    provider = (force_provider or get("LLM_PROVIDER") or DEFAULT_PROVIDER).lower()
    provider = PROVIDER_ALIASES.get(provider, provider)
    navigate = provider == PROVIDER_NAVIGATE
    json_mode = (get("NAVIGATE_JSON_MODE") or DEFAULT_NAVIGATE_JSON_MODE).lower()
    if json_mode not in NAVIGATE_JSON_MODES:
        problems.append("NAVIGATE_JSON_MODE must be one of %s; using %s." % (", ".join(NAVIGATE_JSON_MODES), DEFAULT_NAVIGATE_JSON_MODE))
        json_mode = DEFAULT_NAVIGATE_JSON_MODE
    chat_path = get("NAVIGATE_CHAT_PATH") or DEFAULT_NAVIGATE_CHAT_PATH
    settings = LLMSettings(
        provider=provider,
        # Navigate has NO default model: the exact ID must come from NAVIGATE_MODEL (see docs/navigate.md).
        model=(get("NAVIGATE_MODEL") if navigate else (get("GEMINI_MODEL") or DEFAULT_MODEL)),
        timeout_seconds=_number("LLM_TIMEOUT_SECONDS", get("LLM_TIMEOUT_SECONDS"), DEFAULT_TIMEOUT_SECONDS,
                                MIN_TIMEOUT, MAX_TIMEOUT, float, problems),
        max_output_tokens=_number("LLM_MAX_OUTPUT_TOKENS", get("LLM_MAX_OUTPUT_TOKENS"), DEFAULT_MAX_OUTPUT_TOKENS,
                                  MIN_TOKENS, MAX_TOKENS, int, problems),
        api_key=get("NAVIGATE_API_KEY") if navigate else get("GEMINI_API_KEY"),
        base_url=(get("NAVIGATE_BASE_URL") or DEFAULT_NAVIGATE_BASE_URL).rstrip("/"),
        chat_path=chat_path if chat_path.startswith("/") else "/" + chat_path,
        json_mode=json_mode,
    )
    emit = warn if warn is not None else (lambda text: print("Setting problem: " + text, file=sys.stderr))
    for problem in problems:
        emit(problem)
    return settings
