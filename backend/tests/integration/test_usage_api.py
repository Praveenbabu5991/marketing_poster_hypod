"""Integration tests for usage API endpoints."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.models.usage import UsageLog
from tests.conftest import TEST_USER_ID


# Helper to seed usage logs
async def _seed_usage_logs(db_session):
    """Seed some usage log rows for testing."""
    logs = [
        UsageLog(
            user_id=TEST_USER_ID,
            action_type="text",
            model_name="google_genai/gemini-2.5-flash",
            tool_name="orchestrator_llm",
            status="success",
            cost_usd=0.001,
            prompt_tokens=200,
            completion_tokens=100,
        ),
        UsageLog(
            user_id=TEST_USER_ID,
            action_type="image",
            model_name="gemini-3-pro-image-preview",
            tool_name="generate_image",
            status="success",
            cost_usd=0.039,
            unit_count=1,
        ),
        UsageLog(
            user_id=TEST_USER_ID,
            action_type="image",
            model_name="gemini-3-pro-image-preview",
            tool_name="generate_image",
            status="error",
            cost_usd=0.0,
            error_message="Safety blocked",
        ),
        UsageLog(
            user_id=TEST_USER_ID,
            action_type="video",
            model_name="veo-3.1-generate-001",
            tool_name="generate_video",
            status="success",
            cost_usd=3.20,
            video_duration_seconds=8,
        ),
        UsageLog(
            user_id=TEST_USER_ID,
            action_type="text",
            model_name="google_genai/gemini-2.5-flash",
            tool_name="orchestrator_llm",
            status="success",
            cost_usd=0.002,
            prompt_tokens=300,
            completion_tokens=150,
        ),
        # Another user's log — should NOT be returned
        UsageLog(
            user_id=uuid.uuid4(),
            action_type="text",
            model_name="google_genai/gemini-2.5-flash",
            tool_name="orchestrator_llm",
            status="success",
            cost_usd=0.005,
            prompt_tokens=500,
            completion_tokens=250,
        ),
    ]
    for log in logs:
        db_session.add(log)
    await db_session.commit()
    return logs


class TestUsageSummaryAPI:
    @pytest.mark.asyncio
    async def test_summary_unauthenticated(self, client):
        resp = await client.get("/api/v1/usage/summary")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_summary_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/usage/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_summary_with_data(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get("/api/v1/usage/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Should have 3 groups: text/flash, image/gemini-3, video/veo
        assert len(data["items"]) == 3
        assert data["total_cost_usd"] > 0

        # Find the text group
        text_items = [i for i in data["items"] if i["action_type"] == "text"]
        assert len(text_items) == 1
        assert text_items[0]["total_calls"] == 2
        assert text_items[0]["successful_calls"] == 2
        assert text_items[0]["failed_calls"] == 0
        assert text_items[0]["total_prompt_tokens"] == 500  # 200 + 300

        # Find the image group
        image_items = [i for i in data["items"] if i["action_type"] == "image"]
        assert len(image_items) == 1
        assert image_items[0]["total_calls"] == 2
        assert image_items[0]["successful_calls"] == 1
        assert image_items[0]["failed_calls"] == 1

        # Find the video group
        video_items = [i for i in data["items"] if i["action_type"] == "video"]
        assert len(video_items) == 1
        assert video_items[0]["total_video_seconds"] == 8


class TestUsageHistoryAPI:
    @pytest.mark.asyncio
    async def test_history_unauthenticated(self, client):
        resp = await client.get("/api/v1/usage/history")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_history_empty(self, client, auth_headers):
        resp = await client.get("/api/v1/usage/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_history_with_data(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get("/api/v1/usage/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        # Should only see this user's 5 logs, not the other user's
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_history_pagination(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get(
            "/api/v1/usage/history?limit=2&offset=0", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_history_filter_action_type(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get(
            "/api/v1/usage/history?action_type=video", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["action_type"] == "video"

    @pytest.mark.asyncio
    async def test_history_filter_model_name(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get(
            "/api/v1/usage/history?model_name=veo-3.1-generate-001",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_history_item_fields(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get(
            "/api/v1/usage/history?action_type=video", headers=auth_headers
        )
        data = resp.json()
        item = data["items"][0]

        assert "id" in item
        assert item["action_type"] == "video"
        assert item["model_name"] == "veo-3.1-generate-001"
        assert item["tool_name"] == "generate_video"
        assert item["status"] == "success"
        assert item["cost_usd"] == pytest.approx(3.20, abs=0.01)
        assert item["video_duration_seconds"] == 8
        assert item["created_at"] is not None

    @pytest.mark.asyncio
    async def test_history_error_log_has_message(self, client, auth_headers, db_session):
        await _seed_usage_logs(db_session)

        resp = await client.get(
            "/api/v1/usage/history?action_type=image", headers=auth_headers
        )
        data = resp.json()
        error_items = [i for i in data["items"] if i["status"] == "error"]
        assert len(error_items) == 1
        assert error_items[0]["error_message"] == "Safety blocked"
