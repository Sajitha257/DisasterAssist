"""Answering a question: retrieval first, then the AI check, then Python builds the answer.

Order of work (see docs/gemini.md):

1. Fixed safeguards (electricity, weather). No retrieval, no AI call.
2. BM25 retrieval. If nothing relevant is found: refuse. No AI call.
3. Send ONLY the retrieved approved instructions to the AI model.
4. Validate the model's JSON and every ID in it. Anything wrong: nothing is shown.
   The model may return exactly two fields: "answerable" and "used_ids".
5. If the model says "not answerable": hide the retrieved items.
6. Otherwise show the exact approved text of the chosen instructions, in the
   order retrieval ranked them, with their caveats, source tags, attribution
   notes, scope notes, conflicts and limitations. No text written by the model
   is ever shown: not an overview, not a summary, not an explanation.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from src.chatbot import models as m
from src.chatbot import safeguards
from src.chatbot.providers import base
from src.chatbot.retriever import Retriever

log = logging.getLogger("disasterassist.answer")

# Answer kinds
KIND_ANSWER = "answer"
KIND_ELECTRICITY = "electricity_notice"
KIND_WEATHER = "weather_refusal"
KIND_NO_MATCH = "no_match"              # retrieval found nothing relevant (no AI call)
KIND_NOT_ANSWERABLE = "not_answerable"  # the AI model said the retrieved items do not answer it
KIND_UNAVAILABLE = "unavailable"        # AI service problem (see error_code)
KIND_EMPTY = "empty_question"

NO_MATCH_TEXT = (
    "The approved guide does not contain enough information to answer this question, so no answer is shown. "
    "You can look through the Emergency Safety Guide instead."
)
NOT_ANSWERABLE_TEXT = (
    "The approved instructions found for this question do not answer it, so none are shown. "
    "You can look through the Emergency Safety Guide instead."
)
EMPTY_TEXT = "Please type a question about a disaster (flood, cyclone, earthquake, landslide, tsunami or fire)."


@dataclass(frozen=True)
class ChatAnswer:
    kind: str
    message: str                                    # fixed text for every kind except KIND_ANSWER
    items: Tuple[m.RetrievedItem, ...] = ()         # only the instructions to display
    related_notes: Tuple[m.ContextNote, ...] = ()
    error_code: Optional[str] = None
    question: str = ""
    retrieval_status: Optional[str] = None

    @property
    def shows_instructions(self) -> bool:
        return self.kind == KIND_ANSWER and bool(self.items)


class ResponseError(Exception):
    """The AI response was not usable. Carries no text from the response."""


@dataclass(frozen=True)
class Verdict:
    answerable: bool
    used_ids: Tuple[str, ...]


def parse_verdict(raw: str, allowed_ids: Sequence[str]) -> Verdict:
    """Strictly check the model's JSON. Raises ResponseError for anything unexpected."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise ResponseError("not JSON") from None
    if not isinstance(data, dict) or set(data) != {"answerable", "used_ids"}:
        raise ResponseError("wrong fields")
    answerable, used = data["answerable"], data["used_ids"]
    if not isinstance(answerable, bool) or not isinstance(used, list):
        raise ResponseError("wrong types")
    if not all(isinstance(u, str) for u in used):
        raise ResponseError("ids must be text")
    allowed = set(allowed_ids)
    if any(u not in allowed for u in used):
        raise ResponseError("unknown id")           # an invented or unretrieved ID: reject the whole response
    unique = tuple(dict.fromkeys(used))
    if answerable and not unique:
        raise ResponseError("answerable but no ids")
    return Verdict(answerable=answerable, used_ids=unique if answerable else ())


class AnswerService:
    def __init__(self, retriever: Retriever, provider: Optional[base.Provider], top_k: int = 5):
        self._retriever = retriever
        self._provider = provider
        self._top_k = top_k

    def ask(self, question: object) -> ChatAnswer:
        text = question.strip() if isinstance(question, str) else ""
        if not text:
            return ChatAnswer(KIND_EMPTY, EMPTY_TEXT)

        rule = safeguards.check_question(text)
        if rule == safeguards.ELECTRICITY:
            return ChatAnswer(KIND_ELECTRICITY, safeguards.ELECTRICITY_NOTICE, question=text)
        if rule == safeguards.WEATHER:
            return ChatAnswer(KIND_WEATHER, safeguards.WEATHER_NOTICE, question=text)

        result = self._retriever.search(text, top_k=self._top_k)
        if not result.ok or not result.items:
            return ChatAnswer(KIND_NO_MATCH, NO_MATCH_TEXT, question=result.query, retrieval_status=result.status)

        if self._provider is None:
            return self._unavailable(base.NOT_CONFIGURED, result)
        try:
            reply = self._provider.select(result.query, result.items)
        except base.ProviderError as error:
            return self._unavailable(error.code, result, error.provider)
        except Exception as error:                   # a provider must not crash the website
            log.warning("Provider raised %s", type(error).__name__)
            return self._unavailable(base.UNKNOWN, result)

        try:
            verdict = parse_verdict(reply.content, [i.instruction_id for i in result.items])
        except ResponseError:
            return self._unavailable(base.INVALID_RESPONSE, result)

        if not verdict.answerable:
            return ChatAnswer(KIND_NOT_ANSWERABLE, NOT_ANSWERABLE_TEXT, question=result.query,
                              retrieval_status=result.status)

        chosen = tuple(i for i in result.items if i.instruction_id in verdict.used_ids)   # retrieval order
        return ChatAnswer(
            KIND_ANSWER, "", items=chosen, related_notes=result.related_notes,
            question=result.query, retrieval_status=result.status,
        )

    @staticmethod
    def _unavailable(code: str, result: m.RetrievalResult, provider=None) -> ChatAnswer:
        error = base.ProviderError(code, provider)
        return ChatAnswer(KIND_UNAVAILABLE, error.user_message + " The Emergency Safety Guide is still available.",
                          error_code=code, question=result.query, retrieval_status=result.status)
