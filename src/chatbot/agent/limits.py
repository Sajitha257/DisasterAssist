"""Hard limits and the step record of the Stage 5 agent.

Python owns the workflow. Every step, every retrieval and every Gemini call is
counted here BEFORE it happens. When a limit would be passed, AgentLimitError is
raised and the agent stops: there is no way to loop.

The step record (`AgentTrace.summary()`) never holds the question, a refined query, Gemini text or an API key.
Outcomes are short fixed codes, so that one-line record is safe to print or log.

DIAGNOSTIC DETAILS (`AgentTrace.details`, `detail_lines()`) are separate and are for a person running a check
script, NOT for production logs: per search they hold the approved instruction IDs that were retrieved and, for
the one refined search, the refined query the model proposed (already limited to 150 plain characters by
decisions.py). They never hold the user's question, model text other than that query, or any key.
"""

from dataclasses import dataclass, replace
from typing import List, Tuple

MAX_AGENT_STEPS = 8        # receive, safeguards, plan, retrieve, evaluate, retrieve again, decide, validate
MAX_RETRIEVALS = 2         # the first search plus ONE refined search
MAX_MODEL_CALLS = 3        # plan, evaluate, decide

# Step names
STEP_RECEIVE = "receive"
STEP_SAFEGUARD = "safeguard"
STEP_PLAN = "plan"
STEP_RETRIEVE = "retrieve"
STEP_EVALUATE = "evaluate"
STEP_RETRIEVE_AGAIN = "retrieve_again"
STEP_DECIDE = "decide"
STEP_VALIDATE = "validate"


class AgentLimitError(Exception):
    """A step, retrieval or model-call limit would have been passed."""


@dataclass(frozen=True)
class AgentStep:
    name: str
    outcome: str = ""


@dataclass(frozen=True)
class RetrievalRecord:
    """What ONE search found (diagnostics only). IDs are approved instruction IDs, never question text."""
    number: int                         # 1 = first search, 2 = the refined search
    source: str                         # SOURCE_ORIGINAL or SOURCE_REFINED
    status: str                         # the retrieval status (fixed word)
    ids: Tuple[str, ...]                # retrieved instruction IDs, in retrieval order
    total_matches: int                  # how many approved items matched at all (returned < total = cut off)
    generic: bool                       # True for a question that only names a disaster / section
    expansion_rules: Tuple[str, ...] = ()   # names of the vocabulary-expansion rules that fired (fixed words)
    refined_query: str = ""             # the model's refined query (refined search only; never logged)


SOURCE_ORIGINAL = "original"
SOURCE_REFINED = "refined"


@dataclass(frozen=True)
class AgentTrace:
    steps: Tuple[AgentStep, ...]
    retrievals: int
    model_calls: int
    final_kind: str = ""
    details: Tuple[RetrievalRecord, ...] = ()

    def summary(self) -> str:
        """One line such as 'receive:ok > safeguard:none > plan:retrieve > ...' (no user text)."""
        return " > ".join("%s:%s" % (s.name, s.outcome or "-") for s in self.steps)

    def detail_lines(self) -> List[str]:
        """Readable diagnostic lines (retrieved IDs, refined query). For check scripts only, not for logs."""
        lines = []
        for d in self.details:
            line = "search %d (%s): status=%s, returned %d of %d matches%s%s, ids=%s" % (
                d.number, d.source, d.status, len(d.ids), d.total_matches,
                ", generic question" if d.generic else "",
                ", expansion=" + "+".join(d.expansion_rules) if d.expansion_rules else "",
                ",".join(d.ids) if d.ids else "(none)")
            if d.refined_query:
                line += " | refined query: " + d.refined_query
            lines.append(line)
        return lines


class AgentRun:
    """The counters and the step record of ONE question."""

    def __init__(self, max_steps: int = MAX_AGENT_STEPS, max_retrievals: int = MAX_RETRIEVALS,
                 max_model_calls: int = MAX_MODEL_CALLS):
        self.max_steps = max_steps
        self.max_retrievals = max_retrievals
        self.max_model_calls = max_model_calls
        self._steps: List[AgentStep] = []
        self.retrievals = 0
        self.model_calls = 0
        self.retrieval_status = None          # status of the latest retrieval (a fixed word)
        self._records: List[RetrievalRecord] = []

    def step(self, name: str) -> None:
        if len(self._steps) >= self.max_steps:
            raise AgentLimitError("step limit")
        self._steps.append(AgentStep(name))

    def note(self, outcome: str) -> None:
        """Set the outcome (a fixed code) of the step that is running."""
        if self._steps:
            self._steps[-1] = replace(self._steps[-1], outcome=outcome)

    def count_retrieval(self) -> None:
        if self.retrievals >= self.max_retrievals:
            raise AgentLimitError("retrieval limit")
        self.retrievals += 1

    def record_retrieval(self, record: RetrievalRecord) -> None:
        self._records.append(record)

    def count_model_call(self) -> None:
        if self.model_calls >= self.max_model_calls:
            raise AgentLimitError("model call limit")
        self.model_calls += 1

    def trace(self, final_kind: str = "") -> AgentTrace:
        return AgentTrace(tuple(self._steps), self.retrievals, self.model_calls, final_kind, tuple(self._records))
