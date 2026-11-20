"""A small Porter stemmer (the classic 1980 algorithm), written for this project.

A stemmer cuts a word down to a common root so that different forms of a word
match each other in search: "flooding", "floods" and "flooded" all become
"flood", and "evacuate", "evacuating" and "evacuation" all become "evacu".

It is used only to compare words for SEARCH. The approved text that is shown
to people is never stemmed or changed.
"""

from typing import List, Tuple

_VOWELS = "aeiou"


def _is_consonant(word: str, i: int) -> bool:
    ch = word[i]
    if ch in _VOWELS:
        return False
    if ch == "y":
        return i == 0 or not _is_consonant(word, i - 1)
    return True


def _measure(stem: str) -> int:
    """Count the vowel-then-consonant groups in the stem (Porter's 'm')."""
    shape = ""
    for i in range(len(stem)):
        letter = "c" if _is_consonant(stem, i) else "v"
        if not shape or shape[-1] != letter:
            shape += letter
    return shape.count("vc")


def _has_vowel(stem: str) -> bool:
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _ends_double_consonant(word: str) -> bool:
    return len(word) >= 2 and word[-1] == word[-2] and _is_consonant(word, len(word) - 1)


def _ends_cvc(word: str) -> bool:
    if len(word) < 3:
        return False
    return (
        _is_consonant(word, len(word) - 3)
        and not _is_consonant(word, len(word) - 2)
        and _is_consonant(word, len(word) - 1)
        and word[-1] not in "wxy"
    )


def _replace(word: str, suffix: str, replacement: str, min_measure: int) -> Tuple[str, bool]:
    """If `word` ends with `suffix`, return (new word, True) when the rule applies."""
    stem = word[: len(word) - len(suffix)]
    if _measure(stem) > min_measure:
        return stem + replacement, True
    return word, True  # suffix matched but the rule did not apply: stop searching


_STEP2 = [
    ("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"), ("izer", "ize"),
    ("abli", "able"), ("alli", "al"), ("entli", "ent"), ("eli", "e"), ("ousli", "ous"),
    ("ization", "ize"), ("ation", "ate"), ("ator", "ate"), ("alism", "al"), ("iveness", "ive"),
    ("fulness", "ful"), ("ousness", "ous"), ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"),
]
_STEP3 = [
    ("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"), ("ical", "ic"), ("ful", ""), ("ness", ""),
]
_STEP4 = [
    "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement", "ment", "ent", "ion",
    "ou", "ism", "ate", "iti", "ous", "ive", "ize",
]


def _apply_table(word: str, table: List[Tuple[str, str]]) -> str:
    for suffix, replacement in sorted(table, key=lambda pair: -len(pair[0])):
        if word.endswith(suffix):
            return _replace(word, suffix, replacement, 0)[0]
    return word


def stem(word: str) -> str:
    """Return the stem of one lower-case word. Words of 1-2 letters and digits are unchanged."""
    if len(word) <= 2 or word.isdigit() or not word.isalpha():
        return word
    w = word

    # Step 1a: plurals
    if w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ies"):
        w = w[:-2]
    elif w.endswith("ss"):
        pass
    elif w.endswith("s"):
        w = w[:-1]

    # Step 1b: -eed, -ed, -ing
    flag = False
    if w.endswith("eed"):
        if _measure(w[:-3]) > 0:
            w = w[:-1]
    elif w.endswith("ed") and _has_vowel(w[:-2]):
        w = w[:-2]
        flag = True
    elif w.endswith("ing") and _has_vowel(w[:-3]):
        w = w[:-3]
        flag = True
    if flag:
        if w.endswith(("at", "bl", "iz")):
            w += "e"
        elif _ends_double_consonant(w) and w[-1] not in "lsz":
            w = w[:-1]
        elif _measure(w) == 1 and _ends_cvc(w):
            w += "e"

    # Step 1c: y -> i
    if w.endswith("y") and _has_vowel(w[:-1]):
        w = w[:-1] + "i"

    # Steps 2 and 3
    w = _apply_table(w, _STEP2)
    w = _apply_table(w, _STEP3)

    # Step 4
    for suffix in sorted(_STEP4, key=lambda s: -len(s)):
        if w.endswith(suffix):
            base = w[: -len(suffix)]
            if _measure(base) > 1 and (suffix != "ion" or base.endswith(("s", "t"))):
                w = base
            break

    # Step 5a: final e
    if w.endswith("e"):
        base = w[:-1]
        measure = _measure(base)
        if measure > 1 or (measure == 1 and not _ends_cvc(base)):
            w = base
    # Step 5b: -ll
    if w.endswith("ll") and _measure(w) > 1:
        w = w[:-1]
    return w
