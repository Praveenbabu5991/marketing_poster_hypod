"""Tests for format_response tool."""

import json
import pytest

from agents.tools.format_response import format_response


class TestFormatResponse:

    def test_basic_message(self):
        result = format_response.invoke({"message": "Hello"})
        assert result["type"] == "interactive_response"
        assert result["message"] == "Hello"
        assert result["has_choices"] is False

    def test_with_choices(self):
        choices = json.dumps([
            {"id": "1", "label": "Option A", "description": "First option"},
            {"id": "2", "label": "Option B", "description": "Second option"},
        ])
        result = format_response.invoke({"message": "Pick one", "choices": choices})
        assert result["has_choices"] is True
        assert len(result["choices"]) == 2
        assert result["choice_type"] == "single_select"

    def test_with_media(self):
        media = json.dumps({"image_path": "/generated/test.png"})
        result = format_response.invoke({"message": "Here's your image", "media": media})
        assert "media" in result
        assert result["media"]["image_path"] == "/generated/test.png"

    def test_invalid_choices_json(self):
        result = format_response.invoke({"message": "Test", "choices": "not-json"})
        assert result["has_choices"] is False
        assert result["choices"] == []

    def test_confirmation_type(self):
        result = format_response.invoke({
            "message": "Confirm?",
            "choice_type": "confirmation",
        })
        assert result["choice_type"] == "confirmation"

    def test_free_input_disabled(self):
        result = format_response.invoke({
            "message": "Pick one only",
            "allow_free_input": False,
        })
        assert result["allow_free_input"] is False

    def test_video_media(self):
        media = json.dumps({"video_path": "/generated/test.mp4"})
        result = format_response.invoke({"message": "Video", "media": media})
        assert result["media"]["video_path"] == "/generated/test.mp4"

    def test_custom_placeholder(self):
        result = format_response.invoke({
            "message": "Type something",
            "input_placeholder": "Enter your idea...",
        })
        assert result["input_placeholder"] == "Enter your idea..."
