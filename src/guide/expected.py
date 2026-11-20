
"""The approved structure of the six JSON files.

These facts were read from the six approved files (protected by the SHA-256
checksums) during Stage 1. The validator compares the files with these facts.
If you ever approve a change to a JSON file, these facts must be updated too.
"""

from typing import Dict, Tuple


# Display order of the six main categories. There is no seventh category.
DISASTER_ORDER: Tuple[str, ...] = (
    "flood",
    "cyclone",
    "earthquake",
    "landslide",
    "tsunami",
    "fire",
)

DISASTER_NAMES: Dict[str, str] = {
    "flood": "Flood",
    "cyclone": "Cyclone",
    "earthquake": "Earthquake",
    "landslide": "Landslide",
    "tsunami": "Tsunami",
    "fire": "Fire",
}

APPROVED_PROJECT_NOTICE = (
    "This guide does not replace official evacuation orders or emergency "
    "services. It cannot predict disasters and shows no live alerts."
)

APPROVED_EMERGENCY_NUMBER = "112"

TOP_LEVEL_KEYS = (
    "disaster_id",
    "disaster_name",
    "project_notice",
    "emergency_number",
    "sections",
    "subsections",
    "common_preparedness",
    "known_conflicts",
    "limitations",
    "excluded_guidance",
    "source_references",
)

SECTION_NAMES = ("before", "during", "after")


# Exact key sets of each kind of object.
INSTRUCTION_KEYS = ("instruction_id", "text", "source_tags", "caveat")
CONFLICT_KEYS = ("conflict_id", "text", "source_tags")
LIMITATION_KEYS = ("limitation_id", "text", "source_tags")
EXCLUSION_KEYS = ("exclusion_id", "text", "reason", "source_tags")

SOURCE_KEYS = (
    "source_id",
    "display_label",
    "title",
    "organisation",
    "url",
    "evidence_status",
    "attribution_note",
)

SUBSECTION_KEYS = (
    "subsection_id",
    "subsection_name",
    "description",
    "sections",
)


# Which letter each section's instruction IDs use.
# Example: FLOOD-B-001.
# Fire's During section also holds three FIRE-P-... items.
# FIRE-P-001 to FIRE-P-003.
SECTION_ID_LETTERS = {
    "before": ("B",),
    "during": ("D",),
    "after": ("A",),
}

EXTRA_LETTERS = {
    ("fire", "during"): ("P",),
}


# Approved number of items in each part of each file.
EXPECTED_COUNTS: Dict[str, Dict[str, int]] = {
    "flood": {
        "before": 9,
        "during": 16,
        "after": 8,
        "known_conflicts": 1,
        "limitations": 6,
        "excluded_guidance": 2,
        "source_references": 5,
    },
    "cyclone": {
        "before": 19,
        "during": 14,
        "after": 9,
        "known_conflicts": 1,
        "limitations": 6,
        "excluded_guidance": 4,
        "source_references": 6,
    },
    "earthquake": {
        "before": 13,
        "during": 13,
        "after": 14,
        "known_conflicts": 1,
        "limitations": 6,
        "excluded_guidance": 4,
        "source_references": 6,
    },
    "landslide": {
        "before": 9,
        "during": 5,
        "after": 8,
        "known_conflicts": 0,
        "limitations": 6,
        "excluded_guidance": 1,
        "source_references": 5,
    },
    "tsunami": {
        "before": 10,
        "during": 8,
        "after": 11,
        "known_conflicts": 0,
        "limitations": 10,
        "excluded_guidance": 3,
        "source_references": 7,
    },
    "fire": {
        "before": 30,
        "during": 26,
        "after": 9,
        "known_conflicts": 0,
        "limitations": 9,
        "excluded_guidance": 11,
        "source_references": 11,
    },
}


COMMON_PREPAREDNESS_IDS = (
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7",
    "C8",
)


# Subsections: only Fire (Forest Fire) and Tsunami (INCOIS bulletin levels).
# Each group is: name -> (ID stem, number of items).
SUBSECTION_EXPECTED = {
    "fire": {
        "subsection_id": "forest-fire",
        "subsection_name": "Forest Fire",
        "description_must_contain": "not a separate disaster category",
        "groups": {
            "prevention": ("FIRE-FF-PRV", 5),
            "preparation": ("FIRE-FF-PRP", 10),
            "emergency_evacuation": ("FIRE-FF-EVC", 10),
            "after": ("FIRE-FF-AFT", 2),
        },
    },
    "tsunami": {
        "subsection_id": "tsunami-incois-bulletin-levels",
        "subsection_name": "INCOIS bulletin levels - Official terminology",
        "description_must_contain": "Official terminology only",
        "groups": {
            "bulletin_levels": ("TSUNAMI-BL", 7),
        },
    },
}


# Only this instruction may have no source tag. It must have a caveat.
EMPTY_TAG_ALLOWED_IDS = ("FIRE-D-007",)


# FIRE-D-013 (wet-cloth door gap):
# its caveat must keep all four messages.
FIRE_D_013_ID = "FIRE-D-013"

FIRE_D_013_REQUIRED_PHRASES = (
    "only aims to slow smoke entering",
    "does not filter smoke",
    "does not make the room safe",
    "calling 112 and seeking rescue must not be delayed",
)


# Items whose caveat must point to the preserved conflicts.
CONFLICT_LINKED_ITEMS = (
    ("flood", "FLOOD-B-006"),
    ("cyclone", "CYCLONE-B-013"),
    ("earthquake", "EARTHQUAKE-D-007"),
    ("earthquake", "EARTHQUAKE-A-006"),
)


# The one source whose web address may differ between files
# (the register lists two addresses; earthquake.json shows one
# and fire.json shows the other).
SOURCE_URL_MAY_DIFFER = ("X1\u2020",)
