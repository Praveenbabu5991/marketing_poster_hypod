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
    campaign_post_date: Optional[str] = None,
    campaign_post_caption: Optional[str] = None,
    campaign_post_hashtags: Optional[str] = None,
    campaign_post_type: Optional[str] = None,
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
        campaign_post_date: (Calendar-mode campaigns only) ISO date for this post,
            e.g. "2026-04-03". Automatically merged into media.
        campaign_post_caption: (Calendar-mode campaigns only) Full caption text.
            Automatically merged into media.
        campaign_post_hashtags: (Calendar-mode campaigns only) Hashtags string.
            Automatically merged into media.
        campaign_post_type: (Calendar-mode campaigns only) Content type for this post,
            e.g. "single_post", "carousel", "motion_graphics". Merged into media.
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

    # Auto-inject campaign fields into media when provided
    if campaign_post_date:
        if "media" not in result:
            result["media"] = {}
        result["media"]["campaign_post_date"] = campaign_post_date
        if campaign_post_caption:
            result["media"]["campaign_post_caption"] = campaign_post_caption
        if campaign_post_hashtags:
            result["media"]["campaign_post_hashtags"] = campaign_post_hashtags
        if campaign_post_type:
            result["media"]["campaign_post_type"] = campaign_post_type

    return result
