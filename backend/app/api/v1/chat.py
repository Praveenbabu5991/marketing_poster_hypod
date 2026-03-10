"""SSE streaming chat endpoint + in-chat product upload."""

import uuid as _uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

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

# Shared in-memory checkpointer — single instance across all requests
# so conversation state persists between turns. Will switch to PostgresSaver for production.
_checkpointer = MemorySaver()

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

    # Get and compile agent graph with shared checkpointer
    graph = get_agent_graph(session.agent_type)
    compiled = graph.compile(checkpointer=_checkpointer)

    return StreamingResponse(
        stream_agent(
            compiled_graph=compiled,
            message=request.message,
            brand_context=brand_ctx.to_dict(),
            thread_id=session.thread_id,
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
