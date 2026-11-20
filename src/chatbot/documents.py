"""Builds the searchable documents from the approved data.

Two collections are built:

* Instruction documents: every approved instruction (Before/During/After for
  all six disasters, Forest Fire, the tsunami bulletin levels, and the common
  preparedness items C1-C8, which are identical in all six files and are
  therefore indexed once, as "common").
* Note documents: limitations and known conflicts, so questions about gaps,
  sources or conflicts can find them.

The excluded-guidance part of the files is deliberately NOT read here. It is
never indexed and can never be retrieved.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.chatbot.text import DISASTER_KEYWORDS, index_tokens, normalise, tokenize
from src.guide import expected as ex
from src.guide import limitations as lim
from src.guide.render import GROUP_TITLES, SECTION_TITLES

COMMON = "common"

# Whether the words of an item's caveat are searchable (the caveat is always ATTACHED to the
# item either way). Chosen by measurement, see docs/retrieval.md.
INDEX_CAVEATS = False

# The common preparedness items C1-C8 each begin with a short title ("Emergency bag
# (waterproof).", "Escape plan."). They are also much longer than other items, which
# BM25 penalises. Counting the title once more lets a question about the title find them.
# Only these eight items have such titles; no other item is affected.
HEADING_EXTRA_REPEATS = 1


@dataclass(frozen=True)
class InstructionDoc:
    key: str                        # unique, for example "flood:FLOOD-B-001" or "common:C5"
    instruction_id: str
    disaster_id: str                # one of the six ids, or "common"
    group: str                      # before / during / after / common / forest-fire/prevention ...
    group_label: str
    text: str
    source_tags: Tuple[str, ...]
    caveat: Optional[str]
    tokens: Tuple[str, ...]         # words used by BM25 (text + caveat + page-part words)
    order: int                      # position in the approved files (used to break ties)
    mentions: Tuple[str, ...] = ()  # OTHER disasters that the item's own text names (for cross-filed answers)


@dataclass(frozen=True)
class NoteDoc:
    key: str
    kind: str                       # "limitation" or "conflict"
    note_id: str
    disaster_id: str
    text: str
    source_tags: Tuple[str, ...]
    limitation_kind: Optional[str]
    placement: Optional[str]
    tokens: Tuple[str, ...]
    order: int


def _heading(text: str) -> str:
    """The title at the start of a common preparedness item (its first sentence)."""
    return text.split(". ", 1)[0].rstrip(".")


def _mentions(text: str, own_disaster: str) -> Tuple[str, ...]:
    """Other disasters that the item's own text names, using the same keywords as question analysis."""
    words = set(tokenize(text))
    return tuple(d for d, keywords in DISASTER_KEYWORDS.items() if d != own_disaster and words & keywords)


def _tokens(text: str, caveat: Optional[str], extra_words: str) -> Tuple[str, ...]:
    words = index_tokens(text)
    if caveat and INDEX_CAVEATS:
        words += index_tokens(caveat)
    words += index_tokens(extra_words)
    return tuple(words)


def build_instruction_docs(disasters: Dict[str, dict]) -> List[InstructionDoc]:
    docs: List[InstructionDoc] = []

    def add(disaster_id: str, item: dict, group: str, group_label: str, extra_words: str) -> None:
        docs.append(
            InstructionDoc(
                key="%s:%s" % (disaster_id, item["instruction_id"]),
                instruction_id=item["instruction_id"],
                disaster_id=disaster_id,
                group=group,
                group_label=group_label,
                text=item["text"],
                source_tags=tuple(item["source_tags"]),
                caveat=item["caveat"],
                tokens=_tokens(item["text"], item["caveat"], extra_words),
                order=len(docs),
                mentions=_mentions(item["text"], disaster_id),
            )
        )

    for disaster_id in ex.DISASTER_ORDER:
        data = disasters[disaster_id]
        name = data["disaster_name"]
        for section in ex.SECTION_NAMES:
            for item in data["sections"][section]:
                add(disaster_id, item, section, "%s - %s" % (name, SECTION_TITLES[section]),
                    "%s %s" % (name, section))
        for sub in data["subsections"]:
            for group, items in sub["sections"].items():
                label = "%s - %s" % (sub["subsection_name"], GROUP_TITLES[group])
                if disaster_id == "fire":
                    extra = "fire forest %s" % GROUP_TITLES[group]
                else:
                    extra = "%s bulletin level incois official terminology" % name
                for item in items:
                    add(disaster_id, item, "%s/%s" % (sub["subsection_id"], group), label, extra)

    # C1-C8 are identical in all six files (checked by the Stage 1 validator).
    for item in disasters[ex.DISASTER_ORDER[0]]["common_preparedness"]:
        add(COMMON, item, "common", "Common preparedness",
            "preparedness " + " ".join([_heading(item["text"])] * HEADING_EXTRA_REPEATS))
    return docs


def build_note_docs(disasters: Dict[str, dict]) -> List[NoteDoc]:
    rules = lim.rules_by_id()
    notes: List[NoteDoc] = []
    for disaster_id in ex.DISASTER_ORDER:
        data = disasters[disaster_id]
        name = data["disaster_name"]
        for limitation in data["limitations"]:
            rule = rules[limitation["limitation_id"]]
            notes.append(
                NoteDoc(
                    key="limitation:" + limitation["limitation_id"],
                    kind="limitation",
                    note_id=limitation["limitation_id"],
                    disaster_id=disaster_id,
                    text=limitation["text"],
                    source_tags=tuple(limitation["source_tags"]),
                    limitation_kind=rule.kind,
                    placement=rule.placement,
                    tokens=tuple(index_tokens(limitation["text"] + " " + name)),
                    order=len(notes),
                )
            )
        for conflict in data["known_conflicts"]:
            notes.append(
                NoteDoc(
                    key="conflict:" + conflict["conflict_id"],
                    kind="conflict",
                    note_id=conflict["conflict_id"],
                    disaster_id=disaster_id,
                    text=conflict["text"],
                    source_tags=tuple(conflict["source_tags"]),
                    limitation_kind=None,
                    placement=None,
                    tokens=tuple(index_tokens(conflict["text"] + " conflict " + name)),
                    order=len(notes),
                )
            )
    return notes
