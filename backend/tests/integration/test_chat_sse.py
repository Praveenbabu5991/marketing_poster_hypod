"""Integration tests for SSE chat streaming format."""

import json

import pytest

from app.services.streaming import _sse_event


class TestSSEFormat:

    def test_sse_event_format(self):
        event = _sse_event({"type": "text", "content": "hello", "partial": True})
        assert event.startswith("data: ")
        assert event.endswith("\n\n")
        parsed = json.loads(event.removeprefix("data: ").strip())
        assert parsed["type"] == "text"
        assert parsed["content"] == "hello"

    def test_sse_done_event(self):
        event = _sse_event({"type": "done"})
        parsed = json.loads(event.removeprefix("data: ").strip())
        assert parsed["type"] == "done"

    def test_sse_tool_start_event(self):
        event = _sse_event({
            "type": "tool_start",
            "tool": "generate_image",
            "message": "Creating your image...",
        })
        parsed = json.loads(event.removeprefix("data: ").strip())
        assert parsed["type"] == "tool_start"
        assert parsed["tool"] == "generate_image"

    def test_sse_interactive_event(self):
        content = {
            "type": "interactive_response",
            "message": "Pick one",
            "choices": [{"id": "1", "label": "A"}],
            "has_choices": True,
        }
        event = _sse_event({"type": "interactive", "content": content})
        parsed = json.loads(event.removeprefix("data: ").strip())
        assert parsed["type"] == "interactive"
        assert parsed["content"]["has_choices"] is True

    def test_sse_error_event(self):
        event = _sse_event({"type": "error", "content": "Something went wrong"})
        parsed = json.loads(event.removeprefix("data: ").strip())
        assert parsed["type"] == "error"
