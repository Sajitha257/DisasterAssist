"""Starts the DisasterAssist AI website on your own computer.

Run this from the project folder:   python app.py
Then open this address in your browser:   http://127.0.0.1:7860
Press Ctrl+C in the terminal to stop the website.
"""

from src.config import load_environment
from src.ui.chatbot_tab import CHATBOT_CSS_FILE, build_chatbot_tab
from src.ui.layout import CSS_FILE, build_app


def main() -> None:
    load_environment()
    app = build_app(chatbot_tab=build_chatbot_tab)
    # 127.0.0.1 means "this computer only". Nobody else can open the site.
    app.launch(server_name="127.0.0.1", server_port=7860, css_paths=[CSS_FILE, CHATBOT_CSS_FILE])


if __name__ == "__main__":
    main()
