"""BM25 retrieval over the approved Emergency Safety Guide.

What it does, in order (all in plain code, no AI model):

1. Understand the question (disaster, Before/During/After, meaningful words).
2. Rank approved instructions with BM25 (the rank-bm25 library).
3. Check the result is trustworthy: a question that is empty, off-topic or only
   weakly covered returns NO items and a clear status.
4. Attach, in code, everything that must travel with an item: its caveat, the
   S2* attribution note, scope notes, known conflicts and limitations.
5. Also look for limitations or conflicts that match the question itself.

The text it returns is the approved text, unchanged. It never writes new
safety wording, and it never reads the excluded guidance.
"""

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from rank_bm25 import BM25Okapi

from src.chatbot import models as m
from src.chatbot.documents import COMMON, InstructionDoc, NoteDoc, build_instruction_docs, build_note_docs
from src.chatbot.query import analyse_query, MAX_QUERY_CHARS
from src.guide import expected as ex
from src.guide import limitations as lim
from src.guide.loader import ApprovedData, load_approved_data
from src.guide.render import CONFLICT_CARD_LINKS, SOURCE_SCOPE_RULES, attribution_notes_for

DEFAULT_TOP_K = 5
MAX_TOP_K = 20
MAX_RELATED_NOTES = 3
BM25_K1 = 1.5                     # standard BM25 settings (see docs/retrieval.md)
BM25_B = 0.5
# Safety gate. "Coverage" = share of the question's meaningful words found in the returned items,
# where rare words count for more than common ones (their BM25 IDF weight). A word that never
# occurs anywhere in the approved guide counts as the rarest possible word.
MIN_COVERAGE = 0.5
# A disaster NAMED IN THE QUESTION is a preference, not a wall. An instruction filed under another
# disaster may still be returned if its own text explicitly names the disaster asked about (for
# example "After a coastal earthquake, turn on the radio..." is filed under tsunami). Such items
# are ranked a little below the named disaster's own items. A disaster given with the `disaster`
# argument stays a strict filter.
OUT_OF_FOCUS_FACTOR = 0.8
# When the question names NO disaster, a patchwork of unrelated items that each match one word
# (for example "weather" in one item and "forecast" in another) is not an answer. At least one
# single instruction must contain this share of the question's meaningful words (rarity-weighted).
MIN_BEST_ITEM_COVERAGE = 0.45
# The decision must not depend on how many items the caller asks for, so coverage is judged
# over a fixed number of best candidates (the most any caller can request).
COVERAGE_DEPTH = MAX_TOP_K
MIN_NOTE_TERM_SHARE = 0.5         # a matched note must contain at least half of the question's words

# Generic questions ("What should I do during a flood?") have NO meaningful content words: every item of the
# disaster matches the disaster and section words equally, so BM25 would only rank by item LENGTH (the shortest
# items, such as "Beware of snakes.", would win). For these questions the items are put in a meaningful order
# instead: the named section first (Before / During / After), then the guide's own order.
# `generic_top_k` (used by the agent) lets such a question return the WHOLE section. It must be at least as big
# as the biggest section of the guide (Fire "before" has 30 items); a test checks this against the real data.
GENERIC_MAX_TOP_K = 40
SECTION_PRIORITY = {"during": 1, "before": 2, "after": 3}      # order when the question names no section
# Forest Fire is a subsection of Fire; these are its groups that correspond to Before / During / After.
FOREST_FIRE_GROUPS = {
    "during": ("forest-fire/emergency_evacuation",),
    "before": ("forest-fire/preparation", "forest-fire/prevention"),
    "after": ("forest-fire/after",),
}


class Retriever:
    """Searches the approved guide. Build it once and reuse it."""

    def __init__(self, disasters: Dict[str, dict], top_k: int = DEFAULT_TOP_K):
        """`disasters` must be data that already passed the Stage 1 loader."""
        self._check_top_k(top_k)
        self.default_top_k = top_k
        self._disasters = disasters

        self._docs: List[InstructionDoc] = build_instruction_docs(disasters)
        self._doc_words = [frozenset(d.tokens) for d in self._docs]
        self._bm25 = BM25Okapi([list(d.tokens) for d in self._docs], k1=BM25_K1, b=BM25_B)

        self._note_docs: List[NoteDoc] = build_note_docs(disasters)
        self._note_words = [frozenset(n.tokens) for n in self._note_docs]
        self._note_bm25 = BM25Okapi([list(n.tokens) for n in self._note_docs], k1=BM25_K1, b=BM25_B)

        self._sources = {
            d: {s["display_label"]: m.SourceInfo(s["display_label"], s["title"], s["organisation"], s["url"],
                                                 s["evidence_status"], s["attribution_note"])
                for s in disasters[d]["source_references"]}
            for d in ex.DISASTER_ORDER
        }
        self._raw_sources = {d: {s["display_label"]: s for s in disasters[d]["source_references"]}
                             for d in ex.DISASTER_ORDER}
        rules = lim.rules_by_id()
        self._limitations = {
            d: [(l, rules[l["limitation_id"]]) for l in disasters[d]["limitations"]] for d in ex.DISASTER_ORDER
        }
        self._conflicts_by_card: Dict[str, List[m.ContextNote]] = {}
        for d in ex.DISASTER_ORDER:
            for conflict in disasters[d]["known_conflicts"]:
                note = self._conflict_note(d, conflict)
                for card_id in CONFLICT_CARD_LINKS.get(conflict["conflict_id"], ()):
                    self._conflicts_by_card.setdefault(card_id, []).append(note)

    # ------------------------------------------------------------------ set-up
    @classmethod
    def from_approved_data(cls, approved: Optional[ApprovedData] = None, top_k: int = DEFAULT_TOP_K) -> "Retriever":
        """Build from verified data. With no argument, the approved files are loaded and checked first."""
        approved = approved if approved is not None else load_approved_data()
        return cls(approved.disasters, top_k=top_k)

    @staticmethod
    def _check_top_k(top_k: object) -> int:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("top_k must be a whole number from 1 to %d" % MAX_TOP_K)
        return top_k

    @staticmethod
    def _check_disaster(disaster: Union[None, str, Sequence[str]]) -> Tuple[str, ...]:
        if disaster is None:
            return ()
        names = (disaster,) if isinstance(disaster, str) else tuple(disaster)
        for name in names:
            if name not in ex.DISASTER_ORDER:
                raise ValueError("unknown disaster %r; choose from %s" % (name, ", ".join(ex.DISASTER_ORDER)))
        return tuple(d for d in ex.DISASTER_ORDER if d in names)

    # ----------------------------------------------------------- introspection
    def indexed_instruction_keys(self) -> List[str]:
        return [d.key for d in self._docs]

    def indexed_note_keys(self) -> List[str]:
        return [n.key for n in self._note_docs]

    # ------------------------------------------------------------------ search
    def search(self, query: object, disaster: Union[None, str, Sequence[str]] = None,
               top_k: Optional[int] = None, generic_top_k: Optional[int] = None) -> m.RetrievalResult:
        """Search the approved guide.

        `disaster` (optional) limits the search to one or more of the six
        disasters (the common C1-C8 items are always included). If it is not
        given, the disaster is taken from the question when it names one.
        `generic_top_k` (optional) is the number of items to return for a GENERIC question only (one that
        names a disaster but has no other meaningful word). Other questions still use `top_k`.
        Never raises for any question text; raises ValueError only for a wrong
        `top_k`, `generic_top_k` or an unknown `disaster` value (programming mistakes).
        """
        k = self._check_top_k(top_k if top_k is not None else self.default_top_k)
        if generic_top_k is not None:
            self._check_generic_top_k(generic_top_k)
        explicit = self._check_disaster(disaster)
        analysis = analyse_query(query, ex.DISASTER_ORDER)
        focus = explicit or analysis.disasters
        shown_query = query[:MAX_QUERY_CHARS] if isinstance(query, str) else ""
        generic = not analysis.content_stems

        def result(status: str, message: str, **extra) -> m.RetrievalResult:
            values = dict(
                status=status, query=shown_query, message=message, detected_disasters=analysis.disasters,
                detected_section=analysis.section, forest_fire_mentioned=analysis.forest_fire,
                content_terms=analysis.content_words, unmatched_terms=analysis.content_words, coverage=0.0,
                best_item_coverage=0.0, generic_query=generic, query_truncated=analysis.truncated, total_matches=0,
            )
            values.update(extra)
            return m.RetrievalResult(**values)

        if not analysis.search_terms:
            return result(m.STATUS_EMPTY_QUERY, "The question has no searchable words.")
        if generic and not focus:
            return result(m.STATUS_INSUFFICIENT, "The question does not say what it is about.")

        base_scores = self._bm25.get_scores(list(analysis.search_terms))
        candidates, cross_filed, scores = self._candidates(base_scores, explicit, focus)
        if generic and focus:
            # No meaningful word to rank by: use a meaningful order, not item length (see GENERIC_MAX_TOP_K).
            ranked = self._generic_order(candidates, cross_filed, analysis)
            shown = ranked
            if generic_top_k is not None:
                k = max(k, generic_top_k)
        else:
            ranked = sorted(candidates, key=lambda i: (-scores[i], self._docs[i].order))
            shown = ranked
            if ranked and analysis.expansion_terms:
                # Reviewed expansion: it may only RE-ORDER what the question's own words already found.
                # The gates below keep judging the unexpanded ranking, so refusals are exactly as before.
                expanded = self._bm25.get_scores(list(analysis.search_terms) + list(analysis.expansion_terms))
                _, _, scores = self._candidates(expanded, explicit, focus)
                shown = sorted(ranked, key=lambda i: (-scores[i], self._docs[i].order))
        if not ranked:
            return result(m.STATUS_NO_MATCH, "The approved guide has no information matching this question.")

        top = shown[:k]
        content = set(analysis.content_stems)
        found_in_candidates: Set[str] = set()                # judged over a fixed depth (see COVERAGE_DEPTH)
        for i in ranked[:COVERAGE_DEPTH]:
            found_in_candidates |= content & self._doc_words[i]
        found_in_items: Set[str] = set()                     # what the returned items really contain
        for i in top:
            found_in_items |= content & self._doc_words[i]
        coverage = self._weighted_coverage(content, found_in_candidates)
        unmatched = tuple(w for s, w in zip(analysis.content_stems, analysis.content_words) if s not in found_in_items)
        if content and coverage < MIN_COVERAGE:
            return result(
                m.STATUS_INSUFFICIENT,
                "The approved guide covers too little of this question to answer it safely.",
                unmatched_terms=unmatched, coverage=coverage, total_matches=len(ranked),
            )
        best_item = self._best_item_coverage(content, ranked[:COVERAGE_DEPTH])
        if content and not focus and best_item < MIN_BEST_ITEM_COVERAGE:
            return result(
                m.STATUS_INSUFFICIENT,
                "No single approved instruction matches enough of this question to answer it.",
                unmatched_terms=unmatched, coverage=coverage, best_item_coverage=best_item, total_matches=len(ranked),
            )

        best = max(scores[i] for i in top)         # relative scores stay between 0 and 1 in every ordering
        items = tuple(
            self._build_item(rank, self._docs[i], float(scores[i]), float(scores[i]) / float(best), content, focus, analysis,
                             cross_filed=i in cross_filed)
            for rank, i in enumerate(top, start=1)
        )
        attached = {(n.kind, n.text) for item in items for n in item.notes}
        related = () if generic else self._related_notes(analysis, focus, attached)
        message = "Relevant approved items were found."
        if unmatched:
            message += " Some words of the question were not found: %s." % ", ".join(unmatched)
        return result(
            m.STATUS_OK, message, items=items, related_notes=related, unmatched_terms=unmatched,
            coverage=coverage, best_item_coverage=best_item, total_matches=len(ranked),
        )

    def _candidates(self, scores, explicit, focus):
        """The items that match at all, with the disaster filter / preference applied (unsorted).

        Returns (candidate indexes, indexes filed under another disaster, adjusted scores).
        """
        scores = scores.copy()
        cross_filed: Set[int] = set()
        ranked: List[int] = []
        for i, doc in enumerate(self._docs):
            if scores[i] <= 0:
                continue
            if explicit:                                         # strict filter chosen by the caller
                if doc.disaster_id not in explicit and doc.disaster_id != COMMON:
                    continue
            elif focus and doc.disaster_id not in focus and doc.disaster_id != COMMON:
                if not set(doc.mentions) & set(focus):           # another disaster's item that never names it
                    continue
                scores[i] = scores[i] * OUT_OF_FOCUS_FACTOR
                cross_filed.add(i)
            ranked.append(i)
        return ranked, cross_filed, scores

    @staticmethod
    def _check_generic_top_k(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= GENERIC_MAX_TOP_K:
            raise ValueError("generic_top_k must be a whole number from 1 to %d" % GENERIC_MAX_TOP_K)
        return value

    def _section_tier(self, doc: InstructionDoc, section: Optional[str], forest_fire: bool) -> int:
        """Lower = earlier. 0 and 1 are the section the question names (Forest Fire's own groups first)."""
        forest = doc.group.startswith("forest-fire/")
        if section:
            if forest_fire and doc.group in FOREST_FIRE_GROUPS.get(section, ()):
                return 0
            return 1 if doc.group == section else 9
        if forest_fire and forest:
            return 0
        if doc.group in SECTION_PRIORITY:
            return SECTION_PRIORITY[doc.group]
        return 5 if doc.disaster_id == COMMON else 4              # other sub-sections, then common items

    def _generic_order(self, candidates: List[int], cross_filed: Set[int], analysis) -> List[int]:
        """Meaningful order for a question with no content words: section first, then the guide's own order.

        When the question names a section, ONLY that section's items are kept (so "during a flood" never
        returns "before" items). Items filed under another disaster are left out unless nothing else matched.
        """
        own = [i for i in candidates if i not in cross_filed] or list(candidates)
        tiers = {i: self._section_tier(self._docs[i], analysis.section, analysis.forest_fire) for i in own}
        if analysis.section:
            in_section = [i for i in own if tiers[i] <= 1]
            own = in_section or own
        return sorted(own, key=lambda i: (tiers[i], self._docs[i].order))

    def _weighted_coverage(self, content: Set[str], found: Set[str]) -> float:
        """Share of the question's meaningful words found, weighted by rarity (0 to 1)."""
        if not content:
            return 1.0
        idf = self._bm25.idf
        rarest = max(idf.values())
        weight = lambda stem: idf.get(stem, rarest)
        return sum(weight(s) for s in found) / sum(weight(s) for s in content)

    def _best_item_coverage(self, content: Set[str], candidates: Sequence[int]) -> float:
        """Rarity-weighted share of the question's words contained in the single best instruction."""
        if not content:
            return 1.0
        idf = self._bm25.idf
        rarest = max(idf.values())
        weight = lambda stem: idf.get(stem, rarest)
        total = sum(weight(s) for s in content)
        best = max((sum(weight(s) for s in content & self._doc_words[i]) for i in candidates), default=0.0)
        return best / total

    # ------------------------------------------------------------ item building
    def _build_item(self, rank, doc: InstructionDoc, score, relative, content: Set[str], focus, analysis,
                    cross_filed: bool = False) -> m.RetrievedItem:
        source_disaster = ex.DISASTER_ORDER[0] if doc.disaster_id == COMMON else doc.disaster_id
        sources = tuple(self._sources[source_disaster][t] for t in doc.source_tags)
        pseudo_item = {"instruction_id": doc.instruction_id, "source_tags": list(doc.source_tags)}
        attribution = tuple(attribution_notes_for(pseudo_item, self._raw_sources[source_disaster]))
        matched = tuple(
            w for s, w in zip(analysis.content_stems, analysis.content_words)
            if s in self._doc_words[self._docs.index(doc)]
        )
        return m.RetrievedItem(
            rank=rank, score=score, relative_score=relative, instruction_id=doc.instruction_id,
            disaster_id=doc.disaster_id, group=doc.group, group_label=doc.group_label, text=doc.text,
            source_tags=doc.source_tags, caveat=doc.caveat, matched_terms=matched,
            attribution_notes=attribution, sources=sources, notes=self._item_notes(doc, focus),
            cross_filed=cross_filed,
        )

    def _limitation_note(self, disaster_id: str, limitation: dict, rule: lim.LimitationRule, reason: str,
                         score: Optional[float] = None) -> m.ContextNote:
        return m.ContextNote(
            kind="limitation", note_id=limitation["limitation_id"], also_ids=(), disaster_id=disaster_id,
            text=limitation["text"], source_tags=tuple(limitation["source_tags"]),
            limitation_kind=rule.kind, placement=rule.placement, reason=reason, score=score,
        )

    @staticmethod
    def _conflict_note(disaster_id: str, conflict: dict, reason: str = "attached",
                       score: Optional[float] = None) -> m.ContextNote:
        return m.ContextNote(
            kind="conflict", note_id=conflict["conflict_id"], also_ids=(), disaster_id=disaster_id,
            text=conflict["text"], source_tags=tuple(conflict["source_tags"]), limitation_kind=None,
            placement=None, reason=reason, score=score,
        )

    @staticmethod
    def _merge_same_text(notes: Iterable[m.ContextNote]) -> Tuple[m.ContextNote, ...]:
        """Notes with identical approved text (for example the same first-aid gap in six
        files) become one note. The other IDs are kept in `also_ids`."""
        merged: Dict[Tuple[str, str], m.ContextNote] = {}
        for note in notes:
            key = (note.kind, note.text)
            if key not in merged:
                merged[key] = note
            else:
                first = merged[key]
                merged[key] = m.ContextNote(**{**first.__dict__, "also_ids": first.also_ids + (note.note_id,)})
        return tuple(merged.values())

    @staticmethod
    def _placements_for(doc: InstructionDoc) -> Tuple[str, ...]:
        """Which limitation placements (see limitations.py) belong to this item."""
        if doc.group == "before":
            return ("before_and_after", "before")
        if doc.group == "after":
            return ("before_and_after", "after")
        if doc.group == "common" and doc.instruction_id == "C7":
            return ("first_aid",)
        if doc.group == "tsunami-incois-bulletin-levels/bulletin_levels":
            return ("bulletin_levels",)
        if doc.group == "forest-fire/after":
            return ("forest_fire_after",)
        return ()

    def _item_notes(self, doc: InstructionDoc, focus: Tuple[str, ...]) -> Tuple[m.ContextNote, ...]:
        notes: List[m.ContextNote] = []
        if doc.disaster_id != COMMON:
            for limitation_id, applies in SOURCE_SCOPE_RULES.items():
                for limitation, rule in self._limitations[doc.disaster_id]:
                    if limitation["limitation_id"] == limitation_id and applies(doc.source_tags):
                        notes.append(self._limitation_note(doc.disaster_id, limitation, rule, "attached"))
        notes += self._conflicts_by_card.get(doc.instruction_id, [])
        placements = self._placements_for(doc)
        if placements:
            disasters = (doc.disaster_id,) if doc.disaster_id != COMMON else (focus or ex.DISASTER_ORDER)
            for disaster_id in disasters:
                for limitation, rule in self._limitations[disaster_id]:
                    if rule.placement in placements:
                        notes.append(self._limitation_note(disaster_id, limitation, rule, "attached"))
        return self._merge_same_text(notes)

    # ---------------------------------------------------------- related notes
    def _related_notes(self, analysis, focus: Tuple[str, ...], already_attached: Set[Tuple[str, str]]):
        scores = self._note_bm25.get_scores(list(analysis.search_terms))
        content = set(analysis.content_stems)
        needed = max(1, int(len(content) * MIN_NOTE_TERM_SHARE + 0.9999))
        picked = []
        for i, note in enumerate(self._note_docs):
            if scores[i] <= 0 or (focus and note.disaster_id not in focus):
                continue
            if len(content & self._note_words[i]) < needed or (note.kind, note.text) in already_attached:
                continue
            picked.append(i)
        picked.sort(key=lambda i: (-scores[i], self._note_docs[i].order))
        notes = []
        for i in picked:
            n = self._note_docs[i]
            notes.append(m.ContextNote(
                kind=n.kind, note_id=n.note_id, also_ids=(), disaster_id=n.disaster_id, text=n.text,
                source_tags=n.source_tags, limitation_kind=n.limitation_kind, placement=n.placement,
                reason="matched", score=float(scores[i]),
            ))
        return self._merge_same_text(notes)[:MAX_RELATED_NOTES]
