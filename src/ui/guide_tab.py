"""The Emergency Safety Guide tab (Feature 1).

The six disaster pages are built once, when the website starts, from the
verified approved data. If the data cannot be verified, an error message is
shown instead and NO safety content is displayed.

UI update: the disasters are chosen with six selection cards. The cards only
switch which page is shown; all six pages are built exactly as before.
"""

import sys
from typing import Callable, List

import gradio as gr

from src.guide import expected as ex
from src.guide.loader import ApprovedData, ApprovedDataError, load_approved_data
from src.guide.render import GuideRenderError, render_all_pages, render_error_panel

GUIDE_TITLE = "## Emergency Safety Guide\n\nChoose a disaster to see its approved instructions."

# Card label (icon, name) and a short line of what the page contains.
CARD_ICONS = {"flood": "\U0001F4A7", "cyclone": "\U0001F300", "earthquake": "\U0001F3DA️",
              "landslide": "⛰️", "tsunami": "\U0001F30A", "fire": "\U0001F525"}
CARD_NOTES = {
    "flood": "Before · During · After",
    "cyclone": "Before · During · After",
    "earthquake": "Before · During · After",
    "landslide": "Before · During · After",
    "tsunami": "Includes bulletin levels",
    "fire": "Includes Forest Fire",
}


def _card_label(disaster_id: str) -> str:
    return "%s %s\n%s" % (CARD_ICONS[disaster_id], ex.DISASTER_NAMES[disaster_id], CARD_NOTES[disaster_id])


def _selector(target: str) -> Callable[[], list]:
    """Returns what the page should do when the card `target` is clicked."""

    def select_category() -> list:
        updates: List[object] = [gr.Tabs(selected=target)]
        for disaster_id in ex.DISASTER_ORDER:
            updates.append(gr.Button(variant="primary" if disaster_id == target else "secondary"))
        return updates

    return select_category


def build_guide_tab(load: Callable[[], ApprovedData] = load_approved_data) -> None:
    """Fill the current Gradio tab with the guide. Call inside `with gr.Tab(...)`."""
    try:
        approved = load()
        pages = render_all_pages(approved.disasters)
    except ApprovedDataError as error:
        print("Safety Guide NOT shown: approved data failed verification.", file=sys.stderr)
        for problem in error.problems:
            print("  - " + problem, file=sys.stderr)
        gr.HTML(render_error_panel(), elem_classes=["da-guide-page"])
        return
    except GuideRenderError as error:
        print("Safety Guide NOT shown: %s" % error, file=sys.stderr)
        gr.HTML(render_error_panel(), elem_classes=["da-guide-page"])
        return

    gr.Markdown(GUIDE_TITLE, elem_classes=["da-page-title"])
    first = ex.DISASTER_ORDER[0]
    cards = []
    with gr.Row(elem_classes=["da-grid", "da-cat-grid"]):
        for disaster_id in ex.DISASTER_ORDER:
            cards.append(gr.Button(_card_label(disaster_id),
                                   variant="primary" if disaster_id == first else "secondary",
                                   elem_classes=["da-cat-card"]))
    # The tab bar of this inner group is hidden by the stylesheet: the cards above replace it.
    with gr.Tabs(selected=first, elem_id="da-cat-tabs") as category_tabs:
        for disaster_id in ex.DISASTER_ORDER:
            with gr.Tab(ex.DISASTER_NAMES[disaster_id], id=disaster_id):
                gr.HTML(pages[disaster_id], elem_classes=["da-guide-page"], padding=False)
    for disaster_id, card in zip(ex.DISASTER_ORDER, cards):
        card.click(_selector(disaster_id), inputs=None, outputs=[category_tabs] + cards,
                   api_name=False, queue=False)
