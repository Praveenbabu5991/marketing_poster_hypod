"""Response formatter tool for interactive UI responses.

Adapted from v2 — wrapped with LangChain @tool decorator.
When the orchestrator calls format_response, the graph routes to END.
"""

import json

from langchain_core.tools import tool


@tool
def format_response(
    message: str,
    choices: str = "",
    choice_type: str = "single_select",
    allow_free_input: bool = True,
    input_placeholder: str = "Or type your own...",
    media: str = "",
) -> dict:
    """Build an interactive response for the UI.

    This tool MUST be called for all user-facing responses that need
    interactive elements (choices, media display, etc.).
    Calling this tool terminates the agent turn — user must respond to continue.

    Args:
        message: The text message to display to the user.
        choices: JSON string of choices list. Each choice:
            [{"id": "1", "label": "Option A", "description": "Details..."}]
        choice_type: UI rendering type:
            "single_select" — radio buttons (pick one)
            "multi_select" — checkboxes (pick many)
            "confirmation" — Yes/No buttons
            "menu" — dropdown menu
        allow_free_input: Whether to show a free text input below choices.
        input_placeholder: Placeholder text for the free input field.
        media: JSON string of media to display:
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
        try:
            parsed = json.loads(choices) if isinstance(choices, str) else choices
            result["choices"] = parsed
            result["has_choices"] = bool(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    if media:
        try:
            parsed_media = json.loads(media) if isinstance(media, str) else media
            result["media"] = parsed_media
        except (json.JSONDecodeError, TypeError):
            pass

    return result
