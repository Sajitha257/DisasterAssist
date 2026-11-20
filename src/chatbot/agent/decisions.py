"""Strict checking of what Gemini returns in the planning and evaluation steps.

Gemini may return ONLY small decisions: choices from fixed lists, true/false, and
one short SEARCH query. None of it is ever shown to the user. Anything unexpected
raises AgentResponseError and the whole answer is abandoned (nothing is shown).

The (optional) refined query is used only as the text of one more BM25 search of
the approved guide. It is limited in length and characters, and Python's fixed
safeguards (electricity, weather) are applied to it again by the workflow.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from src.chatbot import text as tx

PLAN_DISASTERS = ("flood", "cyclone", "earthquake", "landslide", "tsunami", "fire", "unknown")
PLAN_INFORMATION = ("before", "during", "after", "general", "unknown")

MAX_REFINED_CHARS = 150
MAX_REFINED_WORDS = 15
_REFINED_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ,'?.\-]*")


class AgentResponseError(Exception):
    """A Gemini reply in the agent steps was not usable. Carries no text from the reply."""


@dataclass(frozen=True)
class Plan:
    needs_retrieval: bool
    disaster: str
    information: str


@dataclass(frozen=True)
class Evaluation:
    sufficient: bool
    refined_query: str          # "" when there is none


def _load_object(raw: object, fields: Tuple[str, ...]) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise AgentResponseError("not JSON") from None
    if not isinstance(data, dict) or set(data) != set(fields):
        raise AgentResponseError("wrong fields")
    return data


def parse_plan(raw: object) -> Plan:
    data = _load_object(raw, ("needs_retrieval", "disaster", "information"))
    needs, disaster, information = data["needs_retrieval"], data["disaster"], data["information"]
    if not isinstance(needs, bool):
        raise AgentResponseError("wrong types")
    if not isinstance(disaster, str) or disaster not in PLAN_DISASTERS:
        raise AgentResponseError("unknown disaster")
    if not isinstance(information, str) or information not in PLAN_INFORMATION:
        raise AgentResponseError("unknown information type")
    return Plan(needs, disaster, information)


def parse_evaluation(raw: object, has_items: bool) -> Evaluation:
    """`has_items` is False when the first search found nothing: then "sufficient" cannot be true."""
    data = _load_object(raw, ("sufficient", "refined_query"))
    sufficient, refined = data["sufficient"], data["refined_query"]
    if not isinstance(sufficient, bool) or not isinstance(refined, str):
        raise AgentResponseError("wrong types")
    refined = refined.strip()
    if sufficient and (refined or not has_items):
        raise AgentResponseError("inconsistent evaluation")
    if refined and not valid_refined_query(refined):
        raise AgentResponseError("bad refined query")
    return Evaluation(sufficient, refined)


def valid_refined_query(query: str) -> bool:
    return (
        0 < len(query) <= MAX_REFINED_CHARS
        and len(query.split()) <= MAX_REFINED_WORDS
        and _REFINED_PATTERN.fullmatch(query) is not None
    )


def same_search(original: str, refined: str) -> bool:
    """True when the refined query would search for exactly the same words (no real refinement)."""
    return tx.tokenize(original) == tx.tokenize(refined)


def refinement_target(original: str, evaluation: Evaluation) -> Optional[str]:
    """The refined query to search with, or None when no second search should happen."""
    if evaluation.sufficient or not evaluation.refined_query:
        return None
    if same_search(original, evaluation.refined_query):
        return None
    return evaluation.refined_query
