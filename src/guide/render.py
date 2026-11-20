"""Turns the validated approved data into HTML for the Emergency Safety Guide.

Rules this file follows (all approved by the project owner):

* Instruction text, caveats, limitations and conflicts are shown EXACTLY as
  stored in the JSON files. They are only HTML-escaped so that special
  characters display safely. Nothing is rewritten, shortened or reordered.
* Every item still carries its ID and its source tags. They are kept in the
  page, but the main card shows only the approved wording; the ID and tags are
  inside an optional "View Source Details" part at the end of the card.
  (Caveats, S2* notes, scope notes and conflict links are NEVER inside it.)
* An item's own caveat is shown inside the same card, straight after the text.
  The FIRE-D-013 caveat is never placed in a collapsible part.
* The S2* attribution note is fetched from the source register at display
  time and attached to every S2*-tagged instruction (in addition to the
  item's own caveat, if it has one).
* Known conflicts are shown in a visible panel, and the items that belong to
  a conflict link to it.
* The long project notice is no longer shown at the top of the page. A compact
  "Emergency number" and "No live alerts" strip is shown instead, and the full
  approved notice is kept, word for word, in "About the Sources".
* Limitations are shown where the approved classification says (see
  limitations.py). Research-process notes go under "About the Sources".
* Excluded guidance is NEVER shown.

The renderer refuses to produce a page (it raises GuideRenderError) if any
instruction, limitation or conflict would be left out, so nothing can be
hidden by accident.
"""

import html
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from src.guide import expected as ex
from src.guide import limitations as lim

# Sources whose attribution note must be attached to every tagged instruction.
ATTRIBUTION_NOTE_LABELS: Tuple[str, ...] = ("S2*",)


def _is_s2_star(tags: Sequence[str]) -> bool:
    return "S2*" in tags


def _is_delhi_govt(tags: Sequence[str]) -> bool:
    return any("Delhi Govt" in tag for tag in tags)


# "Source scope" limitations are shown on each instruction they qualify.
SOURCE_SCOPE_RULES: Dict[str, Callable[[Sequence[str]], bool]] = {
    "TSUNAMI-L-002": _is_s2_star,   # every S2*-tagged tsunami instruction
    "FIRE-L-001": _is_delhi_govt,   # every Delhi Govt-tagged fire instruction
}

# Which cards belong to which preserved conflict (they link to the conflict).
CONFLICT_CARD_LINKS: Dict[str, Tuple[str, ...]] = {
    "FLOOD-CF-001": ("FLOOD-B-006", "C6"),
    "CYCLONE-CF-001": ("CYCLONE-B-013", "C6"),
    "EARTHQUAKE-CF-001": ("EARTHQUAKE-D-007", "EARTHQUAKE-A-006", "C5"),
}

SECTION_TITLES = {"before": "Before", "during": "During", "after": "After"}
COMMON_TITLE = "Common Preparedness"
SOURCE_DETAILS_LABEL = "View Source Details"
NO_ALERTS_LABEL = "No live alerts"
GROUP_TITLES = {
    "prevention": "Prevention",
    "preparation": "Preparation",
    "emergency_evacuation": "Emergency evacuation",
    "after": "After",
    "bulletin_levels": "Bulletin levels",
}
KIND_LABELS = {
    lim.KIND_GAP: "Known gap",
    lim.KIND_SCOPE: "Source scope note",
    lim.KIND_PROCESS: "Research note",
}


class GuideRenderError(Exception):
    """Raised when the guide cannot be shown completely and safely."""


def esc(value: str) -> str:
    """Make text safe to place inside HTML (keeps the characters unchanged)."""
    return html.escape(value, quote=True)


class _PageContext:
    """Collects what was displayed so that omissions can be detected."""

    def __init__(self, disaster_id: str, data: dict):
        self.disaster_id = disaster_id
        self.data = data
        self.source_map: Dict[str, dict] = {s["display_label"]: s for s in data["source_references"]}
        self.rules = lim.rules_by_id()
        self.limitations_by_id: Dict[str, dict] = {l["limitation_id"]: l for l in data["limitations"]}
        self.shown_items: Set[str] = set()
        self.shown_limitations: Set[str] = set()
        self.shown_conflicts: Set[str] = set()
        # conflict link map for this page: card id -> conflict id
        self.card_conflicts: Dict[str, str] = {}
        for conflict in data["known_conflicts"]:
            for card_id in CONFLICT_CARD_LINKS.get(conflict["conflict_id"], ()):
                self.card_conflicts[card_id] = conflict["conflict_id"]

    def dom_id(self, *parts: str) -> str:
        return "-".join((self.disaster_id,) + parts)

    def limitations_at(self, placement: str) -> List[dict]:
        return [
            self.limitations_by_id[rule_id]
            for rule_id in self.limitations_by_id
            if self.rules[rule_id].placement == placement
        ]


def attribution_notes_for(item: dict, source_map: Dict[str, dict]) -> List[Tuple[str, str]]:
    """Return (label, note) pairs to attach to this instruction.

    Today only S2* needs this. The note is read from the source register at
    display time. The JSON files are never changed.
    """
    notes: List[Tuple[str, str]] = []
    for label in ATTRIBUTION_NOTE_LABELS:
        if label in item["source_tags"]:
            source = source_map.get(label)
            note = source["attribution_note"] if source else None
            if not note:
                raise GuideRenderError("%s is tagged %s but the source has no attribution note" % (item["instruction_id"], label))
            notes.append((label, note))
    return notes


def _tags_html(tags: Sequence[str]) -> str:
    if not tags:
        return '<span class="da-notags">No source tag listed in the approved data</span>'
    pills = "".join('<li class="da-tag">%s</li>' % esc(tag) for tag in tags)
    return '<ul class="da-tags" aria-label="Source tags">%s</ul>' % pills


def _count_html(count: int) -> str:
    return '<span class="da-count">%d instruction%s</span>' % (count, "" if count == 1 else "s")


def source_details_html(item_id: str, tags: Sequence[str]) -> str:
    """The optional technical part of a card: instruction ID and source tags (nothing else)."""
    tag_part = _tags_html(tags) if tags else '<span class="da-source-none">None listed in the approved data</span>'
    return (
        '<details class="da-source-details"><summary>%s</summary>'
        '<div class="da-source-body">'
        '<p class="da-source-line"><span class="da-label">Instruction ID</span><span class="da-id">%s</span></p>'
        '<div class="da-source-line"><span class="da-label">Source tags</span>%s</div>'
        '</div></details>'
    ) % (esc(SOURCE_DETAILS_LABEL), esc(item_id), tag_part)


def _note_html(css_kind: str, kind: str, label: str, text: str, extra: str = "", attrs: str = "") -> str:
    return (
        '<div class="da-note %s" data-kind="%s"%s><span class="da-label">%s</span>%s'
        '<span class="da-note-text">%s</span></div>'
    ) % (css_kind, kind, attrs, esc(label), extra, esc(text))


def _render_card(ctx: _PageContext, item: dict) -> str:
    item_id = item["instruction_id"]
    ctx.shown_items.add(item_id)
    parts = [
        '<article class="da-card" id="%s" data-item-id="%s">' % (esc(ctx.dom_id(item_id)), esc(item_id)),
        '<p class="da-text">%s</p>' % esc(item["text"]),
    ]

    caveat = item["caveat"]
    if item_id == ex.FIRE_D_013_ID:
        if not caveat:
            raise GuideRenderError("%s must be shown with its caveat" % item_id)
        parts.append(_note_html("da-caveat da-critical", "caveat", "Important caveat", caveat, attrs=' data-critical="true"'))
    elif caveat:
        parts.append(_note_html("da-caveat", "caveat", "Caveat", caveat))

    for label, note in attribution_notes_for(item, ctx.source_map):
        parts.append(_note_html("da-attrib", "source-note", "Source note (%s)" % label, note, attrs=' data-source="%s"' % esc(label)))

    for limitation_id, applies in SOURCE_SCOPE_RULES.items():
        limitation = ctx.limitations_by_id.get(limitation_id)
        if limitation is not None and applies(item["source_tags"]):
            ctx.shown_limitations.add(limitation_id)
            parts.append(
                _note_html(
                    "da-scope", "scope-note", KIND_LABELS[lim.KIND_SCOPE], limitation["text"],
                    extra='<span class="da-ref">%s</span>' % esc(limitation_id),
                    attrs=' data-limitation-id="%s"' % esc(limitation_id),
                )
            )

    conflict_id = ctx.card_conflicts.get(item_id)
    if conflict_id:
        parts.append(
            '<div class="da-note da-conflict-link" data-kind="conflict-link" data-conflict-id="%s">'
            '<span class="da-label">Known conflict</span>'
            '<a href="#%s">See %s in Known conflicts</a></div>'
            % (esc(conflict_id), esc(ctx.dom_id("conflicts")), esc(conflict_id))
        )
    if not item["source_tags"]:
        # An instruction without a source tag is said so openly, outside the optional details.
        parts.append('<p class="da-notags">No source tag listed in the approved data</p>')
    parts.append(source_details_html(item_id, item["source_tags"]))
    parts.append("</article>")
    return "".join(parts)


def _render_limitation_panel(ctx: _PageContext, limitation: dict, where: str) -> str:
    """A visible panel for a gap or scope note, shown with the content it qualifies."""
    limitation_id = limitation["limitation_id"]
    rule = ctx.rules[limitation_id]
    ctx.shown_limitations.add(limitation_id)
    css = "da-gap" if rule.kind == lim.KIND_GAP else "da-scope-panel"
    if rule.kind == lim.KIND_PROCESS:
        css = "da-research"
    return (
        '<aside class="da-panel %s" data-kind="limitation" data-limitation-id="%s" data-where="%s">'
        '<div class="da-panel-head"><span class="da-label">%s</span><span class="da-ref">%s</span>%s</div>'
        '<p class="da-text">%s</p></aside>'
    ) % (
        css, esc(limitation_id), esc(where), esc(KIND_LABELS[rule.kind]), esc(limitation_id),
        _tags_html(limitation["source_tags"]) if limitation["source_tags"] else "", esc(limitation["text"]),
    )


def _placement_panels(ctx: _PageContext, placement: str, where: str) -> str:
    return "".join(_render_limitation_panel(ctx, l, where) for l in ctx.limitations_at(placement))


def _section(ctx: _PageContext, section_id: str, title: str, body: str, data_attr: str, count: int = 0) -> str:
    return (
        '<section class="da-section" id="%s" %s><div class="da-sec-head"><h3 class="da-h3">%s</h3>%s</div>%s</section>'
        % (esc(ctx.dom_id(section_id)), data_attr, esc(title), _count_html(count) if count else "", body)
    )


def _render_main_section(ctx: _PageContext, name: str) -> str:
    body = ""
    if name == "before":
        body += _placement_panels(ctx, "before_and_after", "before")
        body += _placement_panels(ctx, "before", "before")
    if name == "after":
        body += _placement_panels(ctx, "before_and_after", "after")
        body += _placement_panels(ctx, "after", "after")
    body += "".join(_render_card(ctx, item) for item in ctx.data["sections"][name])
    return _section(ctx, "sec-" + name, SECTION_TITLES[name], body, 'data-section="%s"' % name,
                    len(ctx.data["sections"][name]))


def _render_common(ctx: _PageContext) -> str:
    body = ""
    for item in ctx.data["common_preparedness"]:
        body += _render_card(ctx, item)
        if item["instruction_id"] == "C7":
            body += _placement_panels(ctx, "first_aid", "first_aid")
    return _section(ctx, "sec-common", COMMON_TITLE, body, 'data-section="common"',
                    len(ctx.data["common_preparedness"]))


def _render_subsection(ctx: _PageContext, sub: dict) -> str:
    body = '<p class="da-desc">%s</p>' % esc(sub["description"])
    if ctx.disaster_id == "tsunami":
        body += _placement_panels(ctx, "bulletin_levels", "bulletin_levels")
    for group, items in sub["sections"].items():
        group_body = ""
        if ctx.disaster_id == "fire" and group == "after":
            group_body += _placement_panels(ctx, "forest_fire_after", "forest_fire_after")
        group_body += "".join(_render_card(ctx, item) for item in items)
        body += (
            '<div class="da-group" data-group="%s"><h4 class="da-h4">%s</h4>%s</div>'
            % (esc(group), esc(GROUP_TITLES[group]), group_body)
        )
    total = sum(len(items) for items in sub["sections"].values())
    return (
        '<section class="da-section da-subsection" id="%s" data-subsection="%s">'
        '<div class="da-sec-head"><h3 class="da-h3">%s</h3>%s</div>%s</section>'
        % (esc(ctx.dom_id("sec-" + sub["subsection_id"])), esc(sub["subsection_id"]), esc(sub["subsection_name"]),
           _count_html(total), body)
    )


def _render_conflicts(ctx: _PageContext) -> str:
    conflicts = ctx.data["known_conflicts"]
    if not conflicts:
        return ""
    body = ""
    for conflict in conflicts:
        ctx.shown_conflicts.add(conflict["conflict_id"])
        body += (
            '<aside class="da-panel da-conflict" data-kind="conflict" data-conflict-id="%s">'
            '<div class="da-panel-head"><span class="da-label">Known conflict</span><span class="da-ref">%s</span>%s</div>'
            '<p class="da-text">%s</p></aside>'
        ) % (esc(conflict["conflict_id"]), esc(conflict["conflict_id"]), _tags_html(conflict["source_tags"]), esc(conflict["text"]))
    return (
        '<section class="da-section da-conflicts" id="%s" data-section="conflicts">'
        '<div class="da-sec-head"><h3 class="da-h3">Known conflicts</h3></div>%s</section>'
        % (esc(ctx.dom_id("conflicts")), body)
    )


def _render_about(ctx: _PageContext) -> str:
    notice = (
        '<h4 class="da-h4">About this guide</h4>'
        '<p class="da-project-notice">%s</p>' % esc(ctx.data["project_notice"])
    )
    research = ""
    for limitation in ctx.limitations_by_id.values():
        if ctx.rules[limitation["limitation_id"]].placement == "about_sources":
            panel = _render_limitation_panel(ctx, limitation, "about_sources")
            research += panel.replace(
                '<aside class="da-panel',
                '<aside id="%s" class="da-panel' % esc(ctx.dom_id("about", limitation["limitation_id"])), 1,
            )
    register = ""
    for source in ctx.data["source_references"]:
        note = source["attribution_note"]
        register += (
            '<div class="da-source" data-source-label="%s">'
            '<p class="da-source-title"><span class="da-tag">%s</span> %s</p>'
            '<p class="da-source-line">%s</p>'
            '<p class="da-source-line"><a href="%s" target="_blank" rel="noopener noreferrer">%s</a></p>'
            '<p class="da-source-line"><span class="da-label">Evidence</span>%s</p>%s</div>'
        ) % (
            esc(source["display_label"]), esc(source["display_label"]), esc(source["title"]),
            esc(source["organisation"]), esc(source["url"]), esc(source["url"]), esc(source["evidence_status"]),
            ('<p class="da-source-line" data-kind="attribution-note"><span class="da-label">Attribution note</span>%s</p>' % esc(note)) if note else "",
        )
    return (
        '<details class="da-about" id="%s"><summary>About the Sources</summary>%s'
        '<h4 class="da-h4">Research notes</h4>%s<h4 class="da-h4">Source register</h4>%s</details>'
        % (esc(ctx.dom_id("about")), notice, research, register)
    )


def render_disaster_page(disaster_id: str, data: dict) -> str:
    """Return the complete HTML page for one disaster.

    Raises GuideRenderError if anything would be left out.
    """
    ctx = _PageContext(disaster_id, data)

    nav_links = [("sec-before", "Before"), ("sec-during", "During"), ("sec-after", "After"), ("sec-common", COMMON_TITLE)]
    for sub in data["subsections"]:
        nav_links.append(("sec-" + sub["subsection_id"], sub["subsection_name"] if disaster_id == "fire" else "Bulletin levels"))
    if data["known_conflicts"]:
        nav_links.insert(0, ("conflicts", "Known conflicts"))
    nav_links.append(("about", "About the Sources"))
    nav = "".join(
        '<li><a class="da-nav-link%s" href="#%s">%s</a></li>'
        % (" da-nav-warn" if target == "conflicts" else "", esc(ctx.dom_id(target)), esc(label))
        for target, label in nav_links
    )

    page = [
        '<div class="da-page" data-disaster="%s">' % esc(disaster_id),
        '<header class="da-page-head">'
        '<h2 class="da-h2">%s</h2>'
        '<div class="da-chips" aria-label="Emergency number and guide limits">'
        '<span class="da-chip da-chip-emergency"><span class="da-label">Emergency number</span><strong class="da-112">%s</strong></span>'
        '<a class="da-chip da-chip-link da-112-source" href="#%s">How is %s sourced? See About the Sources</a>'
        '<a class="da-chip da-chip-info" href="#%s">%s</a>'
        '</div></header>'
        % (esc(data["disaster_name"]), esc(data["emergency_number"]), esc(ctx.dom_id("about")),
           esc(data["emergency_number"]), esc(ctx.dom_id("about")), esc(NO_ALERTS_LABEL)),
        '<nav class="da-nav" aria-label="Sections on this page"><ul>%s</ul></nav>' % nav,
        _render_conflicts(ctx),
        _render_main_section(ctx, "before"),
        _render_main_section(ctx, "during"),
        _render_main_section(ctx, "after"),
        _render_common(ctx),
    ]
    for sub in data["subsections"]:
        page.append(_render_subsection(ctx, sub))
    page.append(_render_about(ctx))
    page.append("</div>")

    _check_nothing_left_out(ctx)
    return "".join(page)


def _check_nothing_left_out(ctx: _PageContext) -> None:
    """Fail loudly if an instruction, limitation or conflict was not displayed."""
    from src.guide.validator import iter_instructions

    expected_items = {item["instruction_id"] for _, item in iter_instructions(ctx.data)}
    if expected_items != ctx.shown_items:
        raise GuideRenderError("not displayed: %s" % sorted(expected_items - ctx.shown_items))
    missing = set(ctx.limitations_by_id) - ctx.shown_limitations
    if missing:
        raise GuideRenderError("limitations not displayed: %s" % sorted(missing))
    missing = {c["conflict_id"] for c in ctx.data["known_conflicts"]} - ctx.shown_conflicts
    if missing:
        raise GuideRenderError("conflicts not displayed: %s" % sorted(missing))


def render_all_pages(disasters: Dict[str, dict]) -> Dict[str, str]:
    """Return {disaster id: HTML page} for all six disasters, in display order."""
    return {d: render_disaster_page(d, disasters[d]) for d in ex.DISASTER_ORDER}


def render_error_panel() -> str:
    """Shown instead of the guide if the approved data cannot be verified."""
    return (
        '<div class="da-page da-error" role="alert" data-state="error">'
        "<h2 class=\"da-h2\">Emergency Safety Guide unavailable</h2>"
        "<p>The approved safety data could not be verified, so no safety information is shown. "
        "Please contact the project owner. Details are written in the terminal window.</p></div>"
    )
