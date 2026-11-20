"""The agent's only tool: BM25 search of the approved guide.

The workflow can reach the approved information in no other way: no files, no
shell, no internet, no arbitrary code. Each search is counted, so the agent can
never search more than the limit allows.

A generic question ("What should I do during a flood?") is searched with `GENERIC_TOP_K`, so the model is shown
the WHOLE named section (largest section: 30 items) instead of the first 5 fragments. Other questions use `top_k`.
Every search is also recorded (retrieved IDs, refined query) for the diagnostic trace; see limits.py.
"""

from src.chatbot import models as m
from src.chatbot.agent import limits as lim
from src.chatbot.agent.limits import AgentRun
from src.chatbot.query import analyse_query
from src.chatbot.retriever import GENERIC_MAX_TOP_K, Retriever
from src.guide import expected as ex

GENERIC_TOP_K = GENERIC_MAX_TOP_K


class RetrievalTool:
    def __init__(self, retriever: Retriever, run: AgentRun, top_k: int = 5):
        self._retriever = retriever
        self._run = run
        self._top_k = top_k

    def search(self, query: str, refined: bool = False) -> m.RetrievalResult:
        """`refined` is True only for the one second search, so the diagnostic record can say so."""
        self._run.count_retrieval()                   # raises AgentLimitError after the limit
        result = self._retriever.search(query, top_k=self._top_k, generic_top_k=GENERIC_TOP_K)
        self._run.retrieval_status = result.status
        self._run.record_retrieval(lim.RetrievalRecord(
            number=self._run.retrievals,
            source=lim.SOURCE_REFINED if refined else lim.SOURCE_ORIGINAL,
            status=result.status,
            ids=tuple(i.instruction_id for i in result.items),
            total_matches=result.total_matches,
            generic=result.generic_query,
            expansion_rules=analyse_query(query, ex.DISASTER_ORDER).expansion_rules,
            refined_query=query if refined else "",
        ))
        return result
