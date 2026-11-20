"""The Disaster Information Chatbot tab (Feature 2).

Stage 5: by default the chatbot is the bounded Agentic RAG workflow (src/chatbot/agent/).
It returns the same ChatAnswer as the Stage 4 AnswerService, so nothing below changed.

The chatbot is built once when the website starts. If the approved data fails
verification, an error panel is shown instead. The Emergency Safety Guide tab
does not use anything from this file or from the AI provider.

UI update: clickable example questions, a visible "working" indicator while the
answer is prepared, a Clear chat button, and clearer answer, error and refusal
panels. The answering code (AnswerService / AgentService) is not touched.
"""

import logging
import sys
from pathlib import Path
from typing import Callable, Optional

import gradio as gr

from src.chatbot import answer as ans
from src.chatbot.answer import AnswerService
from src.chatbot.answer_html import render_answer
from src.chatbot.query import MAX_QUERY_CHARS
from src.chatbot.agent.factory import build_agent_service
from src.guide import expected as ex
from src.guide.render import esc, render_error_panel

log = logging.getLogger("disasterassist.ui")
CHATBOT_CSS_FILE = Path(__file__).with_name("chatbot.css")

TITLE_TEXT = "## Disaster Information Chatbot"
INTRO_TEXT = (
    "Ask a question about flood, cyclone, earthquake, landslide, tsunami or fire. "
    "Answers come only from the approved Emergency Safety Guide and are shown exactly as approved."
)
ABOUT_TEXT = (
    "Answers come only from the approved Emergency Safety Guide and are shown exactly as approved. "
    "An AI model only helps to choose which approved instructions fit your question.\n\n"
    "The chatbot needs an internet connection and a Gemini API key. "
    "The Emergency Safety Guide works without them."
)
EXAMPLES = [
    "What should I do during an earthquake?",
    "How do I prepare an emergency bag?",
    "What to do after a flood?",
    "How can I prepare for a cyclone?",
    "What should I do if there is a tsunami warning?",
]
GENERIC_ERROR = "Something went wrong while answering. The Emergency Safety Guide is still available."

EMPTY_STATE = (
    '<div class="da-chat-empty" data-kind="empty"><p>Your answer will appear here.</p>'
    "<p>Type a question above or choose an example.</p></div>"
)
LOADING_HTML = (
    '<div class="da-chat-loading" role="status" aria-live="polite" data-kind="loading">'
    '<span class="da-spinner" aria-hidden="true"></span>'
    "<span><strong>Gemini is working on your question.</strong> "
    "It searches the approved guide first, so this can take a little while.</span></div>"
)


def _question_bubble(text: object) -> str:
    """Shows the question that is being answered (nothing for an empty question)."""
    if not isinstance(text, str) or not text.strip():
        return ""
    return ('<div class="da-chat-question"><span class="da-chat-who">You asked</span>'
            '<p class="da-chat-q-text">%s</p></div>' % esc(text.strip()))


def _safe_answer(service: AnswerService, question: str) -> str:
    try:
        return render_answer(service.ask(question))
    except Exception as error:                       # never show a traceback; never log the question
        log.error("Chatbot failed: %s", type(error).__name__)
        return render_answer(ans.ChatAnswer(ans.KIND_UNAVAILABLE, GENERIC_ERROR, error_code=ans.base.UNKNOWN))


def _example_setter(example: str) -> Callable[[], str]:
    def use_example() -> str:
        return example

    return use_example


def build_chatbot_tab(service_builder: Callable[[], Optional[AnswerService]] = build_agent_service) -> None:
    """Fill the current Gradio tab with the chatbot. Call inside `with gr.Tab(...)`."""
    try:
        service = service_builder()
    except Exception as error:                       # a chatbot problem must never stop the Safety Guide
        log.error("Chatbot could not start: %s", type(error).__name__)
        print("Chatbot NOT started: %s" % type(error).__name__, file=sys.stderr)
        service = None
    if service is None:
        gr.HTML(render_error_panel().replace("Emergency Safety Guide unavailable", "Chatbot unavailable")
                .replace("no safety information is shown", "no answers are shown"), elem_classes=["da-guide-page"])
        return

    gr.Markdown(TITLE_TEXT, elem_classes=["da-page-title"])
    gr.Markdown(INTRO_TEXT, elem_classes=["da-chat-intro"])
    gr.Markdown("**Emergency number: %s**" % ex.APPROVED_EMERGENCY_NUMBER, elem_classes=["da-emergency-strip"])

    gr.Markdown("**Try an example**", elem_classes=["da-example-label"])
    with gr.Row(elem_classes=["da-chips-row"]):
        example_buttons = [gr.Button(text, size="sm", variant="secondary", elem_classes=["da-example"])
                           for text in EXAMPLES]

    question = gr.Textbox(label="Your question", placeholder="Type your question here", lines=2,
                          max_length=MAX_QUERY_CHARS, elem_classes=["da-question"])
    with gr.Row(elem_classes=["da-actions"]):
        ask = gr.Button("Ask", variant="primary", scale=3, elem_classes=["da-btn-main"])
        clear = gr.Button("Clear chat", variant="secondary", scale=1)
    output = gr.HTML(EMPTY_STATE, elem_classes=["da-guide-page", "da-chat-output"], padding=False)

    with gr.Accordion("About this chatbot", open=False, elem_classes=["da-about-chat"]):
        gr.Markdown(ABOUT_TEXT)

    def thinking(text: str) -> str:
        """Step 1 (instant): show the question and the working indicator."""
        if not isinstance(text, str) or not text.strip():
            return ""
        return _question_bubble(text) + LOADING_HTML

    def respond(text: str) -> str:
        """Step 2: the answer (or the clear error / refusal message) replaces the indicator."""
        return _question_bubble(text) + _safe_answer(service, text)

    def reset_chat():
        return "", EMPTY_STATE

    def run(first_event):
        first_event.then(respond, inputs=question, outputs=output, api_name=False, show_progress="hidden")

    run(ask.click(thinking, inputs=question, outputs=output, api_name=False, queue=False, show_progress="hidden"))
    run(question.submit(thinking, inputs=question, outputs=output, api_name=False, queue=False,
                        show_progress="hidden"))
    for example, button in zip(EXAMPLES, example_buttons):
        chosen = button.click(_example_setter(example), inputs=None, outputs=question, api_name=False, queue=False)
        run(chosen.then(thinking, inputs=question, outputs=output, api_name=False, queue=False,
                        show_progress="hidden"))
    clear.click(reset_chat, inputs=None, outputs=[question, output], api_name=False, queue=False)
