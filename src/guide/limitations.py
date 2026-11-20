"""Classification of every limitation into exactly one category.

The JSON files have no field that says where a limitation should be shown, and
the JSON files must not be edited. So this hand-written table decides it.
It was approved by the project owner in principle (Stage 1 table is reviewed
before Stage 2 starts).

Two categories (as approved):

* CATEGORY_SECTION - genuine safety gaps and source-scope notes. These are
  shown clearly in the relevant section of the Safety Guide.
* CATEGORY_ABOUT   - repetitive research-process notes. These are shown under
  "About the Sources".

Every limitation in the six files must appear here exactly once. Automated
tests and the loader check this, so a new, removed or reworded limitation is
noticed immediately.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

CATEGORY_SECTION = "show_in_section"
CATEGORY_ABOUT = "about_the_sources"

KIND_GAP = "safety_gap"
KIND_SCOPE = "source_scope_note"
KIND_PROCESS = "research_process"

# Where a limitation is shown.
ALLOWED_PLACEMENTS = {
    CATEGORY_SECTION: (
        "before",
        "after",
        "before_and_after",
        "first_aid",
        "bulletin_levels",
        "forest_fire_after",
        "source_scope",
    ),
    CATEGORY_ABOUT: ("about_sources",),
}

PLACEMENT_MEANING = {
    "before": "Before section of the same disaster page",
    "after": "After section of the same disaster page",
    "before_and_after": "Both the Before and After sections of the same page",
    "first_aid": "Next to the common First aid item (C7)",
    "bulletin_levels": "With the Tsunami bulletin-levels subsection",
    "forest_fire_after": "With the Forest Fire After subsection",
    "source_scope": "With the items it qualifies (S2* or Delhi Govt items)",
    "about_sources": "About the Sources",
}

REASONS = {
    "gap_after_specific": "Missing guidance people would need after the event. Shown in the After section so the gap is not hidden.",
    "gap_landslide": "Missing landslide warning-product and recovery guidance. Shown in both Before and After sections.",
    "gap_first_aid": "Detailed first-aid steps are not available. Shown next to the First aid item (C7).",
    "gap_recovery_thin": "Recovery guidance is limited for every hazard. Shown in the After section.",
    "tsunami_scope": "Tells users which tsunami content is general guidance and which is official INCOIS terminology. Shown with the bulletin levels.",
    "tsunami_s2": "Attribution of FEMA-adapted S2* material. Shown with the S2* items (together with the S2* attribution note).",
    "tsunami_threat_passed": "'Threat Passed' is not defined in the approved data. Shown with the bulletin levels so no definition is assumed.",
    "tsunami_thresholds": "No numeric tsunami thresholds are approved. Shown with the bulletin levels.",
    "fire_delhi": "Explains that Delhi Govt items are not nationwide rules. Shown with those items.",
    "forest_after": "No further post-forest-fire guidance is verified. Shown with the Forest Fire After subsection.",
    "process_112": "Sourcing and evidence detail for the number 112. Research-process note.",
    "process_blocked": "Lists websites that could not be read during research. Research-process note.",
    "process_dates": "Explains that verification dates are not recorded per source. Research-process note.",
    "process_tn": "Records a source that was not found during research. Research-process note.",
}


@dataclass(frozen=True)
class LimitationRule:
    limitation_id: str
    category: str
    placement: str
    kind: str
    text_starts_with: str  # guard: detects if the approved wording ever changes
    reason_key: str

    @property
    def reason(self) -> str:
        return REASONS[self.reason_key]


def _rule(limitation_id, category, placement, kind, text_starts_with, reason_key):
    return LimitationRule(limitation_id, category, placement, kind, text_starts_with, reason_key)


LIMITATION_RULES: Tuple[LimitationRule, ...] = (
    _rule("FLOOD-L-001", CATEGORY_SECTION, "after", KIND_GAP, "Gap: no verified guidance on structural check", "gap_after_specific"),
    _rule("FLOOD-L-002", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Emergency number 112 is sourced to S4, X3† an", "process_112"),
    _rule("FLOOD-L-003", CATEGORY_SECTION, "first_aid", KIND_GAP, "Detailed first-aid steps are unavailable beca", "gap_first_aid"),
    _rule("FLOOD-L-004", CATEGORY_SECTION, "after", KIND_GAP, "Recovery guidance is thin for every hazard.", "gap_recovery_thin"),
    _rule("FLOOD-L-005", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "NDMA's site pages, SACHET guidance files, the", "process_blocked"),
    _rule("FLOOD-L-006", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Source verification dates are not recorded pe", "process_dates"),
    _rule("CYCLONE-L-001", CATEGORY_SECTION, "after", KIND_GAP, "Gap: no verified guidance on structural check", "gap_after_specific"),
    _rule("CYCLONE-L-002", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Emergency number 112 is sourced to S4, X3† an", "process_112"),
    _rule("CYCLONE-L-003", CATEGORY_SECTION, "first_aid", KIND_GAP, "Detailed first-aid steps are unavailable beca", "gap_first_aid"),
    _rule("CYCLONE-L-004", CATEGORY_SECTION, "after", KIND_GAP, "Recovery guidance is thin for every hazard.", "gap_recovery_thin"),
    _rule("CYCLONE-L-005", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "NDMA's site pages, SACHET guidance files, the", "process_blocked"),
    _rule("CYCLONE-L-006", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Source verification dates are not recorded pe", "process_dates"),
    _rule("EARTHQUAKE-L-001", CATEGORY_SECTION, "after", KIND_GAP, "Gap: it is not available how to judge whether", "gap_after_specific"),
    _rule("EARTHQUAKE-L-002", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Emergency number 112 is sourced to S4, X3† an", "process_112"),
    _rule("EARTHQUAKE-L-003", CATEGORY_SECTION, "first_aid", KIND_GAP, "Detailed first-aid steps are unavailable beca", "gap_first_aid"),
    _rule("EARTHQUAKE-L-004", CATEGORY_SECTION, "after", KIND_GAP, "Recovery guidance is thin for every hazard.", "gap_recovery_thin"),
    _rule("EARTHQUAKE-L-005", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "NDMA's site pages, SACHET guidance files, the", "process_blocked"),
    _rule("EARTHQUAKE-L-006", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Source verification dates are not recorded pe", "process_dates"),
    _rule("LANDSLIDE-L-001", CATEGORY_SECTION, "before_and_after", KIND_GAP, "Gap: landslide warning products and recovery ", "gap_landslide"),
    _rule("LANDSLIDE-L-002", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Emergency number 112 is sourced to S4, X3† an", "process_112"),
    _rule("LANDSLIDE-L-003", CATEGORY_SECTION, "first_aid", KIND_GAP, "Detailed first-aid steps are unavailable beca", "gap_first_aid"),
    _rule("LANDSLIDE-L-004", CATEGORY_SECTION, "after", KIND_GAP, "Recovery guidance is thin for every hazard.", "gap_recovery_thin"),
    _rule("LANDSLIDE-L-005", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "NDMA's site pages, SACHET guidance files, the", "process_blocked"),
    _rule("LANDSLIDE-L-006", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Source verification dates are not recorded pe", "process_dates"),
    _rule("TSUNAMI-L-001", CATEGORY_SECTION, "bulletin_levels", KIND_SCOPE, "Everything outside the INCOIS bulletin levels", "tsunami_scope"),
    _rule("TSUNAMI-L-002", CATEGORY_SECTION, "source_scope", KIND_SCOPE, "S2* tsunami guidance is FEMA-adapted NIDM mat", "tsunami_s2"),
    _rule("TSUNAMI-L-003", CATEGORY_SECTION, "bulletin_levels", KIND_GAP, "'Threat Passed' is not defined. The term appe", "tsunami_threat_passed"),
    _rule("TSUNAMI-L-004", CATEGORY_SECTION, "bulletin_levels", KIND_GAP, "No numeric thresholds are shown. Numeric tsun", "tsunami_thresholds"),
    _rule("TSUNAMI-L-005", CATEGORY_SECTION, "after", KIND_GAP, "Gap: recovery guidance beyond what is listed ", "gap_after_specific"),
    _rule("TSUNAMI-L-006", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Emergency number 112 is sourced to S4, X3† an", "process_112"),
    _rule("TSUNAMI-L-007", CATEGORY_SECTION, "first_aid", KIND_GAP, "Detailed first-aid steps are unavailable beca", "gap_first_aid"),
    _rule("TSUNAMI-L-008", CATEGORY_SECTION, "after", KIND_GAP, "Recovery guidance is thin for every hazard.", "gap_recovery_thin"),
    _rule("TSUNAMI-L-009", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "NDMA's site pages, SACHET guidance files, the", "process_blocked"),
    _rule("TSUNAMI-L-010", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Source verification dates are not recorded pe", "process_dates"),
    _rule("FIRE-L-001", CATEGORY_SECTION, "source_scope", KIND_SCOPE, "Items tagged Delhi Govt come from Delhi Fire ", "fire_delhi"),
    _rule("FIRE-L-002", CATEGORY_SECTION, "after", KIND_GAP, "Gap: no verified Indian official guidance on ", "gap_after_specific"),
    _rule("FIRE-L-003", CATEGORY_SECTION, "forest_fire_after", KIND_GAP, "Gap (Forest Fire): no other post-fire guidanc", "forest_after"),
    _rule("FIRE-L-004", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Tamil Nadu Forest Department public survival ", "process_tn"),
    _rule("FIRE-L-005", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Emergency number 112 is sourced to S4, X3† an", "process_112"),
    _rule("FIRE-L-006", CATEGORY_SECTION, "first_aid", KIND_GAP, "Detailed first-aid steps are unavailable beca", "gap_first_aid"),
    _rule("FIRE-L-007", CATEGORY_SECTION, "after", KIND_GAP, "Recovery guidance is thin for every hazard.", "gap_recovery_thin"),
    _rule("FIRE-L-008", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "NDMA's site pages, SACHET guidance files, the", "process_blocked"),
    _rule("FIRE-L-009", CATEGORY_ABOUT, "about_sources", KIND_PROCESS, "Source verification dates are not recorded pe", "process_dates"),
)


def rules_by_id() -> Dict[str, LimitationRule]:
    return {rule.limitation_id: rule for rule in LIMITATION_RULES}


def check_classification(all_data: Dict[str, dict]) -> List[str]:
    """Check that every limitation in the data is classified exactly once.

    Returns a list of problems (an empty list means everything is correct).
    """
    problems: List[str] = []

    # 1. The table itself: each ID once, valid category and placement.
    seen: Dict[str, int] = {}
    for rule in LIMITATION_RULES:
        seen[rule.limitation_id] = seen.get(rule.limitation_id, 0) + 1
        if rule.category not in ALLOWED_PLACEMENTS:
            problems.append("classification: %s has an unknown category %r" % (rule.limitation_id, rule.category))
        elif rule.placement not in ALLOWED_PLACEMENTS[rule.category]:
            problems.append(
                "classification: %s has placement %r, which is not allowed for category %r"
                % (rule.limitation_id, rule.placement, rule.category)
            )
        if rule.reason_key not in REASONS:
            problems.append("classification: %s has an unknown reason" % rule.limitation_id)
    for limitation_id, count in seen.items():
        if count > 1:
            problems.append("classification: %s is classified %d times (must be exactly once)" % (limitation_id, count))

    # 2. The data: every limitation has a rule and the wording has not changed.
    rules = rules_by_id()
    in_data: Dict[str, str] = {}
    for disaster_id, data in all_data.items():
        items = data.get("limitations", []) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("limitation_id"), str):
                in_data[item["limitation_id"]] = item.get("text", "")
    for limitation_id, text in in_data.items():
        rule = rules.get(limitation_id)
        if rule is None:
            problems.append("classification: %s has no classification (omitted)" % limitation_id)
        elif not str(text).startswith(rule.text_starts_with):
            problems.append(
                "classification: the wording of %s no longer matches the reviewed text" % limitation_id
            )
    for limitation_id in rules:
        if limitation_id not in in_data:
            problems.append("classification: %s is classified but does not exist in the data" % limitation_id)
    return problems


def render_markdown_table(all_data: Dict[str, dict], order: Tuple[str, ...]) -> str:
    """Return the complete classification table as Markdown text."""
    rules = rules_by_id()
    lines = [
        "# Limitations classification table",
        "",
        "Generated from `src/guide/limitations.py` and the approved JSON files.",
        "Every limitation appears exactly once.",
        "",
        "| Limitation ID | Category | Where shown | Kind | Approved text | Reason |",
        "|---|---|---|---|---|---|",
    ]
    totals = {CATEGORY_SECTION: 0, CATEGORY_ABOUT: 0}
    for disaster_id in order:
        for item in all_data[disaster_id]["limitations"]:
            rule = rules[item["limitation_id"]]
            totals[rule.category] += 1
            category_label = (
                "Show in section" if rule.category == CATEGORY_SECTION else "About the Sources"
            )
            text = item["text"].replace("|", "\\|")
            lines.append(
                "| %s | %s | %s | %s | %s | %s |"
                % (rule.limitation_id, category_label, PLACEMENT_MEANING[rule.placement], rule.kind, text, rule.reason)
            )
    lines += [
        "",
        "Totals: %d show in section, %d About the Sources, %d limitations in all."
        % (totals[CATEGORY_SECTION], totals[CATEGORY_ABOUT], sum(totals.values())),
        "",
    ]
    return "\n".join(lines)
