"""Response formatter tool for interactive UI responses.

Adapted from v2 — wrapped with LangChain @tool decorator.
When the orchestrator calls format_response, the graph routes to END.
"""

import json
from typing import Optional

from langchain_core.tools import tool


@tool
def format_response(
    message: str,
    choices: Optional[list[dict]] = None,
    choice_type: str = "single_select",
    allow_free_input: bool = True,
    input_placeholder: str = "Or type your own...",
    media: Optional[dict] = None,
) -> dict:
    """Build an interactive response for the UI.

    This tool MUST be called for all user-facing responses that need
    interactive elements (choices, media display, etc.).
    Calling this tool terminates the agent turn — user must respond to continue.

    Args:
        message: The text message to display to the user.
        choices: List of choice objects. Each choice:
            [{"id": "1", "label": "Option A", "description": "Details..."}]
        choice_type: UI rendering type:
            "single_select" — radio buttons (pick one)
            "multi_select" — checkboxes (pick many)
            "confirmation" — Yes/No buttons
            "menu" — dropdown menu
        allow_free_input: Whether to show a free text input below choices.
        input_placeholder: Placeholder text for the free input field.
        media: Media object to display:
            {"image_path": "/path/to/image.png"} or
            {"video_path": "/path/to/video.mp4"}
    """
    result = {
        "type": "interactive_response",
        "message": message,
        "choices": [],
        "has_choices": False,
        "choice_type": choice_type,
        "allow_free_input": allow_free_input,
        "input_placeholder": input_placeholder,
    }

    if choices:
        # Handle both list and JSON string (backwards compat)
        if isinstance(choices, str):
            try:
                choices = json.loads(choices)
            except (json.JSONDecodeError, TypeError):
                choices = []
        result["choices"] = choices
        result["has_choices"] = bool(choices)

    if media:
        # Handle both dict and JSON string (backwards compat)
        if isinstance(media, str):
            try:
                media = json.loads(media)
            except (json.JSONDecodeError, TypeError):
                media = None
        if media:
            result["media"] = media

    return result
