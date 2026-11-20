"""Fixed safety rules that run in plain Python BEFORE retrieval and BEFORE any AI call.

They do not depend on what the AI model decides.

* Electricity: the approved guide has no verified electrical-safety instructions
  (only passing mentions inside fire, flood and other pages). A question about
  electricity therefore gets a fixed notice, and no instructions are shown.
* Weather forecasts: the chatbot has no weather data and gives no forecasts.

The word lists are examples of wording, not a complete list of every possible
way to ask. A question worded in another way goes on to retrieval, where the
normal checks still apply. See docs/gemini.md ("Known limits").
"""

from typing import Optional

from src.chatbot import text as tx

ELECTRICITY = "electricity"
WEATHER = "weather"

ELECTRICITY_NOTICE = (
    "This chatbot cannot provide verified electrical-safety instructions. "
    "If someone is in immediate danger, call the emergency number 112. "
    "The Emergency Safety Guide shows the approved instructions that exist for each disaster."
)
WEATHER_NOTICE = (
    "This chatbot cannot answer weather or forecast questions. "
    "It only answers questions about the approved disaster safety instructions. "
    "For a weather forecast or warning, use your official national or local weather service."
)

# Words that make a question an electricity question (matched on the whole word).
_ELECTRIC_WORDS = frozenset("""
wire wires wiring circuit circuits breaker breakers fuse fuses mains voltage socket sockets transformer
transformers electrician electricians
""".split())
# A word that STARTS with one of these is also an electricity word (electric, electrical, electricity, electrocuted...).
_ELECTRIC_PREFIXES = ("electri", "electroc")
_POWER_FOLLOWERS = frozenset("""
line lines cable cables supply pole poles outage outages cut cuts failure failures grid station
""".split())

_FORECAST_WORDS = frozenset("forecast forecasts forecasting forecasted".split())
_WEATHER_WORDS = frozenset("""
weather temperature temperatures rain rainfall raining rains humidity monsoon sunny cloudy windy
""".split())
_TIME_OR_PREDICTION_WORDS = frozenset("""
today tomorrow tonight tomorrows week weekend now currently current will going expected expect chance likely
predict prediction predictions predicted next outside report reports update updates
""".split())


def _has_electricity_words(words) -> bool:
    for i, word in enumerate(words):
        if word in _ELECTRIC_WORDS or word.startswith(_ELECTRIC_PREFIXES):
            return True
        if word == "power" and i + 1 < len(words) and words[i + 1] in _POWER_FOLLOWERS:
            return True
        if word in ("live", "downed", "fallen") and i + 1 < len(words) and words[i + 1] in ("wire", "wires", "cable", "cables"):
            return True
    return False


def _has_weather_words(words) -> bool:
    if any(w in _FORECAST_WORDS for w in words):
        return True
    if any(w == "weather" for w in words) and not any(w == "severe" for w in words):
        return True                                   # "what is the weather like", "weather in Delhi"
    has_weather = any(w in _WEATHER_WORDS for w in words)
    return has_weather and any(w in _TIME_OR_PREDICTION_WORDS for w in words)


def check_question(question: object) -> Optional[str]:
    """Return ELECTRICITY, WEATHER or None. Electricity is checked first."""
    if not isinstance(question, str):
        return None
    words = tx.tokenize(question[:2000])
    if _has_electricity_words(words):
        return ELECTRICITY
    if _has_weather_words(words):
        return WEATHER
    return None
