"""SSE streaming chat endpoint + in-chat product upload + message history."""

import json
import uuid as _uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.checkpoint import get_checkpointer
from app.config import UPLOAD_DIR
from app.database import get_db
from app.schemas.chat import ChatRequest
from app.security.dependencies import require_authenticated_user
from app.security.models import UserDetails
from app.services import session_service, brand_service
from app.services.streaming import stream_agent
from agents.registry import get_agent_graph
from brand.context import BrandContext

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: UUID,
    request: ChatRequest,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive SSE stream of agent events."""
    # Validate session belongs to user
    session = await session_service.get_session(db, session_id, user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load brand context
    brand = await brand_service.get_brand(db, session.brand_id, user.user_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    brand_ctx = BrandContext.from_db_model(brand)

    # Get and compile agent graph with PostgreSQL checkpointer
    graph = get_agent_graph(session.agent_type)
    compiled = graph.compile(checkpointer=get_checkpointer())

    return StreamingResponse(
        stream_agent(
            compiled_graph=compiled,
            message=request.message,
            brand_context=brand_ctx.to_dict(),
            thread_id=session.thread_id,
            user_id=user.user_id,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/upload-product")
async def upload_product_in_chat(
    session_id: UUID,
    file: UploadFile,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a product image mid-conversation and add it to the session's brand.

    This endpoint saves the image and automatically appends the path
    to the brand's product_images list so the agent sees it on the next turn.
    """
    # Validate session
    session = await session_service.get_session(db, session_id, user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate file
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save file
    ext = Path(file.filename or "product.png").suffix or ".png"
    filename = f"product_{user.user_id}_{_uuid.uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / "products" / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    # Replace brand's product_images with the new upload.
    # In sales poster / product video context, the user works on ONE product
    # at a time. Uploading a new image means "use this one instead".
    brand = await brand_service.get_brand(db, session.brand_id, user.user_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    brand.product_images = [str(file_path)]
    # Commit immediately so the next chat request sees the new image.
    # Without this, the get_db dependency commits AFTER the response is sent,
    # causing a race condition where the chat request reads stale data.
    await db.commit()
    await db.refresh(brand)

    return {
        "image_path": str(file_path),
        "url": f"/uploads/products/{filename}",
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: UUID,
    user: UserDetails = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Load conversation history from the LangGraph checkpointer."""
    session = await session_service.get_session(db, session_id, user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    graph = get_agent_graph(session.agent_type)
    compiled = graph.compile(checkpointer=get_checkpointer())

    state = await compiled.aget_state(
        {"configurable": {"thread_id": session.thread_id}}
    )

    if not state or not state.values:
        return []

    lc_messages = state.values.get("messages", [])
    return _convert_messages(lc_messages)


_TOOL_LABELS: dict[str, str] = {
    "get_upcoming_events": "Fetched upcoming events",
    "search_web": "Searched the web",
    "get_trending_topics": "Fetched trending topics",
    "generate_image": "Generated image",
    "generate_video": "Generated video",
    "format_response": "Formatted response",
}


def _tool_display_label(tool_name: str) -> str:
    """Short display label for a tool result (avoids dumping raw JSON)."""
    return _TOOL_LABELS.get(tool_name, tool_name or "Tool completed")


def _convert_messages(lc_messages: list) -> list[dict[str, Any]]:
    """Convert LangChain message objects to frontend ChatMessage[] format."""
    result: list[dict[str, Any]] = []
    msg_counter = 0

    # Build set of format_response tool_call IDs so we can skip their ToolMessages
    format_response_call_ids: set[str] = set()
    for msg in lc_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "format_response":
                    format_response_call_ids.add(tc.get("id", ""))

    for msg in lc_messages:
        msg_counter += 1
        msg_id = f"msg-{msg_counter}"

        if isinstance(msg, HumanMessage):
            result.append({
                "id": msg_id,
                "role": "user",
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
            })

        elif isinstance(msg, AIMessage):
            # Check for format_response tool call → interactive message
            format_tc = None
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "format_response":
                        format_tc = tc
                        break

            if format_tc:
                # Parse the interactive response from tool call args
                args = format_tc.get("args", {})
                interactive = args
                if isinstance(args, str):
                    try:
                        interactive = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        interactive = {"message": args}

                message_text = interactive.get("message", "") if isinstance(interactive, dict) else str(interactive)
                result.append({
                    "id": msg_id,
                    "role": "assistant",
                    "content": message_text,
                    "interactive": interactive,
                })
            elif msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if content.strip():
                    result.append({
                        "id": msg_id,
                        "role": "assistant",
                        "content": content,
                    })

        elif isinstance(msg, ToolMessage):
            # Skip ToolMessages that are responses to format_response calls
            tool_call_id = getattr(msg, "tool_call_id", "")
            if tool_call_id in format_response_call_ids:
                continue

            tool_name = getattr(msg, "name", None) or ""
            result.append({
                "id": msg_id,
                "role": "tool",
                "content": _tool_display_label(tool_name),
                "toolName": tool_name,
                "toolActive": False,
            })

    return result
