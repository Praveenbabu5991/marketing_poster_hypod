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
        choices = [
            {"id": "1", "label": "Option A", "description": "First option"},
            {"id": "2", "label": "Option B", "description": "Second option"},
        ]
        result = format_response.invoke({"message": "Pick one", "choices": choices})
        assert result["has_choices"] is True
        assert len(result["choices"]) == 2
        assert result["choice_type"] == "single_select"

    def test_with_media(self):
        media = {"image_path": "/generated/test.png"}
        result = format_response.invoke({"message": "Here's your image", "media": media})
        assert "media" in result
        assert result["media"]["image_path"] == "/generated/test.png"

    def test_empty_choices(self):
        result = format_response.invoke({"message": "Test", "choices": []})
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
        media = {"video_path": "/generated/test.mp4"}
        result = format_response.invoke({"message": "Video", "media": media})
        assert result["media"]["video_path"] == "/generated/test.mp4"

    def test_custom_placeholder(self):
        result = format_response.invoke({
            "message": "Type something",
            "input_placeholder": "Enter your idea...",
        })
        assert result["input_placeholder"] == "Enter your idea..."

    def test_campaign_post_type_merged_into_media(self):
        result = format_response.invoke({
            "message": "Post 1",
            "media": {"image_path": "/generated/img.png"},
            "campaign_post_date": "2026-04-03",
            "campaign_post_caption": "Caption here",
            "campaign_post_hashtags": "#test",
            "campaign_post_type": "single_post",
        })
        assert result["media"]["campaign_post_date"] == "2026-04-03"
        assert result["media"]["campaign_post_caption"] == "Caption here"
        assert result["media"]["campaign_post_hashtags"] == "#test"
        assert result["media"]["campaign_post_type"] == "single_post"

    def test_campaign_post_type_motion_graphics(self):
        result = format_response.invoke({
            "message": "Video post",
            "media": {"video_path": "/generated/video.mp4"},
            "campaign_post_date": "2026-04-04",
            "campaign_post_type": "motion_graphics",
        })
        assert result["media"]["video_path"] == "/generated/video.mp4"
        assert result["media"]["campaign_post_type"] == "motion_graphics"

    def test_campaign_post_type_without_date_not_merged(self):
        """campaign_post_type requires campaign_post_date to trigger merge."""
        result = format_response.invoke({
            "message": "No date",
            "campaign_post_type": "single_post",
        })
        assert "media" not in result
