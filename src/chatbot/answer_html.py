"""Turns a ChatAnswer into HTML for the chatbot tab.

Instruction text, caveats, scope notes, conflicts and limitations are shown
EXACTLY as approved (only HTML-escaped). Same markup and style classes as the
Emergency Safety Guide cards, so the two sections look and behave alike.

UI update: the main card shows the approved wording, the disaster and section it
comes from, and every caveat/note. The instruction ID and source tags are kept in
the page inside an optional "View Source Details" part.
"""

from typing import Iterable, Sequence

from src.chatbot import answer as ans
from src.chatbot import models as m
from src.guide import expected as ex
from src.guide.render import KIND_LABELS, _note_html, esc, source_details_html

COMMON_LABEL = "Common Preparedness"
CROSS_FILED_TEXT = "Filed under another disaster, but its own text names the disaster you asked about."
FOOTER_TEXT = (
    "These are the approved instructions, shown exactly as written in the Emergency Safety Guide. "
    "The AI model only chose which approved instructions fit the question."
)


def _ids(note: m.ContextNote) -> str:
    return ", ".join((note.note_id,) + tuple(note.also_ids))


def _context_note(note: m.ContextNote) -> str:
    if note.kind == "conflict":
        return _note_html("da-conflict", "conflict", "Known conflict", note.text,
                          extra='<span class="da-ref">%s</span>' % esc(_ids(note)),
                          attrs=' data-conflict-id="%s"' % esc(note.note_id))
    label = KIND_LABELS.get(note.limitation_kind, "Limitation")
    css = "da-gap" if note.limitation_kind == "safety_gap" else "da-scope"
    return _note_html(css, "limitation", label, note.text,
                      extra='<span class="da-ref">%s</span>' % esc(_ids(note)),
                      attrs=' data-limitation-id="%s"' % esc(note.note_id))


def _card(item: m.RetrievedItem) -> str:
    # group_label already names the disaster and section, e.g. "Earthquake - During".
    where = COMMON_LABEL if item.disaster_id == "common" else item.group_label.replace(" - ", " \u00b7 ")
    parts = [
        '<article class="da-card" data-item-id="%s">' % esc(item.instruction_id),
        '<p class="da-where">%s</p>' % esc(where),
        '<p class="da-text">%s</p>' % esc(item.text),
    ]
    if item.cross_filed:
        parts.append(_note_html("da-scope", "cross-filed", "Note", CROSS_FILED_TEXT))
    if item.caveat:
        if item.instruction_id == ex.FIRE_D_013_ID:
            parts.append(_note_html("da-caveat da-critical", "caveat", "Important caveat", item.caveat,
                                    attrs=' data-critical="true"'))
        else:
            parts.append(_note_html("da-caveat", "caveat", "Caveat", item.caveat))
    for label, note in item.attribution_notes:
        parts.append(_note_html("da-attrib", "source-note", "Source note (%s)" % label, note,
                                attrs=' data-source="%s"' % esc(label)))
    parts.extend(_context_note(n) for n in item.notes)
    if not item.source_tags:
        parts.append('<p class="da-notags">No source tag listed in the approved data</p>')
    parts.append(source_details_html(item.instruction_id, item.source_tags))
    parts.append("</article>")
    return "".join(parts)


def _sources(items: Iterable[m.RetrievedItem]) -> str:
    seen, rows = set(), []
    for item in items:
        for s in item.sources:
            key = (s.label, s.title)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                '<div class="da-source" data-source-label="%s"><p class="da-source-title"><span class="da-tag">%s</span> %s</p>'
                '<p class="da-source-line">%s</p>'
                '<p class="da-source-line"><a href="%s" target="_blank" rel="noopener noreferrer">%s</a></p>'
                '<p class="da-source-line"><span class="da-label">Evidence</span>%s</p></div>'
                % (esc(s.label), esc(s.label), esc(s.title), esc(s.organisation), esc(s.url), esc(s.url), esc(s.evidence_status))
            )
    if not rows:
        return ""
    return '<details class="da-about"><summary>Sources for these instructions</summary>%s</details>' % "".join(rows)


# Visible heading and style for every kind of message that is not an answer.
_NOTICE_STYLE = {
    ans.KIND_ELECTRICITY: ("Electricity safety", "da-caveat da-critical da-alert-critical"),
    ans.KIND_WEATHER: ("This guide cannot answer that", "da-alert-refusal"),
    ans.KIND_NO_MATCH: ("No approved answer found", "da-alert-info"),
    ans.KIND_NOT_ANSWERABLE: ("No approved answer found", "da-alert-info"),
    ans.KIND_UNAVAILABLE: ("Something went wrong", "da-alert-error"),
    ans.KIND_EMPTY: ("Please type a question", "da-alert-info"),
}
_DEFAULT_NOTICE_STYLE = ("Notice", "da-alert-info")


def _notice(answer: ans.ChatAnswer) -> str:
    title, css = _NOTICE_STYLE.get(answer.kind, _DEFAULT_NOTICE_STYLE)
    role = "alert" if answer.kind in (ans.KIND_UNAVAILABLE, ans.KIND_ELECTRICITY) else "status"
    return ('<div class="da-chat-answer" data-kind="%s"><div class="da-note da-alert %s" role="%s" data-kind="notice">'
            '<span class="da-alert-title">%s</span><span class="da-note-text">%s</span></div></div>'
            % (esc(answer.kind), css, role, esc(title), esc(answer.message)))


def render_answer(answer: ans.ChatAnswer) -> str:
    if answer.kind != ans.KIND_ANSWER:
        return _notice(answer)
    count = len(answer.items)
    parts = ['<div class="da-chat-answer" data-kind="answer">',
             '<p class="da-answer-head">%d approved instruction%s</p>' % (count, "" if count == 1 else "s")]
    parts.extend(_card(i) for i in answer.items)
    for note in answer.related_notes:
        parts.append(_context_note(note))
    parts.append(_sources(answer.items))
    parts.append('<p class="da-footer">%s</p></div>' % esc(FOOTER_TEXT))
    return "".join(parts)
