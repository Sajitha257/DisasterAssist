"""Stage 5: the bounded Agentic RAG workflow. Python controls every step.

    1. receive      Python checks the question is text.
    2. safeguard    Python: electricity -> fixed notice, weather -> refusal.
    3. plan         Gemini: is retrieval needed?
    4. retrieve     Python: BM25 search of the approved guide.
    5. evaluate     Gemini: do the retrieved instructions sufficiently match?
    6. retrieve_again Python: ONE more BM25 search if refinement is valid.
    7. decide       Gemini: is it answerable, and which retrieved IDs answer it?
    8. validate     Python: strict ID checks, then build from exact approved text.

Gemini never writes anything that is shown. Every Gemini reply is checked strictly.
Hard limits on steps, searches and Gemini calls are enforced by AgentRun.
"""

import logging
from typing import Optional, Tuple

from src.chatbot import answer as ans
from src.chatbot import models as m
from src.chatbot import safeguards
from src.chatbot.agent import decisions as dec
from src.chatbot.agent import limits as lim
from src.chatbot.agent.tools import RetrievalTool
from src.chatbot.providers import base
from src.chatbot.query import MAX_QUERY_CHARS
from src.chatbot.retriever import Retriever
from src.guide import expected as ex

log = logging.getLogger("disasterassist.agent")

ERROR_AGENT_LIMIT = "agent_limit"
LIMIT_TEXT = (
    "The question could not be processed within the allowed number of steps, so no answer is shown. "
    "The Emergency Safety Guide is still available."
)


class AgentService:
    """Drop-in replacement for AnswerService: ask(question) returns a ChatAnswer."""

    def __init__(
        self,
        retriever: Retriever,
        provider,
        top_k: int = 5,
        max_steps: int = lim.MAX_AGENT_STEPS,
    ):
        self._retriever = retriever
        self._provider = provider
        self._top_k = top_k
        self._max_steps = max_steps

    def ask(self, question: object) -> ans.ChatAnswer:
        return self.ask_with_trace(question)[0]

    def ask_with_trace(self, question: object) -> Tuple[ans.ChatAnswer, lim.AgentTrace]:
        run = lim.AgentRun(max_steps=self._max_steps)
        asked = question.strip()[:MAX_QUERY_CHARS] if isinstance(question, str) else ""

        try:
            answer = self._run(asked, run)
        except lim.AgentLimitError:
            answer = ans.ChatAnswer(
                ans.KIND_UNAVAILABLE,
                LIMIT_TEXT,
                error_code=ERROR_AGENT_LIMIT,
                question=asked,
                retrieval_status=run.retrieval_status,
            )
        except base.ProviderError as error:
            answer = self._unavailable(error.code, asked, run, error.provider)
        except (dec.AgentResponseError, ans.ResponseError):
            answer = self._unavailable(base.INVALID_RESPONSE, asked, run)
        except Exception as error:
            log.warning("Agent raised %s", type(error).__name__)
            answer = self._unavailable(base.UNKNOWN, asked, run)

        trace = run.trace(answer.kind)
        log.debug("Agent finished: %s", trace.summary())
        return answer, trace

    # ------------------------------------------------------------------ the steps

    def _run(self, asked: str, run: lim.AgentRun) -> ans.ChatAnswer:
        run.step(lim.STEP_RECEIVE)

        if not asked:
            run.note("empty")
            return ans.ChatAnswer(ans.KIND_EMPTY, ans.EMPTY_TEXT)

        run.note("ok")

        run.step(lim.STEP_SAFEGUARD)
        rule = safeguards.check_question(asked)

        if rule == safeguards.ELECTRICITY:
            run.note("electricity")
            return ans.ChatAnswer(
                ans.KIND_ELECTRICITY,
                safeguards.ELECTRICITY_NOTICE,
                question=asked,
            )

        if rule == safeguards.WEATHER:
            run.note("weather")
            return ans.ChatAnswer(
                ans.KIND_WEATHER,
                safeguards.WEATHER_NOTICE,
                question=asked,
            )

        run.note("none")

        if self._provider is None:
            return self._unavailable(base.NOT_CONFIGURED, asked, run)

        tool = RetrievalTool(self._retriever, run, self._top_k)

        # 3. Plan
        run.step(lim.STEP_PLAN)
        run.count_model_call()

        plan = dec.parse_plan(self._provider.plan(asked).content)

        run.note("retrieve" if plan.needs_retrieval else "no_retrieval")

        if not plan.needs_retrieval:
            return self._refuse(asked, run)

        # 4. First retrieval
        run.step(lim.STEP_RETRIEVE)
        first_result = tool.search(asked)

        first_found = first_result.ok and bool(first_result.items)

        # Keep the original search result available for fallback.
        result = first_result
        found = first_found

        run.note(
            result.status if found else "nothing_" + result.status
        )

        # 5. Evaluate
        run.step(lim.STEP_EVALUATE)
        run.count_model_call()

        reply = self._provider.evaluate(
            asked,
            result.items if found else (),
        )

        evaluation = dec.parse_evaluation(
            reply.content,
            has_items=found,
        )

        run.note(
            "sufficient" if evaluation.sufficient else "insufficient"
        )

        # 6. At most ONE more retrieval
        if not evaluation.sufficient:
            refined = dec.refinement_target(asked, evaluation)

            if refined is None or safeguards.check_question(refined) is not None:
                return self._refuse(asked, run)

            run.step(lim.STEP_RETRIEVE_AGAIN)

            refined_result = tool.search(refined, refined=True)

            refined_found = (
                refined_result.ok and bool(refined_result.items)
            )

            run.note(
                refined_result.status
                if refined_found
                else "nothing_" + refined_result.status
            )

            if refined_found:
                # Successful refined search replaces the original results.
                result = refined_result

            elif first_found:
                # Failed refined search: use the original approved results.
                result = first_result

            else:
                # Neither search found usable approved instructions.
                return self._refuse(asked, run)

        # 7. Final decision: judged against the ORIGINAL question
        run.step(lim.STEP_DECIDE)
        run.count_model_call()

        reply = self._provider.select(asked, result.items)

        verdict = ans.parse_verdict(
            reply.content,
            [item.instruction_id for item in result.items],
        )

        run.note(
            "answerable" if verdict.answerable else "not_answerable"
        )

        if not verdict.answerable:
            return ans.ChatAnswer(
                ans.KIND_NOT_ANSWERABLE,
                ans.NOT_ANSWERABLE_TEXT,
                question=asked,
                retrieval_status=result.status,
            )

        # 8. Validate in Python, then build from exact approved text.
        run.step(lim.STEP_VALIDATE)

        chosen = tuple(
            item
            for item in result.items
            if item.instruction_id in verdict.used_ids
        )

        if not self._chosen_is_valid(chosen, verdict, result):
            run.note("rejected")
            return self._unavailable(base.INVALID_RESPONSE, asked, run)

        run.note("ok")

        return ans.ChatAnswer(
            ans.KIND_ANSWER,
            "",
            items=chosen,
            related_notes=result.related_notes,
            question=asked,
            retrieval_status=result.status,
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _chosen_is_valid(
        chosen: Tuple[m.RetrievedItem, ...],
        verdict: ans.Verdict,
        result: m.RetrievalResult,
    ) -> bool:
        """Last Python check before anything is shown."""

        retrieved = {
            item.instruction_id for item in result.items
        }

        if (
            not chosen
            or {item.instruction_id for item in chosen}
            != set(verdict.used_ids)
            or not set(verdict.used_ids) <= retrieved
        ):
            return False

        for item in chosen:
            if not item.instruction_id or not item.text:
                return False

            if item.instruction_id == ex.FIRE_D_013_ID:
                caveat = (item.caveat or "").lower()

                if not all(
                    phrase in caveat
                    for phrase in ex.FIRE_D_013_REQUIRED_PHRASES
                ):
                    return False

        return True

    @staticmethod
    def _refuse(
        asked: str,
        run: lim.AgentRun,
    ) -> ans.ChatAnswer:
        return ans.ChatAnswer(
            ans.KIND_NO_MATCH,
            ans.NO_MATCH_TEXT,
            question=asked,
            retrieval_status=run.retrieval_status,
        )

    @staticmethod
    def _unavailable(
        code: str,
        asked: str,
        run: lim.AgentRun,
        provider=None,
    ) -> ans.ChatAnswer:
        error = base.ProviderError(code, provider)

        return ans.ChatAnswer(
            ans.KIND_UNAVAILABLE,
            error.user_message
            + " The Emergency Safety Guide is still available.",
            error_code=code,
            question=asked,
            retrieval_status=run.retrieval_status,
        )