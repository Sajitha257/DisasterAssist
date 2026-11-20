"""The result types returned by retrieval.

All of them are frozen (read-only). The strings inside them are the approved
strings from the JSON files, never rewritten.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple

# Possible values of RetrievalResult.status
STATUS_OK = "ok"                        # relevant approved items were found
STATUS_EMPTY_QUERY = "empty_query"      # nothing searchable was asked
STATUS_NO_MATCH = "no_match"            # nothing in the approved guide matches
STATUS_INSUFFICIENT = "insufficient"    # too little of the question is covered to answer safely


@dataclass(frozen=True)
class SourceInfo:
    """One entry of a source register, for an item's source tag."""
    label: str
    title: str
    organisation: str
    url: str
    evidence_status: str
    attribution_note: Optional[str]


@dataclass(frozen=True)
class ContextNote:
    """A limitation or a known conflict that must travel with an answer."""
    kind: str                       # "limitation" or "conflict"
    note_id: str                    # for example FLOOD-L-003 or EARTHQUAKE-CF-001
    also_ids: Tuple[str, ...]       # same approved text in other files (for example CYCLONE-L-003)
    disaster_id: str
    text: str
    source_tags: Tuple[str, ...]
    limitation_kind: Optional[str]  # safety_gap / source_scope_note / research_process
    placement: Optional[str]        # where the Safety Guide shows it
    reason: str                     # "attached" (belongs to a returned item) or "matched" (matches the question)
    score: Optional[float] = None


@dataclass(frozen=True)
class RetrievedItem:
    """One approved instruction with everything that must be shown with it."""
    rank: int
    score: float
    relative_score: float           # score divided by the best score (0 to 1)
    instruction_id: str
    disaster_id: str                # flood, cyclone, ... or "common" for C1-C8
    group: str                      # before / during / after / common / forest-fire/prevention / ...
    group_label: str
    text: str                       # exact approved text
    source_tags: Tuple[str, ...]
    caveat: Optional[str]           # exact approved item caveat (or None)
    matched_terms: Tuple[str, ...]  # words of the question found in this item
    attribution_notes: Tuple[Tuple[str, str], ...]   # (label, note), for S2*
    sources: Tuple[SourceInfo, ...]
    notes: Tuple[ContextNote, ...]  # scope notes, conflicts and limitations that belong to this item
    cross_filed: bool = False       # True: filed under another disaster but its own text names the disaster asked about


@dataclass(frozen=True)
class RetrievalResult:
    status: str
    query: str
    message: str                    # plain explanation, mainly for the non-ok statuses
    detected_disasters: Tuple[str, ...]
    detected_section: Optional[str]
    forest_fire_mentioned: bool
    content_terms: Tuple[str, ...]  # the question words that carry meaning
    unmatched_terms: Tuple[str, ...]  # question words found in none of the returned items
    coverage: float                 # share of content terms found in the best 20 candidates (rarity-weighted)
    best_item_coverage: float       # the same share for the single best-matching instruction (1.0 if generic)
    generic_query: bool             # True when the question only names a disaster or section
    query_truncated: bool
    total_matches: int              # how many approved items matched at all
    items: Tuple[RetrievedItem, ...] = field(default_factory=tuple)
    related_notes: Tuple[ContextNote, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK
