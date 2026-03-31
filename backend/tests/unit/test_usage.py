"""Tests for usage monitoring: model, config, callbacks, service."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import VERTEX_PRICING, calculate_cost
from app.models.usage import UsageLog


# ── calculate_cost tests ──────────────────────────────────────────────

class TestCalculateCost:
    def test_text_model_cost(self):
        cost = calculate_cost(
            model_name="google_genai/gemini-2.5-flash",
            action_type="text",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
        )
        # 1M input * 0.30 + 1M output * 2.50 = 2.80
        assert cost == pytest.approx(2.80, abs=0.001)

    def test_text_model_small_tokens(self):
        cost = calculate_cost(
            model_name="gemini-2.5-flash",
            action_type="text",
            prompt_tokens=100,
            completion_tokens=50,
        )
        # 100/1M * 0.30 + 50/1M * 2.50 = 0.00003 + 0.000125 = 0.000155
        assert cost == pytest.approx(0.000155, abs=0.0001)

    def test_image_model_cost(self):
        cost = calculate_cost(
            model_name="gemini-3-pro-image-preview",
            action_type="image",
            unit_count=1,
        )
        assert cost == pytest.approx(0.039, abs=0.001)

    def test_image_model_multiple_units(self):
        cost = calculate_cost(
            model_name="gemini-3-pro-image-preview",
            action_type="image",
            unit_count=3,
        )
        assert cost == pytest.approx(0.117, abs=0.001)

    def test_video_model_cost(self):
        cost = calculate_cost(
            model_name="veo-3.1-generate-001",
            action_type="video",
            video_duration_seconds=8,
        )
        # 8 * 0.40 = 3.20
        assert cost == pytest.approx(3.20, abs=0.01)

    def test_video_model_fast(self):
        cost = calculate_cost(
            model_name="veo-3.1-fast-generate-001",
            action_type="video",
            video_duration_seconds=8,
        )
        # 8 * 0.15 = 1.20
        assert cost == pytest.approx(1.20, abs=0.01)

    def test_unknown_model_zero_cost(self):
        cost = calculate_cost(
            model_name="some-unknown-model",
            action_type="text",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = calculate_cost(
            model_name="gemini-2.5-flash",
            action_type="text",
            prompt_tokens=0,
            completion_tokens=0,
        )
        assert cost == 0.0

    def test_none_tokens_handled(self):
        cost = calculate_cost(
            model_name="gemini-2.5-flash",
            action_type="text",
            prompt_tokens=None,
            completion_tokens=None,
        )
        assert cost == 0.0

    def test_provider_prefix_stripped(self):
        """Model names with provider prefix should still match pricing."""
        cost = calculate_cost(
            model_name="google_genai/gemini-2.5-flash",
            action_type="text",
            prompt_tokens=1000,
        )
        assert cost > 0

    def test_video_zero_duration(self):
        cost = calculate_cost(
            model_name="veo-3.1-generate-001",
            action_type="video",
            video_duration_seconds=0,
        )
        assert cost == 0.0


# ── UsageLog model tests ─────────────────────────────────────────────

class TestUsageLogModel:
    def test_create_usage_log(self):
        log = UsageLog(
            user_id=uuid.uuid4(),
            action_type="text",
            model_name="gemini-2.5-flash",
            tool_name="orchestrator_llm",
            status="success",
            cost_usd=0.001,
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert log.action_type == "text"
        assert log.model_name == "gemini-2.5-flash"
        assert log.status == "success"
        assert log.cost_usd == 0.001

    def test_error_log(self):
        log = UsageLog(
            user_id=uuid.uuid4(),
            action_type="image",
            model_name="gemini-3-pro-image-preview",
            tool_name="generate_image",
            status="error",
            cost_usd=0.0,
            error_message="Safety blocked",
        )
        assert log.status == "error"
        assert log.error_message == "Safety blocked"

    def test_video_log_with_duration(self):
        log = UsageLog(
            user_id=uuid.uuid4(),
            action_type="video",
            model_name="veo-3.1-generate-001",
            tool_name="generate_video",
            status="success",
            cost_usd=3.20,
            video_duration_seconds=8,
        )
        assert log.video_duration_seconds == 8
        assert log.cost_usd == 3.20

    def test_defaults(self):
        """Defaults are applied at flush/insert time by SQLAlchemy, not at construction.
        Verify the Column definitions have the right defaults configured."""
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(UsageLog)
        status_col = mapper.columns["status"]
        cost_col = mapper.columns["cost_usd"]
        unit_col = mapper.columns["unit_count"]
        assert status_col.default.arg == "success"
        assert cost_col.default.arg == 0.0
        assert unit_col.default.arg == 1


# ── VERTEX_PRICING config tests ──────────────────────────────────────

class TestVertexPricing:
    def test_has_flash_pricing(self):
        assert "gemini-2.5-flash" in VERTEX_PRICING
        p = VERTEX_PRICING["gemini-2.5-flash"]
        assert "input_per_million" in p
        assert "output_per_million" in p

    def test_has_image_pricing(self):
        assert "gemini-3-pro-image-preview" in VERTEX_PRICING
        assert "per_image" in VERTEX_PRICING["gemini-3-pro-image-preview"]

    def test_has_video_pricing(self):
        assert "veo-3.1-generate-001" in VERTEX_PRICING
        assert "per_second" in VERTEX_PRICING["veo-3.1-generate-001"]

    def test_has_fast_video_pricing(self):
        assert "veo-3.1-fast-generate-001" in VERTEX_PRICING


# ── Callbacks tests ───────────────────────────────────────────────────

class TestUsageMonitoringHandler:
    def test_tool_action_map(self):
        from agents.callbacks import TOOL_ACTION_MAP
        assert TOOL_ACTION_MAP["generate_image"] == "image"
        assert TOOL_ACTION_MAP["edit_image"] == "image"
        assert TOOL_ACTION_MAP["generate_video"] == "video"
        assert TOOL_ACTION_MAP["animate_image"] == "video"
        assert TOOL_ACTION_MAP["write_caption"] == "text"
        assert TOOL_ACTION_MAP["improve_caption"] == "text"
        assert TOOL_ACTION_MAP["generate_hashtags"] == "text"
        assert TOOL_ACTION_MAP["search_web"] == "search"
        assert TOOL_ACTION_MAP["get_trending_topics"] == "search"

    def test_non_api_tools_excluded(self):
        from agents.callbacks import TOOL_ACTION_MAP
        assert "format_response" not in TOOL_ACTION_MAP
        assert "get_upcoming_events" not in TOOL_ACTION_MAP

    def test_handler_init(self):
        from agents.callbacks import UsageMonitoringHandler
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        handler = UsageMonitoringHandler(user_id=user_id, session_id=session_id)
        assert handler.user_id == user_id
        assert handler.session_id == session_id

    @pytest.mark.asyncio
    async def test_on_tool_end_skips_non_api_tool(self):
        from agents.callbacks import UsageMonitoringHandler
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        await handler.on_tool_end(
            output='{"status": "success"}',
            run_id=uuid.uuid4(),
            name="format_response",
        )
        handler._schedule_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_tool_end_logs_image_tool(self):
        from agents.callbacks import UsageMonitoringHandler
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        output = json.dumps({
            "status": "success",
            "model": "gemini-3-pro-image-preview",
            "prompt_tokens": 100,
            "completion_tokens": 50,
        })
        await handler.on_tool_end(
            output=output,
            run_id=uuid.uuid4(),
            name="generate_image",
        )
        handler._schedule_log.assert_called_once()
        log = handler._schedule_log.call_args[0][0]
        assert log.action_type == "image"
        assert log.model_name == "gemini-3-pro-image-preview"
        assert log.tool_name == "generate_image"
        assert log.status == "success"
        assert log.cost_usd > 0

    @pytest.mark.asyncio
    async def test_on_tool_end_logs_error_tool(self):
        from agents.callbacks import UsageMonitoringHandler
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        output = json.dumps({
            "status": "error",
            "message": "Safety blocked",
            "model": "gemini-3-pro-image-preview",
        })
        await handler.on_tool_end(
            output=output,
            run_id=uuid.uuid4(),
            name="generate_image",
        )
        handler._schedule_log.assert_called_once()
        log = handler._schedule_log.call_args[0][0]
        assert log.status == "error"
        assert log.error_message == "Safety blocked"

    @pytest.mark.asyncio
    async def test_on_tool_end_logs_video_with_duration(self):
        from agents.callbacks import UsageMonitoringHandler
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        output = json.dumps({
            "status": "success",
            "model": "veo-3.1-generate-001",
            "duration_seconds": 8,
        })
        await handler.on_tool_end(
            output=output,
            run_id=uuid.uuid4(),
            name="generate_video",
        )
        handler._schedule_log.assert_called_once()
        log = handler._schedule_log.call_args[0][0]
        assert log.action_type == "video"
        assert log.video_duration_seconds == 8
        assert log.cost_usd == pytest.approx(3.20, abs=0.01)

    @pytest.mark.asyncio
    async def test_on_llm_end_logs_tokens(self):
        from agents.callbacks import UsageMonitoringHandler
        from langchain_core.outputs import LLMResult, Generation
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        result = LLMResult(
            generations=[[Generation(text="hello", generation_info={})]],
            llm_output={
                "model_name": "google_genai/gemini-2.5-flash",
                "token_usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 100,
                },
            },
        )
        await handler.on_llm_end(
            response=result,
            metadata={"langgraph_node": "orchestrator"},
        )
        handler._schedule_log.assert_called_once()
        log = handler._schedule_log.call_args[0][0]
        assert log.action_type == "text"
        assert log.prompt_tokens == 200
        assert log.completion_tokens == 100
        assert log.model_name == "google_genai/gemini-2.5-flash"
        assert log.cost_usd > 0

    @pytest.mark.asyncio
    async def test_on_chat_model_end_logs(self):
        """ChatGoogleGenerativeAI puts usage on AIMessage.usage_metadata."""
        from agents.callbacks import UsageMonitoringHandler
        from langchain_core.outputs import LLMResult, ChatGeneration
        from langchain_core.messages import AIMessage
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        msg = AIMessage(content="hello")
        msg.usage_metadata = {"input_tokens": 50, "output_tokens": 30, "total_tokens": 80}
        result = LLMResult(
            generations=[[ChatGeneration(
                message=msg,
                generation_info={"finish_reason": "STOP", "model_name": "gemini-2.5-flash"},
            )]],
            llm_output={},
        )
        await handler.on_chat_model_end(
            response=result,
        )
        handler._schedule_log.assert_called_once()
        log = handler._schedule_log.call_args[0][0]
        assert log.prompt_tokens == 50
        assert log.completion_tokens == 30
        assert log.model_name == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_on_tool_end_handles_malformed_json(self):
        from agents.callbacks import UsageMonitoringHandler
        handler = UsageMonitoringHandler(user_id=uuid.uuid4())
        handler._schedule_log = MagicMock()

        await handler.on_tool_end(
            output="not valid json",
            run_id=uuid.uuid4(),
            name="generate_image",
        )
        # Should still log, just with defaults
        handler._schedule_log.assert_called_once()
        log = handler._schedule_log.call_args[0][0]
        assert log.model_name == "unknown"
