import asyncio
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from app.models.usage import UsageLog, AIModelName
from app.database import async_session_factory

class UsageMonitoringHandler(AsyncCallbackHandler):
    """Async callback handler to log AI model usage to the database."""
    
    def __init__(self, user_id: UUID, session_id: Optional[UUID] = None):
        self.user_id = user_id
        self.session_id = session_id
        # Capture the main event loop when the handler is instantiated (in the main FastAPI thread)
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
            # We don't want billing errors to crash the agent execution
            print(f"[Monitoring Error] Failed to log usage: {e}")

    def _schedule_log(self, log_entry: UsageLog):
        """Schedule the logging task safely on the main event loop."""
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if self.main_loop and current_loop != self.main_loop:
            # We are inside a background thread (created by LangChain for sync tools).
            # We MUST send this back to the main loop to avoid asyncpg connection errors!
            asyncio.run_coroutine_threadsafe(self._log_usage(log_entry), self.main_loop)
        else:
            # We are already in the main loop (or there is no main loop fallback)
            asyncio.create_task(self._log_usage(log_entry))

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Log text model usage when a generation ends."""
        for generations in response.generations:
            for generation in generations:
                # Extract metadata if available (e.g., token counts from Gemini/OpenAI)
                meta = generation.generation_info or {}
                usage = meta.get("usage", meta.get("token_usage", {}))
                
                # Get model name from response or config
                model_str = response.llm_output.get("model_name", "google_genai/gemini-2.5-flash") if response.llm_output else "google_genai/gemini-2.5-flash"
                
                try:
                    # Map string to Enum
                    model_enum = AIModelName(model_str)
                except ValueError:
                    model_enum = AIModelName.GEMINI_FLASH

                log = UsageLog(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    action_type="text",
                    model_name=model_enum,
                    prompt_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
                    completion_tokens=usage.get("completion_tokens") or usage.get("output_tokens"),
                    unit_count=1,
                    metadata_json={"finish_reason": meta.get("finish_reason")}
                )
                self._schedule_log(log)

    async def on_tool_end(self, output: str, *, run_id: Any, parent_run_id: Any = None, **kwargs: Any) -> None:
        """Log tool usage (Image/Video generation)."""
        # Note: LangChain 'name' is in kwargs for newer versions
        tool_name = kwargs.get("name")
        
        if tool_name in ["generate_image", "edit_image"]:
            log = UsageLog(
                user_id=self.user_id,
                session_id=self.session_id,
                action_type="image",
                model_name=AIModelName.IMAGEN_3,
                unit_count=1,
                metadata_json={"tool": tool_name}
            )
            self._schedule_log(log)
        elif tool_name == "generate_video":
            log = UsageLog(
                user_id=self.user_id,
                session_id=self.session_id,
                action_type="video",
                model_name=AIModelName.VEO_3,
                unit_count=1,
                metadata_json={"tool": tool_name}
            )
            self._schedule_log(log)
