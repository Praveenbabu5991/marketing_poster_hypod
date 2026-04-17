"""SSE streaming chat endpoint + in-chat product upload + message history."""

import calendar as cal_mod
import json
import uuid as _uuid
from datetime import date
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
from app.services import session_service, brand_service, calendar_service
from app.services.streaming import stream_agent
from agents.registry import get_agent_graph
from brand.context import BrandContext

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

import re

_AGENT_LABELS = {
    "single_post": "Post",
    "carousel": "Carousel",
    "campaign": "Campaign",
    "sales_poster": "Sales Poster",
    "ugc": "UGC",
    "product_ugc": "Product UGC",
    "motion_graphics": "Motion Graphics",
    "advertisement": "Advertisement",
    "content_calendar": "Calendar Plan",
}


def _generate_title(message: str, agent_type: str, brand_name: str = "") -> str | None:
    """Extract a short, readable title from a user message.

    Returns None for generic/uninformative messages (e.g. "start", "1", "yes")
    so the caller can retry on the next message.
    """
    # Strip [System Context: ...] and [Calendar Context: ...] blocks
    clean = re.sub(r"\[(?:System|Calendar) Context:[^\]]*\]", "", message).strip()
    # Strip [Current Calendar Slots: ...] blocks
    clean = re.sub(r"\[Current Calendar Slots:[^\]]*\]", "", clean).strip()
    # Strip [Dialogue: "..."] blocks
    clean = re.sub(r'\[Dialogue:\s*"[^"]*"\]', "", clean).strip()
    clean = clean.strip()

    # Calendar-triggered content: "[Calendar: agent_type for Event on YYYY-MM-DD] idea text"
    m = re.match(r"\[Calendar:\s*\w+(?:\s+for\s+(.+?))?\s+on\s+[\d-]+\]\s*(.+)", clean, re.I | re.S)
    if m:
        event = (m.group(1) or "").strip()
        idea = (m.group(2) or "").strip()
        # Use event name as title, or idea if no event
        title = event if event else idea
        if len(title) > 60:
            title = title[:57] + "..."
        return title or None

    # Campaign date-range: "Generate campaign from 2026-02-07 to 2026-02-14, 4 posts: Valentine Week"
    m = re.match(r"Generate campaign from [\d-]+ to [\d-]+,?\s*\d*\s*posts?:\s*(.+)", clean, re.I)
    if m:
        return m.group(1).strip()[:80]

    # Per-slot campaign: "Plan a campaign for Women's Day on 2026-03-08: ..."
    m = re.match(r"Plan a campaign(?:\s+for\s+(.+?))?(?:\s+on\s+[\d-]+)?:\s*(.+)", clean, re.I)
    if m:
        theme = (m.group(2) or m.group(1) or "").strip()
        return theme[:80] if theme else None

    # Calendar slot content: "Create this specific post for X on YYYY-MM-DD: idea"
    m = re.match(r"Create (?:this specific post|a sales poster|a product video)(?:\s+for\s+(.+?))?(?:\s+on\s+[\d-]+)?:\s*(.+?)\.?\s*(?:Skip|Use|$)", clean, re.I | re.S)
    if m:
        event = m.group(1) or ""
        idea = m.group(2) or ""
        title = f"{event}: {idea}".strip(": ") if event else idea.strip()
        return title[:80] if title else None

    # Skip generic/uninformative messages → return None so we retry next turn
    lower = clean.lower()
    if lower in ("start", ""):
        return None
    # Skip pure number selections ("1", "2", etc.)
    if re.match(r"^\d+$", clean):
        return None
    # Skip very short confirmations
    if lower in ("yes", "no", "ok", "sure", "next", "done", "continue",
                 "generate", "next post", "start generating", "finish campaign",
                 "looks good", "use this image", "generate video"):
        return None
    # Skip "Plan N posts" → planner sessions get titled from calendar slot
    if re.match(r"Plan \d+ posts", clean, re.I):
        return None
    # Skip "Regenerate YYYY-MM-DD" planner commands
    if re.match(r"Regenerate \d{4}-\d{2}-\d{2}", clean, re.I):
        return None

    # Fallback: use first line, up to 60 chars
    fallback = clean.split("\n")[0].strip()
    if len(fallback) > 60:
        fallback = fallback[:57] + "..."
    return fallback or None


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

    # For content_calendar sessions, inject calendar context so the planner
    # knows the date range and all current slots (including manually added ones).
    message = request.message
    import sys
    print(f"[CHAT] session={session_id} agent={session.agent_type} msg={message[:500]}", file=sys.stderr, flush=True)
    if session.agent_type == "content_calendar":
        plan = await calendar_service.get_plan_by_planner_session(db, session_id)
        if plan:
            # Build date-range context
            today = date.today()
            is_current_month = today.year == plan.year and today.month == plan.month
            last_day = cal_mod.monthrange(plan.year, plan.month)[1]
            month_name = date(plan.year, plan.month, 1).strftime("%B")

            if is_current_month:
                start = today.day
                remaining = last_day - start
                start_iso = today.isoformat()
                date_ctx = (
                    f"Month: {month_name} {plan.year}. "
                    f"Plan for remaining {remaining} days ({month_name} {start} to {month_name} {last_day}). "
                    f"Start date: {start_iso}. Do NOT create slots before {start_iso}."
                )
            else:
                date_ctx = (
                    f"Month: {month_name} {plan.year}. "
                    f"Plan for full month ({last_day} days)."
                )

            # Build current slots context
            slots = await calendar_service.get_slots(db, plan.id)
            slots_data = [
                {
                    "date": str(s.slot_date),
                    "event_name": s.event_name or "",
                    "event_type": s.event_type or "regular",
                    "post_idea": s.post_idea or "",
                    "post_type": s.post_type or "single_post",
                    "posting_time": s.posting_time or "",
                }
                for s in slots
            ]

            context_block = f"[Calendar Context: {date_ctx}]"
            if slots_data:
                context_block += f"\n[Current Calendar Slots: {json.dumps(slots_data)}]"
            message = f"{context_block}\n\n{message}"
            import sys
            print(f"[CALENDAR] Injected context for plan {plan.id} ({plan.year}-{plan.month:02d}), {len(slots_data)} slots", file=sys.stderr, flush=True)

    # Auto-title: keep trying on each message until we get something meaningful
    if not session.title:
        title = _generate_title(request.message, session.agent_type, brand.name)
        if title:
            session.title = title
            await db.flush()

    # Get and compile agent graph with PostgreSQL checkpointer
    graph = get_agent_graph(session.agent_type)
    compiled = graph.compile(checkpointer=get_checkpointer())

    return StreamingResponse(
        stream_agent(
            compiled_graph=compiled,
            message=message,
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
