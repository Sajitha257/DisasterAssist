
"""Understanding a question (in code, without any AI model).

It finds which disaster the question is about, whether it names Before, During
or After, and which words carry the meaning of the question.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.chatbot import text as tx

MAX_QUERY_CHARS = 1000

# ----------------------------------------------------------------------------------------------------------
# Reviewed query expansion.
#
# Expansion terms are used only to improve ranking of items that the original
# question already matched. They are NOT counted as words in the question.
#
# This means:
# - Coverage calculations remain unchanged.
# - Query safety gates remain unchanged.
# - Disaster detection remains unchanged.
# - Expansion cannot independently make a question answerable.
#
# Fire-related expansion is activated only when FIRE is detected.
# ----------------------------------------------------------------------------------------------------------

_INJURY_WORDS = frozenset({
    "injured",
    "injury",
    "injuries",
    "hurt",
})

_CLOTHING_WORDS = frozenset({
    "clothes",
    "clothing",
    "cloth",
    "garment",
    "garments",
    "wearing",
})

EXPANSIONS = (
    # Someone injured during a fire may need an instruction that uses
    # the words burn or burns.
    ("injury_in_fire", _INJURY_WORDS, "fire", None, (
        "burn",
        "burns",
    )),

    # Injury-related searches outside fire may use first-aid terminology.
    # This rule is deliberately disabled when fire is detected.
    ("injury_first_aid", _INJURY_WORDS, None, "fire", (
        "first",
        "aid",
    )),

    # Clothing catching fire may be described in the approved guide
    # using burning, burn or flames rather than the exact query wording.
    ("clothing_fire", _CLOTHING_WORDS, "fire", None, (
        "burn",
        "burns",
        "burning",
        "flame",
        "flames",
    )),
)


def expansion_for(words, disasters) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Return (stems to add, names of the rules that fired)."""

    terms: List[str] = []
    fired: List[str] = []
    named = set(words)

    for name, triggers, needs, forbids, extra in EXPANSIONS:
        if not named & triggers:
            continue

        if needs is not None and needs not in disasters:
            continue

        if forbids is not None and forbids in disasters:
            continue

        fired.append(name)

        terms.extend(
            tx.normalise(word)
            for word in extra
        )

    return (
        tuple(dict.fromkeys(terms)),
        tuple(fired),
    )


@dataclass(frozen=True)
class QueryAnalysis:
    raw_words: Tuple[str, ...]
    search_terms: Tuple[str, ...]
    # Stems sent to BM25 (disaster and section words included).

    content_stems: Tuple[str, ...]
    # Stems of words carrying meaning (without stop/anchor words).

    content_words: Tuple[str, ...]
    # Original words for those stems (first one seen).

    disasters: Tuple[str, ...]
    # Disasters in display order.

    section: Optional[str]
    forest_fire: bool
    truncated: bool

    # Reviewed vocabulary bridge.
    # These terms only re-order items already found by the original query.
    expansion_terms: Tuple[str, ...] = ()

    # Names of the rules that fired.
    expansion_rules: Tuple[str, ...] = ()


def analyse_query(
    query: object,
    disaster_order: Tuple[str, ...],
) -> QueryAnalysis:
    """Analyse any input safely. Non-text input is treated as an empty question."""

    text = query if isinstance(query, str) else ""

    truncated = len(text) > tx_max()
    text = text[:tx_max()]

    words = tx.tokenize(text)

    disasters = set()
    section: Optional[str] = None
    forest_fire = False
    anchor_positions = set()

    # ------------------------------------------------------------------
    # Disaster and section detection
    # ------------------------------------------------------------------

    for i, word in enumerate(words):

        for disaster, keywords in tx.DISASTER_KEYWORDS.items():
            if word in keywords:
                disasters.add(disaster)
                anchor_positions.add(i)

        if word in tx.FOREST_FIRE_SINGLE_WORDS:
            forest_fire = True

        if word in tx.SECTION_KEYWORDS:
            section = section or tx.SECTION_KEYWORDS[word]
            anchor_positions.add(i)

        if i + 1 < len(words):
            pair = (word, words[i + 1])

            if pair in tx.DISASTER_PHRASES:
                disasters.add(tx.DISASTER_PHRASES[pair])
                anchor_positions.update((i, i + 1))

            if (
                pair[0] in tx.DISASTER_KEYWORDS["flood"]
                and pair[1] in tx.FLOOD_PLACE_WORDS
            ):
                anchor_positions.add(i + 1)

            if pair in tx.FOREST_FIRE_PHRASES:
                disasters.add("fire")
                forest_fire = True
                anchor_positions.update((i, i + 1))

    if forest_fire:
        disasters.add("fire")

    # ------------------------------------------------------------------
    # Original search terms and content words
    # ------------------------------------------------------------------

    search_terms: List[str] = []
    content_stems: List[str] = []
    content_words: Dict[str, str] = {}

    for i, word in enumerate(words):

        if word in tx.SECTION_KEYWORDS:
            search_terms.append(
                tx.normalise(tx.SECTION_KEYWORDS[word])
            )
            continue

        if word in tx.STOP_WORDS:
            continue

        stem = tx.normalise(word)
        search_terms.append(stem)

        if (
            i in anchor_positions
            or word in tx.FOREST_FIRE_SINGLE_WORDS
        ):
            continue

        if stem not in content_words:
            content_stems.append(stem)
            content_words[stem] = word

    # ------------------------------------------------------------------
    # Reviewed vocabulary expansion
    # ------------------------------------------------------------------

    expansion_terms, expansion_rules = expansion_for(
        words,
        disasters,
    )

    return QueryAnalysis(
        raw_words=tuple(words),
        search_terms=tuple(search_terms),
        content_stems=tuple(content_stems),
        content_words=tuple(
            content_words[stem]
            for stem in content_stems
        ),
        disasters=tuple(
            disaster
            for disaster in disaster_order
            if disaster in disasters
        ),
        section=section,
        forest_fire=forest_fire,
        truncated=truncated,
        expansion_terms=tuple(
            term
            for term in expansion_terms
            if term not in search_terms
        ),
        expansion_rules=expansion_rules,
    )


def tx_max() -> int:
    return MAX_QUERY_CHARS
