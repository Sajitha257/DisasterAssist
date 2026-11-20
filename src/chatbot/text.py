"""Word handling for retrieval: splitting text into words, stop words, and the
hand-written keyword tables used to recognise which disaster a question is about.

None of this changes the approved safety text. It only helps to search it.
"""

import re
import unicodedata
from typing import List

from src.chatbot.stemmer import stem

# Words that carry no search value. Words that point to a disaster or to
# Before/During/After are NOT stop words (see the tables below).
STOP_WORDS = frozenset("""
a about above am an and any are as at be been being both but by can could did do does doing done dont doesnt
cant isnt for from get got had has have having he her here hers him his how i if in into is it its just me
might more most my no nor not of off on once only or other our ours out over own same shall she should so
some such than that the their them then there these they this those through to too up us very was we were
what when where which who whom why will with would you your yours
please tell explain give want need know tips tip advice information info thing things something anything
kind sort really also let make much many like going
safety guide guides guideline guidelines guidance precaution precautions measure measures step steps
instruction instructions recommendation recommendations rule rules
""".split())

# Words that show which disaster a question is about (matched on the raw word).
DISASTER_KEYWORDS = {
    "flood": {"flood", "floods", "flooding", "flooded", "floodwater", "floodwaters"},
    "cyclone": {"cyclone", "cyclones", "cyclonic", "hurricane", "hurricanes", "typhoon", "typhoons"},
    "earthquake": {"earthquake", "earthquakes", "quake", "quakes", "tremor", "tremors", "seismic",
                   "aftershock", "aftershocks"},
    "landslide": {"landslide", "landslides", "mudslide", "mudslides", "landslip", "landslips",
                  "rockslide", "rockslides", "rockfall", "rockfalls"},
    "tsunami": {"tsunami", "tsunamis"},
    "fire": {"fire", "fires", "wildfire", "wildfires", "bushfire", "bushfires"},
}

# Two-word phrases that also name a disaster.
DISASTER_PHRASES = {
    ("tidal", "wave"): "tsunami",
    ("tidal", "waves"): "tsunami",
    ("debris", "flow"): "landslide",
    ("debris", "flows"): "landslide",
}

# Forest Fire is a subsection of Fire.
FOREST_FIRE_SINGLE_WORDS = {"wildfire", "wildfires", "bushfire", "bushfires"}
FOREST_FIRE_PHRASES = {("forest", "fire"), ("forest", "fires")}

# In "flooded roads" or "flood streets" the place word only says WHERE the flood is; it is not
# a separate topic to look up. Only these place words, and only after a flood word, are treated
# as part of the disaster phrase. (This is not a synonym list; it is deliberately tiny.)
FLOOD_PLACE_WORDS = {"road", "roads", "street", "streets"}

# Words that point to a part of a disaster page. Each maps to one canonical word.
SECTION_KEYWORDS = {
    "before": "before", "beforehand": "before", "prior": "before",
    "during": "during", "while": "during",
    "after": "after", "afterwards": "after", "aftermath": "after",
}

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def tokenize(text: str) -> List[str]:
    """Split text into lower-case words. Apostrophes are dropped ("don't" -> "dont")."""
    text = unicodedata.normalize("NFKC", text).lower().replace("\u2019", "'")
    words = []
    for raw in _WORD.findall(text):
        if raw.endswith("'s"):
            raw = raw[:-2]
        words.append(raw.replace("'", ""))
    return [w for w in words if w]


def normalise(word: str) -> str:
    """The form of a word used for matching (its stem)."""
    return stem(word)


def index_tokens(text: str) -> List[str]:
    """All words of a text in matching form, with nothing removed (used for documents)."""
    return [normalise(w) for w in tokenize(text)]
