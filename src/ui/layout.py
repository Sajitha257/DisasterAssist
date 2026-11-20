"""Builds the DisasterAssist AI website page.

Home (title, short description and two feature cards), the Emergency Safety Guide
(Feature 1) and the Disaster Information Chatbot (Feature 2).

UI update: the Home "Status" text was removed. Home now has two clear feature cards
whose buttons open the matching section. The three tabs at the top stay available
on every page.
"""

from pathlib import Path
from typing import Callable, Optional

import gradio as gr

from src.guide.loader import ApprovedData, load_approved_data
from src.ui.guide_tab import build_guide_tab

APP_TITLE = "DisasterAssist AI"
CSS_FILE = Path(__file__).with_name("styles.css")

TAB_HOME = "home"
TAB_GUIDE = "guide"
TAB_CHATBOT = "chatbot"

HOME_HERO = """
# DisasterAssist AI

Approved safety information for flood, cyclone, earthquake, landslide, tsunami and fire,
in one simple website. Choose a section below to begin.
"""

GUIDE_CARD = """
### Emergency Safety Guide

Browse approved instructions for each disaster, organised as Before, During, After and
Common Preparedness, with every caveat and source note shown next to its instruction.
"""

CHATBOT_CARD = """
### Disaster Information Chatbot

Ask a question in your own words. Answers come only from the approved guide and are
shown exactly as approved.
"""

HOME_HINT = "You can also use the tabs at the top of the page to move between sections."

PLACEHOLDER_CHATBOT = (
    "### Disaster Information Chatbot\n\n"
    "This section is under construction. The chatbot is not available yet."
)


def _open_tab(tab_id: str) -> Callable[[], gr.Tabs]:
    def open_section() -> gr.Tabs:
        return gr.Tabs(selected=tab_id)

    return open_section


def _build_home(main_tabs: gr.Tabs) -> None:
    gr.Markdown(HOME_HERO, elem_classes=["da-hero"])
    with gr.Row(elem_classes=["da-grid", "da-feature-grid"]):
        with gr.Column(elem_classes=["da-feature"]):
            gr.Markdown(GUIDE_CARD)
            open_guide = gr.Button("Open the Safety Guide", variant="primary", elem_classes=["da-btn-main"])
        with gr.Column(elem_classes=["da-feature"]):
            gr.Markdown(CHATBOT_CARD)
            open_chatbot = gr.Button("Open the Chatbot", variant="primary", elem_classes=["da-btn-main"])
    gr.Markdown(HOME_HINT, elem_classes=["da-hint"])
    open_guide.click(_open_tab(TAB_GUIDE), inputs=None, outputs=main_tabs, api_name=False, queue=False)
    open_chatbot.click(_open_tab(TAB_CHATBOT), inputs=None, outputs=main_tabs, api_name=False, queue=False)


def build_app(load: Callable[[], ApprovedData] = load_approved_data,
              chatbot_tab: Optional[Callable[[], None]] = None) -> gr.Blocks:
    """Create the Gradio page. Nothing runs until app.launch() is called.

    `chatbot_tab` (Stage 4) fills the chatbot tab. Without it the Stage 2 placeholder is shown.
    """
    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as app:
        with gr.Tabs(selected=TAB_HOME, elem_id="da-main-tabs") as main_tabs:
            with gr.Tab("Home", id=TAB_HOME):
                _build_home(main_tabs)
            with gr.Tab("Emergency Safety Guide", id=TAB_GUIDE):
                build_guide_tab(load)
            with gr.Tab("Disaster Information Chatbot", id=TAB_CHATBOT):
                if chatbot_tab is None:
                    gr.Markdown(PLACEHOLDER_CHATBOT)
                else:
                    chatbot_tab()
    return app
