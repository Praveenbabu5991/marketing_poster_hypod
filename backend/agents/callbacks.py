"""Usage monitoring callback handler for LangGraph agents.

Logs every Google API call (LLM + tools) to the usage_logs table with
per-model cost tracking.
"""

import asyncio
import json
import logging
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import ChatResult, LLMResult

from app.config import calculate_cost
from app.database import async_session_factory
from app.models.usage import UsageLog

logger = logging.getLogger(__name__)

# Map tool names -> action_type for usage logging.
# Tools not in this map are non-API tools and are skipped.
TOOL_ACTION_MAP = {
    "generate_image": "image",
    "edit_image": "image",
    "generate_video": "video",
    "animate_image": "video",
    "write_caption": "text",
    "improve_caption": "text",
    "generate_hashtags": "text",
    "search_web": "search",
    "get_trending_topics": "search",
}


class UsageMonitoringHandler(AsyncCallbackHandler):
    """Async callback handler to log AI model usage to the database."""

    def __init__(self, user_id: UUID, session_id: Optional[UUID] = None):
        self.user_id = user_id
        self.session_id = session_id
        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.main_loop = None

    async def _log_usage(self, log_entry: UsageLog):
        """Helper to log usage using a fresh DB session."""
        try:
            async with async_session_factory() as db_session:
                db_session.add(log_entry)
                await db_session.commit()
        except Exception as e:
            logger.warning("[Usage] Failed to log: %s", e)

    def _schedule_log(self, log_entry: UsageLog):
        """Schedule the logging task safely on the main event loop."""
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if self.main_loop and current_loop != self.main_loop:
            asyncio.run_coroutine_threadsafe(self._log_usage(log_entry), self.main_loop)
        else:
            asyncio.create_task(self._log_usage(log_entry))

    async def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        """No-op — required so LangChain doesn't skip on_chat_model_end."""
        pass

    def _log_llm_result(self, response: LLMResult, **kwargs: Any) -> None:
        """Shared logic for on_llm_end and on_chat_model_end."""
        try:
            llm_output = response.llm_output or {}

            # Extract model name from generation_info (most reliable for Gemini)
            model_name = llm_output.get("model_name", "")
            if not model_name:
                for gens in response.generations:
                    for gen in gens:
                        gi = gen.generation_info or {}
                        model_name = gi.get("model_name", "")
                        if model_name:
                            break
                    if model_name:
                        break
            if not model_name:
                model_name = "unknown"

            # Extract token counts — ChatGoogleGenerativeAI puts usage on AIMessage
            prompt_tokens = 0
            completion_tokens = 0

            # Try 1: llm_output.token_usage (OpenAI-style)
            token_usage = llm_output.get("token_usage", {})
            if token_usage:
                prompt_tokens = token_usage.get("prompt_tokens", 0) or 0
                completion_tokens = token_usage.get("completion_tokens", 0) or 0

            # Try 2: ChatGeneration.message.usage_metadata (Gemini via LangChain)
            if prompt_tokens == 0 and completion_tokens == 0:
                for gens in response.generations:
                    for gen in gens:
                        msg = getattr(gen, "message", None)
                        if msg:
                            usage = getattr(msg, "usage_metadata", None)
                            if usage and isinstance(usage, dict):
                                prompt_tokens = usage.get("input_tokens", 0) or 0
                                completion_tokens = usage.get("output_tokens", 0) or 0
                            elif usage:
                                # usage_metadata could be an object with attributes
                                prompt_tokens = getattr(usage, "input_tokens", 0) or 0
                                completion_tokens = getattr(usage, "output_tokens", 0) or 0
                        if prompt_tokens > 0:
                            break
                    if prompt_tokens > 0:
                        break

            # Get node name from kwargs tags (LangGraph passes tags not metadata in callbacks)
            node_name = "llm"
            tags = kwargs.get("tags", [])
            for tag in tags:
                if tag.startswith("graph:step:"):
                    # LangGraph tag format: "graph:step:<N>"
                    continue
                if ":" not in tag and tag not in ("seq:step:1", "seq:step:2"):
                    node_name = tag
                    break
            # Also try response_metadata on message for node context
            if node_name == "llm":
                resp_meta = getattr(
                    getattr(response.generations[0][0], "message", None)
                    if response.generations and response.generations[0] else None,
                    "response_metadata", {}
                ) or {}
                model_provider = resp_meta.get("model_provider", "")
                if model_provider:
                    node_name = "orchestrator"  # Default to orchestrator for chat models

            cost = calculate_cost(
                model_name=model_name,
                action_type="text",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            log = UsageLog(
                user_id=self.user_id,
                session_id=self.session_id,
                action_type="text",
                model_name=model_name,
                tool_name=f"{node_name}_llm",
                status="success",
                cost_usd=cost,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                unit_count=1,
                metadata_json={"node": node_name},
            )
            self._schedule_log(log)
        except Exception as e:
            logger.warning("[Usage] llm_end error: %s", e)

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Log text model usage when a generation ends."""
        self._log_llm_result(response, **kwargs)

    async def on_chat_model_end(self, response: ChatResult, **kwargs: Any) -> None:
        """Log chat model usage (ChatGoogleGenerativeAI uses this instead of on_llm_end)."""
        # ChatResult has the same structure we need: llm_output + generations
        self._log_llm_result(response, **kwargs)

    async def on_tool_end(
        self, output: str, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        """Log tool usage (image/video/caption/hashtag/search)."""
        tool_name = kwargs.get("name", "")

        # Skip non-API tools
        action_type = TOOL_ACTION_MAP.get(tool_name)
        if not action_type:
            return

        try:
            # Parse tool output (it's a JSON string from @tool return dicts)
            if isinstance(output, str):
                try:
                    data = json.loads(output)
                except (json.JSONDecodeError, TypeError):
                    data = {}
            elif hasattr(output, "content"):
                try:
                    data = json.loads(output.content)
                except (json.JSONDecodeError, TypeError):
                    data = {}
            else:
                data = {}

            status = data.get("status", "success")
            if status not in ("success", "error"):
                status = "error" if "error" in str(status).lower() else "success"

            model_name = data.get("model", "unknown")
            prompt_tokens = data.get("prompt_tokens", 0) or 0
            completion_tokens = data.get("completion_tokens", 0) or 0
            duration = data.get("duration_seconds", 0) or 0
            error_msg = data.get("message") if status == "error" else None

            cost = calculate_cost(
                model_name=model_name,
                action_type=action_type,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                unit_count=1,
                video_duration_seconds=duration,
            )

            log = UsageLog(
                user_id=self.user_id,
                session_id=self.session_id,
                action_type=action_type,
                model_name=model_name,
                tool_name=tool_name,
                status=status,
                cost_usd=cost,
                prompt_tokens=prompt_tokens if prompt_tokens else None,
                completion_tokens=completion_tokens if completion_tokens else None,
                unit_count=1,
                video_duration_seconds=duration if duration else None,
                error_message=error_msg[:500] if error_msg else None,
                metadata_json={"tool": tool_name},
            )
            self._schedule_log(log)
        except Exception as e:
            logger.warning("[Usage] on_tool_end error: %s", e)
