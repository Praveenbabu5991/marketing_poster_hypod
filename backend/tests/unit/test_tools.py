"""Tests for tools with mocked external APIs."""

from datetime import datetime

import pytest

from agents.tools.calendar import get_upcoming_events


class TestCalendarTool:
    """Calendar tool doesn't need external APIs — uses static event database."""

    def test_get_upcoming_events_returns_events(self):
        result = get_upcoming_events.invoke({
            "days_ahead": 365,
            "region": "global",
        })
        assert result["status"] == "success"
        assert result["count"] > 0
        assert isinstance(result["events"], list)

    def test_get_upcoming_events_region_filter(self):
        result = get_upcoming_events.invoke({
            "days_ahead": 365,
            "region": "India",
        })
        assert result["status"] == "success"
        # Should include global + India events, exclude US-only
        regions = {e.get("region") for e in result["events"]}
        assert "US" not in regions or all(
            e["region"] in ["global", "India"] for e in result["events"]
        )

    def test_get_upcoming_events_content_themes(self):
        result = get_upcoming_events.invoke({"days_ahead": 365})
        assert "content_themes" in result
        assert isinstance(result["content_themes"], list)
